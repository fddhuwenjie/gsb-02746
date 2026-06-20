"""
L4 front-end / back-end contract tests.

Rather than drive a browser, these tests encode EVERY field the Vue front-end
reads from each API response, and assert:
  - the field exists on every returned object,
  - its type matches what the component expects (e.g. string not null when
    the component does `.substring(0,120)` on it),
  - ordering/pagination semantics the UI relies on.

Why this layer matters: a backend refactor can rename `article.content` to
`article.body`, every unit test in the world still passes, but the UI shows
blank pages. These tests fail at exactly that moment — and they run in ~1s.

To maintain: if you change what a Vue component accesses, update this file.
"""
from __future__ import annotations


class TestHomeViewContract:
    """
    Home.vue (list page) consumes:
      - data.items[]: id, title, author, content, source, issue, year, month,
        category, created_at
      - data.total, data.page, data.page_size
      - /issues -> [{year, month, issue}]
      - Optionally calls .substring(0, 120) on content
    """

    LIST_FIELDS = {
        "id": int,
        "title": str,
        "author": (str, type(None)),
        "content": (str, type(None)),
        "source": (str, type(None)),
        "issue": (str, type(None)),
        "year": (int, type(None)),
        "month": (int, type(None)),
        "category": (str, type(None)),
        "created_at": str,
    }

    def test_list_response_shape_matches_home_view(self, client):
        client.post("/api/crawler/mock")
        r = client.get("/api/articles")
        assert r.status_code == 200
        data = r.json()

        # Top-level envelope
        for k in ("items", "total", "page", "page_size"):
            assert k in data, f"Home.vue expects response.{k}"

        for art in data["items"]:
            for field, expected_type in self.LIST_FIELDS.items():
                assert field in art, f"Home.vue reads article.{field} but it's missing"
                assert isinstance(art[field], expected_type), (
                    f"article.{field} type mismatch: got {type(art[field])}, "
                    f"expected {expected_type}"
                )

    def test_content_is_string_when_present_substring_safe(self, client):
        """
        Home.vue does `article.content.substring(0,120)`. That only works when
        content is a string (None.substring crashes). The API must always return
        a string for content (empty string is acceptable).
        """
        client.post("/api/crawler/mock")
        for art in client.get("/api/articles").json()["items"]:
            # content is Optional[str] in backend, but Vue calls .substring
            # We lock this down: content must be str when accessed by list view.
            assert isinstance(art["content"], str), (
                f"article.content must be str for Home.vue, got {type(art['content'])}"
            )
            # substring should not throw
            _ = art["content"][:120]

    def test_list_sorted_by_created_at_desc(self, client):
        """Timeline/card views assume newest-first ordering."""
        client.post("/api/articles/seed")
        items = client.get("/api/articles").json()["items"]
        ids_in_order = [a["id"] for a in items]
        # Seed inserts in order; newest should come first because of `desc(created_at)`.
        assert ids_in_order == sorted(ids_in_order, reverse=True)

    def test_issues_response_shape(self, client):
        client.post("/api/articles/seed")
        r = client.get("/api/articles/issues")
        assert r.status_code == 200
        for issue in r.json():
            assert "year" in issue and isinstance(issue["year"], (int, type(None)))
            assert "month" in issue
            assert "issue" in issue


class TestArticleViewContract:
    """
    Article.vue (detail page) reads:
      - id, title, author, content, source, year, month, issue, category, file_path
    And does:
      - article.content (passed to navigator.clipboard.writeText)
      - article.author[0] when author is present (avatar)
      - article.title (no special guard besides v-else-if article)
    """

    DETAIL_FIELDS = {
        "id": int,
        "title": str,
        "author": (str, type(None)),
        "content": (str, type(None)),
        "source": (str, type(None)),
        "year": (int, type(None)),
        "month": (int, type(None)),
        "issue": (str, type(None)),
        "category": (str, type(None)),
        "file_path": (str, type(None)),
    }

    def test_detail_response_shape_matches_article_view(self, client):
        client.post("/api/crawler/mock")
        art_id = client.get("/api/articles").json()["items"][0]["id"]
        r = client.get(f"/api/articles/{art_id}")
        assert r.status_code == 200
        art = r.json()
        for field, expected_type in self.DETAIL_FIELDS.items():
            assert field in art, f"Article.vue reads article.{field} but it's missing"
            assert isinstance(art[field], expected_type), (
                f"article.{field} type mismatch: got {type(art[field])}"
            )

    def test_clipboard_copy_works_on_content(self, client):
        """Copy button calls navigator.clipboard.writeText(article.content).
        Content must be str (or at least not None) for that to succeed."""
        client.post("/api/crawler/mock")
        art_id = client.get("/api/articles").json()["items"][0]["id"]
        art = client.get(f"/api/articles/{art_id}").json()
        assert isinstance(art["content"], str)
        assert len(art["content"]) > 0

    def test_detail_missing_returns_404_with_detail_field(self, client):
        """Front-end shows `e.response?.data?.detail` for errors; that field must exist."""
        r = client.get("/api/articles/9999999")
        assert r.status_code == 404
        assert "detail" in r.json()


class TestSettingsViewContract:
    """
    Settings.vue reads: articles_path, sources_config.
    On update failure it reads e.response.data.detail.
    """

    def test_get_settings_shape(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 200
        s = r.json()
        assert "articles_path" in s and isinstance(s["articles_path"], str)
        assert "sources_config" in s and isinstance(s["sources_config"], str)

    def test_put_settings_success_shape(self, client):
        r = client.put("/api/settings", json={"articles_path": "./data/articles_test2"})
        assert r.status_code == 200
        body = r.json()
        # Front-end uses `success` flag in some flows; assert presence
        assert "success" in body
        assert body["success"] is True


class TestCrawlerViewContract:
    """
    Crawler.vue reads from:
      - POST /crawler/mock:        success, message, articles_count
      - POST /articles/seed:       message
      - GET  /crawler/status:      status, message, articles_count
      - GET  /crawler/sources:     {sources: [...]}
      - POST /crawler/start:       (expects {message: ...} or 400/422 with detail)
    """

    def test_mock_response_has_all_three_fields(self, client):
        r = client.post("/api/crawler/mock")
        body = r.json()
        assert "success" in body
        assert "message" in body
        assert "articles_count" in body
        assert isinstance(body["articles_count"], int)

    def test_status_response_fields(self, client):
        client.post("/api/crawler/mock")
        r = client.get("/api/crawler/status")
        body = r.json()
        for k in ("status", "message", "articles_count"):
            assert k in body, f"Crawler.vue polls status.{k}"
        assert body["status"] in ("idle", "running", "completed", "error")

    def test_sources_response_has_sources_array(self, client):
        r = client.get("/api/crawler/sources")
        body = r.json()
        assert "sources" in body
        assert isinstance(body["sources"], list)

    def test_start_crawl_error_includes_detail(self, client):
        from app.api import crawler as cm
        cm.crawl_status = {"status": "running", "message": "x", "articles_count": 0}
        r = client.post("/api/crawler/start", json={"year": 2024, "month": 1})
        assert r.status_code == 400
        assert "detail" in r.json()
        cm.crawl_status = {"status": "idle", "message": "", "articles_count": 0}


class TestFrontendFilterConsistency:
    """
    Home.vue sends year and month as STRING values from <select>, not ints.
    FastAPI's Query(int) will coerce valid numeric strings to int, but if we
    ever send "" (empty string for "all") FastAPI must NOT error.
    This is a classic real-world bug: backend assumes int, frontend sends ''.
    """

    def test_empty_string_year_means_no_filter(self, client):
        client.post("/api/crawler/mock")
        # Vue sends '' for "全部年份"
        r = client.get("/api/articles", params={"year": "", "month": ""})
        assert r.status_code == 200
        assert r.json()["total"] >= 3  # the 3 mock articles

    def test_numeric_string_year_is_coerced(self, client):
        client.post("/api/articles/seed")
        r = client.get("/api/articles", params={"year": "2024"})
        assert r.status_code == 200
        assert r.json()["total"] == 8

    def test_search_empty_string_returns_all(self, client):
        """When search input is cleared, frontend sends '' not undefined."""
        client.post("/api/crawler/mock")
        r = client.get("/api/articles", params={"search": ""})
        assert r.status_code == 200
        assert r.json()["total"] >= 3
