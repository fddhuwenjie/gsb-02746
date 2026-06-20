"""
API smoke tests — these are the original happy-path checks, updated to run
against the per-test isolated database via the `client` fixture.
"""
import pytest


class TestArticlesAPI:
    """文章接口测试"""

    def test_get_articles_empty(self, client):
        response = client.get("/api/articles")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_get_articles_with_pagination(self, client):
        response = client.get("/api/articles?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_get_articles_invalid_page(self, client):
        response = client.get("/api/articles?page=0")
        assert response.status_code == 422

    def test_seed_test_data(self, client):
        response = client.post("/api/articles/seed")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_get_article_not_found(self, client):
        response = client.get("/api/articles/99999")
        assert response.status_code == 404

    def test_get_issues(self, client):
        response = client.get("/api/articles/issues")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_categories(self, client):
        response = client.get("/api/articles/categories")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestCrawlerAPI:
    """抓取接口测试"""

    def test_get_status(self, client):
        response = client.get("/api/crawler/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "message" in data

    def test_get_sources(self, client):
        response = client.get("/api/crawler/sources")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data

    def test_start_crawl_validation(self, client):
        response = client.post("/api/crawler/start", json={"year": 1800, "month": 1})
        assert response.status_code == 422

        response = client.post("/api/crawler/start", json={"year": 2024, "month": 13})
        assert response.status_code == 422

    def test_mock_crawl(self, client):
        response = client.post("/api/crawler/mock")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "articles_count" in data


class TestSettingsAPI:
    """设置接口测试"""

    def test_get_settings(self, client):
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.json()
        assert "articles_path" in data

    def test_update_settings(self, client):
        response = client.put("/api/settings", json={"articles_path": "./data/test_articles"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_settings_invalid_path(self, client):
        response = client.put("/api/settings", json={"articles_path": "../../../etc/passwd"})
        assert response.status_code == 422

    def test_add_source_validation(self, client):
        response = client.post("/api/settings/sources", json={"name": "test"})
        assert response.status_code == 422

        response = client.post("/api/settings/sources", json={
            "name": "test",
            "base_url": "not-a-url",
            "list_pattern": "/{year}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".content"
        })
        assert response.status_code == 422

    def test_add_mock_source(self, client):
        response = client.post("/api/settings/sources/mock")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestHealthCheck:
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
