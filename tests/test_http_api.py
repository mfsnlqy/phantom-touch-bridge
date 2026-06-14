from __future__ import annotations

from fastapi.testclient import TestClient

from intiface_bridge.api.server import create_app
from intiface_bridge.config import load_settings
from intiface_bridge.errors import BridgeError, ErrorCode
from intiface_bridge.models import BackendHealth, CommandResult


class FakeHttpService:
    def __init__(self, *, error_detail: str = "simple") -> None:
        self.settings = load_settings(
            env={
                "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
                "INTIFACE_BRIDGE_BACKEND_ERROR_DETAIL": error_detail,
            }
        )
        self.connected_with: str | None = None
        self.last_strength: int | None = None

    async def health(self) -> BackendHealth:
        return BackendHealth(
            ok=True,
            backend="custom",
            message="Custom backend is healthy.",
            details={"probe": "ok"},
        )

    async def status(self) -> dict[str, object]:
        raise AssertionError("not used in this test")

    async def list_devices(self):
        raise AssertionError("not used in this test")

    async def connect(self, device_name: str | None = None) -> CommandResult:
        self.connected_with = device_name
        return CommandResult(
            backend="custom",
            action="connect",
            device_id="device-1",
            message="connected",
            data={"device_name": device_name},
        )

    async def disconnect(self) -> CommandResult:
        raise AssertionError("not used in this test")

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
        raise AssertionError("not used in this test")


class FailingConnectService(FakeHttpService):
    async def connect(self, device_name: str | None = None) -> CommandResult:
        raise BridgeError(
            ErrorCode.DEVICE_NOT_FOUND,
            "未找到匹配设备。",
            backend="custom",
            details={"query": device_name},
        )


class FailingStrengthService(FakeHttpService):
    async def set_strength(self, value: int) -> CommandResult:
        raise BridgeError(
            ErrorCode.INVALID_STRENGTH,
            "强度超出范围。",
            backend="custom",
            details={"value": value},
        )


def test_get_health_returns_backend_health_contract():
    service = FakeHttpService()
    client = TestClient(create_app(settings=service.settings, service=service))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert response.json() == {
        "ok": True,
        "backend": "custom",
        "message": "Custom backend is healthy.",
        "details": {"probe": "ok"},
    }


def test_post_connect_returns_success_response_and_normalizes_blank_name():
    service = FakeHttpService()
    client = TestClient(create_app(settings=service.settings, service=service))

    response = client.post("/connect", json={"device_name": "   "})

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "backend": "custom",
        "action": "connect",
        "device_id": "device-1",
        "message": "connected",
        "data": {"device_name": None},
        "value": None,
    }
    assert service.connected_with is None


def test_post_set_strength_returns_success_response():
    service = FakeHttpService()
    client = TestClient(create_app(settings=service.settings, service=service))

    response = client.post("/set-strength", json={"value": 42})

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "backend": "custom",
        "action": "set_strength",
        "device_id": "device-1",
        "value": 42,
        "message": "ok",
        "data": None,
    }
    assert service.last_strength == 42


def test_post_connect_returns_unified_bridge_error_response():
    service = FailingConnectService()
    client = TestClient(create_app(settings=service.settings, service=service))

    response = client.post("/connect", json={"device_name": "DEMO"})

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert response.json() == {
        "ok": False,
        "backend": "custom",
        "code": "device_not_found",
        "error": "未找到匹配设备。",
    }


def test_post_connect_returns_verbose_bridge_error_details_when_enabled():
    service = FailingConnectService(error_detail="verbose")
    client = TestClient(create_app(settings=service.settings, service=service))

    response = client.post("/connect", json={"device_name": "DEMO"})

    assert response.status_code == 404
    assert response.json() == {
        "ok": False,
        "backend": "custom",
        "code": "device_not_found",
        "error": "未找到匹配设备。",
        "details": {"query": "DEMO"},
    }


def test_post_set_strength_validation_error_uses_unified_error_shape():
    service = FakeHttpService()
    client = TestClient(create_app(settings=service.settings, service=service))

    response = client.post("/set-strength", json={})

    assert response.status_code == 422
    assert response.json() == {
        "ok": False,
        "backend": "custom",
        "code": "command_failed",
        "error": "请求参数无效。",
    }


def test_post_set_strength_maps_invalid_strength_to_400():
    service = FailingStrengthService()
    client = TestClient(create_app(settings=service.settings, service=service))

    response = client.post("/set-strength", json={"value": 101})

    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "backend": "custom",
        "code": "invalid_strength",
        "error": "强度超出范围。",
    }
