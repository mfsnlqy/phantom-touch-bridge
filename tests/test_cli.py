from __future__ import annotations

import json

from typer.testing import CliRunner

from intiface_bridge.cli import app
from intiface_bridge.config import load_settings
from intiface_bridge.models import BackendHealth, CommandResult, DeviceSummary

runner = CliRunner()


class FakeBridgeService:
    last_connected_with: str | None = None
    last_strength: int | None = None
    stop_calls = 0

    def __init__(self, settings) -> None:
        self.settings = settings
        self.backend_type = settings.backend.type

    async def health(self) -> BackendHealth:
        return BackendHealth(
            ok=True,
            backend=self.backend_type,
            message="ok",
        )

    async def status(self) -> dict[str, object]:
        return {
            "backend": "intiface",
            "selected_device": "Demo Device",
            "selected_device_id": "7",
            "keep_connected": True,
            "client_connected": True,
            "server_url": "ws://127.0.0.1:12345",
        }

    async def list_devices(self) -> list[DeviceSummary]:
        return [
            DeviceSummary(
                id="device-1",
                name="Demo Device",
                connected=False,
                backend=self.backend_type,
                capabilities=["vibrate"],
            )
        ]

    async def connect(self, device_name: str | None = None) -> CommandResult:
        type(self).last_connected_with = device_name
        return CommandResult(
            backend=self.backend_type,
            action="connect",
            device_id="device-1",
            message="connected",
        )

    async def disconnect(self) -> CommandResult:
        return CommandResult(
            backend=self.backend_type,
            action="disconnect",
            message="disconnected",
        )

    async def set_strength(self, value: int) -> CommandResult:
        type(self).last_strength = value
        return CommandResult(
            backend=self.backend_type,
            action="set_strength",
            device_id="device-1",
            value=value,
            message="ok",
        )

    async def stop(self) -> CommandResult:
        type(self).stop_calls += 1
        return CommandResult(
            backend=self.backend_type,
            action="stop",
            device_id="device-1",
            message="stopped",
        )


def _patch_cli(monkeypatch) -> None:
    settings = load_settings(env={"INTIFACE_BRIDGE_BACKEND_TYPE": "custom"})
    monkeypatch.setattr("intiface_bridge.cli.load_settings", lambda config_path=None: settings)
    monkeypatch.setattr("intiface_bridge.cli.configure_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr("intiface_bridge.cli.BridgeService", FakeBridgeService)


def test_cli_help_lists_t20_commands(monkeypatch):
    _patch_cli(monkeypatch)

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "health" in result.stdout
    assert "status" in result.stdout
    assert "devices" in result.stdout
    assert "connect" in result.stdout
    assert "disconnect" in result.stdout
    assert "set-strength" in result.stdout
    assert "stop" in result.stdout
    assert "serve" in result.stdout


def test_cli_status_and_devices_return_json(monkeypatch):
    _patch_cli(monkeypatch)

    status_result = runner.invoke(app, ["status"])
    devices_result = runner.invoke(app, ["devices"])

    assert status_result.exit_code == 0
    assert json.loads(status_result.stdout) == {
        "ok": True,
        "backend": "intiface",
        "connected": True,
        "device_name": "Demo Device",
        "device_id": "7",
        "keep_connected": True,
        "details": {
            "client_connected": True,
            "server_url": "ws://127.0.0.1:12345",
        },
    }
    assert devices_result.exit_code == 0
    assert json.loads(devices_result.stdout) == [
        {
            "id": "device-1",
            "name": "Demo Device",
            "connected": False,
            "backend": "custom",
            "capabilities": ["vibrate"],
        }
    ]


def test_cli_mutation_commands_delegate_to_service(monkeypatch):
    _patch_cli(monkeypatch)
    FakeBridgeService.last_connected_with = None
    FakeBridgeService.last_strength = None
    FakeBridgeService.stop_calls = 0

    connect_result = runner.invoke(app, ["connect", "--device-name", "DEMO"])
    strength_result = runner.invoke(app, ["set-strength", "--value", "42"])
    stop_result = runner.invoke(app, ["stop"])

    assert connect_result.exit_code == 0
    assert json.loads(connect_result.stdout)["action"] == "connect"
    assert FakeBridgeService.last_connected_with == "DEMO"

    assert strength_result.exit_code == 0
    assert json.loads(strength_result.stdout)["value"] == 42
    assert FakeBridgeService.last_strength == 42

    assert stop_result.exit_code == 0
    assert json.loads(stop_result.stdout)["action"] == "stop"
    assert FakeBridgeService.stop_calls == 1
