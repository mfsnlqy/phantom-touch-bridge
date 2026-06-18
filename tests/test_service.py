from __future__ import annotations

import asyncio

from intiface_bridge.config import load_settings
from intiface_bridge.errors import BridgeError, ErrorCode
from intiface_bridge.models import CommandResult
from intiface_bridge.sensors import HeartRateSample
from intiface_bridge.service import BridgeService


class RecordingBackend:
    last_connect_arg: str | None = "__unset__"

    def __init__(self, settings) -> None:
        self.settings = settings

    async def health(self):
        raise AssertionError("not used in this test")

    async def list_devices(self):
        raise AssertionError("not used in this test")

    async def connect(self, device_name: str | None = None) -> CommandResult:
        type(self).last_connect_arg = device_name
        return CommandResult(
            backend=self.settings.backend.type,
            action="connect",
            device_id="device-1",
            message="ok",
        )

    async def disconnect(self):
        raise AssertionError("not used in this test")

    async def status(self):
        raise AssertionError("not used in this test")

    async def set_strength(self, value: int):
        raise AssertionError("not used in this test")

    async def stop(self):
        raise AssertionError("not used in this test")


class FakeHeartRateCollector:
    last_init_kwargs: dict[str, object] | None = None

    def __init__(
        self,
        *,
        device_name: str | None = None,
        device_address: str | None = None,
        notify_char_uuid: str | None = None,
        scan_timeout: float = 8.0,
    ) -> None:
        type(self).last_init_kwargs = {
            "device_name": device_name,
            "device_address": device_address,
            "notify_char_uuid": notify_char_uuid,
            "scan_timeout": scan_timeout,
        }
        self.device_name = device_name
        self.device_address = device_address
        self.notify_char_uuid = notify_char_uuid
        self.target_notify_char_uuid = notify_char_uuid
        self.scan_timeout = scan_timeout
        self.connected = False
        self.streaming = False
        self.selected_device_name: str | None = None
        self.selected_device_address: str | None = None
        self.latest_sample: HeartRateSample | None = None

    async def scan_devices(self, timeout: float | None = None):
        self.last_scan_timeout = timeout
        return [
            {
                "name": "Demo Band",
                "address": "00:11:22:33:44:55",
                "rssi": -40,
                "service_uuids": [],
            }
        ]

    async def connect(self) -> None:
        self.connected = True
        self.streaming = True
        self.selected_device_name = self.device_name or "Demo Band"
        self.selected_device_address = self.device_address or "00:11:22:33:44:55"
        self.latest_sample = HeartRateSample(
            bpm=88,
            measured_at="2026-06-18T00:00:00+00:00",
            sequence=1,
            rr_intervals_ms=[500.0],
            sensor_contact_detected=True,
            energy_expended=None,
            raw_hex="10480002",
        )

    async def disconnect(self) -> None:
        self.connected = False
        self.streaming = False
        self.selected_device_name = None
        self.selected_device_address = None
        self.notify_char_uuid = None
        self.latest_sample = None

    def status(self) -> dict[str, object]:
        return {
            "connected": self.connected,
            "streaming": self.streaming,
            "target_device_name": self.device_name,
            "target_device_address": self.device_address,
            "selected_device_name": self.selected_device_name,
            "selected_device_address": self.selected_device_address,
            "notify_char_uuid": self.notify_char_uuid,
            "last_packet_at": None,
            "last_error": None,
            "latest_bpm": self.latest_sample.bpm if self.latest_sample else None,
        }

    def get_latest_sample(self) -> HeartRateSample | None:
        return self.latest_sample


class MissingTargetHeartRateCollector(FakeHeartRateCollector):
    async def connect(self) -> None:
        raise RuntimeError("请提供设备地址或设备名称。")


class NotFoundHeartRateCollector(FakeHeartRateCollector):
    async def connect(self) -> None:
        raise RuntimeError('未找到名称包含 "Demo Band" 的 BLE 设备。')


class MultipleMatchesHeartRateCollector(FakeHeartRateCollector):
    async def connect(self) -> None:
        raise RuntimeError(
            '找到多个名称包含 "Band" 的 BLE 设备：Band A (AA), Band B (BB)'
        )


def test_custom_connect_preserves_backend_address_fallback():
    RecordingBackend.last_connect_arg = "__unset__"
    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
            "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME": "Demo",
            "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_ADDRESS": "00:11:22:33:44:55",
        }
    )
    service = BridgeService(settings, backend_registry={"custom": RecordingBackend})

    asyncio.run(service.connect())

    assert RecordingBackend.last_connect_arg is None


def test_connect_uses_default_name_when_no_default_address_exists():
    RecordingBackend.last_connect_arg = "__unset__"
    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_BACKEND_TYPE": "intiface",
            "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME": "Demo Device",
        }
    )
    service = BridgeService(settings, backend_registry={"intiface": RecordingBackend})

    asyncio.run(service.connect())

    assert RecordingBackend.last_connect_arg == "Demo Device"


def test_heart_rate_status_uses_configured_defaults(monkeypatch):
    FakeHeartRateCollector.last_init_kwargs = None
    monkeypatch.setattr("intiface_bridge.service.HeartRateCollector", FakeHeartRateCollector)
    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_HEART_RATE_DEVICE_NAME": "Demo Band",
            "INTIFACE_BRIDGE_HEART_RATE_SCAN_TIMEOUT": "12.5",
        }
    )
    service = BridgeService(settings, backend_registry={"intiface": RecordingBackend})

    status = asyncio.run(service.heart_rate_status())

    assert status["target_device_name"] == "Demo Band"
    assert status["connected"] is False
    assert FakeHeartRateCollector.last_init_kwargs == {
        "device_name": "Demo Band",
        "device_address": None,
        "notify_char_uuid": None,
        "scan_timeout": 12.5,
    }


def test_heart_rate_scan_connect_latest_and_disconnect(monkeypatch):
    monkeypatch.setattr("intiface_bridge.service.HeartRateCollector", FakeHeartRateCollector)
    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_HEART_RATE_DEVICE_NAME": "Demo Band",
            "INTIFACE_BRIDGE_HEART_RATE_SCAN_TIMEOUT": "9.0",
        }
    )
    service = BridgeService(settings, backend_registry={"intiface": RecordingBackend})

    devices = asyncio.run(service.heart_rate_scan_devices(timeout=3.0))
    connected_status = asyncio.run(
        service.heart_rate_connect(
            device_name="Demo Band",
            device_address="00:11:22:33:44:55",
            notify_char_uuid="00002A37-0000-1000-8000-00805F9B34FB",
        )
    )
    latest_sample = asyncio.run(service.heart_rate_latest_sample())
    disconnected_status = asyncio.run(service.heart_rate_disconnect())

    assert devices == [
        {
            "name": "Demo Band",
            "address": "00:11:22:33:44:55",
            "rssi": -40,
            "service_uuids": [],
        }
    ]
    assert connected_status["connected"] is True
    assert connected_status["selected_device_name"] == "Demo Band"
    assert connected_status["selected_device_address"] == "00:11:22:33:44:55"
    assert (
        connected_status["notify_char_uuid"]
        == "00002A37-0000-1000-8000-00805F9B34FB"
    )
    assert latest_sample is not None
    assert latest_sample.bpm == 88
    assert disconnected_status["connected"] is False
    assert disconnected_status["streaming"] is False
    assert disconnected_status["selected_device_name"] is None
    assert disconnected_status["selected_device_address"] is None
    assert disconnected_status["notify_char_uuid"] is None
    assert disconnected_status["latest_bpm"] is None


def test_heart_rate_connect_maps_missing_target_to_invalid_request(monkeypatch):
    monkeypatch.setattr(
        "intiface_bridge.service.HeartRateCollector",
        MissingTargetHeartRateCollector,
    )
    settings = load_settings()
    service = BridgeService(settings, backend_registry={"intiface": RecordingBackend})

    try:
        asyncio.run(service.heart_rate_connect())
    except BridgeError as error:
        assert error.backend == "heart_rate"
        assert error.code == ErrorCode.INVALID_REQUEST
        assert error.message == "请提供设备地址或设备名称。"
    else:
        raise AssertionError("expected BridgeError")


def test_heart_rate_connect_maps_not_found_to_device_not_found(monkeypatch):
    monkeypatch.setattr(
        "intiface_bridge.service.HeartRateCollector",
        NotFoundHeartRateCollector,
    )
    settings = load_settings()
    service = BridgeService(settings, backend_registry={"intiface": RecordingBackend})

    try:
        asyncio.run(service.heart_rate_connect(device_name="Demo Band"))
    except BridgeError as error:
        assert error.backend == "heart_rate"
        assert error.code == ErrorCode.DEVICE_NOT_FOUND
        assert error.message == '未找到名称包含 "Demo Band" 的 BLE 设备。'
    else:
        raise AssertionError("expected BridgeError")


def test_heart_rate_connect_maps_multiple_matches_to_conflict(monkeypatch):
    monkeypatch.setattr(
        "intiface_bridge.service.HeartRateCollector",
        MultipleMatchesHeartRateCollector,
    )
    settings = load_settings()
    service = BridgeService(settings, backend_registry={"intiface": RecordingBackend})

    try:
        asyncio.run(service.heart_rate_connect(device_name="Band"))
    except BridgeError as error:
        assert error.backend == "heart_rate"
        assert error.code == ErrorCode.MULTIPLE_DEVICES_MATCHED
        assert error.message.startswith('找到多个名称包含 "Band" 的 BLE 设备')
    else:
        raise AssertionError("expected BridgeError")

