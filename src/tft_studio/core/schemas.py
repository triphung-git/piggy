"""Shared validation for HTTP, desktop IPC and configuration files."""

from pathlib import PurePosixPath
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

Text = Annotated[StrictStr, Field(max_length=200)]


def resource_path(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or ":" in value or not value or any(ord(c) < 32 for c in value):
        raise ValueError("Expected a relative resource path without traversal")
    if path.parts[0] not in ("assets", "TFT_DDragon"):
        raise ValueError("Images must be under assets or TFT_DDragon")
    return path.as_posix()


class OverlayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tournament_title: Text = "YOUR TOURNAMENT NAME"
    stage_title: Text = "STAGE / QUALIFIER"
    game_title: Text = "TEAMFIGHT TACTICS"
    server_port: int = Field(default=8080, ge=1, le=65535)
    background_image: Text = "assets/background.png"
    font_family: Text = "League Spartan"
    player_avatars: dict[Text, Text] = Field(default_factory=dict, max_length=100)
    custom_augments: list[Text | None] = Field(default_factory=list, max_length=6)

    @field_validator("background_image")
    @classmethod
    def validate_background(cls, value: str) -> str:
        return resource_path(value)

    @field_validator("player_avatars")
    @classmethod
    def validate_avatars(cls, value: dict) -> dict:
        return {key: resource_path(path) for key, path in value.items()}

    @field_validator("custom_augments")
    @classmethod
    def validate_augments(cls, values: list) -> list:
        from tft_studio.data.parser import validate_custom_augment

        if any(v is not None and not validate_custom_augment(v) for v in values):
            raise ValueError("Invalid augment identifier")
        return [v.strip() if v and v.strip() else None for v in values]


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    image_base64: Annotated[StrictStr, Field(min_length=1, max_length=16_000_000)]


class RiotSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    riot_id: Annotated[StrictStr, Field(min_length=3, max_length=100)]
    region: Text
    api_key: Annotated[StrictStr, Field(max_length=200)] | None = None

    @field_validator("riot_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        parts = value.strip().split("#")
        if len(parts) != 2 or not all(p.strip() for p in parts) or any(c in value for c in "\r\n"):
            raise ValueError("Riot ID must contain GameName#TagLine")
        return "#".join(p.strip() for p in parts)

    @field_validator("region")
    @classmethod
    def validate_region(cls, value: str) -> str:
        from tft_studio.core.config import REGION_MAPPING

        value = value.upper().strip()
        if value not in REGION_MAPPING:
            raise ValueError("Unsupported region")
        return value

    @field_validator("api_key")
    @classmethod
    def validate_key(cls, value: str | None) -> str | None:
        if value is not None and (not value.startswith("RGAPI-") or any(c in value for c in "\r\n")):
            raise ValueError("Invalid Riot API key")
        return value
