from __future__ import annotations

from fastapi.testclient import TestClient

from intiface_bridge.api.server import create_app
from intiface_bridge.config import load_settings
from intiface_bridge.errors import BridgeError, ErrorCode
from intiface_bridge.models import BackendHealth, CommandResult
from intiface_bridge.sensors import HeartRateSample
from intiface_bridge.service import BridgeService


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

    async def heart_rate_scan_devices(self):
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


class HeartRateLatestService(FakeHttpService):
    async def heart_rate_latest_sample(self):
        return HeartRateSample(
            bpm=91,
            measured_at="2026-06-18T00:00:00+00:00",
            sequence=2,
            rr_intervals_ms=[500.0],
            sensor_contact_detected=True,
            energy_expended=None,
            raw_hex="10480002",
        )


class FailingHeartRateConnectService(FakeHttpService):
    async def heart_rate_connect(
        self,
        *,
        device_name: str | None = None,
        device_address: str | None = None,
        notify_char_uuid: str | None = None,
    ) -> dict[str, object]:
        raise BridgeError(
            ErrorCode.CONNECT_FAILED,
            "连接心率设备失败。",
            backend="heart_rate",
            details={"device_name": device_name},
        )


class NoopBackend:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def health(self):
        raise AssertionError("not used in this test")

    async def list_devices(self):
        raise AssertionError("not used in this test")

    async def connect(self, device_name: str | None = None) -> CommandResult:
        raise AssertionError("not used in this test")

    async def disconnect(self):
        raise AssertionError("not used in this test")

    async def status(self):
        raise AssertionError("not used in this test")

    async def set_strength(self, value: int):
        raise AssertionError("not used in this test")

    async def stop(self):
        raise AssertionError("not used in this test")


class MissingTargetHeartRateCollector:
    def __init__(
        self,
        *,
        device_name: str | None = None,
        device_address: str | None = None,
        notify_char_uuid: str | None = None,
        scan_timeout: float = 8.0,
    ) -> None:
        self.device_name = device_name
        self.device_address = device_address
        self.notify_char_uuid = notify_char_uuid
        self.scan_timeout = scan_timeout
        self.connected = False
        self.streaming = False

    async def connect(self) -> None:
        raise RuntimeError("请提供设备地址或设备名称。")


class NotFoundHeartRateCollector(MissingTargetHeartRateCollector):
    async def connect(self) -> None:
        raise RuntimeError('未找到名称包含 "Demo Band" 的 BLE 设备。')


class MultipleMatchesHeartRateCollector(MissingTargetHeartRateCollector):
    async def connect(self) -> None:
        raise RuntimeError(
            '找到多个名称包含 "Band" 的 BLE 设备：Band A (AA), Band B (BB)'
        )


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

    response = client.post("/connect", json={"device_name": "Demo"})

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

    response = client.post("/connect", json={"device_name": "Demo"})

    assert response.status_code == 404
    assert response.json() == {
        "ok": False,
        "backend": "custom",
        "code": "device_not_found",
        "error": "未找到匹配设备。",
        "details": {"query": "Demo"},
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


def test_heart_rate_latest_without_sample_returns_clear_response():
    service = FakeHttpService()
    client = TestClient(create_app(settings=service.settings, service=service))

    response = client.get("/heart-rate/latest")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "backend": "heart_rate",
        "has_sample": False,
        "sample": None,
    }


def test_heart_rate_latest_with_sample_returns_sample_payload():
    service = HeartRateLatestService()
    client = TestClient(create_app(settings=service.settings, service=service))

    response = client.get("/heart-rate/latest")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "backend": "heart_rate",
        "has_sample": True,
        "sample": {
            "bpm": 91,
            "measured_at": "2026-06-18T00:00:00+00:00",
            "sequence": 2,
            "rr_intervals_ms": [500.0],
            "sensor_contact_detected": True,
            "energy_expended": None,
            "raw_hex": "10480002",
        },
    }


def test_heart_rate_connect_and_disconnect_delegate_through_http():
    service = FakeHttpService()
    client = TestClient(create_app(settings=service.settings, service=service))

    connect_response = client.post(
        "/heart-rate/connect",
        json={
            "device_name": " Demo Band ",
            "device_address": "00:11:22:33:44:55",
            "notify_char_uuid": " 00002A37-0000-1000-8000-00805F9B34FB ",
        },
    )
    disconnect_response = client.post("/heart-rate/disconnect")

    assert connect_response.status_code == 200
    assert connect_response.json()["connected"] is True
    assert service.heart_rate_connected_with == {
        "device_name": "Demo Band",
        "device_address": "00:11:22:33:44:55",
        "notify_char_uuid": "00002A37-0000-1000-8000-00805F9B34FB",
    }
    assert disconnect_response.status_code == 200
    assert disconnect_response.json()["connected"] is False


def test_heart_rate_connect_uses_unified_bridge_error_shape():
    service = FailingHeartRateConnectService()
    client = TestClient(create_app(settings=service.settings, service=service))

    response = client.post("/heart-rate/connect", json={"device_name": "Demo Band"})

    assert response.status_code == 503
    assert response.json() == {
        "ok": False,
        "backend": "heart_rate",
        "code": "connect_failed",
        "error": "连接心率设备失败。",
    }


def test_heart_rate_connect_without_target_returns_400(monkeypatch):
    monkeypatch.setattr(
        "intiface_bridge.service.HeartRateCollector",
        MissingTargetHeartRateCollector,
    )
    settings = load_settings()
    service = BridgeService(settings, backend_registry={"intiface": NoopBackend})
    client = TestClient(create_app(settings=settings, service=service))

    response = client.post("/heart-rate/connect", json={})

    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "backend": "heart_rate",
        "code": "invalid_request",
        "error": "请提供设备地址或设备名称。",
    }


def test_heart_rate_connect_not_found_returns_404(monkeypatch):
    monkeypatch.setattr(
        "intiface_bridge.service.HeartRateCollector",
        NotFoundHeartRateCollector,
    )
    settings = load_settings()
    service = BridgeService(settings, backend_registry={"intiface": NoopBackend})
    client = TestClient(create_app(settings=settings, service=service))

    response = client.post("/heart-rate/connect", json={"device_name": "Demo Band"})

    assert response.status_code == 404
    assert response.json() == {
        "ok": False,
        "backend": "heart_rate",
        "code": "device_not_found",
        "error": '未找到名称包含 "Demo Band" 的 BLE 设备。',
    }


def test_heart_rate_connect_multiple_matches_returns_409(monkeypatch):
    monkeypatch.setattr(
        "intiface_bridge.service.HeartRateCollector",
        MultipleMatchesHeartRateCollector,
    )
    settings = load_settings()
    service = BridgeService(settings, backend_registry={"intiface": NoopBackend})
    client = TestClient(create_app(settings=settings, service=service))

    response = client.post("/heart-rate/connect", json={"device_name": "Band"})

    assert response.status_code == 409
    assert response.json() == {
        "ok": False,
        "backend": "heart_rate",
        "code": "multiple_devices_matched",
        "error": '找到多个名称包含 "Band" 的 BLE 设备：Band A (AA), Band B (BB)',
    }

