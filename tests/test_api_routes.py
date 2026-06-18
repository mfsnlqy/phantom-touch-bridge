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

    async def heart_rate_status(self) -> dict[str, object]:
        return {
            "connected": False,
            "streaming": False,
            "target_device_name": "Demo Band",
            "target_device_address": "00:11:22:33:44:55",
            "selected_device_name": None,
            "selected_device_address": None,
            "notify_char_uuid": None,
            "last_packet_at": None,
            "last_error": None,
            "latest_bpm": None,
        }

    async def heart_rate_latest_sample(self):
        return None

    async def heart_rate_scan_devices(self) -> list[dict[str, object]]:
        return [
            {
                "name": "Demo Band",
                "address": "00:11:22:33:44:55",
                "rssi": -40,
                "service_uuids": ["180d"],
            }
        ]

    async def heart_rate_connect(
        self,
        *,
        device_name: str | None = None,
        device_address: str | None = None,
        notify_char_uuid: str | None = None,
    ) -> dict[str, object]:
        self.heart_rate_connected_with = {
            "device_name": device_name,
            "device_address": device_address,
            "notify_char_uuid": notify_char_uuid,
        }
        return {
            "connected": True,
            "streaming": True,
            "target_device_name": device_name,
            "target_device_address": device_address,
            "selected_device_name": "Demo Band",
            "selected_device_address": "00:11:22:33:44:55",
            "notify_char_uuid": notify_char_uuid,
            "last_packet_at": "2026-06-18T00:00:00+00:00",
            "last_error": None,
            "latest_bpm": 88,
        }

    async def heart_rate_disconnect(self) -> dict[str, object]:
        return {
            "connected": False,
            "streaming": False,
            "target_device_name": "Demo Band",
            "target_device_address": "00:11:22:33:44:55",
            "selected_device_name": None,
            "selected_device_address": None,
            "notify_char_uuid": None,
            "last_packet_at": None,
            "last_error": None,
            "latest_bpm": None,
        }

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
        "version": "0.2.0",
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


def test_heart_rate_routes_use_http_contract():
    service = FakeRouteService()
    app = create_app(settings=service.settings, service=service)
    client = TestClient(app)

    status_response = client.get("/heart-rate/status")
    latest_response = client.get("/heart-rate/latest")
    devices_response = client.get("/heart-rate/devices")
    connect_response = client.post(
        "/heart-rate/connect",
        json={
            "device_name": " Demo Band ",
            "device_address": "00:11:22:33:44:55",
            "notify_char_uuid": " 00002A37-0000-1000-8000-00805F9B34FB ",
        },
    )
    disconnect_response = client.post("/heart-rate/disconnect")

    assert status_response.status_code == 200
    assert status_response.json() == {
        "ok": True,
        "backend": "heart_rate",
        "connected": False,
        "streaming": False,
        "target_device_name": "Demo Band",
        "target_device_address": "00:11:22:33:44:55",
        "selected_device_name": None,
        "selected_device_address": None,
        "notify_char_uuid": None,
        "last_packet_at": None,
        "last_error": None,
        "latest_bpm": None,
    }
    assert latest_response.status_code == 200
    assert latest_response.json() == {
        "ok": True,
        "backend": "heart_rate",
        "has_sample": False,
        "sample": None,
    }
    assert devices_response.status_code == 200
    assert devices_response.json() == [
        {
            "name": "Demo Band",
            "address": "00:11:22:33:44:55",
            "rssi": -40,
            "service_uuids": ["180d"],
        }
    ]
    assert connect_response.status_code == 200
    assert connect_response.json() == {
        "ok": True,
        "backend": "heart_rate",
        "connected": True,
        "streaming": True,
        "target_device_name": "Demo Band",
        "target_device_address": "00:11:22:33:44:55",
        "selected_device_name": "Demo Band",
        "selected_device_address": "00:11:22:33:44:55",
        "notify_char_uuid": "00002A37-0000-1000-8000-00805F9B34FB",
        "last_packet_at": "2026-06-18T00:00:00+00:00",
        "last_error": None,
        "latest_bpm": 88,
    }
    assert service.heart_rate_connected_with == {
        "device_name": "Demo Band",
        "device_address": "00:11:22:33:44:55",
        "notify_char_uuid": "00002A37-0000-1000-8000-00805F9B34FB",
    }
    assert disconnect_response.status_code == 200
    assert disconnect_response.json() == {
        "ok": True,
        "backend": "heart_rate",
        "connected": False,
        "streaming": False,
        "target_device_name": "Demo Band",
        "target_device_address": "00:11:22:33:44:55",
        "selected_device_name": None,
        "selected_device_address": None,
        "notify_char_uuid": None,
        "last_packet_at": None,
        "last_error": None,
        "latest_bpm": None,
    }

