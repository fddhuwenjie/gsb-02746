import pytest
import json
import asyncio
from pathlib import Path
from freezegun import freeze_time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app
from app.models.article import Article
import app.api.crawler as crawler_module
import app.core.config as config_module
from app.api.crawler import crawl_task, CrawlRequest


def seed_articles(db, articles_data):
    for data in articles_data:
        db.add(Article(**data))
    db.commit()


class TestArticlesAfterCrawl:
    def test_mock_crawl_populates_list(self, client, db_session):
        resp = client.post("/api/crawler/mock")
        assert resp.status_code == 200
        assert resp.json()["articles_count"] == 3

        resp = client.get("/api/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        for item in data["items"]:
            assert item["title"].startswith("模拟抓取")
            assert "content" in item
            assert item["year"] is not None

    def test_mock_crawl_then_detail_viewable(self, client):
        client.post("/api/crawler/mock")
        list_resp = client.get("/api/articles")
        article_id = list_resp.json()["items"][0]["id"]

        detail_resp = client.get(f"/api/articles/{article_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["id"] == article_id
        assert len(detail["title"]) > 0
        assert len(detail["content"]) > 0

    def test_mock_crawl_issues_list_populated(self, client):
        client.post("/api/crawler/mock")
        resp = client.get("/api/articles/issues")
        assert resp.status_code == 200
        issues = resp.json()
        assert len(issues) >= 1
        assert all("year" in i and "month" in i for i in issues)

    def test_mock_crawl_categories_populated(self, client):
        client.post("/api/crawler/mock")
        resp = client.get("/api/articles/categories")
        assert resp.status_code == 200
        cats = resp.json()
        assert "模拟分类" in cats


class TestFilteringScenarios:
    @pytest.fixture(autouse=True)
    def setup_data(self, db_session):
        seed_articles(db_session, [
            {"title": "春节随笔", "author": "甲", "content": "过年的故事", "year": 2024, "month": 1, "category": "散文", "source": "读者"},
            {"title": "夏日荷塘", "author": "乙", "content": "夏天风景", "year": 2024, "month": 6, "category": "散文", "source": "读者"},
            {"title": "秋月思亲", "author": "甲", "content": "秋天思念", "year": 2024, "month": 9, "category": "亲情", "source": "读者"},
            {"title": "冬日围炉", "author": "丙", "content": "冬天温暖", "year": 2023, "month": 12, "category": "生活", "source": "读者"},
            {"title": "春的散文精选", "author": "丁", "content": "散文合集", "year": 2023, "month": 3, "category": "散文", "source": "读者"},
            {"title": "人生感悟二则", "author": "戊", "content": "关于人生", "year": 2024, "month": 3, "category": "人生感悟", "source": "读者"},
        ])

    def test_filter_by_year_only(self, client):
        resp = client.get("/api/articles?year=2024")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert all(i["year"] == 2024 for i in data["items"])

    def test_filter_by_year_and_month(self, client):
        resp = client.get("/api/articles?year=2024&month=1")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "春节随笔"

    def test_filter_by_month_cross_year(self, client):
        resp = client.get("/api/articles?month=3")
        data = resp.json()
        assert data["total"] == 2
        titles = {i["title"] for i in data["items"]}
        assert "春的散文精选" in titles
        assert "人生感悟二则" in titles

    def test_search_by_keyword_title(self, client):
        resp = client.get("/api/articles?search=春")
        data = resp.json()
        assert data["total"] == 2
        titles = {i["title"] for i in data["items"]}
        assert "春节随笔" in titles
        assert "春的散文精选" in titles

    def test_search_combined_with_year(self, client):
        resp = client.get("/api/articles?year=2024&search=春")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "春节随笔"

    def test_filter_by_category(self, client):
        resp = client.get("/api/articles?category=散文")
        data = resp.json()
        assert data["total"] == 3
        assert all(i["category"] == "散文" for i in data["items"])

    def test_pagination_isolation(self, client):
        resp = client.get("/api/articles?page=1&page_size=2")
        assert resp.status_code == 200
        d1 = resp.json()
        assert len(d1["items"]) == 2
        assert d1["total"] == 6
        assert d1["page"] == 1
        assert d1["page_size"] == 2

        resp2 = client.get("/api/articles?page=2&page_size=2")
        d2 = resp2.json()
        ids1 = {i["id"] for i in d1["items"]}
        ids2 = {i["id"] for i in d2["items"]}
        assert ids1.isdisjoint(ids2)

    def test_filter_no_results(self, client):
        resp = client.get("/api/articles?year=1999")
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestDuplicateDedup:
    def test_mock_crawl_twice_only_three_articles(self, client):
        client.post("/api/crawler/mock")
        first_total = client.get("/api/articles").json()["total"]
        client.post("/api/crawler/mock")
        second_total = client.get("/api/articles").json()["total"]
        assert first_total == 3
        assert second_total == 3

    def test_seed_then_seed_again_no_duplicate(self, client):
        client.post("/api/articles/seed")
        first_total = client.get("/api/articles").json()["total"]
        client.post("/api/articles/seed")
        second_total = client.get("/api/articles").json()["total"]
        assert first_total == second_total

    @pytest.mark.asyncio
    async def test_crawl_task_dedupes_by_url(self, db_session, temp_articles_dir, monkeypatch):
        async def fake_crawl(self, year, month, issue):
            return [
                {"title": "唯一文章", "content": "c1", "url": "https://x.com/a", "year": 2024, "month": 1, "source": "test"},
                {"title": "唯一文章", "content": "c2", "url": "https://x.com/a", "year": 2024, "month": 1, "source": "test"},
                {"title": "另一篇文章", "content": "c3", "url": "https://x.com/b", "year": 2024, "month": 1, "source": "test"},
            ]
        import app.services.scraper as sc
        monkeypatch.setattr(sc.ArticleScraper, "crawl", fake_crawl)

        sources_path = temp_articles_dir / "sources.json"
        sources_path.write_text(json.dumps({
            "sources": [{"name": "test", "base_url": "https://x.com", "list_pattern": "/{y}",
                         "article_selector": "a", "title_selector": "h1", "content_selector": "c"}]
        }), encoding="utf-8")
        monkeypatch.setattr(config_module.settings, "sources_config", str(sources_path))

        req = CrawlRequest(year=2024, month=1, save_path="data/test_tmp")
        await crawl_task(req, db_session)
        count = db_session.query(Article).count()
        assert count == 2


class TestHistoricalDataCompat:
    def test_article_without_author_displays(self, client, db_session):
        db_session.add(Article(title="旧文章", content="旧内容", year=2020, month=5))
        db_session.commit()

        resp = client.get("/api/articles")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["title"] == "旧文章"
        assert item["author"] is None

        resp2 = client.get(f"/api/articles/{item['id']}")
        assert resp2.status_code == 200
        assert resp2.json()["author"] is None

    def test_article_without_url_field_works(self, client, db_session):
        db_session.add(Article(title="老数据", content="c", year=2019, month=1))
        db_session.commit()

        resp = client.get("/api/articles")
        assert resp.status_code == 200
        assert resp.json()["items"][0]["url"] is None


class TestSettingsChangeCrawlBehavior:
    def test_set_articles_path_persists(self, client, temp_dir, monkeypatch):
        runtime = temp_dir / "runtime.json"
        monkeypatch.setattr(config_module.settings, "runtime_config", str(runtime))

        new_path = str(temp_dir / "custom_path")
        resp = client.put("/api/settings", json={"articles_path": new_path})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp2 = client.get("/api/settings")
        assert resp2.json()["articles_path"] == new_path

    def test_set_path_creates_directory(self, client, temp_dir, monkeypatch):
        runtime = temp_dir / "runtime.json"
        monkeypatch.setattr(config_module.settings, "runtime_config", str(runtime))
        custom = temp_dir / "newdir"
        client.put("/api/settings", json={"articles_path": str(custom)})
        assert custom.exists()


class TestCrawlErrorHandling:
    def test_crawl_without_sources_sets_error(self, client, temp_dir, monkeypatch):
        empty_cfg = temp_dir / "empty.json"
        empty_cfg.write_text(json.dumps({"sources": []}), encoding="utf-8")
        monkeypatch.setattr(config_module.settings, "sources_config", str(empty_cfg))

        resp = client.post("/api/crawler/start", json={"year": 2024, "month": 1})
        assert resp.status_code == 200

        import time
        for _ in range(20):
            st = client.get("/api/crawler/status").json()
            if st["status"] != "running":
                break
            time.sleep(0.1)
        assert st["status"] == "error"
        assert "配置数据源" in st["message"]

    def test_status_resets_between_tests(self, client):
        st = client.get("/api/crawler/status").json()
        assert st["status"] == "idle"


class TestArticleDelete:
    def test_delete_existing_article(self, client, db_session):
        db_session.add(Article(title="待删除", content="c", year=2024, month=1))
        db_session.commit()
        aid = db_session.query(Article).first().id

        resp = client.delete(f"/api/articles/{aid}")
        assert resp.status_code == 200
        assert db_session.query(Article).filter(Article.id == aid).first() is None

    def test_delete_nonexistent_404(self, client):
        resp = client.delete("/api/articles/999999")
        assert resp.status_code == 404
