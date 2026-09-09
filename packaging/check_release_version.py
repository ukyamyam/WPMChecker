from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path


def read_versions(root: Path) -> dict[str, str]:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    electron = json.loads((root / "electron/package.json").read_text(encoding="utf-8"))
    init_text = (root / "backend/wpmchecker/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_text, re.MULTILINE)
    if match is None:
        raise ValueError("backend __version__ is missing")
    return {
        "pyproject.toml": pyproject["project"]["version"],
        "electron/package.json": electron["version"],
        "backend/wpmchecker/__init__.py": match.group(1),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_release_version.py vX.Y.Z", file=sys.stderr)
        return 2
    expected = sys.argv[1].removeprefix("v")
    root = Path(__file__).resolve().parents[1]
    versions = read_versions(root)
    mismatches = {path: version for path, version in versions.items() if version != expected}
    if mismatches:
        details = ", ".join(f"{path}={version}" for path, version in mismatches.items())
        print(f"tag {sys.argv[1]} does not match: {details}", file=sys.stderr)
        return 1
    print(f"release versions match: {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
