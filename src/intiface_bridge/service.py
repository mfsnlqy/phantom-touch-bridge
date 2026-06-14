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

    @property
    def backend_type(self) -> str:
        return self.settings.backend.type

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

    def error_to_result(self, error: Exception) -> ErrorResult:
        normalized = normalize_exception(error, backend=self.backend_type)
        return error_result_from_exception(
            normalized,
            include_details=self.include_error_details,
        )
