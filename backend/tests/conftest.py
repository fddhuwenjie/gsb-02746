import pytest
import os
import json
import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app
import app.api.crawler as crawler_module


@pytest.fixture(autouse=True)
def reset_crawl_status():
    crawler_module.crawl_status = {"status": "idle", "message": "", "articles_count": 0}
    yield


@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def temp_db(temp_dir):
    db_path = temp_dir / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal
    app.dependency_overrides.clear()


@pytest.fixture
def client(temp_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session(temp_db):
    session = temp_db()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def temp_config_dir(temp_dir):
    config_dir = temp_dir / "config"
    config_dir.mkdir()
    yield config_dir


@pytest.fixture
def temp_articles_dir(temp_dir):
    articles_dir = temp_dir / "articles"
    articles_dir.mkdir()
    yield articles_dir


@pytest.fixture
def sample_source_config():
    return {
        "name": "测试数据源",
        "base_url": "https://example.com",
        "list_pattern": "/articles/{year}/{month}",
        "article_selector": ".article-item a",
        "title_selector": "h1.title",
        "content_selector": ".content",
        "author_selector": ".author",
        "category_selector": ".category"
    }


@pytest.fixture
def mock_list_html():
    return """
    <html><body>
        <div class="article-item"><a href="/articles/2024/01/001">文章1</a></div>
        <div class="article-item"><a href="/articles/2024/01/002">文章2</a></div>
        <div class="article-item"><a href="https://example.com/articles/2024/01/003">文章3</a></div>
    </body></html>
    """


@pytest.fixture
def mock_article_html():
    def _make(title="测试标题", author="测试作者", content="测试内容", category="测试分类"):
        return f"""
        <html><body>
            <h1 class="title">{title}</h1>
            <div class="author">{author}</div>
            <div class="category">{category}</div>
            <div class="content">{content}</div>
        </body></html>
        """
    return _make
