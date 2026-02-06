from functools import lru_cache
from typing import Annotated, Generator

from fastapi import Depends, Request

from sqlalchemy.orm import Session
from src.config import Settings
from src.db.interfaces.base import BaseDatabase


@lru_cache
def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


SettingsDep = Annotated[Settings , Depends(get_settings())]