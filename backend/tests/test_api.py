"""
API 接口测试
运行: pytest tests/test_api.py -v
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestArticlesAPI:
    """文章接口测试"""
    
    def test_get_articles_empty(self):
        """测试获取空文章列表"""
        response = client.get("/api/articles")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
    
    def test_get_articles_with_pagination(self):
        """测试分页参数"""
        response = client.get("/api/articles?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10
    
    def test_get_articles_invalid_page(self):
        """测试无效分页参数"""
        response = client.get("/api/articles?page=0")
        assert response.status_code == 422  # Validation error
    
    def test_seed_test_data(self):
        """测试添加测试数据"""
        response = client.post("/api/articles/seed")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_get_article_not_found(self):
        """测试获取不存在的文章"""
        response = client.get("/api/articles/99999")
        assert response.status_code == 404
    
    def test_get_issues(self):
        """测试获取期数列表"""
        response = client.get("/api/articles/issues")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_categories(self):
        """测试获取分类列表"""
        response = client.get("/api/articles/categories")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestCrawlerAPI:
    """抓取接口测试"""
    
    def test_get_status(self):
        """测试获取抓取状态"""
        response = client.get("/api/crawler/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "message" in data
    
    def test_get_sources(self):
        """测试获取数据源"""
        response = client.get("/api/crawler/sources")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
    
    def test_start_crawl_validation(self):
        """测试抓取参数验证"""
        # 无效年份
        response = client.post("/api/crawler/start", json={
            "year": 1800,
            "month": 1
        })
        assert response.status_code == 422
        
        # 无效月份
        response = client.post("/api/crawler/start", json={
            "year": 2024,
            "month": 13
        })
        assert response.status_code == 422
    
    def test_mock_crawl(self):
        """测试模拟抓取"""
        response = client.post("/api/crawler/mock")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "articles_count" in data


class TestSettingsAPI:
    """设置接口测试"""
    
    def test_get_settings(self):
        """测试获取设置"""
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.json()
        assert "articles_path" in data
    
    def test_update_settings(self):
        """测试更新设置"""
        response = client.put("/api/settings", json={
            "articles_path": "./data/test_articles"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    def test_update_settings_invalid_path(self):
        """测试无效路径"""
        response = client.put("/api/settings", json={
            "articles_path": "../../../etc/passwd"
        })
        assert response.status_code == 422
    
    def test_add_source_validation(self):
        """测试数据源验证"""
        # 缺少必填字段
        response = client.post("/api/settings/sources", json={
            "name": "test"
        })
        assert response.status_code == 422
        
        # 无效URL
        response = client.post("/api/settings/sources", json={
            "name": "test",
            "base_url": "not-a-url",
            "list_pattern": "/{year}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".content"
        })
        assert response.status_code == 422
    
    def test_add_mock_source(self):
        """测试添加模拟数据源"""
        response = client.post("/api/settings/sources/mock")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True


class TestHealthCheck:
    """健康检查测试"""
    
    def test_root(self):
        """测试根路径"""
        response = client.get("/")
        assert response.status_code == 200
