import os
import json
import logging
from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path
from typing import Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('./data/app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/rcq.db"
    articles_path: str = "./data/articles"
    sources_config: str = "./config/sources.json"
    runtime_config: str = "./data/runtime_config.json"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    def get_articles_path(self) -> str:
        """获取运行时文章保存路径"""
        runtime = self._load_runtime_config()
        return runtime.get("articles_path") or self.articles_path
    
    def set_articles_path(self, path: str) -> None:
        """持久化保存文章路径"""
        runtime = self._load_runtime_config()
        runtime["articles_path"] = path
        self._save_runtime_config(runtime)
        logger.info(f"文章保存路径已更新: {path}")
    
    def _load_runtime_config(self) -> dict:
        try:
            config_path = Path(self.runtime_config)
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载运行时配置失败: {e}")
        return {}
    
    def _save_runtime_config(self, config: dict) -> None:
        try:
            config_path = Path(self.runtime_config)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存运行时配置失败: {e}")


settings = Settings()

# 确保数据目录存在
Path("./data").mkdir(parents=True, exist_ok=True)
Path(settings.articles_path).mkdir(parents=True, exist_ok=True)
