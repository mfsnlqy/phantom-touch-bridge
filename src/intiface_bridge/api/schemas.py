from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_name: str | None = None


class HeartRateConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_name: str | None = None
    device_address: str | None = None
    notify_char_uuid: str | None = None


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


class HeartRateDeviceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    address: str
    rssi: int | None = None
    service_uuids: list[str]


class HeartRateSampleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bpm: int
    measured_at: str
    sequence: int
    rr_intervals_ms: list[float]
    sensor_contact_detected: bool | None = None
    energy_expended: int | None = None
    raw_hex: str


class HeartRateStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    backend: str = "heart_rate"
    connected: bool
    streaming: bool
    target_device_name: str | None = None
    target_device_address: str | None = None
    selected_device_name: str | None = None
    selected_device_address: str | None = None
    notify_char_uuid: str | None = None
    last_packet_at: str | None = None
    last_error: str | None = None
    latest_bpm: int | None = None


class HeartRateLatestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    backend: str = "heart_rate"
    has_sample: bool
    sample: HeartRateSampleResponse | None = None
