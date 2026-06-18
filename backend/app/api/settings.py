from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
import json
import re
import logging
from pathlib import Path

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class SettingsUpdate(BaseModel):
    articles_path: Optional[str] = None
    
    @field_validator('articles_path')
    @classmethod
    def validate_articles_path(cls, v):
        if v:
            # 检查路径安全性
            forbidden_patterns = ['..', '~', '$', '|', ';', '&', '>', '<']
            for pattern in forbidden_patterns:
                if pattern in v:
                    raise ValueError(f'路径不能包含 {pattern}')
            # 路径长度限制
            if len(v) > 200:
                raise ValueError('路径长度不能超过 200 个字符')
        return v


class SourceConfig(BaseModel):
    name: str
    base_url: str
    list_pattern: str
    article_selector: str
    title_selector: str
    content_selector: str
    author_selector: Optional[str] = None
    category_selector: Optional[str] = None
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('数据源名称不能为空')
        if len(v) > 50:
            raise ValueError('数据源名称不能超过 50 个字符')
        return v.strip()
    
    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        if not v:
            raise ValueError('基础URL不能为空')
        if not v.startswith('http://') and not v.startswith('https://'):
            raise ValueError('基础URL必须以 http:// 或 https:// 开头')
        # 简单的URL格式验证
        url_pattern = r'^https?://[a-zA-Z0-9][-a-zA-Z0-9]*(\.[a-zA-Z0-9][-a-zA-Z0-9]*)+.*$'
        if not re.match(url_pattern, v):
            raise ValueError('基础URL格式不正确')
        return v.rstrip('/')
    
    @field_validator('list_pattern')
    @classmethod
    def validate_list_pattern(cls, v):
        if not v:
            raise ValueError('列表页URL模式不能为空')
        if not v.startswith('/'):
            v = '/' + v
        return v
    
    @field_validator('article_selector', 'title_selector', 'content_selector')
    @classmethod
    def validate_required_selector(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('选择器不能为空')
        return v.strip()


@router.get("")
async def get_settings():
    return {
        "articles_path": settings.get_articles_path(),
        "sources_config": settings.sources_config
    }


@router.put("")
async def update_settings(update: SettingsUpdate):
    try:
        if update.articles_path:
            # 创建目录
            path = Path(update.articles_path)
            path.mkdir(parents=True, exist_ok=True)
            # 持久化保存
            settings.set_articles_path(update.articles_path)
            logger.info(f"设置已更新: articles_path={update.articles_path}")
        return {"success": True, "message": "设置已保存"}
    except Exception as e:
        logger.error(f"更新设置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sources")
async def add_source(source: SourceConfig):
    try:
        config_path = Path(settings.sources_config)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"sources": []}
        
        # 检查是否已存在同名数据源
        existing_names = [s.get("name") for s in data.get("sources", [])]
        if source.name in existing_names:
            raise HTTPException(status_code=400, detail=f"数据源 '{source.name}' 已存在")
        
        data["sources"].append(source.model_dump())
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"数据源已添加: {source.name}")
        return {"success": True, "message": "数据源已添加"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加数据源失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sources/mock")
async def add_mock_source():
    """添加模拟数据源 - 用于测试"""
    mock_source = {
        "name": "模拟数据源（测试用）",
        "base_url": "https://mock.example.com",
        "list_pattern": "/articles/{year}/{month}",
        "article_selector": ".article-item a",
        "title_selector": "h1.article-title",
        "content_selector": ".article-content",
        "author_selector": ".author-name",
        "category_selector": ".category-tag"
    }
    
    try:
        config_path = Path(settings.sources_config)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"sources": []}
        
        # 检查是否已存在
        existing_names = [s.get("name") for s in data.get("sources", [])]
        if mock_source["name"] in existing_names:
            return {"success": True, "message": "模拟数据源已存在", "source": mock_source}
        
        data["sources"].append(mock_source)
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info("模拟数据源已添加")
        return {"success": True, "message": "模拟数据源已添加", "source": mock_source}
    except Exception as e:
        logger.error(f"添加模拟数据源失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
