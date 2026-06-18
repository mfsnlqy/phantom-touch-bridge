from __future__ import annotations

import json

from typer.testing import CliRunner

from intiface_bridge.cli import app
from intiface_bridge.config import load_settings
from intiface_bridge.models import BackendHealth, CommandResult, DeviceSummary

runner = CliRunner()


class FakeBridgeService:
    last_connected_with: str | None = None
    last_heart_rate_connected_with: dict[str, str | None] | None = None
    last_strength: int | None = None
    stop_calls = 0
    heart_rate_disconnect_calls = 0

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


class FakeHeartRateHttp:
    calls: list[dict[str, object]] = []

    @classmethod
    def reset(cls) -> None:
        cls.calls = []

    @classmethod
    def request(
        cls,
        settings,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
    ):
        cls.calls.append(
            {
                "host": settings.bridge.host,
                "port": settings.bridge.port,
                "path": path,
                "method": method,
                "payload": payload,
            }
        )
        if path == "/heart-rate/status":
            return {
                "ok": True,
                "backend": "heart_rate",
                "connected": True,
                "streaming": True,
                "target_device_name": "Demo Band",
                "target_device_address": "00:11:22:33:44:55",
                "selected_device_name": "Demo Band",
                "selected_device_address": "00:11:22:33:44:55",
                "notify_char_uuid": "00002A37-0000-1000-8000-00805F9B34FB",
                "last_packet_at": "2026-06-18T00:00:00+00:00",
                "latest_bpm": 88,
            }
        if path == "/heart-rate/devices":
            return [
                {
                    "name": "Demo Band",
                    "address": "00:11:22:33:44:55",
                    "rssi": -40,
                    "service_uuids": ["180d"],
                }
            ]
        if path == "/heart-rate/connect":
            return {
                "ok": True,
                "backend": "heart_rate",
                "connected": True,
                "streaming": True,
                "target_device_name": payload["device_name"] if payload else None,
                "target_device_address": payload["device_address"] if payload else None,
                "selected_device_name": "Demo Band",
                "selected_device_address": "00:11:22:33:44:55",
                "notify_char_uuid": payload["notify_char_uuid"] if payload else None,
                "last_packet_at": "2026-06-18T00:00:00+00:00",
                "latest_bpm": 88,
            }
        if path == "/heart-rate/disconnect":
            return {
                "ok": True,
                "backend": "heart_rate",
                "connected": False,
                "streaming": False,
                "target_device_name": "Demo Band",
                "target_device_address": "00:11:22:33:44:55",
                "selected_device_name": None,
                "selected_device_address": None,
                "notify_char_uuid": None,
                "last_packet_at": None,
                "latest_bpm": None,
            }
        raise AssertionError(f"unexpected path {path}")


def test_cli_help_lists_t20_commands(monkeypatch):
    _patch_cli(monkeypatch)

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "health" in result.stdout
    assert "status" in result.stdout
    assert "devices" in result.stdout
    assert "connect" in result.stdout
    assert "disconnect" in result.stdout
    assert "heart-rate-status" in result.stdout
    assert "heart-rate-devices" in result.stdout
    assert "heart-rate-connect" in result.stdout
    assert "heart-rate-disconnect" in result.stdout
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

    connect_result = runner.invoke(app, ["connect", "--device-name", "Demo"])
    strength_result = runner.invoke(app, ["set-strength", "--value", "42"])
    stop_result = runner.invoke(app, ["stop"])

    assert connect_result.exit_code == 0
    assert json.loads(connect_result.stdout)["action"] == "connect"
    assert FakeBridgeService.last_connected_with == "Demo"

    assert strength_result.exit_code == 0
    assert json.loads(strength_result.stdout)["value"] == 42
    assert FakeBridgeService.last_strength == 42

    assert stop_result.exit_code == 0
    assert json.loads(stop_result.stdout)["action"] == "stop"
    assert FakeBridgeService.stop_calls == 1


def test_show_config_includes_heart_rate_section(monkeypatch):
    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_BACKEND_TYPE": "custom",
            "INTIFACE_BRIDGE_HEART_RATE_ENABLED": "true",
            "INTIFACE_BRIDGE_HEART_RATE_DEVICE_NAME": "Demo Band",
            "INTIFACE_BRIDGE_HEART_RATE_SCAN_TIMEOUT": "12.5",
        }
    )
    monkeypatch.setattr("intiface_bridge.cli.load_settings", lambda config_path=None: settings)
    monkeypatch.setattr("intiface_bridge.cli.configure_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr("intiface_bridge.cli.BridgeService", FakeBridgeService)

    result = runner.invoke(app, ["show-config"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "bridge": {
            "host": "127.0.0.1",
            "port": 8765,
        },
        "backend": {
            "type": "custom",
            "server_url": "ws://127.0.0.1:12345",
            "default_device_name": "",
            "default_device_address": "",
            "notify_uuid": "",
            "write_uuid": "",
            "error_detail": "simple",
            "keep_connected": True,
        },
        "logging": {
            "level": "INFO",
            "verbose": False,
        },
        "heart_rate": {
            "enabled": True,
            "device_name": "Demo Band",
            "device_address": "",
            "notify_uuid": "",
            "scan_timeout": 12.5,
            "auto_start": False,
        },
    }


def test_cli_heart_rate_status_and_devices_return_json(monkeypatch):
    _patch_cli(monkeypatch)
    FakeHeartRateHttp.reset()
    monkeypatch.setattr(
        "intiface_bridge.cli._call_local_http_json",
        FakeHeartRateHttp.request,
    )

    status_result = runner.invoke(app, ["heart-rate-status"])
    devices_result = runner.invoke(app, ["heart-rate-devices"])

    assert status_result.exit_code == 0
    assert json.loads(status_result.stdout) == {
        "ok": True,
        "backend": "heart_rate",
        "connected": True,
        "streaming": True,
        "target_device_name": "Demo Band",
        "target_device_address": "00:11:22:33:44:55",
        "selected_device_name": "Demo Band",
        "selected_device_address": "00:11:22:33:44:55",
        "notify_char_uuid": "00002A37-0000-1000-8000-00805F9B34FB",
        "last_packet_at": "2026-06-18T00:00:00+00:00",
        "latest_bpm": 88,
    }
    assert devices_result.exit_code == 0
    assert json.loads(devices_result.stdout) == [
        {
            "name": "Demo Band",
            "address": "00:11:22:33:44:55",
            "rssi": -40,
            "service_uuids": ["180d"],
        }
    ]
    assert FakeHeartRateHttp.calls == [
        {
            "host": "127.0.0.1",
            "port": 8765,
            "path": "/heart-rate/status",
            "method": "GET",
            "payload": None,
        },
        {
            "host": "127.0.0.1",
            "port": 8765,
            "path": "/heart-rate/devices",
            "method": "GET",
            "payload": None,
        },
    ]


def test_cli_heart_rate_mutation_commands_delegate_to_service(monkeypatch):
    _patch_cli(monkeypatch)
    FakeHeartRateHttp.reset()
    monkeypatch.setattr(
        "intiface_bridge.cli._call_local_http_json",
        FakeHeartRateHttp.request,
    )

    connect_result = runner.invoke(
        app,
        [
            "heart-rate-connect",
            "--device-name",
            " Demo Band ",
            "--device-address",
            "00:11:22:33:44:55",
            "--notify-char-uuid",
            " 00002A37-0000-1000-8000-00805F9B34FB ",
        ],
    )
    disconnect_result = runner.invoke(app, ["heart-rate-disconnect"])

    assert connect_result.exit_code == 0
    assert json.loads(connect_result.stdout)["connected"] is True
    assert disconnect_result.exit_code == 0
    assert json.loads(disconnect_result.stdout)["connected"] is False
    assert FakeHeartRateHttp.calls == [
        {
            "host": "127.0.0.1",
            "port": 8765,
            "path": "/heart-rate/connect",
            "method": "POST",
            "payload": {
                "device_name": "Demo Band",
                "device_address": "00:11:22:33:44:55",
                "notify_char_uuid": "00002A37-0000-1000-8000-00805F9B34FB",
            },
        },
        {
            "host": "127.0.0.1",
            "port": 8765,
            "path": "/heart-rate/disconnect",
            "method": "POST",
            "payload": None,
        },
    ]

