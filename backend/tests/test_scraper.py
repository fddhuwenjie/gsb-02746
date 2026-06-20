"""Scraper 单元测试：纯逻辑测试，无任何网络依赖，验证解析健壮性、重试、容错。"""
import pytest
import asyncio
import httpx
from pathlib import Path
from unittest.mock import AsyncMock

from app.services.scraper import ArticleScraper, NetworkError, ParseError


def make_source(**overrides):
    base = {
        "name": "测试站点",
        "base_url": "https://example.com",
        "list_pattern": "/archive/{year}/{month}",
        "article_selector": ".list a.article-link",
        "title_selector": "h1.title",
        "content_selector": ".article-body",
        "author_selector": ".author",
        "category_selector": ".cat",
    }
    base.update(overrides)
    return base


class TestUrlBuilding:
    def test_build_list_url_with_default_pattern(self, tmp_path):
        src = {"name": "x", "base_url": "https://x.com"}
        s = ArticleScraper(src, str(tmp_path), client_factory=lambda **kw: _NullClient(),
                           sleep_between_articles=0)
        url = s._build_list_url(2024, 3, None)
        assert url == "https://x.com/2024/03"

    def test_build_list_url_with_issue(self, tmp_path):
        src = make_source(list_pattern="/{year}/{month}/{issue}")
        s = ArticleScraper(src, str(tmp_path), client_factory=lambda **kw: _NullClient(),
                           sleep_between_articles=0)
        url = s._build_list_url(2024, 1, "第2期")
        assert url == "https://example.com/2024/01/第2期"

    def test_month_zero_padded(self, tmp_path):
        src = make_source()
        s = ArticleScraper(src, str(tmp_path), client_factory=lambda **kw: _NullClient(),
                           sleep_between_articles=0)
        assert s._build_list_url(2024, 9, None).endswith("/2024/09")
        assert s._build_list_url(2024, 11, None).endswith("/2024/11")


class _NullClient:
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def request(self, *a, **kw): raise AssertionError("no HTTP expected")


class _StubClient:
    def __init__(self, resp_map):
        self.resp_map = resp_map
        self.calls = []
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def request(self, method, url, **kw):
        self.calls.append(url)
        if url in self.resp_map:
            text = self.resp_map[url]
            return _FakeResp(text)
        return _FakeResp("", status=404)


class _FakeResp:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status
    def raise_for_status(self):
        if self.status_code >= 400:
            req = type("R", (), {"method": "GET", "url": "x"})()
            raise httpx.HTTPStatusError("x", request=req, response=self)


class TestListParsing:
    @pytest.mark.asyncio
    async def test_extracts_absolute_urls(self, tmp_path):
        html = '<html><body><div class="list"><a class="article-link" href="https://example.com/a1">a1</a><a class="article-link" href="https://example.com/a2">a2</a></div></body></html>'
        client = _StubClient({"https://example.com/archive/2024/01": html})
        s = ArticleScraper(make_source(), str(tmp_path), client_factory=lambda **kw: client,
                           sleep_between_articles=0)
        urls = await s._get_article_list(client, "https://example.com/archive/2024/01")
        assert urls == ["https://example.com/a1", "https://example.com/a2"]

    @pytest.mark.asyncio
    async def test_resolves_relative_and_root_urls(self, tmp_path):
        html = '<div class="list"><a class="article-link" href="/a/1">a</a><a class="article-link" href="a/2">b</a></div>'
        client = _StubClient({"L": html})
        s = ArticleScraper(make_source(), str(tmp_path), client_factory=lambda **kw: client,
                           sleep_between_articles=0)
        urls = await s._get_article_list(client, "L")
        assert urls[0] == "https://example.com/a/1"
        assert urls[1] == "https://example.com/a/2"

    @pytest.mark.asyncio
    async def test_filters_anchors_js_and_dedup(self, tmp_path):
        html = '''
        <div class="list">
        <a class="article-link" href="#top">x</a>
        <a class="article-link" href="javascript:void(0)">y</a>
        <a class="article-link" href="/a1">a</a>
        <a class="article-link" href="/a1">dup</a>
        <a class="article-link" href="/a2">b</a>
        </div>
        '''
        client = _StubClient({"L": html})
        s = ArticleScraper(make_source(), str(tmp_path), client_factory=lambda **kw: client,
                           sleep_between_articles=0)
        urls = await s._get_article_list(client, "L")
        assert urls == ["https://example.com/a1", "https://example.com/a2"]

    @pytest.mark.asyncio
    async def test_empty_list_when_selector_matches_nothing(self, tmp_path):
        html = "<html><body><p>改版了，没有文章列表</p></body></html>"
        client = _StubClient({"L": html})
        s = ArticleScraper(make_source(), str(tmp_path), client_factory=lambda **kw: client,
                           sleep_between_articles=0)
        urls = await s._get_article_list(client, "L")
        assert urls == []


class TestArticleParsing:
    ARTICLE_HTML = '''
    <html><body>
      <h1 class="title">测试标题</h1>
      <div class="author">张三</div>
      <div class="cat">随笔</div>
      <div class="article-body"><p>第一段</p><p>第二段</p></div>
    </body></html>
    '''

    @pytest.mark.asyncio
    async def test_parses_all_fields(self, tmp_path):
        client = _StubClient({"L": "", "https://example.com/a1": self.ARTICLE_HTML})
        s = ArticleScraper(make_source(), str(tmp_path / "arts"),
                           client_factory=lambda **kw: client,
                           sleep_between_articles=0)
        art = await s._fetch_article(client, "https://example.com/a1", 2024, 5, "第3期")
        assert art["title"] == "测试标题"
        assert art["author"] == "张三"
        assert art["category"] == "随笔"
        assert "第一段" in art["content"]
        assert art["year"] == 2024
        assert art["month"] == 5
        assert art["issue"] == "第3期"
        assert art["source"] == "测试站点"
        assert art["url"] == "https://example.com/a1"

    @pytest.mark.asyncio
    async def test_degrades_gracefully_when_selectors_missing(self, tmp_path):
        """来源站点改版：标题/作者/分类选择器都不命中时不崩溃，使用降级值。"""
        html = "<html><body><p>改版了</p></body></html>"
        client = _StubClient({"https://example.com/a1": html})
        s = ArticleScraper(make_source(), str(tmp_path),
                           client_factory=lambda **kw: client,
                           sleep_between_articles=0)
        art = await s._fetch_article(client, "https://example.com/a1", 2024, 1, None)
        assert art["title"] == "未知标题"
        assert art["author"] is None
        assert art["category"] is None
        assert art["content"] == ""

    @pytest.mark.asyncio
    async def test_optional_selectors_can_be_omitted_from_config(self, tmp_path):
        src = {
            "name": "简化站",
            "base_url": "https://s.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": "article",
        }
        html = "<html><body><h1>标题</h1><article>正文</article></body></html>"
        client = _StubClient({"https://s.com/a1": html})
        s = ArticleScraper(src, str(tmp_path),
                           client_factory=lambda **kw: client,
                           sleep_between_articles=0)
        art = await s._fetch_article(client, "https://s.com/a1", 2024, 1, None)
        assert art["title"] == "标题"
        assert art["author"] is None
        assert art["category"] is None


class TestRetry:
    @pytest.mark.asyncio
    async def test_retries_on_5xx_then_succeeds(self, tmp_path):
        """5xx 错误应当触发重试，最终成功则正常返回。"""
        calls = {"n": 0}
        class FlakyClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def request(self, method, url, **kw):
                calls["n"] += 1
                if calls["n"] < 3:
                    resp = _FakeResp("", status=503)
                    resp.raise_for_status()
                return _FakeResp("<html><body></body></html>")
        s = ArticleScraper(make_source(), str(tmp_path),
                           client_factory=lambda **kw: FlakyClient(),
                           max_retries=2,
                           sleep_between_articles=0)
        async with FlakyClient() as c:
            resp = await s._request_with_retry(c, "GET", "http://x")
        assert resp.status_code == 200
        assert calls["n"] == 3

    @pytest.mark.asyncio
    async def test_4xx_does_not_retry(self, tmp_path):
        """4xx 是客户端错误，不应重试，快速失败。"""
        calls = {"n": 0}
        class Client404:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def request(self, method, url, **kw):
                calls["n"] += 1
                return _FakeResp("not found", status=404)
        s = ArticleScraper(make_source(), str(tmp_path),
                           client_factory=lambda **kw: Client404(),
                           max_retries=3,
                           sleep_between_articles=0)
        with pytest.raises(NetworkError):
            async with Client404() as c:
                await s._request_with_retry(c, "GET", "http://x")
        assert calls["n"] == 1

    @pytest.mark.asyncio
    async def test_exhausts_retries_and_raises(self, tmp_path):
        calls = {"n": 0}
        class Always500:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def request(self, method, url, **kw):
                calls["n"] += 1
                return _FakeResp("err", status=500)
        s = ArticleScraper(make_source(), str(tmp_path),
                           client_factory=lambda **kw: Always500(),
                           max_retries=2,
                           sleep_between_articles=0)
        with pytest.raises(NetworkError):
            async with Always500() as c:
                await s._request_with_retry(c, "GET", "http://x")
        assert calls["n"] == 3


class TestCrawlFlowTolerance:
    @pytest.mark.asyncio
    async def test_single_article_failure_does_not_break_batch(self, tmp_path):
        """某一篇文章抓取/解析失败时，其他文章仍应成功返回。"""
        list_html = '<div class="list"><a class="article-link" href="/a1">1</a><a class="article-link" href="/a2">2</a><a class="article-link" href="/a3">3</a></div>'
        ok = "<html><body><h1 class='title'>ok</h1><div class='article-body'>body</div></body></html>"
        class MixedClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def request(self, method, url, **kw):
                if "/archive/" in url:
                    return _FakeResp(list_html)
                if "/a2" in url:
                    raise httpx.TimeoutException("boom")
                return _FakeResp(ok)
        s = ArticleScraper(make_source(), str(tmp_path / "a"),
                           client_factory=lambda **kw: MixedClient(),
                           max_retries=0,
                           sleep_between_articles=0)
        articles = await s.crawl(2024, 1)
        assert len(articles) == 2
        titles = {a["title"] for a in articles}
        assert titles == {"ok"}


class TestFileSaving:
    def test_sanitizes_invalid_filename_chars(self, tmp_path):
        src = make_source()
        s = ArticleScraper(src, str(tmp_path), client_factory=lambda **kw: _NullClient(),
                           sleep_between_articles=0)
        fp = s._save_article('标题:带/非法\\字符*?"<>|', "正文", 2024, 3)
        assert ":" not in fp.name
        assert "/" not in fp.name
        assert "\\" not in fp.name
        assert fp.exists()
        assert fp.parent == tmp_path / "2024" / "03"
        assert "正文" in fp.read_text(encoding="utf-8")

    def test_creates_year_month_directory(self, tmp_path):
        s = ArticleScraper(make_source(), str(tmp_path), client_factory=lambda **kw: _NullClient(),
                           sleep_between_articles=0)
        fp = s._save_article("t", "c", 2022, 12)
        assert (tmp_path / "2022" / "12").is_dir()
