from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import Optional
import json
import re
import logging
from pathlib import Path
from datetime import datetime

from app.core.database import get_db
from app.core.config import settings
from app.services.scraper import ArticleScraper
from app.models.article import Article

router = APIRouter()
logger = logging.getLogger(__name__)


class CrawlRequest(BaseModel):
    source_name: Optional[str] = None
    year: int
    month: int
    issue: Optional[str] = None
    save_path: Optional[str] = None
    
    @field_validator('year')
    @classmethod
    def validate_year(cls, v):
        current_year = datetime.now().year
        if v < 1900 or v > current_year + 1:
            raise ValueError(f'年份必须在 1900 到 {current_year + 1} 之间')
        return v
    
    @field_validator('month')
    @classmethod
    def validate_month(cls, v):
        if v < 1 or v > 12:
            raise ValueError('月份必须在 1 到 12 之间')
        return v
    
    @field_validator('issue')
    @classmethod
    def validate_issue(cls, v):
        if v and len(v) > 50:
            raise ValueError('期数长度不能超过 50 个字符')
        return v
    
    @field_validator('save_path')
    @classmethod
    def validate_save_path(cls, v):
        if v:
            # 检查路径安全性
            forbidden_patterns = ['..', '~', '$', '|', ';', '&', '>', '<']
            for pattern in forbidden_patterns:
                if pattern in v:
                    raise ValueError(f'保存路径不能包含 {pattern}')
            # 必须是绝对路径或相对于 data 目录
            if not v.startswith('/app/data') and not v.startswith('./data') and not v.startswith('data'):
                if v.startswith('/'):
                    raise ValueError('保存路径必须在 /app/data 目录下')
        return v


class CrawlStatus(BaseModel):
    status: str
    message: str
    articles_count: int = 0


crawl_status = {"status": "idle", "message": "", "articles_count": 0}


def _ensure_unique(db: Session, article_data: dict) -> bool:
    """Return True if article is new and was added; False if it already exists."""
    if article_data.get("url"):
        exists = db.query(Article).filter(Article.url == article_data["url"]).first()
        if exists:
            return False
    else:
        exists = db.query(Article).filter(
            Article.title == article_data.get("title"),
            Article.year == article_data.get("year"),
            Article.month == article_data.get("month"),
            Article.author == article_data.get("author"),
        ).first()
        if exists:
            return False
    db.add(Article(**article_data))
    return True


def load_sources():
    config_path = Path(settings.sources_config)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"sources": []}


async def crawl_task(request: CrawlRequest, db: Session):
    global crawl_status
    crawl_status = {"status": "running", "message": "正在抓取...", "articles_count": 0}
    logger.info(f"开始抓取任务: year={request.year}, month={request.month}, issue={request.issue}")
    
    try:
        sources = load_sources()
        if not sources.get("sources"):
            msg = "【提供网站地址】请先在设置页面配置数据源，或编辑 config/sources.json"
            crawl_status = {"status": "error", "message": msg, "articles_count": 0}
            logger.warning(msg)
            return
        
        source = sources["sources"][0]
        if request.source_name:
            source = next((s for s in sources["sources"] if s["name"] == request.source_name), source)
        
        # 使用运行时配置的路径或请求中的路径
        save_path = request.save_path or settings.get_articles_path()
        
        scraper = ArticleScraper(source, save_path)
        articles = await scraper.crawl(request.year, request.month, request.issue)
        
        new_count = 0
        dup_count = 0
        for article_data in articles:
            if _ensure_unique(db, article_data):
                new_count += 1
            else:
                dup_count += 1
        db.commit()
        
        msg = f"抓取完成，新增 {new_count} 篇"
        if dup_count:
            msg += f"（跳过重复 {dup_count} 篇）"
        crawl_status = {"status": "completed", "message": msg, "articles_count": new_count}
        logger.info(f"抓取完成: 新增 {new_count} 篇, 重复 {dup_count} 篇")
    except Exception as e:
        error_msg = str(e)
        crawl_status = {"status": "error", "message": error_msg, "articles_count": 0}
        logger.error(f"抓取失败: {error_msg}", exc_info=True)


@router.post("/start")
async def start_crawl(request: CrawlRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if crawl_status["status"] == "running":
        raise HTTPException(status_code=400, detail="已有任务在运行")
    
    logger.info(f"收到抓取请求: {request.model_dump()}")
    background_tasks.add_task(crawl_task, request, db)
    return {"message": "抓取任务已启动"}


@router.get("/status", response_model=CrawlStatus)
async def get_crawl_status():
    return crawl_status


@router.get("/sources")
async def get_sources():
    return load_sources()


@router.post("/mock")
async def mock_crawl(db: Session = Depends(get_db)):
    """模拟抓取 - 用于测试验证抓取流程"""
    global crawl_status
    logger.info("执行模拟抓取")
    
    mock_articles = [
        {
            "title": "模拟抓取：春风十里",
            "author": "模拟作者A",
            "content": "这是一篇通过模拟抓取功能生成的测试文章。春风十里，不如你。在这个美好的季节里，让我们一起感受生活的美好。\n\n模拟抓取功能可以帮助测试人员验证系统的抓取流程是否正常工作，无需配置真实的数据源。",
            "source": "模拟数据源",
            "issue": "模拟期",
            "year": datetime.now().year,
            "month": datetime.now().month,
            "category": "模拟分类"
        },
        {
            "title": "模拟抓取：岁月静好",
            "author": "模拟作者B", 
            "content": "岁月静好，现世安稳。这是另一篇模拟抓取的文章，用于验证批量抓取和入库功能。\n\n通过模拟抓取，您可以：\n1. 验证文章列表显示是否正常\n2. 验证文章详情页是否正常\n3. 验证筛选和搜索功能是否正常",
            "source": "模拟数据源",
            "issue": "模拟期",
            "year": datetime.now().year,
            "month": datetime.now().month,
            "category": "模拟分类"
        },
        {
            "title": "模拟抓取：时光荏苒",
            "author": "模拟作者C",
            "content": "时光荏苒，白驹过隙。第三篇模拟文章，展示不同作者和内容的情况。\n\n模拟数据特点：\n- 标题带有「模拟抓取」前缀，便于识别\n- 使用当前年月，便于筛选测试\n- 分类统一为「模拟分类」",
            "source": "模拟数据源",
            "issue": "模拟期",
            "year": datetime.now().year,
            "month": datetime.now().month,
            "category": "模拟分类"
        }
    ]
    
    crawl_status = {"status": "running", "message": "正在模拟抓取...", "articles_count": 0}
    
    try:
        new_count = 0
        dup_count = 0
        for article_data in mock_articles:
            if _ensure_unique(db, article_data):
                new_count += 1
            else:
                dup_count += 1
        db.commit()
        
        msg = f"模拟抓取完成，新增 {new_count} 篇"
        if dup_count:
            msg += f"（跳过重复 {dup_count} 篇）"
        crawl_status = {"status": "completed", "message": msg, "articles_count": new_count}
        logger.info(f"模拟抓取完成: 新增 {new_count} 篇, 重复 {dup_count} 篇")
        
        return {
            "success": True,
            "message": f"模拟抓取成功，已添加 {new_count} 篇测试文章",
            "articles_count": new_count
        }
    except Exception as e:
        error_msg = str(e)
        crawl_status = {"status": "error", "message": error_msg, "articles_count": 0}
        logger.error(f"模拟抓取失败: {error_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)
