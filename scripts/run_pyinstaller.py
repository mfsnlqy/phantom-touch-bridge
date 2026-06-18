from __future__ import annotations

import os
import sys
from pathlib import Path


def _normalized(path: str | Path) -> str:
    return str(Path(path).resolve()).lower()


def _keep_path(path: str, workspace_root: Path, allowed_paths: list[Path]) -> bool:
    if not path:
        return False

    try:
        resolved = Path(path).resolve()
    except OSError:
        return False

    normalized = _normalized(resolved)
    normalized_workspace = _normalized(workspace_root)

    for allowed in allowed_paths:
        allowed_normalized = _normalized(allowed)
        if normalized == allowed_normalized or normalized.startswith(f"{allowed_normalized}\\"):
            return True

    return not (normalized == normalized_workspace or normalized.startswith(f"{normalized_workspace}\\"))


def main() -> None:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[1]
    repo_src = repo_root / "src"
    workspace_root = repo_root.parent

    allowed_paths = [repo_root, repo_src]

    extra_paths = os.environ.get("PHANTOM_TOUCH_BRIDGE_BUILD_EXTRA_PATHS", "")
    if extra_paths.strip():
        for item in extra_paths.split(os.pathsep):
            if item.strip():
                allowed_paths.append(Path(item.strip()))

    filtered_sys_path = [
        path for path in sys.path if _keep_path(path, workspace_root=workspace_root, allowed_paths=allowed_paths)
    ]

    sys.path[:] = []
    sys.path.append(str(repo_root))
    sys.path.append(str(repo_src))

    for path in filtered_sys_path:
        if path not in sys.path:
            sys.path.append(path)

    print("[phantom-touch-bridge] Filtered sys.path for PyInstaller:")
    for path in sys.path:
        print(f"  {path}")

    from PyInstaller.__main__ import run

    run(sys.argv[1:])


if __name__ == "__main__":
    main()
