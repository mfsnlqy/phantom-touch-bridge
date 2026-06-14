from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import typer

from intiface_bridge import __version__
from intiface_bridge.api.server import run_server
from intiface_bridge.api.schemas import StatusResponse
from intiface_bridge.config import AppSettings, load_settings
from intiface_bridge.errors import BridgeError
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
