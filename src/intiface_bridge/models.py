from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DeviceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str
    connected: bool = False
    backend: str
    capabilities: list[str] = Field(default_factory=list)
    last_error: str | None = None


class BackendHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    backend: str
    message: str = ""
    details: dict[str, Any] | None = None


class CommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    backend: str
    action: str
    device_id: str | None = None
    value: int | None = None
    message: str | None = None
    data: dict[str, Any] | None = None


class ErrorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = False
    backend: str | None = None
    code: str
    error: str
    details: dict[str, Any] | None = None
