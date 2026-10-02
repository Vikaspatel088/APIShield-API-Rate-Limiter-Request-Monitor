from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = 'APIShield'
    app_env: str = 'local'
    host: str = '0.0.0.0'
    port: int = 8000
    log_level: str = 'INFO'
    rate_limit_mode: str = 'local'
    redis_url: str = 'redis://localhost:6379/0'
    trusted_proxies: str = '127.0.0.1,localhost'
    demo_limit: int = 5
    demo_window_seconds: int = 20

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=False,
    )

    @property
    def trusted_proxy_list(self) -> List[str]:
        return [item.strip() for item in self.trusted_proxies.split(',') if item.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
