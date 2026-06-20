"""
API 集成测试。

使用 conftest.py 提供的 client fixture，每个测试一个内存 SQLite，
sources.json / runtime_config.json 隔离到 tmp_path，互不干扰。

覆盖：
- 文章列表分页
- 年/月/issue/category/search 多维筛选
- 历史/兼容数据：旧字段缺失（url/file_path/category 为 None）下仍能列表展示
- 文章详情查询、404 行为
- seed 添加测试数据后列表立刻可见
- 设置持久化（PUT /settings + 新进程读取等价行为）
- 数据源配置校验（必填、URL 格式、重名拒绝）
- 抓取参数校验
- mock 抓取流程：成功后文章在列表中、status 切换为 completed
- 配置变更后的真实抓取入库（注入 fake scraper）→ 设置改 articles_path 后，传递给 ArticleScraper
- 重复抓取去重：同 (source, url) 不会重复入库
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api import crawler as crawler_module


# ---------------- 文章列表 / 详情 ----------------

class TestArticleListing:
    def test_empty_list_initial(self, client):
        r = client.get("/api/articles")
        assert r.status_code == 200
        body = r.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1
        assert body["page_size"] == 20

    def test_pagination_metadata(self, client, seed_articles):
        seed_articles([
            {"title": f"标题{i}", "year": 2024, "month": 1, "category": "随笔"}
            for i in range(25)
        ])
        r = client.get("/api/articles?page=2&page_size=10")
        body = r.json()
        assert body["page"] == 2
        assert body["page_size"] == 10
        assert body["total"] == 25
        assert len(body["items"]) == 10

    def test_invalid_pagination_rejected(self, client):
        assert client.get("/api/articles?page=0").status_code == 422
        assert client.get("/api/articles?page_size=0").status_code == 422
        assert client.get("/api/articles?page_size=999").status_code == 422

    def test_filter_by_year_and_month(self, client, seed_articles):
        seed_articles([
            {"title": "Y2024M1", "year": 2024, "month": 1},
            {"title": "Y2024M2", "year": 2024, "month": 2},
            {"title": "Y2023M1", "year": 2023, "month": 1},
        ])
        r = client.get("/api/articles?year=2024&month=1")
        items = r.json()["items"]
        assert {i["title"] for i in items} == {"Y2024M1"}

    def test_filter_by_search_keyword(self, client, seed_articles):
        seed_articles([
            {"title": "人生的意义", "year": 2024, "month": 1},
            {"title": "读书的乐趣", "year": 2024, "month": 1},
            {"title": "另一篇人生感悟", "year": 2024, "month": 2},
        ])
        r = client.get("/api/articles?search=人生")
        titles = [i["title"] for i in r.json()["items"]]
        assert set(titles) == {"人生的意义", "另一篇人生感悟"}

    def test_filter_by_issue_and_category(self, client, seed_articles):
        seed_articles([
            {"title": "A", "issue": "第1期", "category": "散文", "year": 2024, "month": 1},
            {"title": "B", "issue": "第1期", "category": "随笔", "year": 2024, "month": 1},
            {"title": "C", "issue": "第2期", "category": "散文", "year": 2024, "month": 1},
        ])
        r1 = client.get("/api/articles?issue=第1期")
        assert {i["title"] for i in r1.json()["items"]} == {"A", "B"}
        r2 = client.get("/api/articles?category=散文")
        assert {i["title"] for i in r2.json()["items"]} == {"A", "C"}

    def test_history_data_with_missing_fields_renders(self, client, seed_articles):
        """旧版数据可能没有 url/file_path/category，列表与详情仍应正常返回。"""
        seed_articles([{"title": "老数据", "year": 2020, "month": 6}])
        r = client.get("/api/articles")
        items = r.json()["items"]
        assert items[0]["title"] == "老数据"
        assert items[0]["url"] is None if "url" in items[0] else True
        assert items[0]["category"] is None
        # 详情也能开
        aid = items[0]["id"]
        d = client.get(f"/api/articles/{aid}")
        assert d.status_code == 200
        assert d.json()["title"] == "老数据"

    def test_get_article_404(self, client):
        assert client.get("/api/articles/99999").status_code == 404

    def test_issues_and_categories_aggregation(self, client, seed_articles):
        seed_articles([
            {"title": "A", "year": 2024, "month": 1, "issue": "第1期", "category": "散文"},
            {"title": "B", "year": 2024, "month": 2, "issue": "第2期", "category": "随笔"},
            {"title": "C", "year": 2023, "month": 12, "issue": "第12期", "category": "散文"},
        ])
        issues = client.get("/api/articles/issues").json()
        assert {(i["year"], i["month"]) for i in issues} == {
            (2024, 1), (2024, 2), (2023, 12)
        }
        # 排序：年降序，月降序
        assert issues[0]["year"] == 2024 and issues[0]["month"] == 2
        cats = client.get("/api/articles/categories").json()
        assert set(cats) == {"散文", "随笔"}


# ---------------- Mock 抓取 ----------------

class TestMockCrawl:
    def test_mock_crawl_inserts_three_articles_visible_in_list(self, client):
        before = client.get("/api/articles").json()["total"]
        r = client.post("/api/crawler/mock")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["articles_count"] == 3

        listing = client.get("/api/articles").json()
        assert listing["total"] == before + 3
        # 标题前缀可以识别为模拟数据
        assert all("模拟抓取" in t for t in [i["title"] for i in listing["items"]])

        # status 状态机
        st = client.get("/api/crawler/status").json()
        assert st["status"] == "completed"
        assert st["articles_count"] == 3


# ---------------- 设置 ----------------

class TestSettings:
    def test_get_default_settings(self, client, isolated_settings):
        r = client.get("/api/settings").json()
        # 默认值来自 isolated_settings 的注入
        assert r["articles_path"].startswith(str(isolated_settings["articles"].parent))

    def test_update_persists_articles_path_and_survives_reload(self, client, isolated_settings, tmp_path):
        new_path = str(tmp_path / "myarticles")
        r = client.put("/api/settings", json={"articles_path": new_path})
        assert r.status_code == 200

        # runtime_config.json 应当已写入
        runtime = json.loads(Path(isolated_settings["runtime"]).read_text(encoding="utf-8"))
        assert runtime["articles_path"] == new_path

        # 再次 GET 设置（模拟刷新页面），应返回新值
        r2 = client.get("/api/settings").json()
        assert r2["articles_path"] == new_path
        # 目录被自动创建
        assert Path(new_path).is_dir()

    def test_invalid_path_rejected(self, client):
        for bad in ["../etc/passwd", "/etc/$home", "a;b", "with|pipe"]:
            assert client.put("/api/settings", json={"articles_path": bad}).status_code == 422


# ---------------- 数据源配置 ----------------

class TestSources:
    def test_add_valid_source(self, client, isolated_settings):
        payload = {
            "name": "示例期刊",
            "base_url": "https://reader.example.com",
            "list_pattern": "/archive/{year}/{month}",
            "article_selector": ".item a",
            "title_selector": "h1",
            "content_selector": ".body",
        }
        r = client.post("/api/settings/sources", json=payload)
        assert r.status_code == 200
        # 写入文件
        data = json.loads(isolated_settings["sources"].read_text(encoding="utf-8"))
        names = [s["name"] for s in data["sources"]]
        assert "示例期刊" in names

    def test_duplicate_source_name_rejected(self, client, write_sources):
        write_sources([
            {"name": "A", "base_url": "https://a.com", "list_pattern": "/{year}",
             "article_selector": "a", "title_selector": "h1", "content_selector": ".c"}
        ])
        payload = {
            "name": "A",
            "base_url": "https://a.com",
            "list_pattern": "/{year}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".c",
        }
        r = client.post("/api/settings/sources", json=payload)
        assert r.status_code == 400

    def test_invalid_url_rejected(self, client):
        bad = {
            "name": "x",
            "base_url": "not-a-url",
            "list_pattern": "/x",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".c",
        }
        assert client.post("/api/settings/sources", json=bad).status_code == 422

    def test_required_selectors_must_be_non_empty(self, client):
        # title_selector 空字符串
        bad = {
            "name": "x",
            "base_url": "https://x.com",
            "list_pattern": "/x",
            "article_selector": "a",
            "title_selector": "   ",
            "content_selector": ".c",
        }
        assert client.post("/api/settings/sources", json=bad).status_code == 422

    def test_get_sources_reflects_disk_state(self, client, write_sources):
        write_sources([
            {"name": "S1", "base_url": "https://s1.com", "list_pattern": "/{year}",
             "article_selector": "a", "title_selector": "h1", "content_selector": ".c"}
        ])
        r = client.get("/api/crawler/sources").json()
        assert [s["name"] for s in r["sources"]] == ["S1"]


# ---------------- 抓取参数校验 ----------------

class TestCrawlerValidation:
    def test_year_out_of_range(self, client):
        assert client.post("/api/crawler/start", json={"year": 1800, "month": 1}).status_code == 422
        assert client.post("/api/crawler/start", json={"year": 9999, "month": 1}).status_code == 422

    def test_month_out_of_range(self, client):
        assert client.post("/api/crawler/start", json={"year": 2024, "month": 0}).status_code == 422
        assert client.post("/api/crawler/start", json={"year": 2024, "month": 13}).status_code == 422

    def test_save_path_security(self, client):
        r = client.post("/api/crawler/start", json={
            "year": 2024, "month": 1, "save_path": "../etc"
        })
        assert r.status_code == 422


# ---------------- 抓取行为 / 端到端联动 ----------------

@pytest.fixture
def fake_scraper(monkeypatch):
    """
    用一个可记录构造参数和返回固定数据的假 scraper 替换真实 ArticleScraper。
    既能验证「设置变更后抓取行为变化」（save_path 是否传过来），
    也能稳定地测「抓取后列表可见 + 去重」。
    """
    calls = {"init_args": [], "crawl_args": []}

    class FakeScraper:
        def __init__(self, source_config, save_path, max_retries=1):
            calls["init_args"].append({
                "source": source_config,
                "save_path": save_path,
                "max_retries": max_retries,
            })
            self._articles = source_config.get("_fake_articles", [])

        async def crawl(self, year, month, issue=None):
            calls["crawl_args"].append({"year": year, "month": month, "issue": issue})
            # 注入 year/month/issue/source 字段，模拟真实 scraper 输出
            out = []
            for a in self._articles:
                row = dict(a)
                row.setdefault("source", "FakeSource")
                row.setdefault("year", year)
                row.setdefault("month", month)
                row.setdefault("issue", issue)
                out.append(row)
            return out

    monkeypatch.setattr(crawler_module, "ArticleScraper", FakeScraper)
    return calls


def _wait_until(predicate, max_iters=50):
    """简单的同步轮询，直到 predicate() 为真或超过次数。"""
    import time
    for _ in range(max_iters):
        if predicate():
            return True
        time.sleep(0.02)
    return False


class TestCrawlIntegration:
    def test_crawl_results_visible_in_list_after_completion(self, client, write_sources, fake_scraper):
        write_sources([{
            "name": "FakeSource",
            "base_url": "https://fake.test",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".c",
            "_fake_articles": [
                {"title": "T1", "content": "c1", "url": "https://fake.test/1"},
                {"title": "T2", "content": "c2", "url": "https://fake.test/2"},
            ],
        }])

        r = client.post("/api/crawler/start", json={"year": 2024, "month": 5})
        assert r.status_code == 200

        # 等待后台任务完成
        assert _wait_until(
            lambda: client.get("/api/crawler/status").json()["status"] == "completed"
        ), client.get("/api/crawler/status").json()

        listing = client.get("/api/articles").json()
        titles = [i["title"] for i in listing["items"]]
        assert {"T1", "T2"} <= set(titles)

    def test_settings_change_propagates_to_crawl_save_path(
        self, client, write_sources, fake_scraper, tmp_path
    ):
        new_path = str(tmp_path / "configured_articles")
        client.put("/api/settings", json={"articles_path": new_path})

        write_sources([{
            "name": "FakeSource",
            "base_url": "https://fake.test",
            "list_pattern": "/{year}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".c",
            "_fake_articles": [{"title": "X", "content": "x", "url": "https://fake.test/x"}],
        }])
        client.post("/api/crawler/start", json={"year": 2024, "month": 5})
        _wait_until(lambda: client.get("/api/crawler/status").json()["status"] != "running")

        # 关键断言：构造 ArticleScraper 时使用了新的 save_path
        assert fake_scraper["init_args"], "ArticleScraper should have been constructed"
        assert fake_scraper["init_args"][-1]["save_path"] == new_path

    def test_crawl_dedupes_repeated_articles_across_runs(self, client, write_sources, fake_scraper):
        write_sources([{
            "name": "FakeSource",
            "base_url": "https://fake.test",
            "list_pattern": "/{year}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".c",
            "_fake_articles": [
                {"title": "重复文章", "content": "c", "url": "https://fake.test/dup"},
                {"title": "唯一文章", "content": "c", "url": "https://fake.test/unique"},
            ],
        }])

        # 第一次抓取
        client.post("/api/crawler/start", json={"year": 2024, "month": 5})
        _wait_until(lambda: client.get("/api/crawler/status").json()["status"] == "completed")
        first = client.get("/api/articles").json()["total"]
        assert first == 2

        # 第二次抓取（同样的 url + source）
        client.post("/api/crawler/start", json={"year": 2024, "month": 5})
        _wait_until(lambda: client.get("/api/crawler/status").json()["status"] == "completed")

        listing = client.get("/api/articles").json()
        # 不允许出现重复
        assert listing["total"] == 2
        # status 信息提示去重
        st = client.get("/api/crawler/status").json()
        assert "跳过" in st["message"] or "跳过重复" in st["message"]

    def test_crawl_without_configured_source_reports_error(self, client, write_sources, fake_scraper):
        write_sources([])  # 没有任何数据源
        client.post("/api/crawler/start", json={"year": 2024, "month": 5})
        _wait_until(lambda: client.get("/api/crawler/status").json()["status"] != "running")
        st = client.get("/api/crawler/status").json()
        assert st["status"] == "error"
        # 没真正调用过 scraper
        assert fake_scraper["crawl_args"] == []
