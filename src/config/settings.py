from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from typing import List, Optional
import yaml


class DateTimeRange(BaseModel):
    start: str
    end: str


class TCPageConfig(BaseModel):
    id: str
    name: str
    url: str
    check_interval: int = Field(default=60, ge=30)
    date_range: DateTimeRange
    time_range: DateTimeRange


class SeekerConfig(BaseModel):
    tc_url: str
    test_name: str
    check_interval: int = Field(default=60, ge=30)
    date_range: DateTimeRange
    time_range: DateTimeRange


class TargetTC(BaseModel):
    name: str
    url: str


class Settings(BaseSettings):
    moodle_url: str = "https://moodle.czu.cz"
    moodle_username: str
    moodle_password: str
    telegram_bot_token: str
    telegram_chat_id: str
    log_level: str = "INFO"
    session_cache_file: str = ".session_cache.pkl"
    tc_pages: List[TCPageConfig] = []
    seeker: Optional[SeekerConfig] = None
    target_tcs: List[TargetTC] = []

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @classmethod
    def load_with_config(cls, config_file: str = "config.yaml"):
        """Load settings from environment and config.yaml"""
        settings = cls()

        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if 'tc_pages' in config_data:
            settings.tc_pages = [TCPageConfig(**tc) for tc in config_data['tc_pages']]

        if 'seeker' in config_data:
            settings.seeker = SeekerConfig(**config_data['seeker'])

        if 'target_tcs' in config_data:
            settings.target_tcs = [TargetTC(**tc) for tc in config_data['target_tcs']]

        return settings
