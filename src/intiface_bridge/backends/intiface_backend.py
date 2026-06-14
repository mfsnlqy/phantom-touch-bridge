from __future__ import annotations

import asyncio
from typing import Any

from buttplug import ButtplugClient, DeviceOutputCommand, OutputType

from intiface_bridge.config import AppSettings
from intiface_bridge.errors import BridgeError, ErrorCode, normalize_exception
from intiface_bridge.mappers.strength import is_stop_strength, map_to_continuous_strength
from intiface_bridge.models import BackendHealth, CommandResult, DeviceSummary
from intiface_bridge.utils.matching import require_single_name_match

DEFAULT_SCAN_SECONDS = 8.0
APP_NAME = "phantom-touch-bridge"


class IntifaceBackend:
    backend_name = "intiface"

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.server_url = settings.backend.server_url
        self.keep_connected = settings.backend.keep_connected
        self._client: ButtplugClient | None = None
        self._device: Any | None = None

    async def health(self) -> BackendHealth:
        probe_client = ButtplugClient(APP_NAME)
        try:
            await probe_client.connect(self.server_url)
        except Exception as error:
            raise normalize_exception(
                error,
                backend=self.backend_name,
                default_code=ErrorCode.BACKEND_UNAVAILABLE,
                default_message=f"无法连接到 Intiface 服务：{self.server_url}",
                details={"server_url": self.server_url},
            ) from error
        finally:
            try:
                await probe_client.disconnect()
            except Exception:
                pass

        return BackendHealth(
            ok=True,
            backend=self.backend_name,
            message="Intiface 服务探测成功。",
            details={
                "server_url": self.server_url,
                "client_connected": self._client is not None,
                "probe_disconnect": True,
            },
        )

    async def list_devices(self) -> list[DeviceSummary]:
        devices = await self._scan_devices()
        try:
            return [self._to_device_summary(device) for device in devices]
        finally:
            if not self.keep_connected and self._device is None:
                await self._disconnect_client()

    async def connect(self, device_name: str | None = None) -> CommandResult:
        query = (device_name or "").strip()
        if not query:
            raise BridgeError(
                ErrorCode.DEVICE_NOT_FOUND,
                "请先提供设备名称后再连接 Intiface 设备。",
                backend=self.backend_name,
            )

        devices = await self._scan_devices()
        device = require_single_name_match(
            devices,
            query,
            self._device_name,
            backend=self.backend_name,
        )
        self._device = device

        return CommandResult(
            backend=self.backend_name,
            action="connect",
            device_id=self._device_id(device),
            message=f'已选择设备 "{self._device_name(device)}"。',
            data={
                "device_name": self._device_name(device),
                "server_url": self.server_url,
            },
        )

    async def disconnect(self) -> CommandResult:
        selected_name = self._device_name(self._device) if self._device is not None else None
        self._device = None
        await self._disconnect_client()

        return CommandResult(
            backend=self.backend_name,
            action="disconnect",
            message=(
                f'已断开设备 "{selected_name}" 并关闭 Intiface 客户端。'
                if selected_name
                else "已关闭 Intiface 客户端。"
            ),
        )

    async def status(self) -> dict[str, Any]:
        return {
            "backend": self.backend_name,
            "server_url": self.server_url,
            "client_connected": self._client is not None,
            "selected_device": self._device_name(self._device),
            "selected_device_id": self._device_id(self._device),
            "keep_connected": self.keep_connected,
        }

    async def set_strength(self, value: int) -> CommandResult:
        device = self._require_connected_device()
        if not device.has_output(OutputType.VIBRATE):
            raise BridgeError(
                ErrorCode.CAPABILITY_NOT_SUPPORTED,
                f'设备 "{self._device_name(device)}" 不支持振动能力。',
                backend=self.backend_name,
                details={"device_name": self._device_name(device)},
            )

        if is_stop_strength(value):
            return await self.stop()

        strength = map_to_continuous_strength(value)
        try:
            await device.run_output(DeviceOutputCommand(OutputType.VIBRATE, strength))
        except Exception as error:
            raise normalize_exception(
                error,
                backend=self.backend_name,
                default_code=ErrorCode.COMMAND_FAILED,
                default_message="发送 Intiface 振动命令失败。",
                details={"device_name": self._device_name(device), "value": value},
            ) from error

        return CommandResult(
            backend=self.backend_name,
            action="set_strength",
            device_id=self._device_id(device),
            value=value,
            message=f'已将设备 "{self._device_name(device)}" 的强度设置为 {value}。',
            data={"fraction": strength},
        )

    async def stop(self) -> CommandResult:
        device = self._require_connected_device()
        try:
            await device.stop()
        except Exception as error:
            raise normalize_exception(
                error,
                backend=self.backend_name,
                default_code=ErrorCode.COMMAND_FAILED,
                default_message="发送 Intiface 停止命令失败。",
                details={"device_name": self._device_name(device)},
            ) from error

        return CommandResult(
            backend=self.backend_name,
            action="stop",
            device_id=self._device_id(device),
            message=f'已停止设备 "{self._device_name(device)}"。',
        )

    async def _ensure_client(self) -> ButtplugClient:
        if self._client is not None:
            return self._client

        client = ButtplugClient(APP_NAME)
        try:
            await client.connect(self.server_url)
        except Exception as error:
            raise normalize_exception(
                error,
                backend=self.backend_name,
                default_code=ErrorCode.BACKEND_UNAVAILABLE,
                default_message=f"无法连接到 Intiface 服务：{self.server_url}",
                details={"server_url": self.server_url},
            ) from error

        self._client = client
        return client

    async def _scan_devices(self, scan_seconds: float = DEFAULT_SCAN_SECONDS) -> list[Any]:
        client = await self._ensure_client()
        try:
            await client.start_scanning()
            try:
                await asyncio.sleep(scan_seconds)
            finally:
                await client.stop_scanning()
        except Exception as error:
            raise normalize_exception(
                error,
                backend=self.backend_name,
                default_code=ErrorCode.COMMAND_FAILED,
                default_message="通过 Intiface 扫描设备失败。",
                details={"server_url": self.server_url, "scan_seconds": scan_seconds},
            ) from error

        devices = list(client.devices.values())
        return devices

    async def _disconnect_client(self) -> None:
        if self._client is None:
            return

        try:
            await self._client.disconnect()
        except Exception as error:
            raise normalize_exception(
                error,
                backend=self.backend_name,
                default_code=ErrorCode.COMMAND_FAILED,
                default_message="断开 Intiface 连接失败。",
            ) from error
        finally:
            self._client = None

    def _require_connected_device(self) -> Any:
        if self._device is None:
            raise BridgeError(
                ErrorCode.NOT_CONNECTED,
                "当前没有已连接的 Intiface 设备，请先执行 connect。",
                backend=self.backend_name,
            )
        return self._device

    def _to_device_summary(self, device: Any) -> DeviceSummary:
        return DeviceSummary(
            id=self._device_id(device),
            name=self._device_name(device),
            connected=self._device_id(device) == self._device_id(self._device),
            backend=self.backend_name,
            capabilities=self._device_capabilities(device),
        )

    def _device_capabilities(self, device: Any) -> list[str]:
        capabilities: list[str] = []
        if device.has_output(OutputType.VIBRATE):
            capabilities.append("vibrate")
        if device.has_output(OutputType.ROTATE):
            capabilities.append("rotate")
        if device.has_output(OutputType.POSITION_WITH_DURATION):
            capabilities.append("linear")
        return capabilities

    def _device_id(self, device: Any | None) -> str | None:
        if device is None:
            return None
        raw_id = getattr(device, "index", None)
        if raw_id is None:
            raw_id = getattr(device, "id", None)
        if raw_id is None:
            raw_id = self._device_name(device)
        return str(raw_id) if raw_id is not None else None

    def _device_name(self, device: Any | None) -> str | None:
        if device is None:
            return None
        name = getattr(device, "name", None)
        normalized = str(name).strip() if name is not None else ""
        if normalized:
            return normalized
        device_id = self._device_id_without_fallback(device)
        suffix = device_id if device_id is not None else "unnamed"
        return f"Unknown Device ({suffix})"

    def _device_id_without_fallback(self, device: Any | None) -> str | None:
        if device is None:
            return None
        raw_id = getattr(device, "index", None)
        if raw_id is None:
            raw_id = getattr(device, "id", None)
        return str(raw_id) if raw_id is not None else None

