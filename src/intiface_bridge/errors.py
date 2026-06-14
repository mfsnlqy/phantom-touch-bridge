from __future__ import annotations

from enum import StrEnum
from typing import Any

from intiface_bridge.models import ErrorResult


class ErrorCode(StrEnum):
    BACKEND_UNAVAILABLE = "backend_unavailable"
    DEVICE_NOT_FOUND = "device_not_found"
    MULTIPLE_DEVICES_MATCHED = "multiple_devices_matched"
    NOT_CONNECTED = "not_connected"
    CAPABILITY_NOT_SUPPORTED = "capability_not_supported"
    INVALID_STRENGTH = "invalid_strength"
    CONNECT_FAILED = "connect_failed"
    COMMAND_FAILED = "command_failed"


class BridgeError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        backend: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.backend = backend
        self.details = details

    def to_error_result(self, *, include_details: bool = False) -> ErrorResult:
        return ErrorResult(
            backend=self.backend,
            code=self.code.value,
            error=self.message,
            details=self.details if include_details else None,
        )


def error_result_from_exception(
    error: BridgeError,
    *,
    include_details: bool = False,
) -> ErrorResult:
    return error.to_error_result(include_details=include_details)


def normalize_exception(
    error: Exception,
    *,
    backend: str | None = None,
    default_code: ErrorCode = ErrorCode.COMMAND_FAILED,
    default_message: str | None = None,
    details: dict[str, Any] | None = None,
) -> BridgeError:
    if isinstance(error, BridgeError):
        if backend is None and details is None:
            return error

        merged_details = dict(error.details or {})
        if details:
            merged_details.update(details)

        return BridgeError(
            error.code,
            error.message,
            backend=error.backend or backend,
            details=merged_details or None,
        )

    message = default_message if default_message is not None else str(error)
    merged_details = {"exception_type": type(error).__name__}
    if details:
        merged_details.update(details)

    return BridgeError(
        default_code,
        message or "Unexpected backend error.",
        backend=backend,
        details=merged_details,
    )
