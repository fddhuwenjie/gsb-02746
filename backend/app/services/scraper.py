import httpx
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Dict, Any, Optional
import asyncio
import re
import logging
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """爬虫异常基类"""
    pass


class NetworkError(ScraperError):
    """网络请求异常"""
    pass


class ParseError(ScraperError):
    """页面解析异常"""
    pass


class ArticleScraper:
    def __init__(self, source_config: Dict[str, Any], save_path: str):
        self.config = source_config
        self.save_path = Path(save_path)
        self.save_path.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        logger.info(f"初始化爬虫: source={source_config.get('name')}, save_path={save_path}")
    
    async def crawl(self, year: int, month: int, issue: Optional[str] = None) -> List[Dict[str, Any]]:
        list_url = self._build_list_url(year, month, issue)
        logger.info(f"开始抓取列表页: {list_url}")
        
        try:
            article_urls = await self._get_article_list(list_url)
            logger.info(f"获取到 {len(article_urls)} 个文章链接")
        except Exception as e:
            logger.error(f"获取文章列表失败: {e}", exc_info=True)
            raise NetworkError(f"获取文章列表失败: {e}")
        
        articles = []
        for i, url in enumerate(article_urls):
            try:
                logger.debug(f"抓取文章 [{i+1}/{len(article_urls)}]: {url}")
                article = await self._fetch_article(url, year, month, issue)
                if article:
                    articles.append(article)
                    logger.info(f"成功抓取: {article.get('title', '未知标题')}")
                await asyncio.sleep(0.5)  # 礼貌性延迟
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
    
    async def _get_article_list(self, list_url: str) -> List[str]:
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=30, follow_redirects=True) as client:
                response = await client.get(list_url)
                response.raise_for_status()
        except httpx.TimeoutException:
            raise NetworkError(f"请求超时: {list_url}")
        except httpx.HTTPStatusError as e:
            raise NetworkError(f"HTTP错误 {e.response.status_code}: {list_url}")
        except Exception as e:
            raise NetworkError(f"网络请求失败: {e}")
        
        try:
            soup = BeautifulSoup(response.text, "lxml")
            selector = self.config.get("article_selector", "a")
            links = soup.select(selector)
            
            urls = []
            for link in links:
                href = link.get("href")
                if href:
                    urls.append(urljoin(self.config["base_url"], href))
            
            return urls
        except Exception as e:
            raise ParseError(f"解析文章列表失败: {e}")
    
    async def _fetch_article(self, url: str, year: int, month: int, issue: Optional[str]) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=30, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.TimeoutException:
            raise NetworkError(f"请求超时: {url}")
        except httpx.HTTPStatusError as e:
            raise NetworkError(f"HTTP错误 {e.response.status_code}: {url}")
        except Exception as e:
            raise NetworkError(f"网络请求失败: {e}")
        
        try:
            soup = BeautifulSoup(response.text, "lxml")
            
            title_el = soup.select_one(self.config.get("title_selector", "h1"))
            title = title_el.get_text(strip=True) if title_el else "未知标题"
            
            content_el = soup.select_one(self.config.get("content_selector", "article"))
            content = content_el.get_text(strip=True) if content_el else ""
            
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
