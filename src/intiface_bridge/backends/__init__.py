from __future__ import annotations

from intiface_bridge.backends.base import BackendFactory
from intiface_bridge.backends.custom_backend import CustomBackend
from intiface_bridge.backends.intiface_backend import IntifaceBackend


def get_default_backend_registry() -> dict[str, BackendFactory]:
    return {
        "custom": CustomBackend,
        "intiface": IntifaceBackend,
    }


__all__ = ["CustomBackend", "IntifaceBackend", "get_default_backend_registry"]
