"""文章 API 回归测试：覆盖筛选、搜索、分页、详情、聚合以及历史数据兼容。"""
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from app.models.article import Article


def _add(db, **kw):
    defaults = dict(title="t", content="c", year=2024, month=1)
    defaults.update(kw)
    a = Article(**defaults)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


class TestFiltering:
    def test_filter_by_year_and_month_returns_only_matching(self, client, sample_articles_factory):
        sample_articles_factory(count=12, base_year=2024, base_month=1)
        r = client.get("/api/articles", params={"year": 2024, "month": 3, "page_size": 50})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        for it in data["items"]:
            assert it["year"] == 2024
            assert it["month"] == 3

    def test_filter_by_category(self, client, sample_articles_factory):
        sample_articles_factory(count=8, base_year=2024, base_month=1)
        r = client.get("/api/articles", params={"category": "科技", "page_size": 50})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        for it in data["items"]:
            assert it["category"] == "科技"

    def test_combined_filters_year_month_category(self, client, sample_articles_factory):
        sample_articles_factory(count=12, base_year=2024, base_month=1)
        r = client.get("/api/articles", params={
            "year": 2024, "month": 1, "category": "随笔", "page_size": 50
        })
        data = r.json()
        for it in data["items"]:
            assert it["year"] == 2024
            assert it["month"] == 1
            assert it["category"] == "随笔"


class TestSearch:
    def test_search_matches_title(self, client, db_session):
        _add(db_session, title="深度学习三百年", year=2024, month=1)
        _add(db_session, title="午后随笔", year=2024, month=1)
        r = client.get("/api/articles", params={"search": "深度", "page_size": 50})
        data = r.json()
        titles = [i["title"] for i in data["items"]]
        assert "深度学习三百年" in titles
        assert "午后随笔" not in titles

    def test_search_matches_author(self, client, db_session):
        _add(db_session, title="无名标题1", author="王小明", year=2024, month=1)
        _add(db_session, title="另文", author="李四", year=2024, month=1)
        r = client.get("/api/articles", params={"search": "小明", "page_size": 50})
        data = r.json()
        authors = [i["author"] for i in data["items"]]
        assert "王小明" in authors
        assert "李四" not in authors

    def test_search_returns_empty_when_no_match(self, client, db_session):
        _add(db_session, title="abc", year=2024, month=1)
        r = client.get("/api/articles", params={"search": "zzzzz不存在"})
        assert r.status_code == 200
        assert r.json()["total"] == 0


class TestPaginationAndOrdering:
    def test_newest_first(self, client, db_session):
        a1 = _add(db_session, title="old", year=2024, month=1)
        a2 = _add(db_session, title="new", year=2024, month=2)
        db_session.query(Article).filter(Article.id == a1.id).update(
            {"created_at": datetime(2024, 1, 1)})
        db_session.query(Article).filter(Article.id == a2.id).update(
            {"created_at": datetime(2024, 2, 1)})
        db_session.commit()
        r = client.get("/api/articles", params={"page_size": 50})
        items = r.json()["items"]
        assert items[0]["title"] == "new"

    def test_pagination_respects_page_size(self, client, sample_articles_factory):
        sample_articles_factory(count=15, base_year=2024, base_month=1)
        r = client.get("/api/articles", params={"page": 1, "page_size": 5})
        d = r.json()
        assert d["page"] == 1
        assert d["page_size"] == 5
        assert len(d["items"]) == 5
        assert d["total"] >= 15

    def test_page_out_of_range_returns_empty(self, client, sample_articles_factory):
        sample_articles_factory(count=3, base_year=2024, base_month=1)
        r = client.get("/api/articles", params={"page": 99, "page_size": 5})
        assert r.status_code == 200
        assert r.json()["items"] == []


class TestArticleDetail:
    def test_detail_includes_content_and_url(self, client, db_session):
        art = _add(db_session, title="有内容的文章", author="张三", content="正文全文",
                   year=2024, month=5, category="随笔",
                   url="https://example.com/abc", issue="第1期")
        r = client.get(f"/api/articles/{art.id}")
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == art.id
        assert d["title"] == "有内容的文章"
        assert d["content"] == "正文全文"
        assert d["author"] == "张三"
        assert d["url"] == "https://example.com/abc"
        assert d["category"] == "随笔"
        assert d["issue"] == "第1期"
        assert "created_at" in d

    def test_detail_404_for_nonexistent(self, client):
        r = client.get("/api/articles/999999")
        assert r.status_code == 404


class TestAggregations:
    def test_issues_grouped_by_year_month(self, client, db_session):
        _add(db_session, title="a", year=2024, month=1, issue="第1期")
        _add(db_session, title="b", year=2024, month=1, issue="第1期")
        _add(db_session, title="c", year=2024, month=2, issue="第2期")
        _add(db_session, title="d", year=2023, month=12, issue=None)
        r = client.get("/api/articles/issues")
        assert r.status_code == 200
        issues = r.json()
        assert {"year": 2024, "month": 1, "issue": "第1期"} in issues
        assert {"year": 2024, "month": 2, "issue": "第2期"} in issues
        assert issues[0]["year"] >= issues[-1]["year"]

    def test_categories_distinct(self, client, db_session):
        _add(db_session, title="a", category="科技", year=2024, month=1)
        _add(db_session, title="b", category="科技", year=2024, month=1)
        _add(db_session, title="c", category="生活", year=2024, month=1)
        _add(db_session, title="d", category=None, year=2024, month=1)
        r = client.get("/api/articles/categories")
        cats = r.json()
        assert "科技" in cats
        assert "生活" in cats
        assert None not in cats


class TestHistoricalCompatibility:
    """旧版本数据缺少可选字段时，API 不应崩溃。"""

    def test_article_without_url_or_author_or_category(self, client, db_session):
        art = _add(db_session, title="旧文章", content="旧内容", year=2020, month=3)
        r_list = client.get("/api/articles", params={"year": 2020, "month": 3})
        assert r_list.status_code == 200
        assert r_list.json()["total"] == 1
        r = client.get(f"/api/articles/{art.id}")
        assert r.status_code == 200
        d = r.json()
        assert d["author"] is None
        assert d["category"] is None
        assert d["url"] is None

    def test_seed_endpoint_still_works(self, client):
        """seed 端点是历史测试数据入口，必须保持可用。"""
        r = client.post("/api/articles/seed")
        assert r.status_code == 200
        assert "message" in r.json()
        lst = client.get("/api/articles").json()
        assert lst["total"] >= 8


class TestDelete:
    def test_delete_existing(self, client, db_session):
        a = _add(db_session, title="del", year=2024, month=1)
        r = client.delete(f"/api/articles/{a.id}")
        assert r.status_code == 200
        assert client.get(f"/api/articles/{a.id}").status_code == 404

    def test_delete_nonexistent(self, client):
        r = client.delete("/api/articles/999999")
        assert r.status_code == 404
