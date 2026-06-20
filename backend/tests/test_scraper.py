import pytest
import respx
from pathlib import Path
from bs4 import BeautifulSoup

from app.services.scraper import ArticleScraper, NetworkError, ParseError


class TestScraperURLBuilding:
    def test_build_list_url_basic(self, sample_source_config, temp_articles_dir):
        scraper = ArticleScraper(sample_source_config, str(temp_articles_dir))
        url = scraper._build_list_url(2024, 1, None)
        assert url == "https://example.com/articles/2024/01"

    def test_build_list_url_pads_month(self, sample_source_config, temp_articles_dir):
        scraper = ArticleScraper(sample_source_config, str(temp_articles_dir))
        url = scraper._build_list_url(2024, 3, None)
        assert url.endswith("/03")

    def test_build_list_url_with_issue(self, sample_source_config, temp_articles_dir):
        config = {**sample_source_config, "list_pattern": "/{year}/{month}/{issue}"}
        scraper = ArticleScraper(config, str(temp_articles_dir))
        url = scraper._build_list_url(2024, 1, "第1期")
        assert url == "https://example.com/2024/01/第1期"


class TestScraperHTMLParsing:
    @pytest.mark.asyncio
    async def test_parse_list_normal(self, sample_source_config, temp_articles_dir, mock_list_html):
        scraper = ArticleScraper(sample_source_config, str(temp_articles_dir))
        with respx.mock:
            respx.get("https://example.com/articles/2024/01").respond(
                text=mock_list_html, status_code=200
            )
            urls = await scraper._get_article_list("https://example.com/articles/2024/01")
            assert len(urls) == 3
            assert urls[0] == "https://example.com/articles/2024/01/001"
            assert urls[2] == "https://example.com/articles/2024/01/003"

    @pytest.mark.asyncio
    async def test_parse_list_relative_urls_resolved(self, temp_articles_dir):
        html = '<html><body><div class="list"><a href="/a/1">Link 1</a><a href="b/2">Link 2</a></div></body></html>'
        config = {
            "name": "test",
            "base_url": "https://example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": ".list a",
            "title_selector": "h1",
            "content_selector": "article"
        }
        scraper = ArticleScraper(config, str(temp_articles_dir))
        with respx.mock:
            respx.get("https://example.com/list").respond(text=html, status_code=200)
            urls = await scraper._get_article_list("https://example.com/list")
            assert len(urls) == 2
            assert urls[0] == "https://example.com/a/1"
            assert urls[1] == "https://example.com/b/2"

    @pytest.mark.asyncio
    async def test_parse_list_selector_changed_structure(self, temp_articles_dir):
        """站点改版：class名变化导致选择器不匹配，应优雅处理而非崩溃"""
        changed_html = '<html><body><div class="new-list"><a href="/a/1">A</a></div></body></html>'
        config = {
            "name": "test",
            "base_url": "https://example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": ".article-item a",
            "title_selector": "h1",
            "content_selector": "article"
        }
        scraper = ArticleScraper(config, str(temp_articles_dir))
        with respx.mock:
            respx.get("https://example.com/2024/01").respond(text=changed_html, status_code=200)
            urls = await scraper._get_article_list("https://example.com/2024/01")
            assert urls == []

    @pytest.mark.asyncio
    async def test_parse_article_full(self, sample_source_config, temp_articles_dir, mock_article_html):
        html = mock_article_html("标题A", "作者A", "内容A", "分类A")
        scraper = ArticleScraper(sample_source_config, str(temp_articles_dir))
        with respx.mock:
            respx.get("https://example.com/a/1").respond(text=html, status_code=200)
            article = await scraper._fetch_article(
                "https://example.com/a/1", 2024, 1, "第1期"
            )
            assert article["title"] == "标题A"
            assert article["author"] == "作者A"
            assert "内容A" in article["content"]
            assert article["category"] == "分类A"
            assert article["year"] == 2024
            assert article["month"] == 1

    @pytest.mark.asyncio
    async def test_parse_article_missing_optional_fields(self, temp_articles_dir):
        """站点改版：作者、分类字段缺失时不崩溃，返回None"""
        html = '<html><body><h1 class="title">标题</h1><div class="content">正文</div></body></html>'
        config = {
            "name": "test",
            "base_url": "https://example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1.title",
            "content_selector": ".content",
            "author_selector": ".author",
            "category_selector": ".category"
        }
        scraper = ArticleScraper(config, str(temp_articles_dir))
        with respx.mock:
            respx.get("https://example.com/a/1").respond(text=html, status_code=200)
            article = await scraper._fetch_article("https://example.com/a/1", 2024, 1, None)
            assert article["title"] == "标题"
            assert article["author"] is None
            assert article["category"] is None

    @pytest.mark.asyncio
    async def test_parse_article_title_missing_fallback(self, temp_articles_dir):
        """标题选择器完全不匹配时，用默认值而不是抛异常"""
        html = '<html><body><div>No H1 here</div><div class="content">正文</div></body></html>'
        config = {
            "name": "test",
            "base_url": "https://example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1.not-exist",
            "content_selector": ".content"
        }
        scraper = ArticleScraper(config, str(temp_articles_dir))
        with respx.mock:
            respx.get("https://example.com/a/1").respond(text=html, status_code=200)
            article = await scraper._fetch_article("https://example.com/a/1", 2024, 1, None)
            assert article["title"] == "未知标题"
            assert article["content"] == "正文"


class TestScraperNetworkErrors:
    @pytest.mark.asyncio
    async def test_timeout_raises_network_error(self, sample_source_config, temp_articles_dir):
        import httpx
        scraper = ArticleScraper(sample_source_config, str(temp_articles_dir))
        with respx.mock:
            respx.get("https://example.com/2024/01").mock(
                side_effect=httpx.TimeoutException("timeout")
            )
            with pytest.raises(NetworkError, match="超时"):
                await scraper._get_article_list("https://example.com/2024/01")

    @pytest.mark.asyncio
    async def test_404_raises_network_error(self, sample_source_config, temp_articles_dir):
        scraper = ArticleScraper(sample_source_config, str(temp_articles_dir))
        with respx.mock:
            respx.get("https://example.com/2024/01").respond(status_code=404)
            with pytest.raises(NetworkError, match="404"):
                await scraper._get_article_list("https://example.com/2024/01")

    @pytest.mark.asyncio
    async def test_500_raises_network_error(self, sample_source_config, temp_articles_dir):
        scraper = ArticleScraper(sample_source_config, str(temp_articles_dir))
        with respx.mock:
            respx.get("https://example.com/a/1").respond(status_code=500)
            with pytest.raises(NetworkError, match="500"):
                await scraper._fetch_article("https://example.com/a/1", 2024, 1, None)

    @pytest.mark.asyncio
    async def test_partial_failure_continues(self, temp_articles_dir):
        """一篇文章抓取失败不影响其他文章，整体流程不中断"""
        list_html = """
        <html><body>
            <div class="article-item"><a href="/ok1">OK1</a></div>
            <div class="article-item"><a href="/fail">FAIL</a></div>
            <div class="article-item"><a href="/ok2">OK2</a></div>
        </body></html>
        """
        ok_html = """<html><body><h1 class="title">__TITLE__</h1><div class="content">ok</div></body></html>"""
        config = {
            "name": "test",
            "base_url": "https://example.com",
            "list_pattern": "/articles/{year}/{month}",
            "article_selector": ".article-item a",
            "title_selector": "h1.title",
            "content_selector": ".content"
        }
        scraper = ArticleScraper(config, str(temp_articles_dir))
        with respx.mock:
            respx.get("https://example.com/articles/2024/01").respond(text=list_html)
            respx.get("https://example.com/ok1").respond(text=ok_html.replace("__TITLE__", "OK1"))
            respx.get("https://example.com/fail").respond(status_code=500)
            respx.get("https://example.com/ok2").respond(text=ok_html.replace("__TITLE__", "OK2"))
            articles = await scraper.crawl(2024, 1, None)
            assert len(articles) == 2
            titles = {a["title"] for a in articles}
            assert "OK1" in titles
            assert "OK2" in titles


class TestScraperFileSaving:
    def test_save_article_creates_directory_structure(self, sample_source_config, temp_articles_dir):
        scraper = ArticleScraper(sample_source_config, str(temp_articles_dir))
        path = scraper._save_article("测试标题", "内容", 2024, 3)
        assert path.exists()
        assert "2024" in str(path)
        assert "03" in str(path)
        assert path.suffix == ".txt"
        saved_content = path.read_text(encoding="utf-8")
        assert "测试标题" in saved_content
        assert "内容" in saved_content

    def test_save_article_sanitizes_filename(self, sample_source_config, temp_articles_dir):
        scraper = ArticleScraper(sample_source_config, str(temp_articles_dir))
        path = scraper._save_article('标题/含:特殊*字符?"<>|', "内容", 2024, 1)
        for ch in '/:*?"<>|':
            assert ch not in path.name


class TestScraperStructureVariants:
    """防御性测试：即使选择器部分匹配也能容错"""

    @pytest.mark.asyncio
    async def test_content_selector_partial_match(self, temp_articles_dir):
        html = """
        <html><body>
            <h1 class="title-main">  文章标题  </h1>
            <article class="post-body">文章正文内容</article>
        </body></html>
        """
        config = {
            "name": "test",
            "base_url": "https://example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1.title-main",
            "content_selector": "article.post-body"
        }
        scraper = ArticleScraper(config, str(temp_articles_dir))
        with respx.mock:
            respx.get("https://example.com/a/1").respond(text=html)
            article = await scraper._fetch_article("https://example.com/a/1", 2024, 1, None)
            assert article["title"] == "文章标题"
            assert "文章正文内容" in article["content"]

    @pytest.mark.asyncio
    async def test_extra_whitespace_stripped(self, temp_articles_dir):
        html = """
        <html><body>
            <h1 class="title">  带空格的标题  </h1>
            <div class="author">  作者名  </div>
            <div class="content">  正文  </div>
        </body></html>
        """
        config = {
            "name": "test",
            "base_url": "https://example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1.title",
            "content_selector": ".content",
            "author_selector": ".author"
        }
        scraper = ArticleScraper(config, str(temp_articles_dir))
        with respx.mock:
            respx.get("https://example.com/a/1").respond(text=html)
            article = await scraper._fetch_article("https://example.com/a/1", 2024, 1, None)
            assert article["title"] == "带空格的标题"
            assert article["author"] == "作者名"
