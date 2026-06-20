import pytest
import json
from pathlib import Path
from freezegun import freeze_time

from app.core.config import Settings


class TestSettingsPersistence:
    def test_get_articles_path_default(self, temp_dir):
        s = Settings(
            database_url=f"sqlite:///{temp_dir}/t.db",
            articles_path=str(temp_dir / "default_articles"),
            sources_config=str(temp_dir / "sources.json"),
            runtime_config=str(temp_dir / "runtime.json")
        )
        assert s.get_articles_path().endswith("default_articles")

    def test_set_then_get_articles_path_persists(self, temp_dir):
        runtime_path = temp_dir / "runtime.json"
        s = Settings(
            database_url=f"sqlite:///{temp_dir}/t.db",
            articles_path=str(temp_dir / "default"),
            sources_config=str(temp_dir / "sources.json"),
            runtime_config=str(runtime_path)
        )
        new_path = str(temp_dir / "custom_articles")
        s.set_articles_path(new_path)
        assert runtime_path.exists()
        with open(runtime_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["articles_path"] == new_path

        s2 = Settings(
            database_url=f"sqlite:///{temp_dir}/t.db",
            articles_path=str(temp_dir / "default"),
            sources_config=str(temp_dir / "sources.json"),
            runtime_config=str(runtime_path)
        )
        assert s2.get_articles_path() == new_path

    def test_runtime_config_missing_returns_default(self, temp_dir):
        s = Settings(
            database_url=f"sqlite:///{temp_dir}/t.db",
            articles_path=str(temp_dir / "fallback"),
            sources_config=str(temp_dir / "sources.json"),
            runtime_config=str(temp_dir / "nonexistent.json")
        )
        assert s.get_articles_path().endswith("fallback")

    def test_runtime_config_corrupt_falls_back_gracefully(self, temp_dir):
        runtime_path = temp_dir / "bad.json"
        runtime_path.write_text("not json{{{", encoding="utf-8")
        s = Settings(
            database_url=f"sqlite:///{temp_dir}/t.db",
            articles_path=str(temp_dir / "safe_default"),
            sources_config=str(temp_dir / "sources.json"),
            runtime_config=str(runtime_path)
        )
        assert s.get_articles_path().endswith("safe_default")


class TestPathValidation:
    def test_crawl_request_rejects_path_traversal(self, client):
        resp = client.post("/api/crawler/start", json={
            "year": 2024,
            "month": 1,
            "save_path": "../../../etc"
        })
        assert resp.status_code == 422

    def test_settings_reject_path_traversal(self, client):
        resp = client.put("/api/settings", json={
            "articles_path": "../../../etc/passwd"
        })
        assert resp.status_code == 422

    def test_crawl_request_rejects_forbidden_chars(self, client):
        for forbidden in ["..", "~", "$", "|", ";", "&", ">", "<"]:
            resp = client.post("/api/crawler/start", json={
                "year": 2024,
                "month": 1,
                "save_path": f"data/test{forbidden}path"
            })
            assert resp.status_code == 422


class TestSourceValidation:
    def test_source_name_required(self, client):
        resp = client.post("/api/settings/sources", json={
            "name": "",
            "base_url": "https://example.com",
            "list_pattern": "/{year}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".content"
        })
        assert resp.status_code == 422

    def test_source_url_must_start_with_http(self, client):
        resp = client.post("/api/settings/sources", json={
            "name": "test",
            "base_url": "ftp://example.com",
            "list_pattern": "/{year}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".content"
        })
        assert resp.status_code == 422

    def test_source_url_must_have_domain(self, client):
        resp = client.post("/api/settings/sources", json={
            "name": "test",
            "base_url": "https://",
            "list_pattern": "/{year}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".content"
        })
        assert resp.status_code == 422

    def test_source_selectors_required(self, client):
        resp = client.post("/api/settings/sources", json={
            "name": "test",
            "base_url": "https://example.com",
            "list_pattern": "/{year}",
            "article_selector": "   ",
            "title_selector": "",
            "content_selector": ".content"
        })
        assert resp.status_code == 422

    def test_source_list_pattern_gets_leading_slash(self, client, temp_dir, monkeypatch):
        from app.core import config as config_module
        sources_path = temp_dir / "sources.json"
        monkeypatch.setattr(config_module.settings, "sources_config", str(sources_path))
        resp = client.post("/api/settings/sources", json={
            "name": "mytest",
            "base_url": "https://example.com",
            "list_pattern": "{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".content"
        })
        assert resp.status_code == 200
        saved = json.loads(sources_path.read_text(encoding="utf-8"))
        assert saved["sources"][0]["list_pattern"].startswith("/")
