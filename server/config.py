import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "gaokao-volunteer-gd"
    database_path: str = "gaokao.db"
    data_year: int = 2025
    province: str = "广东"
    batch: str = "本科普通批"
    max_volunteers: int = 45
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "deepseek-chat"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 优先从环境变量读取端口（云托管会传入 PORT 环境变量）
SERVER_PORT: int = int(os.environ.get("PORT", "8000"))

settings = Settings()
