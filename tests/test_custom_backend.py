from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from intiface_bridge.backends.custom_backend import CustomBackend
from intiface_bridge.config import load_settings
from intiface_bridge.errors import BridgeError, ErrorCode


class FakeBleakClient:
    def __init__(self, device, disconnected_callback=None):
        self.device = device
        self.disconnected_callback = disconnected_callback
        self.is_connected = False

    async def connect(self):
        self.is_connected = True

    async def start_notify(self, uuid, callback):
        self.notify_uuid = uuid
        self.callback = callback

    async def stop_notify(self, uuid):
        self.stopped_notify_uuid = uuid

    async def write_gatt_char(self, uuid, payload, response=False):
        self.last_write = (uuid, payload, response)

    async def disconnect(self):
        self.is_connected = False


def test_list_devices_only_marks_supported_candidate(monkeypatch):
    async def fake_discover(timeout=8.0, return_adv=True):
        return {
            "AA:BB:CC:DD:EE:FF": (
                SimpleNamespace(name="Demo Device", address="AA:BB:CC:DD:EE:FF"),
                SimpleNamespace(local_name="Demo Device"),
            ),
            "11:22:33:44:55:66": (
                SimpleNamespace(name="Other Device", address="11:22:33:44:55:66"),
                SimpleNamespace(local_name="Other Device"),
            ),
        }

    monkeypatch.setattr(
        "intiface_bridge.backends.custom_backend.BleakScanner.discover",
        fake_discover,
    )

    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
            "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME": "DEMO",
        }
    )
    backend = CustomBackend(settings)

    devices = asyncio.run(backend.list_devices())

    assert [(item.name, item.capabilities) for item in devices] == [
        ("Other Device", []),
        ("Demo Device", ["vibrate"]),
    ]


def test_set_strength_rejects_bool(monkeypatch):
    async def fake_discover(timeout=8.0, return_adv=True):
        return {
            "AA:BB:CC:DD:EE:FF": (
                SimpleNamespace(name="Demo Device", address="AA:BB:CC:DD:EE:FF"),
                SimpleNamespace(local_name="Demo Device"),
            ),
        }

    async def fake_find_device_by_address(address, timeout=10.0):
        return SimpleNamespace(name="Demo Device", address=address)

    monkeypatch.setattr("intiface_bridge.backends.custom_backend.BleakClient", FakeBleakClient)
    monkeypatch.setattr(
        "intiface_bridge.backends.custom_backend.BleakScanner.discover",
        fake_discover,
    )
    monkeypatch.setattr(
        "intiface_bridge.backends.custom_backend.BleakScanner.find_device_by_address",
        fake_find_device_by_address,
    )

    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
            "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME": "DEMO",
        }
    )
    backend = CustomBackend(settings)
    asyncio.run(backend.connect("DEMO"))

    with pytest.raises(BridgeError) as exc_info:
        asyncio.run(backend.set_strength(True))

    assert exc_info.value.code == ErrorCode.INVALID_STRENGTH


def test_custom_backend_keeps_empty_default_device_name():
    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
            "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME": "   ",
        }
    )

    backend = CustomBackend(settings)
    health = asyncio.run(backend.health())

    assert backend.default_device_name == ""
    assert health.details["default_device_name"] == ""


def test_failed_connect_clears_selected_device_state(monkeypatch):
    class FailingNotifyBleakClient(FakeBleakClient):
        async def start_notify(self, uuid, callback):
            raise RuntimeError("notify failed")

    async def fake_discover(timeout=8.0, return_adv=True):
        return {
            "AA:BB:CC:DD:EE:FF": (
                SimpleNamespace(name="Demo Device", address="AA:BB:CC:DD:EE:FF"),
                SimpleNamespace(local_name="Demo Device"),
            ),
        }

    async def fake_find_device_by_address(address, timeout=10.0):
        return SimpleNamespace(name="Demo Device", address=address)

    monkeypatch.setattr(
        "intiface_bridge.backends.custom_backend.BleakClient",
        FailingNotifyBleakClient,
    )
    monkeypatch.setattr(
        "intiface_bridge.backends.custom_backend.BleakScanner.discover",
        fake_discover,
    )
    monkeypatch.setattr(
        "intiface_bridge.backends.custom_backend.BleakScanner.find_device_by_address",
        fake_find_device_by_address,
    )

    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
            "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME": "DEMO",
        }
    )
    backend = CustomBackend(settings)

    with pytest.raises(BridgeError) as exc_info:
        asyncio.run(backend.connect("DEMO"))

    assert exc_info.value.code == ErrorCode.CONNECT_FAILED
    assert backend.device_name is None
    assert backend.device_address is None


def test_connect_address_failure_does_not_fallback_to_name_match(monkeypatch):
    async def fake_discover(timeout=8.0, return_adv=True):
        return {
            "11:22:33:44:55:66": (
                SimpleNamespace(name="Demo Device", address="11:22:33:44:55:66"),
                SimpleNamespace(local_name="Demo Device"),
            ),
        }

    async def fake_find_device_by_address(address, timeout=10.0):
        return None

    monkeypatch.setattr(
        "intiface_bridge.backends.custom_backend.BleakScanner.discover",
        fake_discover,
    )
    monkeypatch.setattr(
        "intiface_bridge.backends.custom_backend.BleakScanner.find_device_by_address",
        fake_find_device_by_address,
    )

    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
            "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME": "DEMO",
        }
    )
    backend = CustomBackend(settings)

    with pytest.raises(BridgeError) as exc_info:
        asyncio.run(backend.connect("AA:BB:CC:DD:EE:FF"))

    assert exc_info.value.code == ErrorCode.DEVICE_NOT_FOUND
    assert 'AA:BB:CC:DD:EE:FF' in str(exc_info.value)
    assert backend.device_name is None
    assert backend.device_address is None


def test_custom_backend_happy_path_connect_status_set_strength_stop(monkeypatch):
    async def fake_discover(timeout=8.0, return_adv=True):
        return {
            "AA:BB:CC:DD:EE:FF": (
                SimpleNamespace(name="Demo Device", address="AA:BB:CC:DD:EE:FF"),
                SimpleNamespace(local_name="Demo Device"),
            ),
        }

    async def fake_find_device_by_address(address, timeout=10.0):
        return SimpleNamespace(name="Demo Device", address=address)

    monkeypatch.setattr("intiface_bridge.backends.custom_backend.BleakClient", FakeBleakClient)
    monkeypatch.setattr(
        "intiface_bridge.backends.custom_backend.BleakScanner.discover",
        fake_discover,
    )
    monkeypatch.setattr(
        "intiface_bridge.backends.custom_backend.BleakScanner.find_device_by_address",
        fake_find_device_by_address,
    )

    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
            "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME": "DEMO",
        }
    )
    backend = CustomBackend(settings)

    connect_result = asyncio.run(backend.connect("DEMO"))
    status_after_connect = asyncio.run(backend.status())
    set_result = asyncio.run(backend.set_strength(42))
    write_after_set = backend.client.last_write
    stop_result = asyncio.run(backend.stop())
    write_after_stop = backend.client.last_write
    status_after_stop = asyncio.run(backend.status())

    assert connect_result.action == "connect"
    assert connect_result.device_id == "AA:BB:CC:DD:EE:FF"
    assert status_after_connect["connected"] is True
    assert status_after_connect["device_name"] == "Demo Device"
    assert status_after_connect["device_address"] == "AA:BB:CC:DD:EE:FF"

    assert set_result.action == "set_strength"
    assert set_result.value == 42
    assert write_after_set == (
        backend.write_uuid,
        bytes.fromhex("A090012A"),
        False,
    )

    assert stop_result.action == "stop"
    assert write_after_stop == (
        backend.write_uuid,
        bytes.fromhex("A0900100"),
        False,
    )
    assert status_after_stop["connected"] is True
    assert status_after_stop["last_value"] == 0


def test_custom_backend_respects_custom_uuid_overrides(monkeypatch):
    async def fake_discover(timeout=8.0, return_adv=True):
        return {
            "AA:BB:CC:DD:EE:FF": (
                SimpleNamespace(name="Demo Device", address="AA:BB:CC:DD:EE:FF"),
                SimpleNamespace(local_name="Demo Device"),
            ),
        }

    async def fake_find_device_by_address(address, timeout=10.0):
        return SimpleNamespace(name="Demo Device", address=address)

    monkeypatch.setattr("intiface_bridge.backends.custom_backend.BleakClient", FakeBleakClient)
    monkeypatch.setattr(
        "intiface_bridge.backends.custom_backend.BleakScanner.discover",
        fake_discover,
    )
    monkeypatch.setattr(
        "intiface_bridge.backends.custom_backend.BleakScanner.find_device_by_address",
        fake_find_device_by_address,
    )

    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
            "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME": "DEMO",
            "INTIFACE_BRIDGE_BACKEND_NOTIFY_UUID": "0000DEAD-0000-1000-8000-00805F9B34FB",
            "INTIFACE_BRIDGE_BACKEND_WRITE_UUID": "0000BEEF-0000-1000-8000-00805F9B34FB",
        }
    )
    backend = CustomBackend(settings)

    asyncio.run(backend.connect("DEMO"))
    asyncio.run(backend.set_strength(42))

    assert backend.notify_uuid == "0000DEAD-0000-1000-8000-00805F9B34FB"
    assert backend.write_uuid == "0000BEEF-0000-1000-8000-00805F9B34FB"
    assert backend.client.notify_uuid == "0000DEAD-0000-1000-8000-00805F9B34FB"
    assert backend.client.last_write == (
        "0000BEEF-0000-1000-8000-00805F9B34FB",
        bytes.fromhex("A090012A"),
        False,
    )


def test_custom_backend_health_reports_uuid_override_state():
    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
            "INTIFACE_BRIDGE_BACKEND_NOTIFY_UUID": "0000DEAD-0000-1000-8000-00805F9B34FB",
        }
    )
    backend = CustomBackend(settings)

    health = asyncio.run(backend.health())

    assert health.details == {
        "default_device_name": "",
        "keep_connected": True,
        "custom_uuid_overrides": True,
    }
