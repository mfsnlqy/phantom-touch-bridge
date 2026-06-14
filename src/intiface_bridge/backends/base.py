from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeAlias

from intiface_bridge.config import AppSettings
from intiface_bridge.models import BackendHealth, CommandResult, DeviceSummary


class DeviceBackend(Protocol):
    async def health(self) -> BackendHealth: ...

    async def list_devices(self) -> list[DeviceSummary]: ...

    async def connect(self, device_name: str | None = None) -> CommandResult: ...

    async def disconnect(self) -> CommandResult: ...

    async def status(self) -> dict[str, Any]: ...

    async def set_strength(self, value: int) -> CommandResult: ...

    async def stop(self) -> CommandResult: ...


BackendFactory: TypeAlias = Callable[[AppSettings], DeviceBackend]
