"""
L3 API regression tests — the user-facing contract.

These tests drive the FastAPI TestClient against an isolated DB and exercise
the main end-to-end paths a real user would walk: crawl/mock → list appears →
filter/search → open detail → copy (read content) → change settings.
The priority is to lock down behaviour that future refactors are most likely
to silently break (e.g. a filter silently dropping ALL rows, or settings not
persisting).
"""
from __future__ import annotations

import json

import pytest


class TestMockCrawlToListVisible:
    """After a mock crawl, articles MUST appear in the list endpoint."""

    def test_mock_crawl_returns_count(self, client):
        r = client.post("/api/crawler/mock")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["articles_count"] == 3

    def test_after_mock_list_shows_articles(self, client):
        client.post("/api/crawler/mock")
        r = client.get("/api/articles")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        titles = [a["title"] for a in data["items"]]
        assert any("春风十里" in t for t in titles)

    def test_mock_then_status_reports_completed(self, client):
        client.post("/api/crawler/mock")
        r = client.get("/api/crawler/status")
        assert r.status_code == 200
        assert r.json()["status"] in ("completed", "idle")


class TestFilterByYearMonthKeyword:
    """Filter behaviour is the most frequently broken UI contract."""

    @pytest.fixture(autouse=True)
    def _seeded(self, client):
        # 8 seed articles span 2024 months 1-4 plus (from seed) 2024/1 through 2024/4
        client.post("/api/articles/seed")

    def test_filter_by_year_only(self, client):
        r = client.get("/api/articles?year=2024")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 8
        for a in data["items"]:
            assert a["year"] == 2024

    def test_filter_by_year_and_month(self, client):
        r = client.get("/api/articles?year=2024&month=1")
        data = r.json()
        assert data["total"] == 3  # seed has 3 articles for 2024/1
        for a in data["items"]:
            assert a["year"] == 2024
            assert a["month"] == 1

    def test_filter_by_month_alone(self, client):
        """Selecting month without year should filter across years."""
        r = client.get("/api/articles?month=1")
        data = r.json()
        for a in data["items"]:
            assert a["month"] == 1

    def test_filter_year_month_no_results(self, client):
        r = client.get("/api/articles?year=1999&month=1")
        data = r.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_search_by_title_keyword(self, client):
        r = client.get("/api/articles?search=母亲")
        data = r.json()
        assert data["total"] >= 1
        assert any("母亲" in a["title"] for a in data["items"])

    def test_search_by_author_name(self, client):
        """Front-end placeholder promises '搜索标题、作者'; backend MUST match author too."""
        r = client.get("/api/articles?search=张三")
        data = r.json()
        assert data["total"] >= 1
        assert any(a["author"] == "张三" for a in data["items"])

    def test_combined_year_and_search(self, client):
        r = client.get("/api/articles?year=2024&search=人生")
        data = r.json()
        for a in data["items"]:
            assert a["year"] == 2024
            assert "人生" in a["title"]

    def test_pagination_respects_page_size(self, client):
        r = client.get("/api/articles?page=1&page_size=2")
        data = r.json()
        assert len(data["items"]) == 2
        assert data["page_size"] == 2
        assert data["total"] == 8


class TestArticleDetail:
    """Detail endpoint returns complete article; content matches stored content."""

    def test_detail_returns_full_content(self, client):
        client.post("/api/articles/seed")
        # pick any id
        r = client.get("/api/articles")
        art_id = r.json()["items"][0]["id"]
        d = client.get(f"/api/articles/{art_id}")
        assert d.status_code == 200
        art = d.json()
        assert art["id"] == art_id
        assert art["title"]
        assert art["content"]  # must not be empty/None
        assert "created_at" in art

    def test_detail_404_for_missing(self, client):
        r = client.get("/api/articles/9999999")
        assert r.status_code == 404

    def test_delete_removes_article(self, client):
        client.post("/api/articles/seed")
        r = client.get("/api/articles")
        aid = r.json()["items"][0]["id"]
        d = client.delete(f"/api/articles/{aid}")
        assert d.status_code == 200
        assert client.get(f"/api/articles/{aid}").status_code == 404


class TestIssuesAndCategories:
    def test_issues_endpoint_returns_distinct_sorted(self, client):
        client.post("/api/articles/seed")
        r = client.get("/api/articles/issues")
        assert r.status_code == 200
        issues = r.json()
        assert isinstance(issues, list)
        assert len(issues) >= 1
        # sorted descending by year then month
        years = [i["year"] for i in issues]
        assert years == sorted(years, reverse=True)

    def test_categories_endpoint_returns_unique(self, client):
        client.post("/api/articles/seed")
        r = client.get("/api/articles/categories")
        cats = r.json()
        assert isinstance(cats, list)
        assert len(cats) == len(set(cats))
        assert "人生感悟" in cats


class TestSettingsPersistenceApi:
    """PUT settings MUST be visible on next GET (writes runtime_config.json)."""

    def test_put_then_get_roundtrip(self, client):
        new_path = "./data/articles_persist_test"
        r = client.put("/api/settings", json={"articles_path": new_path})
        assert r.status_code == 200
        g = client.get("/api/settings")
        assert g.json()["articles_path"] == new_path

    def test_put_rejects_traversal(self, client):
        r = client.put("/api/settings", json={"articles_path": "../../etc/passwd"})
        assert r.status_code == 422


class TestSourceConfigValidation:
    """Adding data sources MUST validate thoroughly — bad config crashes crawler."""

    def _valid_source(self, **overrides):
        base = {
            "name": "测试源",
            "base_url": "https://example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": "article",
        }
        base.update(overrides)
        return base

    def test_add_valid_source_succeeds(self, client, isolated_paths):
        r = client.post("/api/settings/sources", json=self._valid_source())
        assert r.status_code == 200
        assert r.json()["success"] is True
        # Persisted to disk
        on_disk = json.loads(isolated_paths["sources_config"].read_text(encoding="utf-8"))
        assert any(s["name"] == "测试源" for s in on_disk["sources"])

    def test_duplicate_source_name_rejected(self, client):
        client.post("/api/settings/sources", json=self._valid_source())
        r = client.post("/api/settings/sources", json=self._valid_source())
        assert r.status_code == 400

    def test_invalid_url_rejected(self, client):
        r = client.post("/api/settings/sources", json=self._valid_source(base_url="not-a-url"))
        assert r.status_code == 422

    def test_missing_required_fields_rejected(self, client):
        r = client.post("/api/settings/sources", json={"name": "x"})
        assert r.status_code == 422

    def test_base_url_normalized_strip_trailing_slash(self, client, isolated_paths):
        r = client.post("/api/settings/sources", json=self._valid_source(
            name="trimmed", base_url="https://example.com/"
        ))
        assert r.status_code == 200
        on_disk = json.loads(isolated_paths["sources_config"].read_text(encoding="utf-8"))
        src = next(s for s in on_disk["sources"] if s["name"] == "trimmed")
        assert src["base_url"] == "https://example.com"

    def test_add_mock_source_twice_is_idempotent(self, client):
        a = client.post("/api/settings/sources/mock")
        assert a.status_code == 200
        b = client.post("/api/settings/sources/mock")
        assert b.status_code == 200
        # Should not have created duplicates
        sources = client.get("/api/crawler/sources").json()["sources"]
        names = [s["name"] for s in sources]
        assert names.count("模拟数据源（测试用）") == 1


class TestMockCrawlIdempotency:
    """Calling mock crawl twice MUST NOT duplicate records (dedup guard)."""

    def test_double_mock_does_not_double_articles(self, client):
        client.post("/api/crawler/mock")
        first_total = client.get("/api/articles").json()["total"]
        client.post("/api/crawler/mock")
        second_total = client.get("/api/articles").json()["total"]
        assert second_total == first_total
        # Message should indicate skipped duplicates
        status = client.get("/api/crawler/status").json()
        assert "重复" in status["message"] or status["articles_count"] == 0

    def test_mock_then_seed_are_distinct(self, client):
        """Mock articles and seed articles have different titles, should coexist."""
        client.post("/api/crawler/mock")
        client.post("/api/articles/seed")
        data = client.get("/api/articles").json()
        titles = " ".join(a["title"] for a in data["items"])
        assert "模拟抓取" in titles
        assert "人生" in titles or "母亲" in titles


class TestCrawlValidation:
    def test_invalid_year_rejected(self, client):
        r = client.post("/api/crawler/start", json={"year": 1800, "month": 1})
        assert r.status_code == 422

    def test_invalid_month_rejected(self, client):
        r = client.post("/api/crawler/start", json={"year": 2024, "month": 13})
        assert r.status_code == 422

    def test_concurrent_crawl_rejected(self, client):
        """If a crawl is already running, starting another must 400."""
        from app.api import crawler as cm
        cm.crawl_status = {"status": "running", "message": "x", "articles_count": 0}
        r = client.post("/api/crawler/start", json={"year": 2024, "month": 1})
        assert r.status_code == 400
        cm.crawl_status = {"status": "idle", "message": "", "articles_count": 0}
