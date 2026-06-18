from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SRC_PATH = REPO_ROOT / "src"

src_text = str(SRC_PATH)
if src_text not in sys.path:
    sys.path.insert(0, src_text)
