"""抓取流程集成测试：通过直接调用 crawl_task 验证核心业务，通过 API 验证接口契约。
覆盖：模拟抓取可见、重复抓取去重、失败重试/容错、状态流转、设置变更影响行为、站点改版容忍。"""
import json
import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from app.api import crawler as crawler_module
from app.api.crawler import crawl_task, _save_articles_dedup, CrawlRequest
from app.models.article import Article
from app.core import database as db_core
from app.services.scraper import NetworkError, ParseError


def _write_source(tmp_path, source):
    cfg = Path(__file__).parent.parent / "config" / "sources.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"sources": [source]}, ensure_ascii=False), encoding="utf-8")
    return cfg


class _FakeScraper:
    def __init__(self, source_cfg, save_path, articles=None, fail=False, empty=False):
        self.source_cfg = source_cfg
        self.save_path = save_path
        self._articles = articles or []
        self._fail = fail
        self._empty = empty

    async def crawl(self, year, month, issue=None):
        if self._fail:
            raise NetworkError("模拟网络错误")
        if self._empty:
            return []
        result = []
        for i, a in enumerate(self._articles):
            entry = {
                "title": a["title"],
                "author": a.get("author"),
                "content": a.get("content", "正文"),
                "source": self.source_cfg.get("name"),
                "issue": issue,
                "year": year,
                "month": month,
                "category": a.get("category"),
                "file_path": f"{self.save_path}/{year}/{month:02d}/t{i}.txt",
                "url": a.get("url", f"https://example.com/{year}/{month}/{i}"),
            }
            result.append(entry)
        return result


def _factory(articles=None, fail=False, empty=False):
    created = []
    def make(src, path):
        s = _FakeScraper(src, str(path), articles=articles, fail=fail, empty=empty)
        created.append(s)
        return s
    return make, created


class TestMockCrawlEndToEnd:
    def test_mock_crawl_makes_articles_visible_in_list(self, client, reset_crawl_status):
        r = client.post("/api/crawler/mock")
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True
        assert d["articles_count"] >= 3

        lst = client.get("/api/articles", params={"page_size": 50}).json()
        titles = [it["title"] for it in lst["items"]]
        assert any("春风十里" in t for t in titles)
        assert any("岁月静好" in t for t in titles)

    def test_mock_crawl_dedup_on_second_call(self, client):
        client.post("/api/crawler/mock")
        first_total = client.get("/api/articles").json()["total"]
        client.post("/api/crawler/mock")
        second_total = client.get("/api/articles").json()["total"]
        assert second_total == first_total


class TestDedup:
    def test_save_articles_dedup_by_url(self, db_session):
        arts = [
            {"title": "同一文章", "content": "c", "year": 2024, "month": 1,
             "url": "https://x.com/a1"},
            {"title": "同一文章", "content": "c", "year": 2024, "month": 1,
             "url": "https://x.com/a1"},
            {"title": "不同文章", "content": "c", "year": 2024, "month": 1,
             "url": "https://x.com/a2"},
        ]
        added = _save_articles_dedup(db_session, arts)
        assert added == 2
        assert db_session.query(Article).count() == 2

    def test_dedup_falls_back_to_title_when_no_url(self, db_session):
        arts = [
            {"title": "唯一标题", "content": "c", "year": 2024, "month": 1},
            {"title": "唯一标题", "content": "c", "year": 2024, "month": 1},
            {"title": "另一篇", "content": "c", "year": 2024, "month": 1},
        ]
        added = _save_articles_dedup(db_session, arts)
        assert added == 2

    def test_dedup_same_title_different_month_is_separate(self, db_session):
        arts = [
            {"title": "同题", "content": "c", "year": 2024, "month": 1},
            {"title": "同题", "content": "c", "year": 2024, "month": 2},
        ]
        added = _save_articles_dedup(db_session, arts)
        assert added == 2


class TestCrawlTaskCore:
    @pytest.mark.asyncio
    async def test_crawl_task_happy_path_persists_articles(self, db_session, isolate_filesystem, monkeypatch):
        src = {"name": "测试源", "base_url": "https://x.com",
               "list_pattern": "/{year}/{month}", "article_selector": "a",
               "title_selector": "h1", "content_selector": "article"}
        cfg = Path(crawler_module.settings.sources_config)
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps({"sources": [src]}), encoding="utf-8")

        arts = [{"title": "抓取1", "url": "https://x.com/a/1"},
                {"title": "抓取2", "url": "https://x.com/a/2"}]
        factory, instances = _factory(articles=arts)
        req = CrawlRequest(year=2024, month=5)
        await crawl_task(req, scraper_factory=factory)

        assert crawler_module.crawl_status["status"] == "completed"
        assert crawler_module.crawl_status["articles_count"] == 2
        db_session.close()
        with db_core.SessionLocal() as fresh:
            rows = fresh.query(Article).all()
            assert len(rows) == 2
            assert rows[0].source == "测试源"
            assert rows[0].year == 2024
            assert rows[0].month == 5

    @pytest.mark.asyncio
    async def test_crawl_task_dedup_articles_across_runs(self, db_session, isolate_filesystem):
        src = {"name": "测试源", "base_url": "https://x.com",
               "list_pattern": "/{year}/{month}", "article_selector": "a",
               "title_selector": "h1", "content_selector": "article"}
        cfg = Path(crawler_module.settings.sources_config)
        cfg.write_text(json.dumps({"sources": [src]}), encoding="utf-8")

        arts = [{"title": "文章A", "url": "https://x.com/a1"}]
        f1, _ = _factory(articles=arts)
        await crawl_task(CrawlRequest(year=2024, month=1), scraper_factory=f1)
        db_session.close()
        with db_core.SessionLocal() as fresh:
            assert fresh.query(Article).count() == 1

        f2, _ = _factory(articles=[
            {"title": "文章A", "url": "https://x.com/a1"},
            {"title": "文章B", "url": "https://x.com/b1"},
        ])
        await crawl_task(CrawlRequest(year=2024, month=1), scraper_factory=f2)
        with db_core.SessionLocal() as fresh:
            assert fresh.query(Article).count() == 2
        assert crawler_module.crawl_status["articles_count"] == 1

    @pytest.mark.asyncio
    async def test_crawl_task_reports_error_when_no_source_configured(self, db_session):
        cfg = Path(crawler_module.settings.sources_config)
        cfg.write_text(json.dumps({"sources": []}), encoding="utf-8")
        await crawl_task(CrawlRequest(year=2024, month=1))
        assert crawler_module.crawl_status["status"] == "error"
        assert "配置数据源" in crawler_module.crawl_status["message"]

    @pytest.mark.asyncio
    async def test_crawl_task_reports_error_when_scraper_fails(self, db_session, isolate_filesystem):
        src = {"name": "测试源", "base_url": "https://x.com",
               "list_pattern": "/{year}/{month}", "article_selector": "a",
               "title_selector": "h1", "content_selector": "article"}
        cfg = Path(crawler_module.settings.sources_config)
        cfg.write_text(json.dumps({"sources": [src]}), encoding="utf-8")

        f, _ = _factory(fail=True)
        await crawl_task(CrawlRequest(year=2024, month=1), scraper_factory=f)
        assert crawler_module.crawl_status["status"] == "error"
        assert "网络错误" in crawler_module.crawl_status["message"]
        db_session.close()
        with db_core.SessionLocal() as fresh:
            assert fresh.query(Article).count() == 0

    @pytest.mark.asyncio
    async def test_crawl_task_empty_result_is_not_error(self, db_session, isolate_filesystem):
        """站点改版导致选择器抓不到文章时，应完成（added=0）而不是挂死/崩溃。"""
        src = {"name": "测试源", "base_url": "https://x.com",
               "list_pattern": "/{year}/{month}", "article_selector": ".old-class a",
               "title_selector": "h1", "content_selector": "article"}
        cfg = Path(crawler_module.settings.sources_config)
        cfg.write_text(json.dumps({"sources": [src]}), encoding="utf-8")

        f, _ = _factory(empty=True)
        await crawl_task(CrawlRequest(year=2024, month=1), scraper_factory=f)
        assert crawler_module.crawl_status["status"] == "completed"
        assert crawler_module.crawl_status["articles_count"] == 0


class TestCrawlApi:
    def test_start_returns_202_like_response(self, client, db_session, monkeypatch, isolate_filesystem):
        src = {"name": "测试源", "base_url": "https://x.com",
               "list_pattern": "/{year}/{month}", "article_selector": "a",
               "title_selector": "h1", "content_selector": "article"}
        cfg = Path(crawler_module.settings.sources_config)
        cfg.write_text(json.dumps({"sources": [src]}), encoding="utf-8")

        async def _fake_crawl(request, scraper_factory=None):
            crawler_module.crawl_status = {"status": "running", "message": "mock", "articles_count": 0}
            await asyncio.sleep(0.01)
            crawler_module.crawl_status = {"status": "completed", "message": "ok", "articles_count": 0}

        monkeypatch.setattr(crawler_module, "crawl_task", _fake_crawl)
        r = client.post("/api/crawler/start", json={"year": 2024, "month": 5})
        assert r.status_code == 200
        assert "message" in r.json()

    def test_start_rejects_when_already_running(self, client):
        crawler_module.crawl_status = {"status": "running", "message": "...", "articles_count": 0}
        r = client.post("/api/crawler/start", json={"year": 2024, "month": 5})
        assert r.status_code == 400
        assert "已有任务" in r.json()["detail"]

    def test_start_validates_year_and_month(self, client):
        r = client.post("/api/crawler/start", json={"year": 1800, "month": 1})
        assert r.status_code == 422
        r = client.post("/api/crawler/start", json={"year": 2024, "month": 13})
        assert r.status_code == 422

    def test_status_endpoint_reflects_current_state(self, client):
        crawler_module.crawl_status = {"status": "completed", "message": "ok", "articles_count": 3}
        r = client.get("/api/crawler/status")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "completed"
        assert d["articles_count"] == 3

    def test_save_path_validation_blocks_path_traversal(self, client):
        r = client.post("/api/crawler/start", json={
            "year": 2024, "month": 1, "save_path": "../../../etc"
        })
        assert r.status_code == 422


class TestSettingsAffectCrawl:
    """验证：设置变更后抓取行为随之变化（保存到不同路径）。"""

    @pytest.mark.asyncio
    async def test_save_path_from_request_is_used(self, db_session, tmp_path, isolate_filesystem):
        src = {"name": "测试源", "base_url": "https://x.com",
               "list_pattern": "/{year}/{month}", "article_selector": "a",
               "title_selector": "h1", "content_selector": "article"}
        cfg = Path(crawler_module.settings.sources_config)
        cfg.write_text(json.dumps({"sources": [src]}), encoding="utf-8")

        custom_rel = "./data/crawl_req_custom"
        captured = {}
        class CapturingScraper(_FakeScraper):
            def __init__(self, src_cfg, save_path, **kw):
                super().__init__(src_cfg, save_path, **kw)
                captured["path"] = save_path
            async def crawl(self, *a, **kw):
                Path(self.save_path).mkdir(parents=True, exist_ok=True)
                return await super().crawl(*a, **kw)

        def factory(src, path):
            return CapturingScraper(src, path, articles=[{"title": "x", "url": "u"}])

        await crawl_task(CrawlRequest(year=2024, month=1, save_path=custom_rel),
                         scraper_factory=factory)
        assert captured["path"] == custom_rel

    @pytest.mark.asyncio
    async def test_persisted_settings_path_used_as_default(self, db_session, tmp_path, isolate_filesystem):
        from app.core.config import settings
        custom = tmp_path / "persisted_store"
        settings.set_articles_path(str(custom))
        src = {"name": "测试源", "base_url": "https://x.com",
               "list_pattern": "/{year}/{month}", "article_selector": "a",
               "title_selector": "h1", "content_selector": "article"}
        cfg = Path(crawler_module.settings.sources_config)
        cfg.write_text(json.dumps({"sources": [src]}), encoding="utf-8")

        captured = {}
        class Cap(_FakeScraper):
            def __init__(self, src_cfg, save_path, **kw):
                super().__init__(src_cfg, save_path, **kw)
                captured["path"] = save_path
            async def crawl(self, *a, **kw):
                Path(self.save_path).mkdir(parents=True, exist_ok=True)
                return await super().crawl(*a, **kw)

        await crawl_task(CrawlRequest(year=2024, month=1), scraper_factory=lambda s, p: Cap(s, p, articles=[{"title": "x", "url": "u"}]))
        assert str(custom) in str(captured["path"])
