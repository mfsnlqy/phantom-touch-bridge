from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_name: str | None = None


class SetStrengthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


class StatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    backend: str
    connected: bool
    device_name: str | None = None
    device_id: str | None = None
    keep_connected: bool | None = None
    details: dict[str, Any] | None = None
