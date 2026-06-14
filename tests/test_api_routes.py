from __future__ import annotations

from fastapi.testclient import TestClient

from intiface_bridge.api.server import create_app
from intiface_bridge.config import load_settings
from intiface_bridge.models import BackendHealth, CommandResult, DeviceSummary


class FakeRouteService:
    def __init__(self) -> None:
        self.settings = load_settings(
            env={
                "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
                "INTIFACE_BRIDGE_BACKEND_ERROR_DETAIL": "simple",
            }
        )
        self.connected_with: str | None = None
        self.last_strength: int | None = None
        self.health_calls = 0

    async def health(self) -> BackendHealth:
        self.health_calls += 1
        return BackendHealth(
            ok=True,
            backend="custom",
            message="Custom backend is healthy.",
            details={"probe": "ok"},
        )

    async def status(self) -> dict[str, object]:
        return {
            "backend": "intiface",
            "server_url": "ws://127.0.0.1:12345",
            "client_connected": True,
            "selected_device": "Demo Device",
            "selected_device_id": "7",
            "keep_connected": True,
        }

    async def connect(self, device_name: str | None = None) -> CommandResult:
        self.connected_with = device_name
        return CommandResult(
            backend="custom",
            action="connect",
            device_id="device-1",
            message="connected",
        )

    async def list_devices(self) -> list[DeviceSummary]:
        return [
            DeviceSummary(
                id="device-1",
                name="Demo Device",
                connected=False,
                backend="custom",
                capabilities=["vibrate"],
            )
        ]

    async def disconnect(self) -> CommandResult:
        return CommandResult(
            backend="custom",
            action="disconnect",
            device_id="device-1",
            message="disconnected",
        )

    async def set_strength(self, value: int) -> CommandResult:
        self.last_strength = value
        return CommandResult(
            backend="custom",
            action="set_strength",
            device_id="device-1",
            value=value,
            message="ok",
        )

    async def stop(self) -> CommandResult:
        return CommandResult(
            backend="custom",
            action="stop",
            device_id="device-1",
            message="stopped",
        )

def test_health_routes_and_status_use_http_contract():
    service = FakeRouteService()
    app = create_app(settings=service.settings, service=service)
    client = TestClient(app)

    healthz_response = client.get("/healthz")
    health_response = client.get("/health")
    status_response = client.get("/status")

    assert healthz_response.status_code == 200
    assert healthz_response.json() == {
        "ok": True,
        "name": "phantom-touch-bridge",
        "version": "0.1.0",
        "backend": "custom",
    }
    assert health_response.status_code == 200
    assert health_response.json() == {
        "ok": True,
        "backend": "custom",
        "message": "Custom backend is healthy.",
        "details": {"probe": "ok"},
    }
    assert status_response.status_code == 200
    assert status_response.json() == {
        "ok": True,
        "backend": "intiface",
        "connected": True,
        "device_name": "Demo Device",
        "device_id": "7",
        "keep_connected": True,
        "details": {
            "server_url": "ws://127.0.0.1:12345",
            "client_connected": True,
        },
    }
    assert service.health_calls == 1


def test_connect_and_devices_routes_delegate_through_http():
    service = FakeRouteService()
    app = create_app(settings=service.settings, service=service)
    client = TestClient(app)

    devices_response = client.get("/devices")
    connect_response = client.post("/connect", json={"device_name": "   "})

    assert devices_response.status_code == 200
    assert devices_response.json() == [
        {
            "id": "device-1",
            "name": "Demo Device",
            "connected": False,
            "backend": "custom",
            "capabilities": ["vibrate"],
            "last_error": None,
        }
    ]
    assert connect_response.status_code == 200
    assert connect_response.json()["action"] == "connect"
    assert service.connected_with is None


def test_validation_error_uses_unified_error_shape():
    service = FakeRouteService()
    app = create_app(settings=service.settings, service=service)
    client = TestClient(app)

    response = client.post("/set-strength", json={})

    assert response.status_code == 422
    assert response.json() == {
        "ok": False,
        "backend": "custom",
        "code": "command_failed",
        "error": "请求参数无效。",
    }
