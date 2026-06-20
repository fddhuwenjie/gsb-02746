"""
测试基础设施：每个测试独立的内存DB、临时文件系统、重置全局状态。

测试替身策略（见文末总结）：
- DB：每个测试用独立内存 SQLite，测试结束 drop_all
- 文件系统：pytest tmp_path，文章保存/runtime_config/sources.json 全部落 tmp_path
- HTTP：测试 Scraper 时注入 FakeAsyncClient / _StubClient，零网络访问
- 全局状态：crawl_task 的 crawl_status 每次测试前重置
- 时间：涉及时间的测试直接构造 datetime，不依赖 freezegun
"""
import json
import pytest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core import database as db_module
from app.core.config import settings as global_settings
from app.models.article import Base
from app.api import crawler as crawler_module


@pytest.fixture(autouse=True)
def isolate_filesystem(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    articles_dir = data_dir / "articles"
    articles_dir.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    sources_path = config_dir / "sources.json"
    runtime_path = data_dir / "runtime_config.json"

    db_path = data_dir / "test.db"

    monkeypatch.setattr(global_settings, "database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(global_settings, "articles_path", str(articles_dir))
    monkeypatch.setattr(global_settings, "sources_config", str(sources_path))
    monkeypatch.setattr(global_settings, "runtime_config", str(runtime_path))

    sources_path.write_text(json.dumps({"sources": []}, ensure_ascii=False), encoding="utf-8")
    if runtime_path.exists():
        runtime_path.unlink()

    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(db_module, "engine", test_engine)
    monkeypatch.setattr(db_module, "SessionLocal", TestingSessionLocal)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.main import app
    app.dependency_overrides[db_module.get_db] = override_get_db

    yield TestingSessionLocal, tmp_path

    app.dependency_overrides.pop(db_module.get_db, None)
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture(autouse=True)
def reset_crawl_status():
    crawler_module.crawl_status = {"status": "idle", "message": "", "articles_count": 0}
    yield
    crawler_module.crawl_status = {"status": "idle", "message": "", "articles_count": 0}


@pytest.fixture
def db_session(isolate_filesystem):
    session_factory, _ = isolate_filesystem
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(isolate_filesystem):
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_articles_factory(db_session):
    def make(count: int = 5, base_year: int = 2024, base_month: int = 1,
             with_urls: bool = False, source: str = "测试来源"):
        from app.models.article import Article
        articles = []
        for i in range(count):
            m = ((base_month - 1 + i) % 12) + 1
            y = base_year + ((base_month - 1 + i) // 12)
            art = Article(
                title=f"测试文章_{i+1}_{y}_{m}",
                author=f"作者{(i % 3) + 1}" if i % 3 != 0 else None,
                content=f"这是第{i+1}篇测试文章的内容，包含若干文字用来验证搜索匹配。",
                source=source,
                issue=f"第{(i % 2) + 1}期",
                year=y,
                month=m,
                category=["随笔", "科技", "生活", "书评"][i % 4],
                url=f"https://example.com/article/{i+1}" if with_urls else None,
            )
            db_session.add(art)
            articles.append(art)
        db_session.commit()
        for a in articles:
            db_session.refresh(a)
        return articles
    return make


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            request = type("R", (), {"method": "GET", "url": "http://fake"})()
            raise httpx.HTTPStatusError("HTTP error", request=request, response=self)


class FakeAsyncClient:
    """可注入到 ArticleScraper 的假 HTTP 客户端。"""

    def __init__(self, list_html: str = "<html><body></body></html>",
                 article_html_map=None,
                 default_article_html: str = "<html><body><h1>默认标题</h1><article>默认正文</article></body></html>",
                 failure_sequence=None):
        self.list_html = list_html
        self.article_html_map = article_html_map or {}
        self.default_article_html = default_article_html
        self.failure_sequence = failure_sequence or []
        self.calls = []
        self._fail_iter = iter(self.failure_sequence)
        self._entered = False

    async def __aenter__(self):
        self._entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._entered = False
        return False

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        try:
            exc = next(self._fail_iter)
            raise exc
        except StopIteration:
            pass
        if url in self.article_html_map:
            return FakeResponse(self.article_html_map[url])
        if "/article/" in url or "/art" in url:
            return FakeResponse(self.default_article_html)
        return FakeResponse(self.list_html)

    async def get(self, url, **kwargs):
        return await self.request("GET", url, **kwargs)


@pytest.fixture
def fake_client_factory():
    factories = []

    def _make(**kwargs):
        client = FakeAsyncClient(**kwargs)
        factories.append(client)
        return client

    yield _make, factories
