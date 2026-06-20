import httpx
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import asyncio
import re
import logging

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    pass


class NetworkError(ScraperError):
    pass


class ParseError(ScraperError):
    pass


def _default_client_factory(**kwargs):
    return httpx.AsyncClient(headers=kwargs.get("headers"),
                             timeout=kwargs.get("timeout", 30),
                             follow_redirects=True)


class ArticleScraper:
    def __init__(self, source_config: Dict[str, Any], save_path: str,
                 client_factory: Optional[Callable[..., httpx.AsyncClient]] = None,
                 max_retries: int = 2,
                 sleep_between_articles: float = 0.5):
        self.config = source_config
        self.save_path = Path(save_path)
        self.save_path.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self._client_factory = client_factory or _default_client_factory
        self.max_retries = max_retries
        self._sleep_between = sleep_between_articles
        logger.info(f"初始化爬虫: source={source_config.get('name')}, save_path={save_path}")

    async def _request_with_retry(self, client: httpx.AsyncClient, method: str, url: str) -> httpx.Response:
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await client.request(method, url)
                response.raise_for_status()
                return response
            except httpx.TimeoutException as e:
                last_exc = NetworkError(f"请求超时: {url}")
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    last_exc = NetworkError(f"HTTP错误 {e.response.status_code}: {url}")
                else:
                    raise NetworkError(f"HTTP错误 {e.response.status_code}: {url}")
            except Exception as e:
                last_exc = NetworkError(f"网络请求失败: {e}")
            if attempt < self.max_retries:
                wait = 0.5 * (2 ** attempt)
                logger.warning(f"请求失败，{wait:.1f}s 后重试 ({attempt+1}/{self.max_retries}): {url}")
                await asyncio.sleep(wait)
        raise last_exc

    async def crawl(self, year: int, month: int, issue: Optional[str] = None) -> List[Dict[str, Any]]:
        list_url = self._build_list_url(year, month, issue)
        logger.info(f"开始抓取列表页: {list_url}")

        async with self._client_factory(headers=self.headers) as client:
            try:
                article_urls = await self._get_article_list(client, list_url)
                logger.info(f"获取到 {len(article_urls)} 个文章链接")
            except Exception as e:
                logger.error(f"获取文章列表失败: {e}", exc_info=True)
                raise NetworkError(f"获取文章列表失败: {e}")

            articles = []
            for i, url in enumerate(article_urls):
                try:
                    logger.debug(f"抓取文章 [{i+1}/{len(article_urls)}]: {url}")
                    article = await self._fetch_article(client, url, year, month, issue)
                    if article:
                        articles.append(article)
                        logger.info(f"成功抓取: {article.get('title', '未知标题')}")
                    if self._sleep_between > 0 and i < len(article_urls) - 1:
                        await asyncio.sleep(self._sleep_between)
                except Exception as e:
                    logger.warning(f"抓取文章失败 [{url}]: {e}")
                    continue

        logger.info(f"抓取完成: 成功 {len(articles)}/{len(article_urls)} 篇")
        return articles

    def _build_list_url(self, year: int, month: int, issue: Optional[str]) -> str:
        pattern = self.config.get("list_pattern", "/{year}/{month}")
        url = self.config["base_url"] + pattern.format(
            year=year,
            month=f"{month:02d}",
            issue=issue or ""
        )
        return url

    async def _get_article_list(self, client: httpx.AsyncClient, list_url: str) -> List[str]:
        try:
            response = await self._request_with_retry(client, "GET", list_url)
        except NetworkError:
            raise

        try:
            soup = BeautifulSoup(response.text, "lxml")
            selector = self.config.get("article_selector", "a")
            links = soup.select(selector)

            urls = []
            seen = set()
            for link in links:
                href = link.get("href")
                if not href:
                    continue
                href = href.strip()
                if href.startswith("#") or href.startswith("javascript:"):
                    continue
                if not href.startswith("http"):
                    if href.startswith("/"):
                        href = self.config["base_url"] + href
                    else:
                        href = self.config["base_url"] + "/" + href
                if href in seen:
                    continue
                seen.add(href)
                urls.append(href)

            return urls
        except NetworkError:
            raise
        except Exception as e:
            raise ParseError(f"解析文章列表失败: {e}")

    async def _fetch_article(self, client: httpx.AsyncClient, url: str, year: int, month: int, issue: Optional[str]) -> Optional[Dict[str, Any]]:
        try:
            response = await self._request_with_retry(client, "GET", url)
        except NetworkError:
            raise

        try:
            soup = BeautifulSoup(response.text, "lxml")

            title_el = soup.select_one(self.config.get("title_selector", "h1"))
            title = title_el.get_text(strip=True) if title_el else "未知标题"

            content_el = soup.select_one(self.config.get("content_selector", "article"))
            content = content_el.get_text(strip=True) if content_el else ""

            if not content_el or not content:
                logger.debug(f"文章正文为空或选择器未命中: {url}")

            author = None
            if self.config.get("author_selector"):
                author_el = soup.select_one(self.config["author_selector"])
                author = author_el.get_text(strip=True) if author_el else None

            category = None
            if self.config.get("category_selector"):
                cat_el = soup.select_one(self.config["category_selector"])
                category = cat_el.get_text(strip=True) if cat_el else None

            file_path = self._save_article(title, content, year, month)

            return {
                "title": title,
                "author": author,
                "content": content,
                "source": self.config.get("name"),
                "issue": issue,
                "year": year,
                "month": month,
                "category": category,
                "file_path": str(file_path),
                "url": url
            }
        except NetworkError:
            raise
        except Exception as e:
            raise ParseError(f"解析文章内容失败: {e}")

    def _save_article(self, title: str, content: str, year: int, month: int) -> Path:
        safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)[:50]
        dir_path = self.save_path / str(year) / f"{month:02d}"
        dir_path.mkdir(parents=True, exist_ok=True)

        file_path = dir_path / f"{safe_title}.txt"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"标题: {title}\n\n{content}")
            logger.debug(f"文章已保存: {file_path}")
        except Exception as e:
            logger.error(f"保存文章失败: {e}")

        return file_path
