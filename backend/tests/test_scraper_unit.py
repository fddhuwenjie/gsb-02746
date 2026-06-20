"""
L1 unit tests — Scraper parsing / URL building / fault tolerance.

These tests hit ArticleScraper directly (no FastAPI, no DB) with a fake HTTP
client. They protect the most fragile real-world contract: *the source site's
HTML structure drifts over time*. Each failure mode here is a bug a maintainer
will actually ship some day.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.services.scraper import (
    ArticleScraper,
    NetworkError,
    ParseError,
)


BASE_SOURCE = {
    "name": "测试期刊",
    "base_url": "https://example.com",
    "list_pattern": "/archive/{year}/{month}",
    "article_selector": ".article-list a",
    "title_selector": "h1.title",
    "content_selector": "div.body",
    "author_selector": ".author",
    "category_selector": ".cat",
}


class TestUrlBuilding:
    """URL pattern expansion — pattern strings are user-editable config."""

    def test_basic_year_month(self, tmp_path):
        s = ArticleScraper(BASE_SOURCE, str(tmp_path))
        # scraper pads month with f"{month:02d}" before format
        assert s._build_list_url(2024, 3, None) == "https://example.com/archive/2024/03"

    def test_month_zero_padded(self, tmp_path):
        s = ArticleScraper(BASE_SOURCE, str(tmp_path))
        assert s._build_list_url(2024, 11, None).endswith("/11")
        assert s._build_list_url(2024, 1, None).endswith("/01")

    def test_issue_interpolated_when_present(self, tmp_path):
        src = {**BASE_SOURCE, "list_pattern": "/{year}/{issue}"}
        s = ArticleScraper(src, str(tmp_path))
        url = s._build_list_url(2024, 1, "no12")
        assert url == "https://example.com/2024/no12"

    def test_missing_pattern_defaults(self, tmp_path):
        """If user deletes list_pattern in config, fall back to /{year}/{month}."""
        src = {**BASE_SOURCE}
        src.pop("list_pattern")
        s = ArticleScraper(src, str(tmp_path))
        url = s._build_list_url(2024, 5, None)
        assert url == "https://example.com/{year}/{month}".format(year=2024, month="05")
        # (default pattern is "/{year}/{month}" — uses month:02d via format)


class TestArticleListParsing:
    """List-page parsing — selectors change often when sites redesign."""

    @pytest.mark.asyncio
    async def test_happy_path_extracts_links(self, tmp_path, fake_http_factory, monkeypatch):
        html = """
        <html><body>
          <ul class="article-list">
            <li><a href="/article/1">一</a></li>
            <li><a href="https://example.com/article/2">二</a></li>
          </ul>
        </body></html>
        """
        fake = fake_http_factory({"https://example.com/archive/2024/01": html})
        s = ArticleScraper(BASE_SOURCE, str(tmp_path))
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake.client_cls)
        urls = await s._get_article_list("https://example.com/archive/2024/01")
        assert urls == [
            "https://example.com/article/1",
            "https://example.com/article/2",
        ]

    @pytest.mark.asyncio
    async def test_selector_returns_nothing_yields_empty(self, tmp_path, fake_http_factory, monkeypatch):
        """Site redesign: selector no longer matches anything. Must not crash."""
        html = "<html><body><div class='new-list'><a href='/x'>x</a></div></body></html>"
        fake = fake_http_factory({"https://example.com/archive/2024/01": html})
        s = ArticleScraper(BASE_SOURCE, str(tmp_path))
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake.client_cls)
        urls = await s._get_article_list("https://example.com/archive/2024/01")
        assert urls == []

    @pytest.mark.asyncio
    async def test_links_without_href_are_skipped(self, tmp_path, fake_http_factory, monkeypatch):
        html = """
        <div class="article-list">
          <a name="anchor"></a>
          <a href="/ok">ok</a>
          <a>missing href</a>
        </div>
        """
        fake = fake_http_factory({"https://example.com/archive/2024/01": html})
        s = ArticleScraper(BASE_SOURCE, str(tmp_path))
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake.client_cls)
        urls = await s._get_article_list("https://example.com/archive/2024/01")
        assert urls == ["https://example.com/ok"]


class TestArticleFetchParsing:
    """Detail-page parsing — selector drift / missing fields."""

    DETAIL_HTML = """
    <html><body>
      <h1 class="title">测试标题</h1>
      <div class="author">张三</div>
      <div class="cat">散文</div>
      <div class="body">这是正文。</div>
    </body></html>
    """

    @pytest.mark.asyncio
    async def test_happy_path_parses_all_fields(self, tmp_path, fake_http_factory, monkeypatch):
        fake = fake_http_factory({"https://example.com/a/1": self.DETAIL_HTML})
        s = ArticleScraper(BASE_SOURCE, str(tmp_path))
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake.client_cls)
        art = await s._fetch_article("https://example.com/a/1", 2024, 1, None)
        assert art["title"] == "测试标题"
        assert art["author"] == "张三"
        assert art["category"] == "散文"
        assert "这是正文" in art["content"]
        assert art["url"] == "https://example.com/a/1"
        assert art["year"] == 2024 and art["month"] == 1

    @pytest.mark.asyncio
    async def test_missing_title_falls_back_to_unknown(self, tmp_path, fake_http_factory, monkeypatch):
        """Site renamed h1.title → h1.headline AND .body → .post — must not crash."""
        html = "<html><body><h1 class='headline'>真实标题</h1><div class='post'>正文</div></body></html>"
        fake = fake_http_factory({"https://example.com/a/1": html})
        s = ArticleScraper(BASE_SOURCE, str(tmp_path))
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake.client_cls)
        art = await s._fetch_article("https://example.com/a/1", 2024, 1, None)
        assert art["title"] == "未知标题"  # title selector didn't match
        assert art["content"] == ""       # content selector didn't match

    @pytest.mark.asyncio
    async def test_optional_selectors_absent_do_not_crash(self, tmp_path, fake_http_factory, monkeypatch):
        """author/category_selector not configured — values become None."""
        src = {**BASE_SOURCE}
        src.pop("author_selector")
        src.pop("category_selector")
        html = "<html><body><h1 class='title'>T</h1><div class='body'>C</div></body></html>"
        fake = fake_http_factory({"https://example.com/a/1": html})
        s = ArticleScraper(src, str(tmp_path))
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake.client_cls)
        art = await s._fetch_article("https://example.com/a/1", 2024, 1, None)
        assert art["author"] is None
        assert art["category"] is None
        assert art["title"] == "T"

    @pytest.mark.asyncio
    async def test_file_saved_to_year_month_dir(self, tmp_path, fake_http_factory, monkeypatch):
        fake = fake_http_factory({"https://example.com/a/1": self.DETAIL_HTML})
        save_dir = tmp_path / "arts"
        s = ArticleScraper(BASE_SOURCE, str(save_dir))
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake.client_cls)
        art = await s._fetch_article("https://example.com/a/1", 2024, 3, None)
        fp = Path(art["file_path"])
        assert fp.parent == save_dir / "2024" / "03"
        assert fp.exists()
        assert "测试标题" in fp.read_text(encoding="utf-8")


class TestNetworkFaults:
    """Network-level failures must raise typed ScraperError, not raw httpx."""

    @pytest.mark.asyncio
    async def test_timeout_raises_network_error(self, tmp_path, fake_http_factory, monkeypatch):
        fake = fake_http_factory({
            "https://example.com/archive/2024/01": httpx.TimeoutException("slow"),
        })
        s = ArticleScraper(BASE_SOURCE, str(tmp_path))
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake.client_cls)
        with pytest.raises(NetworkError, match="超时"):
            await s._get_article_list("https://example.com/archive/2024/01")

    @pytest.mark.asyncio
    async def test_http_500_raises_network_error(self, tmp_path, fake_http_factory, monkeypatch):
        fake = fake_http_factory({
            "https://example.com/archive/2024/01": ("server exploded", 500),
        })
        s = ArticleScraper(BASE_SOURCE, str(tmp_path))
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake.client_cls)
        with pytest.raises(NetworkError, match="500"):
            await s._get_article_list("https://example.com/archive/2024/01")

    @pytest.mark.asyncio
    async def test_single_article_failure_does_not_abort_whole_crawl(
        self, tmp_path, fake_http_factory, monkeypatch
    ):
        """If one article URL fails, we still return the others — partial > nothing."""
        list_html = """
        <div class="article-list">
          <a href="/a/1">one</a>
          <a href="/a/2">two</a>
          <a href="/a/3">three</a>
        </div>
        """
        ok_detail = "<html><body><h1 class='title'>T</h1><div class='body'>C</div></body></html>"
        fake = fake_http_factory({
            "https://example.com/archive/2024/01": list_html,
            "https://example.com/a/1": ok_detail,
            "https://example.com/a/2": httpx.TimeoutException("dead"),
            "https://example.com/a/3": ok_detail,
        })
        # patch sleep to speed up
        monkeypatch.setattr("app.services.scraper.asyncio.sleep", lambda *_: None)
        s = ArticleScraper(BASE_SOURCE, str(tmp_path))
        monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", fake.client_cls)
        results = await s.crawl(2024, 1, None)
        titles = [r["title"] for r in results]
        assert titles.count("T") == 2  # one timed out, skipped


class TestFilenameSanitization:
    def test_unsafe_chars_replaced(self, tmp_path):
        s = ArticleScraper(BASE_SOURCE, str(tmp_path))
        fp = s._save_article('a/b:c*d?e"f<g>h|i', "正文", 2024, 1)
        assert "/" not in fp.name
        assert ":" not in fp.name
        assert "*" not in fp.name

    def test_long_title_truncated(self, tmp_path):
        s = ArticleScraper(BASE_SOURCE, str(tmp_path))
        long_title = "字" * 500
        fp = s._save_article(long_title, "正文", 2024, 1)
        # safe_title[:50] + ".txt"
        stem = fp.stem
        assert len(stem) <= 50
