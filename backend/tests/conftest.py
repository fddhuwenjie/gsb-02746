"""
pytest fixtures — isolate DB, filesystem, HTTP and time for every test.

Design rules:
- Each test function gets its own temporary directory (`tmp_path` from pytest).
- The global `settings` object is patched to point *all* paths under tmp_path so
  tests never touch the real `data/` or `config/` directories.
- A fresh SQLAlchemy engine + session is built per test; tables are created and
  dropped through the standard `Base.metadata`.
- The FastAPI `get_db` dependency is overridden to yield the per-test session.
- The module-level `crawl_status` dict is reset to idle before every test.
- A lightweight `FakeHTTP` helper replaces `httpx.AsyncClient` for scraper tests
  without pulling in extra dependencies (no respx / no pytest-httpx required).
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Ensure backend root is importable when tests are run directly.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core import database as _db_mod  # noqa: E402
from app.core import config as _cfg_mod  # noqa: E402
from app.core.config import settings as _settings  # noqa: E402
from app.main import app as _app  # noqa: E402
from app.api import crawler as _crawler_mod  # noqa: E402
from app.models.article import Article  # noqa: E402  (ensure model is registered)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def isolated_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Dict[str, Path]:
    """Redirect every persistent path setting to a temp directory."""
    db_file = tmp_path / "data" / "test.db"
    articles_dir = tmp_path / "data" / "articles"
    runtime_cfg = tmp_path / "data" / "runtime_config.json"
    sources_cfg = tmp_path / "config" / "sources.json"

    for p in (db_file.parent, articles_dir, runtime_cfg.parent, sources_cfg.parent):
        p.mkdir(parents=True, exist_ok=True)

    # Seed an empty sources config so crawler doesn't FileNotFound.
    sources_cfg.write_text(json.dumps({"sources": []}, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(_settings, "database_url", f"sqlite:///{db_file}")
    monkeypatch.setattr(_settings, "articles_path", str(articles_dir))
    monkeypatch.setattr(_settings, "runtime_config", str(runtime_cfg))
    monkeypatch.setattr(_settings, "sources_config", str(sources_cfg))

    return {
        "db_file": db_file,
        "articles_dir": articles_dir,
        "runtime_config": runtime_cfg,
        "sources_config": sources_cfg,
        "root": tmp_path,
    }


@pytest.fixture()
def db_session(isolated_paths: Dict[str, Path]):
    """
    Create an isolated SQLAlchemy engine + session with fresh tables.
    Yields the session; drops tables on cleanup.
    """
    engine = create_engine(
        _settings.database_url, connect_args={"check_same_thread": False}
    )
    _db_mod.Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    # Also patch the module-level engine/SessionLocal so code that imports
    # them directly sees the isolated DB.
    orig_engine = _db_mod.engine
    orig_session_local = _db_mod.SessionLocal
    _db_mod.engine = engine
    _db_mod.SessionLocal = TestingSession

    try:
        yield session
    finally:
        session.close()
        _db_mod.Base.metadata.drop_all(bind=engine)
        engine.dispose()
        _db_mod.engine = orig_engine
        _db_mod.SessionLocal = orig_session_local


@pytest.fixture()
def client(db_session, isolated_paths: Dict[str, Path]):
    """
    FastAPI TestClient with overridden get_db dependency and reset global state.
    """
    # Reset crawler global status
    _crawler_mod.crawl_status = {"status": "idle", "message": "", "articles_count": 0}

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    _app.dependency_overrides[_db_mod.get_db] = _override_get_db
    with TestClient(_app) as c:
        yield c
    _app.dependency_overrides.clear()


@pytest.fixture()
def seed_articles(db_session):
    """Insert a fixed, deterministically dated set of articles and return them."""
    items = [
        Article(title="2024年第一篇", author="作者甲", content="一月内容A",
                source="读者", year=2024, month=1, category="散文"),
        Article(title="2024年第二篇", author="作者乙", content="一月内容B",
                source="读者", year=2024, month=1, category="人生感悟"),
        Article(title="2024二月文章", author="作者丙", content="二月内容",
                source="读者", year=2024, month=2, category="散文"),
        Article(title="2023年旧文", author="作者丁", content="2023年内容",
                source="读者", year=2023, month=12, category="怀旧"),
        Article(title="无年份文章", author=None, content="历史兼容：元数据缺失",
                source="读者", year=None, month=None, category=None),
        Article(title="重复文章", author="作者Z", content="可能被重复抓取",
                source="读者", year=2024, month=5, category="测试",
                url="https://example.com/a/unique-1"),
    ]
    for a in items:
        db_session.add(a)
    db_session.commit()
    for a in items:
        db_session.refresh(a)
    return items


# ---------------------------------------------------------------------------
# Fake HTTP helper for scraper tests
# ---------------------------------------------------------------------------

class _FakeResponse:
    """Minimal stand-in for httpx.Response used by ArticleScraper."""
    def __init__(self, text: str, status_code: int = 200, url: str = ""):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.request = types.SimpleNamespace(url=url)

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx as _httpx
            request = _httpx.Request("GET", self.url or "http://fake/")
            resp = _httpx.Response(self.status_code, request=request, text=self.text or "")
            raise _httpx.HTTPStatusError(
                f"{self.status_code} error", request=request, response=resp
            )


class _FakeAsyncClient:
    """
    Replacement for httpx.AsyncClient whose `.get(url)` returns responses from
    a user-supplied mapping. Supports per-call failures (exceptions).

    Usage in a test:

        fake = FakeHttp({
            "https://example.com/list": "<html>...</html>",
            "https://example.com/a1":   "<html>...</html>",
        })
        monkeypatch.setattr(scraper_mod.httpx, "AsyncClient", fake.client_cls)
    """

    def __init__(
        self,
        responses: Dict[str, Any],
        default_status: int = 200,
    ):
        # responses maps url -> either html-string, _FakeResponse, or Exception
        self._responses: Dict[str, Any] = dict(responses)
        self._calls: List[Tuple[str, int]] = []  # (url, level) — for assertions
        self._default_status = default_status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, **kwargs):
        self._calls.append((url, len(self._calls)))
        entry = self._responses.get(url)
        if entry is None:
            return _FakeResponse("", 404, url=url)
        if isinstance(entry, Exception):
            raise entry
        if isinstance(entry, _FakeResponse):
            entry.raise_for_status()
            return entry
        if isinstance(entry, tuple):
            text, status = entry
            resp = _FakeResponse(text, status, url=url)
            resp.raise_for_status()
            return resp
        resp = _FakeResponse(str(entry), self._default_status, url=url)
        resp.raise_for_status()
        return resp

    @property
    def calls(self) -> List[str]:
        return [u for u, _ in self._calls]

    def client_cls(self, *args, **kwargs):
        """Return self when called as a constructor (so `async with httpx.AsyncClient(...) as c` works)."""
        return self


@pytest.fixture()
def fake_http_factory():
    """Factory to build _FakeAsyncClient instances bound to a response map."""
    def _factory(responses: Dict[str, Any], default_status: int = 200):
        return _FakeAsyncClient(responses, default_status=default_status)
    return _factory


@pytest.fixture()
def deterministic_time(monkeypatch: pytest.MonkeyPatch):
    """
    Freeze datetime.now / datetime.utcnow to a deterministic value.
    Returns the frozen datetime for test assertions.
    """
    import datetime as _dt
    fixed = _dt.datetime(2025, 3, 15, 10, 0, 0)

    class _FixedDateTime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed if tz is None else fixed.replace(tzinfo=tz)

        @classmethod
        def utcnow(cls):
            return fixed

    monkeypatch.setattr(_dt, "datetime", _FixedDateTime)
    return fixed
