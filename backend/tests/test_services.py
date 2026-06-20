"""
L2 service-integration tests.

These exercise the core business rules against a real (but isolated) SQLite DB
and real filesystem under tmp_path. No HTTP calls are made — network is mocked
at the Scraper boundary. Focus: rules that break silently if someone refactors
without thinking (dedup, persistence, backwards compatibility).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api import crawler as crawler_mod
from app.api.crawler import _ensure_unique, crawl_task, CrawlRequest
from app.core.config import settings
from app.models.article import Article


class TestDedupLogic:
    """_ensure_unique is the single point that prevents DB-duplication on re-crawl."""

    def test_new_url_article_is_added(self, db_session):
        added = _ensure_unique(db_session, {
            "title": "X", "author": "A", "content": "c", "source": "s",
            "year": 2024, "month": 1, "url": "https://example.com/a/1",
        })
        assert added is True
        db_session.commit()
        assert db_session.query(Article).count() == 1

    def test_same_url_is_deduped(self, db_session):
        data = {
            "title": "X", "author": "A", "content": "c", "source": "s",
            "year": 2024, "month": 1, "url": "https://example.com/a/1",
        }
        assert _ensure_unique(db_session, dict(data)) is True
        db_session.commit()
        assert _ensure_unique(db_session, dict(data)) is False
        db_session.commit()
        assert db_session.query(Article).count() == 1

    def test_same_title_author_date_without_url_is_deduped(self, db_session):
        """For mock crawls that have no URL, dedup falls back to title+author+ym."""
        data = {
            "title": "模拟文", "author": "佚名", "content": "c", "source": "mock",
            "year": 2025, "month": 3,
        }
        assert _ensure_unique(db_session, dict(data)) is True
        db_session.commit()
        assert _ensure_unique(db_session, dict(data)) is False
        db_session.commit()
        assert db_session.query(Article).count() == 1

    def test_same_title_different_author_not_considered_duplicate(self, db_session):
        base = {"title": "同题", "content": "c", "source": "s", "year": 2024, "month": 1}
        assert _ensure_unique(db_session, {**base, "author": "甲"}) is True
        db_session.commit()
        assert _ensure_unique(db_session, {**base, "author": "乙"}) is True
        db_session.commit()
        assert db_session.query(Article).count() == 2

    def test_dedup_works_even_when_url_differs_same_article_title(self, db_session):
        """URL is a stronger identity signal than title — different URL = different row."""
        assert _ensure_unique(db_session, {
            "title": "T", "author": "A", "content": "c", "source": "s",
            "year": 2024, "month": 1, "url": "https://a.com/1",
        }) is True
        db_session.commit()
        assert _ensure_unique(db_session, {
            "title": "T", "author": "A", "content": "c", "source": "s",
            "year": 2024, "month": 1, "url": "https://a.com/1?utm=x",
        }) is True  # different url, treated as different
        db_session.commit()
        assert db_session.query(Article).count() == 2


class TestSettingsPersistence:
    """
    Settings MUST survive process restarts — they're written to runtime_config.json.
    A regression here means users' saved path evaporates after restart.
    """

    def test_set_then_get_roundtrip(self, isolated_paths):
        settings.set_articles_path(str(isolated_paths["root"] / "custom_articles"))
        # Simulate a fresh process — a new Settings instance loads from file.
        from app.core.config import Settings
        fresh = Settings(
            database_url=settings.database_url,
            articles_path=settings.articles_path,
            sources_config=settings.sources_config,
            runtime_config=settings.runtime_config,
        )
        assert Path(fresh.get_articles_path()) == isolated_paths["root"] / "custom_articles"

    def test_get_articles_path_falls_back_to_default_when_file_missing(self, isolated_paths):
        # Ensure no runtime config exists
        if isolated_paths["runtime_config"].exists():
            isolated_paths["runtime_config"].unlink()
        assert settings.get_articles_path() == settings.articles_path

    def test_corrupt_runtime_config_does_not_crash(self, isolated_paths):
        """A half-written JSON file must not 500 the whole settings page."""
        isolated_paths["runtime_config"].write_text("{not valid json", encoding="utf-8")
        # Should fall back to default, not raise.
        assert settings.get_articles_path() == settings.articles_path


class TestHistoricalDataCompatibility:
    """
    Over time the Article schema evolved (added url/issue/category). Old rows
    have NULL for those columns. The API/list view must not crash on them.
    """

    def test_null_metadata_rows_list_ok(self, client, seed_articles):
        # seed_articles includes one article with year=None/month=None/author=None/category=None
        r = client.get("/api/articles")
        assert r.status_code == 200
        titles = [a["title"] for a in r.json()["items"]]
        assert "无年份文章" in titles

    def test_null_metadata_rows_returned_from_detail(self, client, seed_articles):
        null_article = next(a for a in seed_articles if a.title == "无年份文章")
        r = client.get(f"/api/articles/{null_article.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "无年份文章"
        assert data["year"] is None
        assert data["author"] is None

    def test_filter_year_excludes_null_year_rows(self, client, seed_articles):
        r = client.get("/api/articles?year=2024")
        assert r.status_code == 200
        data = r.json()
        for item in data["items"]:
            assert item["year"] == 2024
        titles = [a["title"] for a in data["items"]]
        assert "无年份文章" not in titles
        assert "2023年旧文" not in titles


class TestCrawlTaskEndToEnd:
    """crawl_task wired through Scraper (with fake HTTP) and _ensure_unique."""

    def _write_source(self, isolated_paths, source_cfg):
        isolated_paths["sources_config"].write_text(
            json.dumps({"sources": [source_cfg]}, ensure_ascii=False), encoding="utf-8"
        )

    @pytest.mark.asyncio
    async def test_crawl_persists_articles_and_uses_configured_save_path(
        self, db_session, isolated_paths, fake_http_factory, monkeypatch
    ):
        """Articles land in settings.articles_path (which is tmp-isolated by fixture)."""
        expected_root = Path(isolated_paths["articles_dir"])
        self._write_source(isolated_paths, {
            "name": "mock-src", "base_url": "https://example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": ".links a",
            "title_selector": "h1",
            "content_selector": "main",
        })

        list_html = '<div class="links"><a href="/s/1">a</a></div>'
        detail_html = "<html><body><h1>抓取文章</h1><main>正文内容</main></body></html>"
        fake = fake_http_factory({
            "https://example.com/2024/01": list_html,
            "https://example.com/s/1": detail_html,
        })
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake.client_cls)
        monkeypatch.setattr("app.services.scraper.asyncio.sleep", lambda *_: None)

        # Do NOT pass save_path — should fall back to (patched) settings.articles_path
        req = CrawlRequest(year=2024, month=1)
        await crawl_task(req, db_session)

        assert crawler_mod.crawl_status["status"] == "completed"
        assert crawler_mod.crawl_status["articles_count"] == 1
        art = db_session.query(Article).first()
        assert art.title == "抓取文章"
        assert (expected_root / "2024" / "01").exists()

    @pytest.mark.asyncio
    async def test_crawl_with_no_sources_sets_error_status(
        self, db_session, isolated_paths
    ):
        # Empty sources list
        self._write_source(isolated_paths, None)  # overwrite with no sources
        isolated_paths["sources_config"].write_text(
            json.dumps({"sources": []}, ensure_ascii=False), encoding="utf-8"
        )
        req = CrawlRequest(year=2024, month=1)
        await crawl_task(req, db_session)
        assert crawler_mod.crawl_status["status"] == "error"
        assert "配置数据源" in crawler_mod.crawl_status["message"]

    @pytest.mark.asyncio
    async def test_second_crawl_with_same_urls_dedups(
        self, db_session, isolated_paths, fake_http_factory, monkeypatch
    ):
        """Running the same crawl twice must not double-count."""
        self._write_source(isolated_paths, {
            "name": "mock-src", "base_url": "https://example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": ".links a",
            "title_selector": "h1", "content_selector": "main",
        })
        list_html = '<div class="links"><a href="/s/1">a</a><a href="/s/2">b</a></div>'
        detail = "<html><body><h1>T</h1><main>C</main></body></html>"
        responses = {
            "https://example.com/2024/02": list_html,
            "https://example.com/s/1": detail,
            "https://example.com/s/2": detail,
        }
        fake = fake_http_factory(responses)
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake.client_cls)
        monkeypatch.setattr("app.services.scraper.asyncio.sleep", lambda *_: None)

        req = CrawlRequest(year=2024, month=2)
        await crawl_task(req, db_session)
        first_count = crawler_mod.crawl_status["articles_count"]
        assert first_count == 2
        assert db_session.query(Article).count() == 2

        # Second crawl — same URLs
        fake2 = fake_http_factory(responses)
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake2.client_cls)
        await crawl_task(req, db_session)
        assert crawler_mod.crawl_status["articles_count"] == 0
        assert crawler_mod.crawl_status["message"].startswith("抓取完成")
        assert "跳过重复 2 篇" in crawler_mod.crawl_status["message"]
        assert db_session.query(Article).count() == 2  # still only 2
