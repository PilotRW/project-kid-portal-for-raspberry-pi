import hashlib
import json
import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


Decision = Literal["ALLOW", "BLOCK", "REQUIRE_PARENT_APPROVAL"]


class SiteConfig(BaseModel):
    label: str
    url: str
    domain: str


class YouTubeConfig(BaseModel):
    max_results: int = Field(default=20, ge=1, le=25)
    safe_search: Literal["none", "moderate", "strict"] = "strict"
    region_code: str = "US"


class FilteringConfig(BaseModel):
    allowed_channels: list[str] = Field(default_factory=list)
    blocked_channels: list[str] = Field(default_factory=list)
    allowed_keywords: list[str] = Field(default_factory=list)
    blocked_keywords: list[str] = Field(default_factory=list)
    approval_keywords: list[str] = Field(default_factory=list)
    blocked_categories: list[str] = Field(default_factory=list)
    default_decision: Decision = "REQUIRE_PARENT_APPROVAL"
    max_duration_seconds: int | None = Field(default=3600, ge=1)


class ParentConfig(BaseModel):
    pin_sha256: str
    view_pin_sha256: str = "fe2592b42a727e977f055947385b709cc82b16b9a87f88c6abf3900d65d0cdc3"
    default_unrestricted_minutes: int = Field(default=30, ge=1, le=240)

    def verify_pin(self, pin: str) -> bool:
        return hashlib.sha256(pin.encode("utf-8")).hexdigest() == self.pin_sha256

    def verify_view_pin(self, pin: str) -> bool:
        return hashlib.sha256(pin.encode("utf-8")).hexdigest() == self.view_pin_sha256

    def set_view_pin(self, pin: str) -> None:
        self.view_pin_sha256 = hashlib.sha256(pin.encode("utf-8")).hexdigest()


class LimitConfig(BaseModel):
    daily_minutes: int = Field(default=90, ge=1, le=1440)


class PortalConfig(BaseModel):
    allowed_sites: list[SiteConfig]
    youtube: YouTubeConfig = Field(default_factory=YouTubeConfig)
    filtering: FilteringConfig = Field(default_factory=FilteringConfig)
    parent: ParentConfig
    limits: LimitConfig = Field(default_factory=LimitConfig)


class ConfigService:
    def __init__(self, config_path: Path | None = None) -> None:
        default_path = Path(__file__).resolve().parents[2] / "config" / "kid-portal.json"
        self.config_path = config_path or Path(os.environ.get("KID_PORTAL_CONFIG", default_path))

    def load(self) -> PortalConfig:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Missing config file: {self.config_path}")
        raw = self.config_path.read_text(encoding="utf-8")
        if self.config_path.suffix in {".yaml", ".yml"}:
            data = yaml.safe_load(raw)
        else:
            data = json.loads(raw)
        return PortalConfig.model_validate(data)

    def save(self, config: PortalConfig) -> None:
        payload = config.model_dump(mode="json")
        if self.config_path.suffix in {".yaml", ".yml"}:
            self.config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        else:
            self.config_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
