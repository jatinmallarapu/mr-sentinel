"""Keep connection targets in operator configuration, outside webhook payloads."""

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import AnyHttpUrl, BaseModel, Field


class Settings(BaseModel):
    engine: Literal["vllm", "sglang"]
    model: str = Field(min_length=1)
    base_url: AnyHttpUrl
    review_timeout_seconds: float = Field(default=90, gt=0, le=300)
    risk_threshold: int = Field(default=70, ge=0, le=100)
    max_diff_chars: int = Field(default=24000, ge=1000, le=100000)


def load_settings() -> Settings:
    path = Path(os.environ.get("SENTINEL_CONFIG", "config.yaml"))
    return Settings.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
