"""全局配置。所有密钥只在此层读取，绝不向前端暴露。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", encoding="utf-8")


class Settings:
    # --- LLM ---
    api_key: str = os.getenv("SILICONFLOW_API_KEY", "")
    base_url: str = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model: str = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-72B-Instruct")
    model_fast: str = os.getenv("LLM_MODEL_FAST", "Qwen/Qwen2.5-7B-Instruct")

    # --- 服务 ---
    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8000"))
    trend_cache_ttl: int = int(os.getenv("TREND_CACHE_TTL", "600"))

    # --- 账号体系 ---
    allowed_email_domain: str = os.getenv("ALLOWED_EMAIL_DOMAIN", "163.com")
    session_days: int = int(os.getenv("SESSION_DAYS", "30"))
    # 163 邮箱 SMTP（授权码不是登录密码，需在邮箱设置里单独开启）
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.163.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "465"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_auth_code: str = os.getenv("SMTP_AUTH_CODE", "")

    # --- 图片 ---
    unsplash_key: str = os.getenv("UNSPLASH_ACCESS_KEY", "")
    photo_dir: Path = BASE_DIR / "web" / "assets" / "photos"

    # --- 路径 ---
    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "app" / "data"
    web_dir: Path = BASE_DIR / "web"

    @property
    def llm_ready(self) -> bool:
        return bool(self.api_key) and self.api_key.startswith("sk-")

    @property
    def mail_ready(self) -> bool:
        return bool(self.smtp_user and self.smtp_auth_code)

    @property
    def photos_ready(self) -> bool:
        return bool(self.unsplash_key)


settings = Settings()
