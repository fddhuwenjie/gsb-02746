"""设置持久化测试 + 数据源配置基本有效性验证。"""
import json
import pytest
from pathlib import Path

from app.core.config import settings
from app.api import crawler as crawler_module


class TestSettingsPersistence:
    def test_get_settings_returns_current_path(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 200
        d = r.json()
        assert "articles_path" in d
        assert "sources_config" in d

    def test_update_path_persists_and_visible_on_refetch(self, client, tmp_path):
        new_path = str(tmp_path / "new_articles")
        r = client.put("/api/settings", json={"articles_path": new_path})
        assert r.status_code == 200
        assert r.json()["success"] is True

        r2 = client.get("/api/settings")
        assert r2.json()["articles_path"] == new_path
        assert Path(new_path).is_dir()

    def test_settings_object_reads_persisted_value(self, client, tmp_path):
        """直接验证 settings.get_articles_path() 读取持久化文件，模拟重启后行为。"""
        new_path = str(tmp_path / "persist_check")
        client.put("/api/settings", json={"articles_path": new_path})
        assert settings.get_articles_path() == new_path

    def test_update_settings_rejects_path_traversal(self, client):
        r = client.put("/api/settings", json={"articles_path": "../../../etc/passwd"})
        assert r.status_code == 422

    def test_update_settings_rejects_tilde_and_shell_chars(self, client):
        for bad in ["~/secret", "/tmp/a|b", "/tmp/a;b", "/tmp/a&b", "/tmp/a$b"]:
            r = client.put("/api/settings", json={"articles_path": bad})
            assert r.status_code == 422, f"expected 422 for {bad}"

    def test_runtime_config_survives_settings_obj_reload(self, client, tmp_path):
        """关键回归：确保持久化不是写内存而是写文件，模拟进程重启语义。"""
        new_path = str(tmp_path / "restart_test")
        client.put("/api/settings", json={"articles_path": new_path})
        runtime_file = Path(settings.runtime_config)
        assert runtime_file.exists()
        on_disk = json.loads(runtime_file.read_text(encoding="utf-8"))
        assert on_disk["articles_path"] == new_path


class TestSourceConfigValidation:
    def test_add_source_missing_required_fields_rejected(self, client):
        r = client.post("/api/settings/sources", json={"name": "只有名"})
        assert r.status_code == 422

    def test_add_source_invalid_url_rejected(self, client):
        r = client.post("/api/settings/sources", json={
            "name": "坏URL",
            "base_url": "not-a-url",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".content",
        })
        assert r.status_code == 422

    def test_add_source_url_must_have_scheme(self, client):
        r = client.post("/api/settings/sources", json={
            "name": "无scheme",
            "base_url": "example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".content",
        })
        assert r.status_code == 422

    def test_add_source_empty_name_rejected(self, client):
        r = client.post("/api/settings/sources", json={
            "name": "   ",
            "base_url": "https://example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".content",
        })
        assert r.status_code == 422

    def test_add_source_strips_trailing_slash_from_base_url(self, client):
        r = client.post("/api/settings/sources", json={
            "name": "trailing",
            "base_url": "https://example.com/",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".content",
        })
        assert r.status_code == 200
        cfg = json.loads(Path(settings.sources_config).read_text(encoding="utf-8"))
        added = [s for s in cfg["sources"] if s["name"] == "trailing"][0]
        assert added["base_url"] == "https://example.com"

    def test_add_source_prepends_slash_to_list_pattern(self, client):
        r = client.post("/api/settings/sources", json={
            "name": "pat",
            "base_url": "https://example.com",
            "list_pattern": "{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".content",
        })
        assert r.status_code == 200
        cfg = json.loads(Path(settings.sources_config).read_text(encoding="utf-8"))
        added = [s for s in cfg["sources"] if s["name"] == "pat"][0]
        assert added["list_pattern"].startswith("/")

    def test_add_duplicate_source_name_rejected(self, client):
        payload = {
            "name": "唯一",
            "base_url": "https://example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".content",
        }
        assert client.post("/api/settings/sources", json=payload).status_code == 200
        r2 = client.post("/api/settings/sources", json=payload)
        assert r2.status_code == 400

    def test_add_mock_source_is_idempotent(self, client):
        r1 = client.post("/api/settings/sources/mock")
        assert r1.status_code == 200
        r2 = client.post("/api/settings/sources/mock")
        assert r2.status_code == 200
        cfg = json.loads(Path(settings.sources_config).read_text(encoding="utf-8"))
        names = [s["name"] for s in cfg["sources"]]
        assert names.count("模拟数据源（测试用）") == 1

    def test_source_visible_in_crawler_sources_endpoint(self, client):
        client.post("/api/settings/sources", json={
            "name": "端点可见",
            "base_url": "https://example.com",
            "list_pattern": "/{year}/{month}",
            "article_selector": "a",
            "title_selector": "h1",
            "content_selector": ".c",
        })
        r = client.get("/api/crawler/sources")
        assert r.status_code == 200
        names = [s["name"] for s in r.json()["sources"]]
        assert "端点可见" in names


class TestSourcesFileCompatibility:
    def test_missing_sources_file_returns_empty_list(self, client):
        cfg_path = Path(settings.sources_config)
        if cfg_path.exists():
            cfg_path.unlink()
        r = client.get("/api/crawler/sources")
        assert r.status_code == 200
        assert r.json() == {"sources": []}

    def test_malformed_sources_file_does_not_crash_endpoint(self, client):
        cfg_path = Path(settings.sources_config)
        cfg_path.write_text("不是合法JSON", encoding="utf-8")
        from app.api.crawler import load_sources
        with pytest.raises(Exception):
            load_sources()
