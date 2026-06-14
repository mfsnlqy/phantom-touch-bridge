from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from intiface_bridge import __version__
from intiface_bridge.api.schemas import ConnectRequest, SetStrengthRequest, StatusResponse
from intiface_bridge.models import BackendHealth
from intiface_bridge.models import CommandResult, DeviceSummary
from intiface_bridge.service import BridgeService

router = APIRouter()


def get_bridge_service(request: Request) -> BridgeService:
    return request.app.state.service


def _normalize_status(raw: dict[str, Any]) -> StatusResponse:
    backend = str(raw.get("backend") or "unknown")
    device_name = _first_non_empty(raw.get("device_name"), raw.get("selected_device"))
    device_id = _first_non_empty(
        raw.get("device_id"),
        raw.get("device_address"),
        raw.get("selected_device_id"),
    )
    connected = bool(raw.get("connected"))
    if "connected" not in raw:
        connected = bool(device_id or device_name)

    details = {
        key: value
        for key, value in raw.items()
        if key
        not in {
            "backend",
            "connected",
            "device_name",
            "device_id",
            "device_address",
            "selected_device",
            "selected_device_id",
            "keep_connected",
        }
    }

    return StatusResponse(
        backend=backend,
        connected=connected,
        device_name=device_name,
        device_id=device_id,
        keep_connected=raw.get("keep_connected"),
        details=details or None,
    )


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return None


@router.get("/healthz", tags=["health"])
async def healthz(request: Request) -> dict[str, str | bool]:
    settings = request.app.state.settings
    return {
        "ok": True,
        "name": "phantom-touch-bridge",
        "version": __version__,
        "backend": settings.backend.type,
    }


@router.get("/health", response_model=BackendHealth, tags=["health"])
async def health(
    service: BridgeService = Depends(get_bridge_service),
) -> BackendHealth:
    return await service.health()


@router.get("/backend/health", response_model=BackendHealth, tags=["health"])
async def backend_health(
    service: BridgeService = Depends(get_bridge_service),
) -> BackendHealth:
    return await service.health()


@router.get("/status", response_model=StatusResponse, tags=["device"])
async def status(
    service: BridgeService = Depends(get_bridge_service),
) -> StatusResponse:
    return _normalize_status(await service.status())


@router.get("/devices", response_model=list[DeviceSummary], tags=["device"])
async def list_devices(
    service: BridgeService = Depends(get_bridge_service),
) -> list[DeviceSummary]:
    return await service.list_devices()


@router.post("/connect", response_model=CommandResult, tags=["device"])
async def connect(
    payload: ConnectRequest | None = None,
    service: BridgeService = Depends(get_bridge_service),
) -> CommandResult:
    device_name = None
    if payload is not None and payload.device_name is not None:
        device_name = payload.device_name.strip() or None
    return await service.connect(device_name)


@router.post("/disconnect", response_model=CommandResult, tags=["device"])
async def disconnect(
    service: BridgeService = Depends(get_bridge_service),
) -> CommandResult:
    return await service.disconnect()


@router.post("/set-strength", response_model=CommandResult, tags=["device"])
async def set_strength(
    payload: SetStrengthRequest,
    service: BridgeService = Depends(get_bridge_service),
) -> CommandResult:
    return await service.set_strength(payload.value)


@router.post("/stop", response_model=CommandResult, tags=["device"])
async def stop(
    service: BridgeService = Depends(get_bridge_service),
) -> CommandResult:
    return await service.stop()

