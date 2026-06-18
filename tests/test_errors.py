from __future__ import annotations

import asyncio

from intiface_bridge.config import load_settings
from intiface_bridge.errors import (
    BridgeError,
    ErrorCode,
    error_result_from_exception,
    normalize_exception,
)
from intiface_bridge.service import BridgeService


class ExplodingBackend:
    backend_name = "custom"

    def __init__(self, settings) -> None:
        self.settings = settings

    async def health(self):
        raise RuntimeError("backend boom")

    async def list_devices(self):
        raise AssertionError("not used in this test")

    async def connect(self, device_name: str | None = None):
        raise RuntimeError(f"cannot connect: {device_name}")

    async def disconnect(self):
        raise AssertionError("not used in this test")

    async def status(self):
        raise AssertionError("not used in this test")

    async def set_strength(self, value: int):
        raise AssertionError("not used in this test")

    async def stop(self):
        raise AssertionError("not used in this test")


class NormalizedErrorBackend:
    backend_name = "custom"

    def __init__(self, settings) -> None:
        self.settings = settings

    async def health(self):
        raise AssertionError("not used in this test")

    async def list_devices(self):
        raise AssertionError("not used in this test")

    async def connect(self, device_name: str | None = None):
        raise normalize_exception(
            RuntimeError(f"cannot connect: {device_name}"),
            backend="custom",
            default_code=ErrorCode.DEVICE_NOT_FOUND,
            default_message="后端内未找到设备。",
            details={"query": device_name, "scan_seconds": 8},
        )

    async def disconnect(self):
        raise AssertionError("not used in this test")

    async def status(self):
        raise AssertionError("not used in this test")

    async def set_strength(self, value: int):
        raise AssertionError("not used in this test")

    async def stop(self):
        raise AssertionError("not used in this test")


def test_bridge_error_to_error_result_omits_details_by_default():
    error = BridgeError(
        ErrorCode.CONNECT_FAILED,
        "连接失败。",
        backend="custom",
        details={"address": "00:11:22:33:44:55"},
    )

    result = error.to_error_result()

    assert result.model_dump(exclude_none=True) == {
        "ok": False,
        "backend": "custom",
        "code": "connect_failed",
        "error": "连接失败。",
    }


def test_error_result_from_exception_can_include_details():
    error = BridgeError(
        ErrorCode.INVALID_STRENGTH,
        "强度无效。",
        backend="custom",
        details={"value": 101},
    )

    result = error_result_from_exception(error, include_details=True)

    assert result.model_dump(exclude_none=True) == {
        "ok": False,
        "backend": "custom",
        "code": "invalid_strength",
        "error": "强度无效。",
        "details": {"value": 101},
    }


def test_normalize_exception_merges_bridge_error_details_and_backend():
    original = BridgeError(
        ErrorCode.DEVICE_NOT_FOUND,
        "未找到设备。",
        details={"query": "demo"},
    )

    normalized = normalize_exception(
        original,
        backend="custom",
        details={"scan_seconds": 8},
    )

    assert normalized is not original
    assert normalized.code == ErrorCode.DEVICE_NOT_FOUND
    assert normalized.message == "未找到设备。"
    assert normalized.backend == "custom"
    assert normalized.details == {
        "query": "demo",
        "scan_seconds": 8,
    }


def test_normalize_exception_wraps_regular_exception_with_default_context():
    normalized = normalize_exception(
        RuntimeError("boom"),
        backend="intiface",
        default_code=ErrorCode.BACKEND_UNAVAILABLE,
        default_message="后端探测失败。",
        details={"server_url": "ws://127.0.0.1:12345"},
    )

    assert normalized.code == ErrorCode.BACKEND_UNAVAILABLE
    assert normalized.message == "后端探测失败。"
    assert normalized.backend == "intiface"
    assert normalized.details == {
        "exception_type": "RuntimeError",
        "server_url": "ws://127.0.0.1:12345",
    }


def test_bridge_service_error_to_result_respects_simple_error_mode():
    service = BridgeService(
        load_settings(
            env={
                "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
                "INTIFACE_BRIDGE_BACKEND_ERROR_DETAIL": "simple",
            }
        )
    )

    result = service.error_to_result(
        BridgeError(
            ErrorCode.COMMAND_FAILED,
            "命令失败。",
            details={"payload": "A0900164"},
        )
    )

    assert result.model_dump(exclude_none=True) == {
        "ok": False,
        "backend": "custom",
        "code": "command_failed",
        "error": "命令失败。",
    }


def test_bridge_service_error_to_result_respects_verbose_error_mode():
    service = BridgeService(
        load_settings(
            env={
                "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
                "INTIFACE_BRIDGE_BACKEND_ERROR_DETAIL": "verbose",
            }
        )
    )

    result = service.error_to_result(
        BridgeError(
            ErrorCode.COMMAND_FAILED,
            "命令失败。",
            details={"payload": "A0900164"},
        )
    )

    assert result.model_dump(exclude_none=True) == {
        "ok": False,
        "backend": "custom",
        "code": "command_failed",
        "error": "命令失败。",
        "details": {"payload": "A0900164"},
    }


def test_bridge_service_health_normalizes_runtime_exception_from_backend():
    service = BridgeService(
        load_settings(env={"INTIFACE_BRIDGE_BACKEND_TYPE": "custom"}),
        backend_registry={"custom": ExplodingBackend},
    )

    try:
        asyncio.run(service.health())
    except BridgeError as error:
        assert error.code == ErrorCode.BACKEND_UNAVAILABLE
        assert error.message == "后端健康检查失败。"
        assert error.backend == "custom"
        assert error.details == {"exception_type": "RuntimeError"}
    else:
        raise AssertionError("expected BridgeError from service.health()")


def test_bridge_service_connect_normalizes_runtime_exception_and_keeps_verbose_details():
    service = BridgeService(
        load_settings(
            env={
                "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
                "INTIFACE_BRIDGE_BACKEND_ERROR_DETAIL": "verbose",
            }
        ),
        backend_registry={"custom": ExplodingBackend},
    )

    try:
        asyncio.run(service.connect("DEMO"))
    except BridgeError as error:
        result = service.error_to_result(error)
        assert error.code == ErrorCode.CONNECT_FAILED
        assert error.message == "连接设备失败。"
        assert error.backend == "custom"
        assert error.details == {"exception_type": "RuntimeError"}
        assert result.model_dump(exclude_none=True) == {
            "ok": False,
            "backend": "custom",
            "code": "connect_failed",
            "error": "连接设备失败。",
            "details": {"exception_type": "RuntimeError"},
        }
    else:
        raise AssertionError("expected BridgeError from service.connect()")


def test_bridge_service_preserves_backend_normalized_error_details_in_verbose_mode():
    service = BridgeService(
        load_settings(
            env={
                "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
                "INTIFACE_BRIDGE_BACKEND_ERROR_DETAIL": "verbose",
            }
        ),
        backend_registry={"custom": NormalizedErrorBackend},
    )

    try:
        asyncio.run(service.connect("DEMO"))
    except BridgeError as error:
        result = service.error_to_result(error)
        assert error.code == ErrorCode.DEVICE_NOT_FOUND
        assert error.message == "后端内未找到设备。"
        assert error.backend == "custom"
        assert error.details == {
            "exception_type": "RuntimeError",
            "query": "DEMO",
            "scan_seconds": 8,
        }
        assert result.model_dump(exclude_none=True) == {
            "ok": False,
            "backend": "custom",
            "code": "device_not_found",
            "error": "后端内未找到设备。",
            "details": {
                "exception_type": "RuntimeError",
                "query": "DEMO",
                "scan_seconds": 8,
            },
        }
    else:
        raise AssertionError("expected BridgeError from service.connect()")


def test_bridge_service_preserves_backend_normalized_error_but_hides_details_in_simple_mode():
    service = BridgeService(
        load_settings(
            env={
                "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
                "INTIFACE_BRIDGE_BACKEND_ERROR_DETAIL": "simple",
            }
        ),
        backend_registry={"custom": NormalizedErrorBackend},
    )

    try:
        asyncio.run(service.connect("DEMO"))
    except BridgeError as error:
        result = service.error_to_result(error)
        assert error.code == ErrorCode.DEVICE_NOT_FOUND
        assert error.message == "后端内未找到设备。"
        assert error.backend == "custom"
        assert error.details == {
            "exception_type": "RuntimeError",
            "query": "DEMO",
            "scan_seconds": 8,
        }
        assert result.model_dump(exclude_none=True) == {
            "ok": False,
            "backend": "custom",
            "code": "device_not_found",
            "error": "后端内未找到设备。",
        }
    else:
        raise AssertionError("expected BridgeError from service.connect()")

