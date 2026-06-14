from __future__ import annotations

import asyncio
from typing import Any

from bleak import BleakClient, BleakScanner

from intiface_bridge.config import AppSettings
from intiface_bridge.errors import BridgeError, ErrorCode, normalize_exception
from intiface_bridge.mappers.strength import validate_strength
from intiface_bridge.models import BackendHealth, CommandResult, DeviceSummary
from intiface_bridge.utils.matching import require_single_name_match

DEFAULT_SERVICE_UUID = "00009000-0000-1000-8000-00805f9b34fb"
DEFAULT_NOTIFY_UUID = "00009001-0000-1000-8000-00805f9b34fb"
DEFAULT_WRITE_UUID = "00009002-0000-1000-8000-00805f9b34fb"
DEFAULT_PACKET_PREFIX = bytes.fromhex("A09001")
DEFAULT_SCAN_SECONDS = 8.0


class CustomBackend:
    backend_name = "custom"

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.service_uuid = DEFAULT_SERVICE_UUID
        self.notify_uuid = settings.backend.notify_uuid.strip() or DEFAULT_NOTIFY_UUID
        self.write_uuid = settings.backend.write_uuid.strip() or DEFAULT_WRITE_UUID
        self.packet_prefix = DEFAULT_PACKET_PREFIX
        self.keep_connected = settings.backend.keep_connected
        self.default_device_name = settings.backend.default_device_name.strip()
        self.default_device_address = settings.backend.default_device_address.strip()

        self.client: BleakClient | None = None
        self.device_name: str | None = None
        self.device_address: str | None = None
        self.last_payload: str | None = None
        self.last_value: int | None = None
        self.last_notification: str | None = None
        self.notification_count = 0
        self.last_error: str | None = None
        self._lock = asyncio.Lock()

    async def health(self) -> BackendHealth:
        return BackendHealth(
            ok=True,
            backend=self.backend_name,
            message="Custom BLE backend 已就绪。",
            details={
                "default_device_name": self.default_device_name,
                "keep_connected": self.keep_connected,
                "custom_uuid_overrides": bool(
                    self.settings.backend.notify_uuid.strip()
                    or self.settings.backend.write_uuid.strip()
                ),
            },
        )

    async def list_devices(self) -> list[DeviceSummary]:
        try:
            devices = await BleakScanner.discover(timeout=DEFAULT_SCAN_SECONDS, return_adv=True)
        except Exception as error:
            raise normalize_exception(
                error,
                backend=self.backend_name,
                default_code=ErrorCode.COMMAND_FAILED,
                default_message="扫描 BLE 设备失败。",
            ) from error

        summaries: list[DeviceSummary] = []
        for address, (device, adv) in sorted(devices.items()):
            name = self._display_name(device.name or adv.local_name, address)
            summaries.append(
                DeviceSummary(
                    id=address,
                    name=name,
                    connected=bool(self.client and self.client.is_connected and address == self.device_address),
                    backend=self.backend_name,
                    capabilities=["vibrate"] if self._is_supported_candidate(name, address) else [],
                )
            )
        return summaries

    async def connect(self, device_name: str | None = None) -> CommandResult:
        query = (device_name or "").strip()
        fallback_name = self.default_device_name.strip()
        fallback_address = self.default_device_address.strip()
        if not query and not fallback_name and not fallback_address:
            raise BridgeError(
                ErrorCode.DEVICE_NOT_FOUND,
                "custom backend 缺少默认设备名称和默认设备地址，无法建立连接。",
                backend=self.backend_name,
            )

        async with self._lock:
            await self._connect_locked(
                query or None,
                fallback_name=fallback_name or None,
                fallback_address=fallback_address or None,
            )
            return CommandResult(
                backend=self.backend_name,
                action="connect",
                device_id=self.device_address,
                message=f'已连接设备 "{self.device_name}"。',
                data={
                    "device_name": self.device_name,
                    "device_address": self.device_address,
                },
            )

    async def disconnect(self) -> CommandResult:
        async with self._lock:
            await self._disconnect_locked()
            return CommandResult(
                backend=self.backend_name,
                action="disconnect",
                device_id=self.device_address,
                message="已断开 custom BLE 设备。",
            )

    async def status(self) -> dict[str, Any]:
        return {
            "backend": self.backend_name,
            "connected": bool(self.client and self.client.is_connected),
            "device_name": self.device_name or self.default_device_name,
            "device_address": self.device_address or self.default_device_address,
            "last_value": self.last_value,
            "notification_count": self.notification_count,
            "last_error": self.last_error,
            "keep_connected": self.keep_connected,
        }

    async def set_strength(self, value: int) -> CommandResult:
        payload = self._build_percent_payload(value)
        await self._write_payload(payload)
        self.last_value = value
        return CommandResult(
            backend=self.backend_name,
            action="set_strength",
            device_id=self.device_address,
            value=value,
            message=f'已将设备 "{self.device_name}" 的强度设置为 {value}。',
        )

    async def stop(self) -> CommandResult:
        payload = self._build_percent_payload(0)
        await self._write_payload(payload)
        self.last_value = 0
        return CommandResult(
            backend=self.backend_name,
            action="stop",
            device_id=self.device_address,
            message=f'已停止设备 "{self.device_name or self.default_device_name}"。',
        )

    async def _connect_locked(
        self,
        query: str | None,
        *,
        fallback_name: str | None = None,
        fallback_address: str | None = None,
    ) -> None:
        target_query = (query or fallback_name or fallback_address or "").strip()
        if self.client and self.client.is_connected:
            if (
                self.device_name
                and target_query
                and target_query.lower() in self.device_name.lower()
            ):
                return
            if self.device_address and target_query and self.device_address.lower() == target_query.lower():
                return
            await self._disconnect_locked()

        device = await self._find_device(
            query=query,
            fallback_name=fallback_name,
            fallback_address=fallback_address,
        )
        target_name = self._display_name(device.name, device.address)
        target_address = device.address

        client = BleakClient(device, disconnected_callback=self._handle_disconnect)
        try:
            await client.connect()
            if not client.is_connected:
                raise RuntimeError("BLE 连接未建立。")
            await client.start_notify(self.notify_uuid, self._handle_notification)
        except Exception as error:
            self.last_error = str(error)
            self.device_name = None
            self.device_address = None
            try:
                if client.is_connected:
                    await client.disconnect()
            except Exception:
                pass
            raise normalize_exception(
                error,
                backend=self.backend_name,
                default_code=ErrorCode.CONNECT_FAILED,
                default_message="连接 custom BLE 设备失败。",
                details={"query": target_query, "device_address": getattr(device, "address", None)},
            ) from error

        self.client = client
        self.device_name = target_name
        self.device_address = target_address
        self.last_error = None

    async def _disconnect_locked(self) -> None:
        if self.client and self.client.is_connected:
            try:
                await self.client.stop_notify(self.notify_uuid)
            except Exception:
                pass
            try:
                await self.client.disconnect()
            except Exception as error:
                raise normalize_exception(
                    error,
                    backend=self.backend_name,
                    default_code=ErrorCode.COMMAND_FAILED,
                    default_message="断开 custom BLE 设备失败。",
                ) from error
        self.client = None
        self.device_name = None
        self.device_address = None

    async def _find_device(
        self,
        *,
        query: str | None,
        fallback_name: str | None,
        fallback_address: str | None,
    ):
        address_query = self._resolve_address_query(query, fallback_address)
        if address_query is not None:
            device = await self._find_device_by_address(address_query)
            if device is not None:
                return device
            raise BridgeError(
                ErrorCode.DEVICE_NOT_FOUND,
                f'未找到地址为 "{address_query}" 的 BLE 设备。',
                backend=self.backend_name,
                details={"address": address_query},
            )

        name_query = self._resolve_name_query(query, fallback_name)
        if not name_query:
            missing_target = address_query or fallback_address or fallback_name or query
            raise BridgeError(
                ErrorCode.DEVICE_NOT_FOUND,
                f'未找到可用于连接的设备目标："{missing_target or "unknown"}"。',
                backend=self.backend_name,
            )

        devices = await self.list_devices()
        matched_summary = require_single_name_match(
            devices,
            name_query,
            lambda item: item.name,
            backend=self.backend_name,
        )
        address = matched_summary.id
        if not address:
            raise BridgeError(
                ErrorCode.DEVICE_NOT_FOUND,
                f'无法解析设备 "{matched_summary.name}" 的蓝牙地址。',
                backend=self.backend_name,
            )

        device = await self._find_device_by_address(address)
        if device is not None:
            return device

        raise BridgeError(
            ErrorCode.DEVICE_NOT_FOUND,
            f'未找到地址为 "{address}" 的 BLE 设备。',
            backend=self.backend_name,
            details={"address": address},
        )

    async def _find_device_by_address(self, address: str):
        try:
            device = await BleakScanner.find_device_by_address(address, timeout=10.0)
        except Exception as error:
            raise normalize_exception(
                error,
                backend=self.backend_name,
                default_code=ErrorCode.CONNECT_FAILED,
                default_message="按地址查找 BLE 设备失败。",
                details={"address": address},
            ) from error
        return device

    async def _write_payload(self, payload: bytes) -> None:
        await self._ensure_connected()
        async with self._lock:
            if not self.client or not self.client.is_connected:
                raise BridgeError(
                    ErrorCode.NOT_CONNECTED,
                    "custom BLE 设备尚未连接，请先执行 connect。",
                    backend=self.backend_name,
                )
            try:
                await self.client.write_gatt_char(self.write_uuid, payload, response=False)
            except Exception as error:
                self.last_error = str(error)
                raise normalize_exception(
                    error,
                    backend=self.backend_name,
                    default_code=ErrorCode.COMMAND_FAILED,
                    default_message="写入 custom BLE payload 失败。",
                    details={"payload": self._format_hex(payload)},
                ) from error
            self.last_payload = self._format_hex(payload)
            self.last_error = None

    async def _ensure_connected(self) -> None:
        async with self._lock:
            if self.client and self.client.is_connected:
                return
            await self._connect_locked(
                self.device_address or self.device_name,
                fallback_name=self.default_device_name,
                fallback_address=self.default_device_address,
            )

    def _build_percent_payload(self, value: int) -> bytes:
        normalized = validate_strength(value)
        return self.packet_prefix + bytes([normalized])

    def _handle_disconnect(self, _: BleakClient) -> None:
        self.last_error = "BLE disconnected."

    def _handle_notification(self, _: Any, data: bytearray) -> None:
        self.last_notification = self._format_hex(bytes(data))
        self.notification_count += 1

    def _display_name(self, name: str | None, address: str | None) -> str:
        normalized = (name or "").strip()
        if normalized:
            return normalized
        return f"Unknown Device ({address or 'unknown'})"

    def _is_supported_candidate(self, name: str, address: str | None) -> bool:
        if address and address.lower() == self.default_device_address.lower():
            return True
        expected_name = self.default_device_name.strip().lower()
        if not expected_name:
            return False
        return expected_name in name.lower()

    def _resolve_address_query(
        self,
        query: str | None,
        fallback_address: str | None,
    ) -> str | None:
        normalized = (query or "").strip()
        if self._looks_like_address(normalized):
            return normalized
        if normalized:
            return None
        fallback = (fallback_address or "").strip()
        return fallback or None

    def _resolve_name_query(self, query: str | None, fallback_name: str | None) -> str | None:
        normalized = (query or "").strip()
        if normalized and not self._looks_like_address(normalized):
            return normalized
        fallback = (fallback_name or "").strip()
        return fallback or None

    def _looks_like_address(self, value: str) -> bool:
        if not value:
            return False
        parts = value.split(":")
        if len(parts) != 6:
            return False
        return all(len(part) == 2 for part in parts)

    def _format_hex(self, data: bytes) -> str:
        return data.hex().upper()
