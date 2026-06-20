"""
测试 fixtures。

设计目标：
1. 数据库：每个测试一份独立的内存 SQLite，互不干扰；通过 dependency_overrides 替换 get_db。
2. 配置文件：sources.json / runtime_config.json 全部指向 tmp_path，避免污染仓库与全局状态。
3. 抓取状态：crawler.crawl_status 是模块级全局变量，每个测试前后重置。
4. 测试客户端：复用 FastAPI TestClient，但每个 fixture 独立构造，确保隔离。
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import config as config_module
from app.core import database as db_module
from app.api import crawler as crawler_module
from app.main import app


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """把所有持久化路径指向 tmp_path，避免污染真实文件。"""
    sources_path = tmp_path / "sources.json"
    runtime_path = tmp_path / "runtime.json"
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()

    monkeypatch.setattr(config_module.settings, "sources_config", str(sources_path))
    monkeypatch.setattr(config_module.settings, "runtime_config", str(runtime_path))
    monkeypatch.setattr(config_module.settings, "articles_path", str(articles_dir))
    return {
        "sources": sources_path,
        "runtime": runtime_path,
        "articles": articles_dir,
        "tmp": tmp_path,
    }


@pytest.fixture
def db_session(monkeypatch):
    """每个测试一个内存 SQLite，通过 StaticPool 让多个连接共享同一份内存数据。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    # 创建表
    from app.models import article  # noqa: F401  确保模型被注册
    db_module.Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session, TestingSession
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(isolated_settings, db_session):
    """FastAPI TestClient，注入隔离的 DB。"""
    session, TestingSession = db_session

    def _override_get_db():
        local = TestingSession()
        try:
            yield local
        finally:
            local.close()

    app.dependency_overrides[db_module.get_db] = _override_get_db
    # 重置抓取状态
    crawler_module.crawl_status = {"status": "idle", "message": "", "articles_count": 0}
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def write_sources(isolated_settings):
    """工具：写入数据源配置。"""
    def _write(sources):
        Path(isolated_settings["sources"]).write_text(
            json.dumps({"sources": sources}, ensure_ascii=False),
            encoding="utf-8",
        )
    return _write


@pytest.fixture
def seed_articles(db_session):
    """直接通过 ORM 注入历史文章数据，方便构造筛选/兼容性场景。"""
    session, _ = db_session
    from app.models.article import Article

    def _seed(rows):
        objs = [Article(**row) for row in rows]
        session.add_all(objs)
        session.commit()
        return objs

    return _seed
