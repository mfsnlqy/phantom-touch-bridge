from __future__ import annotations

from pathlib import Path


_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "intiface_bridge"
__path__ = [str(_SRC_PACKAGE)]
__file__ = str(_SRC_PACKAGE / "__init__.py")

with open(__file__, "r", encoding="utf-8") as handle:
    exec(compile(handle.read(), __file__, "exec"), globals(), globals())
