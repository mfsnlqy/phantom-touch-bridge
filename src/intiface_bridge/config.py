from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Literal
import os
import tomllib

from pydantic import BaseModel, ConfigDict, Field

BackendType = Literal["intiface", "custom"]
ErrorDetail = Literal["simple", "verbose"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

DEFAULT_CONFIG_PATH = Path("phantom_touch_bridge.toml")
ENV_PREFIX = "INTIFACE_BRIDGE_"


class BridgeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = "127.0.0.1"
    port: int = 8765


class BackendSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: BackendType = "intiface"
    server_url: str = "ws://127.0.0.1:12345"
    default_device_name: str = ""
    default_device_address: str = ""
    notify_uuid: str = ""
    write_uuid: str = ""
    error_detail: ErrorDetail = "simple"
    keep_connected: bool = True


class LoggingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: LogLevel = "INFO"
    verbose: bool = False


class HeartRateSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    device_name: str = ""
    device_address: str = ""
    notify_uuid: str = ""
    scan_timeout: float = Field(default=8.0, gt=0)
    auto_start: bool = False


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bridge: BridgeSettings = Field(default_factory=BridgeSettings)
    backend: BackendSettings = Field(default_factory=BackendSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    heart_rate: HeartRateSettings = Field(default_factory=HeartRateSettings)


def get_default_settings() -> AppSettings:
    return AppSettings()


def load_settings(
    config_path: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> AppSettings:
    env_data = env if env is not None else dict(os.environ)
    file_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    raw_data: dict[str, Any] = _settings_to_dict(get_default_settings())

    if file_path.exists():
        raw_data = _deep_merge(raw_data, _load_toml_file(file_path))

    raw_data = _deep_merge(raw_data, _load_env_overrides(env_data))
    return AppSettings.model_validate(raw_data)


def _load_toml_file(file_path: Path) -> dict[str, Any]:
    with file_path.open("rb") as handle:
        loaded = tomllib.load(handle)
    return loaded if isinstance(loaded, dict) else {}


def _load_env_overrides(env: dict[str, str]) -> dict[str, Any]:
    data: dict[str, Any] = {}

    host = env.get(f"{ENV_PREFIX}HOST")
    port = env.get(f"{ENV_PREFIX}PORT")
    backend_type = env.get(f"{ENV_PREFIX}BACKEND_TYPE")
    server_url = env.get(f"{ENV_PREFIX}BACKEND_SERVER_URL")
    default_device_name = env.get(f"{ENV_PREFIX}BACKEND_DEFAULT_DEVICE_NAME")
    default_device_address = env.get(f"{ENV_PREFIX}BACKEND_DEFAULT_DEVICE_ADDRESS")
    notify_uuid = env.get(f"{ENV_PREFIX}BACKEND_NOTIFY_UUID")
    write_uuid = env.get(f"{ENV_PREFIX}BACKEND_WRITE_UUID")
    error_detail = env.get(f"{ENV_PREFIX}BACKEND_ERROR_DETAIL")
    keep_connected = env.get(f"{ENV_PREFIX}BACKEND_KEEP_CONNECTED")
    log_level = env.get(f"{ENV_PREFIX}LOG_LEVEL")
    log_verbose = env.get(f"{ENV_PREFIX}LOG_VERBOSE")
    heart_rate_enabled = env.get(f"{ENV_PREFIX}HEART_RATE_ENABLED")
    heart_rate_device_name = env.get(f"{ENV_PREFIX}HEART_RATE_DEVICE_NAME")
    heart_rate_device_address = env.get(f"{ENV_PREFIX}HEART_RATE_DEVICE_ADDRESS")
    heart_rate_notify_uuid = env.get(f"{ENV_PREFIX}HEART_RATE_NOTIFY_UUID")
    heart_rate_scan_timeout = env.get(f"{ENV_PREFIX}HEART_RATE_SCAN_TIMEOUT")
    heart_rate_auto_start = env.get(f"{ENV_PREFIX}HEART_RATE_AUTO_START")

    if host is not None:
        data.setdefault("bridge", {})["host"] = host
    if port is not None:
        data.setdefault("bridge", {})["port"] = int(port)

    if backend_type is not None:
        data.setdefault("backend", {})["type"] = backend_type
    if server_url is not None:
        data.setdefault("backend", {})["server_url"] = server_url
    if default_device_name is not None:
        data.setdefault("backend", {})["default_device_name"] = default_device_name
    if default_device_address is not None:
        data.setdefault("backend", {})["default_device_address"] = default_device_address
    if notify_uuid is not None:
        data.setdefault("backend", {})["notify_uuid"] = notify_uuid
    if write_uuid is not None:
        data.setdefault("backend", {})["write_uuid"] = write_uuid
    if error_detail is not None:
        data.setdefault("backend", {})["error_detail"] = error_detail
    if keep_connected is not None:
        data.setdefault("backend", {})["keep_connected"] = _parse_bool(keep_connected)
    if log_level is not None:
        data.setdefault("logging", {})["level"] = log_level.upper()
    if log_verbose is not None:
        data.setdefault("logging", {})["verbose"] = _parse_bool(log_verbose)
    if heart_rate_enabled is not None:
        data.setdefault("heart_rate", {})["enabled"] = _parse_bool(heart_rate_enabled)
    if heart_rate_device_name is not None:
        data.setdefault("heart_rate", {})["device_name"] = heart_rate_device_name.strip()
    if heart_rate_device_address is not None:
        data.setdefault("heart_rate", {})["device_address"] = heart_rate_device_address.strip()
    if heart_rate_notify_uuid is not None:
        data.setdefault("heart_rate", {})["notify_uuid"] = heart_rate_notify_uuid
    if heart_rate_scan_timeout is not None:
        data.setdefault("heart_rate", {})["scan_timeout"] = float(heart_rate_scan_timeout)
    if heart_rate_auto_start is not None:
        data.setdefault("heart_rate", {})["auto_start"] = _parse_bool(heart_rate_auto_start)

    return data


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _settings_to_dict(settings: AppSettings) -> dict[str, Any]:
    return settings.model_dump(mode="python")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
