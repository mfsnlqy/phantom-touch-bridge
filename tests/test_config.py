from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from intiface_bridge.config import load_settings


def test_load_settings_exposes_default_heart_rate_configuration():
    settings = load_settings(config_path="missing-config.toml", env={})

    assert settings.heart_rate.enabled is False
    assert settings.heart_rate.device_name == ""
    assert settings.heart_rate.device_address == ""
    assert settings.heart_rate.notify_uuid == ""
    assert settings.heart_rate.scan_timeout == 8.0
    assert settings.heart_rate.auto_start is False


def test_load_settings_applies_heart_rate_env_overrides():
    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_HEART_RATE_ENABLED": "true",
            "INTIFACE_BRIDGE_HEART_RATE_DEVICE_NAME": "Demo Band",
            "INTIFACE_BRIDGE_HEART_RATE_DEVICE_ADDRESS": "00:11:22:33:44:55",
            "INTIFACE_BRIDGE_HEART_RATE_NOTIFY_UUID": "00002A37-0000-1000-8000-00805F9B34FB",
            "INTIFACE_BRIDGE_HEART_RATE_SCAN_TIMEOUT": "12.5",
            "INTIFACE_BRIDGE_HEART_RATE_AUTO_START": "yes",
        }
    )

    assert settings.heart_rate.enabled is True
    assert settings.heart_rate.device_name == "Demo Band"
    assert settings.heart_rate.device_address == "00:11:22:33:44:55"
    assert (
        settings.heart_rate.notify_uuid
        == "00002A37-0000-1000-8000-00805F9B34FB"
    )
    assert settings.heart_rate.scan_timeout == 12.5
    assert settings.heart_rate.auto_start is True


def test_load_settings_allows_blank_heart_rate_env_overrides():
    settings = load_settings(
        env={
            "INTIFACE_BRIDGE_HEART_RATE_ENABLED": "false",
            "INTIFACE_BRIDGE_HEART_RATE_DEVICE_NAME": " ",
            "INTIFACE_BRIDGE_HEART_RATE_DEVICE_ADDRESS": "   ",
        }
    )

    assert settings.heart_rate.enabled is False
    assert settings.heart_rate.device_name == ""
    assert settings.heart_rate.device_address == ""


def test_load_settings_applies_heart_rate_toml_overrides(tmp_path: Path):
    config_path = tmp_path / "intiface_bridge.toml"
    config_path.write_text(
        "\n".join(
            [
                "[backend]",
                'type = "custom"',
                'default_device_name = "Demo"',
                "",
                "[heart_rate]",
                "enabled = true",
                'device_name = "Demo Band"',
                'device_address = "00:11:22:33:44:66"',
                'notify_uuid = "00002a37-0000-1000-8000-00805f9b34fb"',
                "scan_timeout = 10.0",
                "auto_start = false",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(config_path=config_path, env={})

    assert settings.backend.type == "custom"
    assert settings.backend.default_device_name == "Demo"
    assert settings.heart_rate.enabled is True
    assert settings.heart_rate.device_name == "Demo Band"
    assert settings.heart_rate.device_address == "00:11:22:33:44:66"
    assert settings.heart_rate.notify_uuid == "00002a37-0000-1000-8000-00805f9b34fb"
    assert settings.heart_rate.scan_timeout == 10.0
    assert settings.heart_rate.auto_start is False


def test_env_overrides_take_precedence_over_toml_for_heart_rate(tmp_path: Path):
    config_path = tmp_path / "intiface_bridge.toml"
    config_path.write_text(
        "\n".join(
            [
                "[heart_rate]",
                "enabled = false",
                'device_name = "Demo Band"',
                "scan_timeout = 9.0",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(
        config_path=config_path,
        env={
            "INTIFACE_BRIDGE_HEART_RATE_ENABLED": "true",
            "INTIFACE_BRIDGE_HEART_RATE_DEVICE_NAME": "Demo Band",
            "INTIFACE_BRIDGE_HEART_RATE_SCAN_TIMEOUT": "12.5",
        },
    )

    assert settings.heart_rate.enabled is True
    assert settings.heart_rate.device_name == "Demo Band"
    assert settings.heart_rate.scan_timeout == 12.5


def test_example_config_file_can_be_loaded():
    config_path = Path(__file__).resolve().parent.parent / "phantom_touch_bridge.example.toml"

    settings = load_settings(config_path=config_path, env={})

    assert settings.backend.type == "intiface"
    assert settings.heart_rate.enabled is False
    assert settings.heart_rate.scan_timeout == 8.0


def test_load_settings_rejects_non_positive_heart_rate_scan_timeout():
    with pytest.raises(ValidationError):
        load_settings(
            env={
                "INTIFACE_BRIDGE_HEART_RATE_SCAN_TIMEOUT": "0",
            }
        )

