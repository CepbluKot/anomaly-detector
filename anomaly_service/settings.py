"""
Environment-based settings for the anomaly detection service.

Source credentials (for reading metrics) come from the JSON config.
Env vars here are ONLY for the output ClickHouse where anomaly results are stored.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.anomaly-detector",
        extra="ignore",
    )

    anomaly_ch_host: str = "localhost"
    anomaly_ch_port: int = 8123
    anomaly_ch_user: str = "default"
    anomaly_ch_password: str = ""
    anomaly_ch_database: str = "default"

    log_level: str = "INFO"
