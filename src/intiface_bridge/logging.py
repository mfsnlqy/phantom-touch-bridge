from __future__ import annotations

import logging as pylogging

from intiface_bridge.config import AppSettings

_DEFAULT_FORMAT = "%(levelname)s %(name)s: %(message)s"
_VERBOSE_FORMAT = "%(asctime)s %(levelname)s %(name)s:%(lineno)d | %(message)s"


def configure_logging(settings: AppSettings, *, force: bool = False) -> None:
    level = getattr(pylogging, settings.logging.level.upper(), pylogging.INFO)
    verbose = settings.logging.verbose

    pylogging.basicConfig(
        level=level,
        format=_VERBOSE_FORMAT if verbose else _DEFAULT_FORMAT,
        force=force,
    )


def get_logger(name: str) -> pylogging.Logger:
    return pylogging.getLogger(name)
