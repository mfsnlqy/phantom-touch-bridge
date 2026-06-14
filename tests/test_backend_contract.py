from __future__ import annotations

import inspect

from intiface_bridge.backends import (
    CustomBackend,
    IntifaceBackend,
    __all__ as backends_all,
    get_default_backend_registry,
)
from intiface_bridge.backends.base import DeviceBackend
from intiface_bridge.config import load_settings

REQUIRED_BACKEND_METHODS = [
    "health",
    "list_devices",
    "connect",
    "disconnect",
    "status",
    "set_strength",
    "stop",
]


def test_default_backend_registry_contains_expected_backends():
    registry = get_default_backend_registry()

    assert set(registry) == {"custom", "intiface"}
    assert registry["custom"] is CustomBackend
    assert registry["intiface"] is IntifaceBackend


def test_backends_package_exports_stable_public_api():
    assert set(backends_all) == {
        "CustomBackend",
        "IntifaceBackend",
        "get_default_backend_registry",
    }


def test_registered_backends_match_device_backend_protocol_signatures():
    registry = get_default_backend_registry()

    instances = {
        "custom": registry["custom"](
            load_settings(env={"INTIFACE_BRIDGE_BACKEND_TYPE": "custom"})
        ),
        "intiface": registry["intiface"](
            load_settings(env={"INTIFACE_BRIDGE_BACKEND_TYPE": "intiface"})
        ),
    }

    protocol_methods = {
        method_name: getattr(DeviceBackend, method_name)
        for method_name in REQUIRED_BACKEND_METHODS
    }

    for backend_name, instance in instances.items():
        backend_cls = type(instance)
        for method_name in REQUIRED_BACKEND_METHODS:
            method = getattr(instance, method_name, None)
            assert method is not None, f"{backend_name} missing method {method_name}"
            assert callable(method), f"{backend_name}.{method_name} must be callable"
            assert inspect.iscoroutinefunction(method), (
                f"{backend_name}.{method_name} must be async"
            )

            protocol_signature = inspect.signature(protocol_methods[method_name])
            backend_signature = inspect.signature(getattr(backend_cls, method_name))
            assert backend_signature == protocol_signature, (
                f"{backend_name}.{method_name} signature drifted from DeviceBackend: "
                f"{backend_signature!s} != {protocol_signature!s}"
            )


def test_registered_backend_instances_match_selected_backend_type():
    registry = get_default_backend_registry()

    custom_settings = load_settings(env={"INTIFACE_BRIDGE_BACKEND_TYPE": "custom"})
    intiface_settings = load_settings(env={"INTIFACE_BRIDGE_BACKEND_TYPE": "intiface"})

    custom_backend = registry["custom"](custom_settings)
    intiface_backend = registry["intiface"](intiface_settings)

    assert custom_backend.backend_name == "custom"
    assert intiface_backend.backend_name == "intiface"
