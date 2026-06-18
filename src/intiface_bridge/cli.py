from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import typer

from intiface_bridge import __version__
from intiface_bridge.api.server import run_server
from intiface_bridge.api.schemas import HeartRateStatusResponse, StatusResponse
from intiface_bridge.config import AppSettings, load_settings
from intiface_bridge.errors import BridgeError, ErrorCode
from intiface_bridge.logging import configure_logging, get_logger
from intiface_bridge.service import BridgeService

app = typer.Typer(
    add_completion=False,
    help="Local bridge CLI for Intiface-first device control.",
)
logger = get_logger(__name__)


def _get_settings(ctx: typer.Context) -> AppSettings:
    settings = ctx.obj.get("settings")
    if not isinstance(settings, AppSettings):
        raise typer.Exit(code=1)
    return settings


def _get_service(ctx: typer.Context) -> BridgeService:
    service = ctx.obj.get("service")
    if not isinstance(service, BridgeService):
        raise typer.Exit(code=1)
    return service


def _echo_payload(payload: Any) -> None:
    typer.echo(json.dumps(_to_jsonable(payload), ensure_ascii=False, indent=2))


def _to_jsonable(payload: Any) -> Any:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json", exclude_none=True)
    if isinstance(payload, list):
        return [_to_jsonable(item) for item in payload]
    if isinstance(payload, tuple):
        return [_to_jsonable(item) for item in payload]
    if isinstance(payload, dict):
        return {key: _to_jsonable(value) for key, value in payload.items()}
    return payload


def _run_service_call(ctx: typer.Context, coro: Any) -> None:
    service = _get_service(ctx)
    try:
        result = asyncio.run(coro)
    except BridgeError as error:
        _echo_payload(service.error_to_result(error))
        raise typer.Exit(code=1) from error
    _echo_payload(result)


def _emit_bridge_error(error: BridgeError) -> None:
    _echo_payload(error.to_error_result())
    raise typer.Exit(code=1)


def _call_local_http_json(
    settings: AppSettings,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> Any:
    base_url = f"http://{settings.bridge.host}:{settings.bridge.port}"
    request_data = None
    headers: dict[str, str] = {}
    if payload is not None:
        request_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(
        f"{base_url}{path}",
        data=request_data,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request) as response:
            raw_body = response.read().decode("utf-8")
    except HTTPError as error:
        raw_body = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError as decode_error:
            raise BridgeError(
                ErrorCode.COMMAND_FAILED,
                f"本地服务返回了无法解析的响应（HTTP {error.code}）。",
                backend="heart_rate",
            ) from decode_error
        if isinstance(parsed, dict):
            _echo_payload(parsed)
            raise typer.Exit(code=1)
        raise BridgeError(
            ErrorCode.COMMAND_FAILED,
            f"本地服务返回了意外响应（HTTP {error.code}）。",
            backend="heart_rate",
        ) from error
    except URLError as error:
        raise BridgeError(
            ErrorCode.BACKEND_UNAVAILABLE,
            "未连接到本地服务。请先运行 `phantom-touch-bridge serve`，再使用心率 CLI 管理命令。",
            backend="heart_rate",
        ) from error

    if not raw_body:
        return None

    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as error:
        raise BridgeError(
            ErrorCode.COMMAND_FAILED,
            "本地服务返回了无法解析的响应。",
            backend="heart_rate",
        ) from error


def _run_heart_rate_http_command(
    ctx: typer.Context,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> None:
    settings = _get_settings(ctx)
    try:
        result = _call_local_http_json(
            settings,
            path,
            method=method,
            payload=payload,
        )
    except BridgeError as error:
        _emit_bridge_error(error)
    _echo_payload(result)


def _normalize_status(raw: dict[str, Any]) -> StatusResponse:
    backend = str(raw.get("backend") or "unknown")
    device_name = _first_non_empty(raw.get("device_name"), raw.get("selected_device"))
    device_id = _first_non_empty(
        raw.get("device_id"),
        raw.get("device_address"),
        raw.get("selected_device_id"),
    )
    connected = bool(raw.get("connected"))
    if "connected" not in raw:
        connected = bool(device_id or device_name)

    details = {
        key: value
        for key, value in raw.items()
        if key
        not in {
            "backend",
            "connected",
            "device_name",
            "device_id",
            "device_address",
            "selected_device",
            "selected_device_id",
            "keep_connected",
        }
    }
    return StatusResponse(
        backend=backend,
        connected=connected,
        device_name=device_name,
        device_id=device_id,
        keep_connected=raw.get("keep_connected"),
        details=details or None,
    )


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return None


def _normalize_heart_rate_status(raw: dict[str, Any]) -> HeartRateStatusResponse:
    return HeartRateStatusResponse(
        connected=bool(raw.get("connected")),
        streaming=bool(raw.get("streaming")),
        target_device_name=_first_non_empty(raw.get("target_device_name")),
        target_device_address=_first_non_empty(raw.get("target_device_address")),
        selected_device_name=_first_non_empty(raw.get("selected_device_name")),
        selected_device_address=_first_non_empty(raw.get("selected_device_address")),
        notify_char_uuid=_first_non_empty(raw.get("notify_char_uuid")),
        last_packet_at=_first_non_empty(raw.get("last_packet_at")),
        last_error=_first_non_empty(raw.get("last_error")),
        latest_bpm=raw.get("latest_bpm"),
    )


@app.callback()
def main_callback(
    ctx: typer.Context,
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to a TOML config file.",
    ),
) -> None:
    settings = load_settings(config_path=config)
    configure_logging(settings, force=True)
    ctx.obj = {
        "settings": settings,
        "service": BridgeService(settings),
    }
    logger.debug("CLI initialized with backend=%s", settings.backend.type)


@app.command()
def version() -> None:
    """Show the current package version."""
    typer.echo(__version__)


@app.command("show-config")
def show_config(ctx: typer.Context) -> None:
    """Print the resolved configuration."""
    settings = _get_settings(ctx)
    _echo_payload(settings.model_dump(mode="json"))


@app.command()
def health(ctx: typer.Context) -> None:
    """Run a minimal backend health check."""
    service = _get_service(ctx)
    logger.debug("Running CLI health check for backend=%s", service.backend_type)
    _run_service_call(ctx, service.health())


@app.command()
def status(ctx: typer.Context) -> None:
    """Show the current backend/device status."""
    service = _get_service(ctx)
    logger.debug("Running CLI status for backend=%s", service.backend_type)
    try:
        payload = asyncio.run(service.status())
    except BridgeError as error:
        _echo_payload(service.error_to_result(error))
        raise typer.Exit(code=1) from error
    _echo_payload(_normalize_status(payload))


@app.command("devices")
def devices(ctx: typer.Context) -> None:
    """List available devices for the selected backend."""
    service = _get_service(ctx)
    logger.debug("Listing devices for backend=%s", service.backend_type)
    _run_service_call(ctx, service.list_devices())


@app.command()
def connect(
    ctx: typer.Context,
    device_name: str | None = typer.Option(
        None,
        "--device-name",
        help="Device name or name fragment to connect.",
    ),
) -> None:
    """Connect to a device by name."""
    service = _get_service(ctx)
    logger.debug(
        "Running CLI connect for backend=%s device_name=%s",
        service.backend_type,
        device_name,
    )
    resolved_device_name = device_name.strip() if device_name is not None else None
    _run_service_call(ctx, service.connect(resolved_device_name or None))


@app.command()
def disconnect(ctx: typer.Context) -> None:
    """Disconnect the current device or backend session."""
    service = _get_service(ctx)
    logger.debug("Running CLI disconnect for backend=%s", service.backend_type)
    _run_service_call(ctx, service.disconnect())


@app.command("heart-rate-status")
def heart_rate_status(ctx: typer.Context) -> None:
    """Show the current heart-rate collector status from the running local service."""
    settings = _get_settings(ctx)
    logger.debug(
        "Running CLI heart-rate-status against local service %s:%s",
        settings.bridge.host,
        settings.bridge.port,
    )
    _run_heart_rate_http_command(ctx, "/heart-rate/status")


@app.command("heart-rate-devices")
def heart_rate_devices(ctx: typer.Context) -> None:
    """List nearby heart-rate devices through the running local service."""
    settings = _get_settings(ctx)
    logger.debug(
        "Running CLI heart-rate-devices against local service %s:%s",
        settings.bridge.host,
        settings.bridge.port,
    )
    _run_heart_rate_http_command(ctx, "/heart-rate/devices")


@app.command("heart-rate-connect")
def heart_rate_connect(
    ctx: typer.Context,
    device_name: str | None = typer.Option(
        None,
        "--device-name",
        help="Heart-rate device name or name fragment to connect.",
    ),
    device_address: str | None = typer.Option(
        None,
        "--device-address",
        help="Exact BLE address of the heart-rate device.",
    ),
    notify_char_uuid: str | None = typer.Option(
        None,
        "--notify-char-uuid",
        help="Optional notify characteristic UUID override.",
    ),
) -> None:
    """Connect to a heart-rate device through the running local service."""
    settings = _get_settings(ctx)
    logger.debug(
        "Running CLI heart-rate-connect against local service %s:%s device_name=%s device_address=%s",
        settings.bridge.host,
        settings.bridge.port,
        device_name,
        device_address,
    )
    resolved_device_name = device_name.strip() if device_name is not None else None
    resolved_device_address = (
        device_address.strip() if device_address is not None else None
    )
    resolved_notify_char_uuid = (
        notify_char_uuid.strip() if notify_char_uuid is not None else None
    )
    _run_heart_rate_http_command(
        ctx,
        "/heart-rate/connect",
        method="POST",
        payload={
            "device_name": resolved_device_name or None,
            "device_address": resolved_device_address or None,
            "notify_char_uuid": resolved_notify_char_uuid or None,
        },
    )


@app.command("heart-rate-disconnect")
def heart_rate_disconnect(ctx: typer.Context) -> None:
    """Disconnect the current heart-rate device through the running local service."""
    settings = _get_settings(ctx)
    logger.debug(
        "Running CLI heart-rate-disconnect against local service %s:%s",
        settings.bridge.host,
        settings.bridge.port,
    )
    _run_heart_rate_http_command(ctx, "/heart-rate/disconnect", method="POST")


@app.command("set-strength")
def set_strength(
    ctx: typer.Context,
    value: int = typer.Option(
        ...,
        "--value",
        help="Target strength using the shared 0-100 scale.",
    ),
) -> None:
    """Set device strength using the shared 0-100 scale."""
    service = _get_service(ctx)
    logger.debug("Running CLI set-strength for backend=%s value=%s", service.backend_type, value)
    _run_service_call(ctx, service.set_strength(value))


@app.command()
def stop(ctx: typer.Context) -> None:
    """Stop the current device."""
    service = _get_service(ctx)
    logger.debug("Running CLI stop for backend=%s", service.backend_type)
    _run_service_call(ctx, service.stop())


@app.command()
def serve(ctx: typer.Context) -> None:
    """Start the local HTTP bridge server."""
    settings = _get_settings(ctx)
    logger.info(
        "Starting HTTP bridge server on %s:%s with backend=%s",
        settings.bridge.host,
        settings.bridge.port,
        settings.backend.type,
    )
    run_server(settings)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

