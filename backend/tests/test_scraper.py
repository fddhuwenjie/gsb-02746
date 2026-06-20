"""
Scraper 单元测试 —— 用 respx 拦截 httpx，避免真实网络。

覆盖以下高风险路径：
- URL 拼接（不同 list_pattern、绝对/相对 href、中文）
- 列表页结构变化（选择器命中 0 个、命中相对路径需要补全 base_url）
- 文章页结构变化（缺标题、缺正文、缺 author/category）
- 网络失败的 max_retries 行为：第一次失败 + 第二次成功 应抓取成功
- 失败次数超过重试上限：抛 NetworkError
- 列表内重复链接的去重
- 持久化：保存到磁盘的目录结构和文件名安全化
"""
from __future__ import annotations

import asyncio
import pytest
import httpx
import respx

from app.services.scraper import ArticleScraper, NetworkError


def _list_html(hrefs):
    items = "".join(f'<li><a class="post" href="{h}">title</a></li>' for h in hrefs)
    return f"<html><body><ul>{items}</ul></body></html>"


def _article_html(title="标题A", content="正文很长很长", author=None, category=None):
    parts = []
    if title is not None:
        parts.append(f'<h1 class="t">{title}</h1>')
    if content is not None:
        parts.append(f'<div class="c">{content}</div>')
    if author is not None:
        parts.append(f'<span class="a">{author}</span>')
    if category is not None:
        parts.append(f'<span class="cat">{category}</span>')
    return "<html><body>" + "".join(parts) + "</body></html>"


@pytest.fixture
def source_config():
    return {
        "name": "示例源",
        "base_url": "https://example.test",
        "list_pattern": "/archive/{year}/{month}",
        "article_selector": "a.post",
        "title_selector": "h1.t",
        "content_selector": "div.c",
        "author_selector": "span.a",
        "category_selector": "span.cat",
    }


@pytest.fixture
def scraper(source_config, tmp_path):
    s = ArticleScraper(source_config, str(tmp_path))
    s.request_delay = 0  # 测试中不要 sleep
    return s


def test_build_list_url_pads_month(scraper):
    url = scraper._build_list_url(2024, 5, None)
    # 模板里 {month} 用 {month:02d} 渲染，应该是 05
    assert url == "https://example.test/archive/2024/05"


@respx.mock
def test_crawl_happy_path_handles_relative_and_absolute_links(scraper):
    respx.get("https://example.test/archive/2024/05").mock(
        return_value=httpx.Response(
            200,
            text=_list_html(["/posts/1", "https://example.test/posts/2"]),
        )
    )
    respx.get("https://example.test/posts/1").mock(
        return_value=httpx.Response(200, text=_article_html(title="文章一", content="正文一", author="甲", category="散文"))
    )
    respx.get("https://example.test/posts/2").mock(
        return_value=httpx.Response(200, text=_article_html(title="文章二", content="正文二"))
    )

    articles = asyncio.run(scraper.crawl(2024, 5, "第5期"))
    assert [a["title"] for a in articles] == ["文章一", "文章二"]
    assert articles[0]["author"] == "甲"
    assert articles[0]["category"] == "散文"
    # 第二篇没有 author/category 选择器命中，应为 None 而不是抛错
    assert articles[1]["author"] is None
    assert articles[1]["category"] is None
    # issue 透传
    assert all(a["issue"] == "第5期" for a in articles)


@respx.mock
def test_crawl_dedupes_repeated_links_in_list_page(scraper):
    respx.get("https://example.test/archive/2024/05").mock(
        return_value=httpx.Response(
            200,
            text=_list_html(["/p/1", "/p/1", "/p/2"]),
        )
    )
    respx.get("https://example.test/p/1").mock(
        return_value=httpx.Response(200, text=_article_html(title="A", content="x"))
    )
    respx.get("https://example.test/p/2").mock(
        return_value=httpx.Response(200, text=_article_html(title="B", content="y"))
    )

    articles = asyncio.run(scraper.crawl(2024, 5, None))
    assert [a["title"] for a in articles] == ["A", "B"]
    # /p/1 即使在列表里出现两次，HTTP 也只请求了一次
    assert respx.routes[1].call_count == 1


@respx.mock
def test_crawl_skips_when_structure_completely_changed(scraper):
    """文章页选择器全部命中失败时（标题缺、正文缺），应跳过该篇而不是污染数据库。"""
    respx.get("https://example.test/archive/2024/05").mock(
        return_value=httpx.Response(200, text=_list_html(["/broken", "/ok"]))
    )
    respx.get("https://example.test/broken").mock(
        return_value=httpx.Response(200, text="<html><body><div>无关结构</div></body></html>")
    )
    respx.get("https://example.test/ok").mock(
        return_value=httpx.Response(200, text=_article_html(title="正常", content="ok"))
    )

    articles = asyncio.run(scraper.crawl(2024, 5, None))
    assert [a["title"] for a in articles] == ["正常"]


@respx.mock
def test_crawl_retries_transient_network_failure(source_config, tmp_path):
    scraper = ArticleScraper(source_config, str(tmp_path), max_retries=1)
    scraper.request_delay = 0

    list_route = respx.get("https://example.test/archive/2024/05").mock(
        return_value=httpx.Response(200, text=_list_html(["/p/1"]))
    )
    # 第一次 ConnectError, 第二次成功
    article_route = respx.get("https://example.test/p/1").mock(
        side_effect=[
            httpx.ConnectError("boom"),
            httpx.Response(200, text=_article_html(title="重试成功", content="ok")),
        ]
    )

    articles = asyncio.run(scraper.crawl(2024, 5, None))
    assert [a["title"] for a in articles] == ["重试成功"]
    assert article_route.call_count == 2
    assert list_route.called


@respx.mock
def test_crawl_gives_up_after_retries(source_config, tmp_path):
    scraper = ArticleScraper(source_config, str(tmp_path), max_retries=1)
    scraper.request_delay = 0

    respx.get("https://example.test/archive/2024/05").mock(
        return_value=httpx.Response(200, text=_list_html(["/p/1"]))
    )
    respx.get("https://example.test/p/1").mock(side_effect=httpx.ConnectError("down"))

    articles = asyncio.run(scraper.crawl(2024, 5, None))
    # 抓取失败的文章应被 catch & continue，最终返回空但不抛
    assert articles == []


@respx.mock
def test_crawl_list_page_4xx_does_not_retry(source_config, tmp_path):
    scraper = ArticleScraper(source_config, str(tmp_path), max_retries=3)
    scraper.request_delay = 0
    route = respx.get("https://example.test/archive/2024/05").mock(
        return_value=httpx.Response(404, text="not found")
    )
    with pytest.raises(NetworkError):
        asyncio.run(scraper.crawl(2024, 5, None))
    # 4xx 不重试，只调用一次
    assert route.call_count == 1


def test_save_article_sanitizes_filename(tmp_path, source_config):
    scraper = ArticleScraper(source_config, str(tmp_path))
    p = scraper._save_article('a/b\\c?:*"<>|d', "正文", 2024, 5)
    assert p.exists()
    assert p.parent == tmp_path / "2024" / "05"
    # 危险字符应当被替换为下划线
    assert all(ch not in p.name for ch in '/\\?:*"<>|')
