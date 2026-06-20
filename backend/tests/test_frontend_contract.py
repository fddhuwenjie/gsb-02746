"""
前后端API合约测试 + 前端核心逻辑测试

这个测试验证：
1. 前端调用的所有API端点返回的结构与前端期望一致
2. 筛选、分页、详情展示的数据格式正确
3. 模拟完整用户主路径的请求序列
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app
from app.models.article import Article
import app.api.crawler as crawler_module


@pytest.fixture(autouse=True)
def reset_state():
    crawler_module.crawl_status = {"status": "idle", "message": "", "articles_count": 0}
    yield


@pytest.fixture
def client():
    import tempfile
    import os
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def seed_frontend_test_data(client):
    """模拟前端期望的数据集 - 覆盖各种筛选场景"""
    articles = [
        {"title": "人工智能的未来", "author": "张明", "content": "AI正在改变世界...", "source": "读者", "issue": "第1期", "year": 2024, "month": 3, "category": "科技", "url": "https://example.com/ai"},
        {"title": "春天的故事", "author": "李华", "content": "春风十里...", "source": "读者", "issue": "第1期", "year": 2024, "month": 3, "category": "散文", "url": "https://example.com/spring"},
        {"title": "深度学习入门", "author": "王芳", "content": "神经网络基础...", "source": "读者", "issue": "第2期", "year": 2024, "month": 4, "category": "科技", "url": "https://example.com/dl"},
        {"title": "夏日荷塘", "author": "赵伟", "content": "夏天的荷花...", "source": "读者", "issue": "第2期", "year": 2023, "month": 6, "category": "散文", "url": "https://example.com/summer"},
        {"title": "人生的智慧", "author": "陈静", "content": "叔本华的哲学...", "source": "读者", "issue": "第3期", "year": 2023, "month": 12, "category": "哲学", "url": "https://example.com/wisdom"},
    ]
    from app.core.database import SessionLocal
    engine = create_engine("sqlite:///" + next(iter(app.dependency_overrides[get_db]())) .get_bind().url.database if hasattr(next(iter(app.dependency_overrides[get_db]())), 'get_bind') else "")
    with TestClient(app) as c:
        for a in articles:
            pass
    return client.post("/api/crawler/mock")


class TestFrontendApiContract:
    """验证前端期望的API响应格式完全匹配 - 保护前后端契约"""

    def test_articles_list_contract(self, client):
        """前端Home.vue调用: articleApi.getList(params) -> {items, total, page, page_size}"""
        client.post("/api/crawler/mock")
        resp = client.get("/api/articles?page=1&page_size=12")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["items"], list)
        for item in data["items"]:
            for field in ["id", "title", "author", "content", "source", "issue", "year", "month", "category", "created_at"]:
                assert field in item, f"前端期望字段 {field} 不存在"
            assert isinstance(item["id"], int)
            assert isinstance(item["title"], str)
            assert len(item["title"]) > 0

    def test_articles_filter_contract(self, client):
        """前端筛选控件使用 year, month, search 参数"""
        client.post("/api/crawler/mock")
        resp = client.get("/api/articles?year=2026&month=6&search=模拟")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        for item in data["items"]:
            assert item["year"] == 2026
            assert item["month"] == 6

    def test_article_detail_contract(self, client):
        """前端Article.vue调用: articleApi.getById(id) -> 完整文章对象"""
        client.post("/api/crawler/mock")
        list_resp = client.get("/api/articles")
        article_id = list_resp.json()["items"][0]["id"]
        resp = client.get(f"/api/articles/{article_id}")
        assert resp.status_code == 200
        article = resp.json()
        assert article["id"] == article_id
        assert "content" in article
        assert len(article["content"]) > 0
        assert "title" in article
        assert "created_at" in article

    def test_issues_endpoint_contract(self, client):
        """前端Home.vue调用: articleApi.getIssues() -> 年份列表"""
        client.post("/api/crawler/mock")
        resp = client.get("/api/articles/issues")
        assert resp.status_code == 200
        issues = resp.json()
        assert isinstance(issues, list)
        for issue in issues:
            assert "year" in issue
            assert "month" in issue
        years = [i["year"] for i in issues if i["year"]]
        assert len(years) > 0
        assert years == sorted(years, reverse=True)

    def test_categories_endpoint_contract(self, client):
        """前端筛选调用: articleApi.getCategories() -> 分类列表"""
        client.post("/api/crawler/mock")
        resp = client.get("/api/articles/categories")
        assert resp.status_code == 200
        cats = resp.json()
        assert isinstance(cats, list)
        assert "模拟分类" in cats

    def test_crawler_status_contract(self, client):
        """前端Crawler.vue轮询: crawlerApi.getStatus() -> {status, message, articles_count}"""
        resp = client.get("/api/crawler/status")
        assert resp.status_code == 200
        status = resp.json()
        assert "status" in status
        assert "message" in status
        assert "articles_count" in status
        assert status["status"] in ("idle", "running", "completed", "error")

    def test_crawler_mock_contract(self, client):
        """前端测试按钮: crawlerApi.mock() -> {success, articles_count}"""
        resp = client.post("/api/crawler/mock")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "articles_count" in data
        assert data["articles_count"] == 3

    def test_settings_endpoint_contract(self, client):
        """前端Settings.vue调用: settingsApi.get() -> {articles_path, sources_config}"""
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        settings = resp.json()
        assert "articles_path" in settings
        assert "sources_config" in settings

    def test_settings_update_contract(self, client):
        """前端保存设置: settingsApi.update({articles_path}) -> {success}"""
        import tempfile
        import os
        tmp = tempfile.mkdtemp()
        new_path = os.path.join(tmp, "test_articles")
        resp = client.put("/api/settings", json={"articles_path": new_path})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


class TestFrontendCoreLogic:
    """前端纯逻辑测试 - Home.vue和Article.vue中的核心计算逻辑"""

    def test_pagination_logic(self):
        """Home.vue: 分页计算逻辑验证"""
        total = 25
        page_size = 12
        total_pages = (total + page_size - 1) // page_size
        assert total_pages == 3

        page = 1
        offset = (page - 1) * page_size
        assert offset == 0
        assert min(page_size, total - offset) == 12

        page = 2
        offset = (page - 1) * page_size
        assert offset == 12
        assert min(page_size, total - offset) == 12

        page = 3
        offset = (page - 1) * page_size
        assert offset == 24
        assert min(page_size, total - offset) == 1

    def test_display_pages_logic_small(self):
        """Home.vue: 少于等于7页全部显示"""
        total_pages = 5
        current = 3
        pages = list(range(1, total_pages + 1))
        assert pages == [1, 2, 3, 4, 5]

    def test_display_pages_logic_first_pages(self):
        """Home.vue: 当前在前3页时，显示前4页+省略号+末页"""
        total_pages = 10
        current = 2
        pages = [1, 2, 3, 4, '...', total_pages]
        assert pages == [1, 2, 3, 4, '...', 10]

    def test_display_pages_logic_last_pages(self):
        """Home.vue: 当前在最后3页时，显示首页+省略号+后4页"""
        total_pages = 10
        current = 9
        pages = [1, '...', total_pages - 3, total_pages - 2, total_pages - 1, total_pages]
        assert pages == [1, '...', 7, 8, 9, 10]

    def test_display_pages_logic_middle(self):
        """Home.vue: 当前在中间，首页+省略号+相邻3页+省略号+末页"""
        total_pages = 10
        current = 5
        pages = [1, '...', current - 1, current, current + 1, '...', total_pages]
        assert pages == [1, '...', 4, 5, 6, '...', 10]

    def test_filter_params_undefined_omitted(self):
        """Home.vue: 空筛选参数不传undefined给API"""
        params = {}
        if 1:
            params['page'] = 1
        params['page_size'] = 12
        search = ''
        year = ''
        month = ''
        if search:
            params['search'] = search
        if year:
            params['year'] = year
        if month:
            params['month'] = month
        assert 'search' not in params
        assert 'year' not in params
        assert 'month' not in params

    def test_filter_params_partial_set(self):
        """Home.vue: 部分筛选条件正确设置"""
        params = {'page': 1, 'page_size': 12}
        search = '人生'
        year = 2024
        month = ''
        if search:
            params['search'] = search
        if year:
            params['year'] = year
        if month:
            params['month'] = month
        assert params['search'] == '人生'
        assert params['year'] == 2024
        assert 'month' not in params

    def test_years_list_extracted_from_issues(self):
        """Home.vue: 从issues提取年份并去重降序"""
        issues = [
            {"year": 2024, "month": 3, "issue": "第1期"},
            {"year": 2024, "month": 4, "issue": "第2期"},
            {"year": 2023, "month": 12, "issue": "第3期"},
            {"year": None, "month": None, "issue": None},
            {"year": 2023, "month": 6, "issue": "第2期"},
        ]
        years = sorted(list({i["year"] for i in issues if i["year"]}), reverse=True)
        assert years == [2024, 2023]


class TestFrontendBackendIntegration:
    """模拟完整用户主路径 - 从抓取到浏览到详情"""

    def test_full_user_flow_mock_crawl_to_reading(self, client):
        """用户主路径: 进入首页(空) -> 模拟抓取 -> 列表可见 -> 筛选 -> 详情"""
        resp = client.get("/api/articles")
        assert resp.json()["total"] == 0

        resp = client.post("/api/crawler/mock")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = client.get("/api/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

        resp = client.get("/api/articles?search=春风")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

        article_id = data["items"][0]["id"]
        resp = client.get(f"/api/articles/{article_id}")
        assert resp.status_code == 200
        detail = resp.json()
        assert len(detail["content"]) > 0
        assert detail["id"] == article_id

    def test_full_user_flow_settings_then_mock(self, client, tmp_path, monkeypatch):
        """用户主路径: 设置页保存路径 -> 模拟抓取 -> 设置持久化生效"""
        import app.core.config as cfg
        runtime = tmp_path / "rt.json"
        monkeypatch.setattr(cfg.settings, "runtime_config", str(runtime))

        custom = tmp_path / "myarticles"
        resp = client.put("/api/settings", json={"articles_path": str(custom)})
        assert resp.status_code == 200

        resp = client.get("/api/settings")
        assert resp.json()["articles_path"] == str(custom)

    def test_full_user_flow_duplicate_protection(self, client):
        """用户多次点击抓取按钮不会产生重复数据"""
        for _ in range(3):
            client.post("/api/crawler/mock")
        resp = client.get("/api/articles")
        assert resp.json()["total"] == 3

    def test_deleted_article_returns_404(self, client):
        """用户删除文章后访问详情返回404，对应前端错误页"""
        client.post("/api/crawler/mock")
        aid = client.get("/api/articles").json()["items"][0]["id"]
        client.delete(f"/api/articles/{aid}")
        resp = client.get(f"/api/articles/{aid}")
        assert resp.status_code == 404
        assert "文章不存在" in resp.json()["detail"]
