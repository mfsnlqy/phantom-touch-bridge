from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from intiface_bridge.backends import get_default_backend_registry
from intiface_bridge.backends.base import BackendFactory, DeviceBackend
from intiface_bridge.config import AppSettings
from intiface_bridge.errors import (
    BridgeError,
    ErrorCode,
    error_result_from_exception,
    normalize_exception,
)
from intiface_bridge.models import BackendHealth, CommandResult, DeviceSummary, ErrorResult
from intiface_bridge.sensors import HeartRateCollector, HeartRateSample, normalize_uuid

T = TypeVar("T")


class BridgeService:
    def __init__(
        self,
        settings: AppSettings,
        *,
        backend_registry: dict[str, BackendFactory] | None = None,
    ) -> None:
        self.settings = settings
        self._backend_registry: dict[str, BackendFactory] = (
            backend_registry.copy()
            if backend_registry is not None
            else get_default_backend_registry()
        )
        self._backend: DeviceBackend | None = None
        self._heart_rate_collector: HeartRateCollector | None = None

    @property
    def backend_type(self) -> str:
        return self.settings.backend.type

    @property
    def heart_rate_backend_type(self) -> str:
        return "heart_rate"

    @property
    def default_device_name(self) -> str | None:
        device_name = self.settings.backend.default_device_name.strip()
        return device_name or None

    @property
    def include_error_details(self) -> bool:
        return self.settings.backend.error_detail == "verbose"

    def register_backend(self, name: str, factory: BackendFactory) -> None:
        self._backend_registry[name] = factory

    def _resolve_backend_factory(self) -> BackendFactory:
        factory = self._backend_registry.get(self.backend_type)
        if factory is None:
            raise BridgeError(
                ErrorCode.BACKEND_UNAVAILABLE,
                f'未注册后端 "{self.backend_type}"。',
                backend=self.backend_type,
            )
        return factory

    def _get_backend(self) -> DeviceBackend:
        if self._backend is None:
            factory = self._resolve_backend_factory()
            self._backend = factory(self.settings)
        return self._backend

    def _build_heart_rate_collector(
        self,
        *,
        device_name: str | None = None,
        device_address: str | None = None,
        notify_char_uuid: str | None = None,
    ) -> HeartRateCollector:
        resolved_device_name = (
            device_name
            if device_name is not None
            else self.settings.heart_rate.device_name
        )
        resolved_device_address = (
            device_address
            if device_address is not None
            else self.settings.heart_rate.device_address
        )
        resolved_notify_char_uuid = (
            notify_char_uuid
            if notify_char_uuid is not None
            else self.settings.heart_rate.notify_uuid
        )
        return HeartRateCollector(
            device_name=resolved_device_name or None,
            device_address=resolved_device_address or None,
            notify_char_uuid=resolved_notify_char_uuid or None,
            scan_timeout=self.settings.heart_rate.scan_timeout,
        )

    def _heart_rate_collector_matches(
        self,
        collector: HeartRateCollector,
        expected: HeartRateCollector,
    ) -> bool:
        current_notify = (
            normalize_uuid(collector.target_notify_char_uuid)
            if collector.target_notify_char_uuid
            else None
        )
        expected_notify = (
            normalize_uuid(expected.notify_char_uuid)
            if expected.notify_char_uuid
            else None
        )
        return (
            collector.device_name == expected.device_name
            and collector.device_address == expected.device_address
            and current_notify == expected_notify
            and collector.scan_timeout == expected.scan_timeout
        )

    async def _get_heart_rate_collector(
        self,
        *,
        device_name: str | None = None,
        device_address: str | None = None,
        notify_char_uuid: str | None = None,
    ) -> HeartRateCollector:
        if (
            self._heart_rate_collector is not None
            and device_name is None
            and device_address is None
            and notify_char_uuid is None
        ):
            return self._heart_rate_collector

        expected_collector = self._build_heart_rate_collector(
            device_name=device_name,
            device_address=device_address,
            notify_char_uuid=notify_char_uuid,
        )
        if self._heart_rate_collector is None:
            self._heart_rate_collector = expected_collector
            return self._heart_rate_collector

        if self._heart_rate_collector_matches(
            self._heart_rate_collector,
            expected_collector,
        ):
            return self._heart_rate_collector

        if self._heart_rate_collector.connected or self._heart_rate_collector.streaming:
            await self._heart_rate_collector.disconnect()
        self._heart_rate_collector = expected_collector
        return self._heart_rate_collector

    async def _run_backend_call(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        default_code: ErrorCode,
        default_message: str,
    ) -> T:
        try:
            return await operation()
        except Exception as error:
            raise normalize_exception(
                error,
                backend=self.backend_type,
                default_code=default_code,
                default_message=default_message,
            ) from error

    async def _run_heart_rate_call(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        default_code: ErrorCode,
        default_message: str,
    ) -> T:
        try:
            return await operation()
        except Exception as error:
            raise self._normalize_heart_rate_exception(
                error,
                default_code=default_code,
                default_message=default_message,
            ) from error

    def _normalize_heart_rate_exception(
        self,
        error: Exception,
        *,
        default_code: ErrorCode,
        default_message: str,
    ) -> BridgeError:
        if isinstance(error, BridgeError):
            return normalize_exception(
                error,
                backend=self.heart_rate_backend_type,
            )

        message = str(error).strip()
        details = {"exception_type": type(error).__name__}

        if message == "请提供设备地址或设备名称。":
            return BridgeError(
                ErrorCode.INVALID_REQUEST,
                message,
                backend=self.heart_rate_backend_type,
                details=details,
            )

        if message.startswith('未找到地址为 "') or message.startswith(
            '未找到名称包含 "'
        ) or (
            message.startswith('BLE 设备 "') and "在连接前消失。" in message
        ):
            return BridgeError(
                ErrorCode.DEVICE_NOT_FOUND,
                message,
                backend=self.heart_rate_backend_type,
                details=details,
            )

        if message.startswith('找到多个名称包含 "'):
            return BridgeError(
                ErrorCode.MULTIPLE_DEVICES_MATCHED,
                message,
                backend=self.heart_rate_backend_type,
                details=details,
            )

        if message.startswith('未找到通知特征 "') or message.startswith(
            "未找到标准 Heart Rate Measurement 特征。"
        ):
            return BridgeError(
                ErrorCode.INVALID_REQUEST,
                message,
                backend=self.heart_rate_backend_type,
                details=details,
            )

        return normalize_exception(
            error,
            backend=self.heart_rate_backend_type,
            default_code=default_code,
            default_message=default_message,
        )

    async def health(self) -> BackendHealth:
        backend = self._get_backend()
        return await self._run_backend_call(
            backend.health,
            default_code=ErrorCode.BACKEND_UNAVAILABLE,
            default_message="后端健康检查失败。",
        )

    async def list_devices(self) -> list[DeviceSummary]:
        backend = self._get_backend()
        return await self._run_backend_call(
            backend.list_devices,
            default_code=ErrorCode.COMMAND_FAILED,
            default_message="获取设备列表失败。",
        )

    async def connect(self, device_name: str | None = None) -> CommandResult:
        backend = self._get_backend()
        resolved_device_name = device_name
        if resolved_device_name is None and not self.settings.backend.default_device_address.strip():
            resolved_device_name = self.default_device_name
        return await self._run_backend_call(
            lambda: backend.connect(resolved_device_name),
            default_code=ErrorCode.CONNECT_FAILED,
            default_message="连接设备失败。",
        )

    async def disconnect(self) -> CommandResult:
        backend = self._get_backend()
        return await self._run_backend_call(
            backend.disconnect,
            default_code=ErrorCode.COMMAND_FAILED,
            default_message="断开设备失败。",
        )

    async def status(self) -> dict[str, Any]:
        backend = self._get_backend()
        return await self._run_backend_call(
            backend.status,
            default_code=ErrorCode.COMMAND_FAILED,
            default_message="获取后端状态失败。",
        )

    async def set_strength(self, value: int) -> CommandResult:
        backend = self._get_backend()
        return await self._run_backend_call(
            lambda: backend.set_strength(value),
            default_code=ErrorCode.COMMAND_FAILED,
            default_message="设置强度失败。",
        )

    async def stop(self) -> CommandResult:
        backend = self._get_backend()
        return await self._run_backend_call(
            backend.stop,
            default_code=ErrorCode.COMMAND_FAILED,
            default_message="停止设备失败。",
        )

    async def heart_rate_status(self) -> dict[str, Any]:
        collector = await self._get_heart_rate_collector()
        return collector.status()

    async def heart_rate_latest_sample(self) -> HeartRateSample | None:
        collector = await self._get_heart_rate_collector()
        return collector.get_latest_sample()

    async def heart_rate_scan_devices(
        self,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        collector = await self._get_heart_rate_collector()
        return await self._run_heart_rate_call(
            lambda: collector.scan_devices(timeout=timeout),
            default_code=ErrorCode.COMMAND_FAILED,
            default_message="扫描心率设备失败。",
        )

    async def heart_rate_connect(
        self,
        *,
        device_name: str | None = None,
        device_address: str | None = None,
        notify_char_uuid: str | None = None,
    ) -> dict[str, Any]:
        collector = await self._get_heart_rate_collector(
            device_name=device_name,
            device_address=device_address,
            notify_char_uuid=notify_char_uuid,
        )
        await self._run_heart_rate_call(
            collector.connect,
            default_code=ErrorCode.CONNECT_FAILED,
            default_message="连接心率设备失败。",
        )
        return collector.status()

    async def heart_rate_disconnect(self) -> dict[str, Any]:
        collector = await self._get_heart_rate_collector()
        await self._run_heart_rate_call(
            collector.disconnect,
            default_code=ErrorCode.COMMAND_FAILED,
            default_message="断开心率设备失败。",
        )
        return collector.status()

    def error_to_result(self, error: Exception) -> ErrorResult:
        normalized = normalize_exception(error, backend=self.backend_type)
        return error_result_from_exception(
            normalized,
            include_details=self.include_error_details,
        )
