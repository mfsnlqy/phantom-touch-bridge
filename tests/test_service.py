from __future__ import annotations

import asyncio

from intiface_bridge.config import load_settings
from intiface_bridge.models import CommandResult
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


def test_custom_connect_preserves_backend_address_fallback():
    RecordingBackend.last_connect_arg = "__unset__"
    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
            "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME": "DEMO",
            "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_ADDRESS": "AA:BB:CC:DD:EE:FF",
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
