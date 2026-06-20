"""
前后端契约测试（Frontend Contract Tests）

目的：防止后端响应结构的"静默破坏性变更"——这些变更往往让单元/集成测试通过，
但前端页面访问不到字段就白屏。测试方式：
1. 基于前端实际引用的字段清单（直接来源于 Home.vue / Article.vue / Crawler.vue / Settings.vue / api/index.js）
   构造"字段必须存在"契约
2. 在后端 API 响应上做字段存在性与类型断言，不依赖 UI 渲染
3. 验证前端传参名（search/year/month/page/page_size）和后端接收名严格一致

注意：
- 这不是 E2E 测试，不跑浏览器，不做网络请求（除了到 TestClient），因此快速且稳定
- 任何后端删除字段 / 重命名字段 / 字段类型变化都会在此被测出来
"""
import pytest
from fastapi.testclient import TestClient
from app.models.article import Article


# ---- 以下字段清单直接来自前端代码扫描，作为 SOT（source of truth） ----

# Home.vue 列表卡片/列表项/时间线项访问的字段
LIST_ITEM_REQUIRED_FIELDS = {
    "id": int,
    "title": str,
    "author": (str, type(None)),
    "content": (str, type(None)),
    "category": (str, type(None)),
    "year": (int, type(None)),
    "month": (int, type(None)),
    "issue": (str, type(None)),
}

# Article.vue 详情页访问的字段（包括复制按钮需要的 content、底部展示的 source/file_path）
DETAIL_REQUIRED_FIELDS = {
    "id": int,
    "title": str,
    "author": (str, type(None)),
    "content": (str, type(None)),
    "category": (str, type(None)),
    "year": (int, type(None)),
    "month": (int, type(None)),
    "issue": (str, type(None)),
    "source": (str, type(None)),
    "file_path": (str, type(None)),
    "url": (str, type(None)),
    "created_at": str,
}

# Home.vue loadArticles 解构用的外层字段
LIST_RESPONSE_REQUIRED_FIELDS = {
    "items": list,
    "total": int,
    "page": int,
    "page_size": int,
}

# Home.vue issues 聚合使用的字段
ISSUE_ITEM_FIELDS = {"year": (int, type(None)), "month": (int, type(None)), "issue": (str, type(None))}

# Crawler.vue 轮询状态使用的字段
CRAWL_STATUS_FIELDS = {"status": str, "message": str, "articles_count": int}

# Crawler.vue 数据源展示
CRAWL_SOURCES_OUTER = {"sources": list}
SOURCE_ITEM_MIN_FIELDS = {"name": str, "base_url": str}

# Settings.vue 加载设置使用
SETTINGS_FIELDS = {"articles_path": str, "sources_config": str}

# Crawler.vue mock 返回
MOCK_RESPONSE_FIELDS = {"success": bool, "message": str, "articles_count": int}

# 前端 API 层调用的 query 参数名必须被后端接受
FRONTEND_LIST_PARAMS = ["page", "page_size", "search", "year", "month"]


def _seed_one(client):
    """seed 一次，返回首个文章 id。"""
    client.post("/api/articles/seed")
    lst = client.get("/api/articles", params={"page_size": 1}).json()
    return lst["items"][0]["id"]


def _assert_type(value, expected_type, label):
    __tracebackhide__ = True
    if isinstance(expected_type, tuple):
        assert isinstance(value, expected_type), \
            f"字段 {label} 类型错误：期望 {expected_type}，实际 {type(value)} (值={value!r})"
    else:
        assert isinstance(value, expected_type), \
            f"字段 {label} 类型错误：期望 {expected_type}，实际 {type(value)} (值={value!r})"


def _assert_fields(obj, field_map, where):
    __tracebackhide__ = True
    for name, typ in field_map.items():
        assert name in obj, f"{where} 响应缺少字段 {name}；实际 keys={sorted(obj.keys())}"
        _assert_type(obj[name], typ, f"{where}.{name}")


class TestArticleListContract:
    def test_list_response_shape(self, client):
        client.post("/api/articles/seed")
        r = client.get("/api/articles")
        assert r.status_code == 200
        data = r.json()
        _assert_fields(data, LIST_RESPONSE_REQUIRED_FIELDS, "GET /api/articles")
        assert isinstance(data["items"], list)

    def test_list_item_fields_after_seed(self, client):
        client.post("/api/articles/seed")
        r = client.get("/api/articles", params={"page_size": 50})
        items = r.json()["items"]
        assert len(items) >= 1
        for i, it in enumerate(items):
            _assert_fields(it, LIST_ITEM_REQUIRED_FIELDS, f"GET /api/articles items[{i}]")

    def test_list_item_fields_after_mock_crawl(self, client):
        client.post("/api/crawler/mock")
        r = client.get("/api/articles", params={"page_size": 50, "search": "模拟抓取"})
        items = r.json()["items"]
        assert len(items) >= 1
        for i, it in enumerate(items):
            _assert_fields(it, LIST_ITEM_REQUIRED_FIELDS, f"mock items[{i}]")
            assert it["title"].startswith("模拟抓取")
            assert it["author"] is not None, "模拟数据应带 author，否则列表 '佚名' 逻辑要单独验证"

    def test_list_accepts_all_frontend_query_params(self, client):
        """前端传入的参数名后端必须识别，不能静默忽略（否则筛选看似可用实则无效）。"""
        client.post("/api/articles/seed")
        r = client.get("/api/articles", params={
            "page": 1, "page_size": 5,
            "search": "人生", "year": 2024, "month": 1
        })
        assert r.status_code == 200
        d = r.json()
        assert d["page"] == 1
        assert d["page_size"] == 5
        for it in d["items"]:
            assert it["year"] == 2024
            assert it["month"] == 1

    def test_list_content_is_short_in_list_view_docs(self, client):
        """注意：此断言不是强制截断（后端没做截断是设计选择），只是保证字段存在。"""
        client.post("/api/articles/seed")
        it = client.get("/api/articles", params={"page_size": 1}).json()["items"][0]
        assert "content" in it


class TestArticleDetailContract:
    def test_detail_contract(self, client):
        aid = _seed_one(client)
        r = client.get(f"/api/articles/{aid}")
        assert r.status_code == 200
        _assert_fields(r.json(), DETAIL_REQUIRED_FIELDS, f"GET /api/articles/{aid}")

    def test_detail_includes_full_content_for_copy(self, client):
        """复制按钮需要全文，不能是截断版。"""
        client.post("/api/articles/seed")
        aid = client.get("/api/articles", params={"search": "人生的意义", "page_size": 1}).json()["items"][0]["id"]
        r = client.get(f"/api/articles/{aid}")
        assert "人生的意义不在于你拥有多少" in r.json()["content"]

    def test_detail_404_shape_is_json(self, client):
        r = client.get("/api/articles/999999")
        assert r.status_code == 404
        assert "application/json" in r.headers.get("content-type", "")
        assert "detail" in r.json()


class TestIssuesCategoriesContract:
    def test_issues_shape(self, client):
        client.post("/api/articles/seed")
        r = client.get("/api/articles/issues")
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)
        for i, it in enumerate(arr):
            _assert_fields(it, ISSUE_ITEM_FIELDS, f"issues[{i}]")

    def test_categories_is_str_list(self, client):
        client.post("/api/articles/seed")
        r = client.get("/api/articles/categories")
        assert r.status_code == 200
        arr = r.json()
        for c in arr:
            assert isinstance(c, str)


class TestCrawlerContract:
    def test_status_shape(self, client):
        r = client.get("/api/crawler/status")
        assert r.status_code == 200
        _assert_fields(r.json(), CRAWL_STATUS_FIELDS, "GET /crawler/status")

    def test_mock_shape(self, client):
        r = client.post("/api/crawler/mock")
        assert r.status_code == 200
        _assert_fields(r.json(), MOCK_RESPONSE_FIELDS, "POST /crawler/mock")

    def test_sources_outer_shape(self, client):
        r = client.get("/api/crawler/sources")
        assert r.status_code == 200
        data = r.json()
        _assert_fields(data, CRAWL_SOURCES_OUTER, "GET /crawler/sources")

    def test_start_crawl_response_shape(self, client):
        """启动接口不返回 articles_count（异步），但必须返回 message 字段。"""
        r = client.post("/api/crawler/start", json={"year": 2024, "month": 1})
        assert r.status_code in (200, 400, 500)
        if r.status_code == 200:
            assert "message" in r.json()
        else:
            assert "detail" in r.json()


class TestSettingsContract:
    def test_settings_get_shape(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 200
        _assert_fields(r.json(), SETTINGS_FIELDS, "GET /api/settings")

    def test_settings_update_shape(self, client, tmp_path):
        p = str(tmp_path / "contract_articles")
        r = client.put("/api/settings", json={"articles_path": p})
        assert r.status_code == 200
        d = r.json()
        assert "success" in d and isinstance(d["success"], bool)
        assert "message" in d and isinstance(d["message"], str)

    def test_add_source_response_shape(self, client):
        r = client.post("/api/settings/sources", json={
            "name": "契约测试源",
            "base_url": "https://contract.example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".c",
        })
        assert r.status_code == 200
        d = r.json()
        assert "success" in d and "message" in d


class TestFrontendBackendLinkage:
    """前后端联动：mock 抓取后，前端依赖的筛选/搜索链条完整可用。"""

    def test_mock_then_filter_by_current_month(self, client):
        client.post("/api/crawler/mock")
        from datetime import datetime
        now = datetime.now()
        r = client.get("/api/articles", params={
            "year": now.year, "month": now.month, "search": "模拟抓取", "page_size": 50
        })
        assert r.status_code == 200
        d = r.json()
        assert d["total"] >= 1
        for it in d["items"]:
            assert it["year"] == now.year
            assert it["month"] == now.month
            assert "模拟抓取" in it["title"]

    def test_mock_then_detail_chain(self, client):
        """模拟抓取后：列表 -> 详情 -> 拿到全文 链路打通。"""
        client.post("/api/crawler/mock")
        items = client.get("/api/articles", params={"page_size": 50}).json()["items"]
        assert len(items) >= 1
        aid = items[0]["id"]
        detail = client.get(f"/api/articles/{aid}").json()
        assert detail["id"] == aid
        assert detail["content"] and len(detail["content"]) > 10
        assert detail["source"] == "模拟数据源"

    def test_search_author_visible_to_frontend(self, client):
        """前端默认展示 author || '佚名'，验证按作者搜索能命中数据。"""
        client.post("/api/articles/seed")
        r = client.get("/api/articles", params={"search": "张三", "page_size": 50})
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(it["author"] == "张三" for it in items)
