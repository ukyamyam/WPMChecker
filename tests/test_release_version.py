from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_release_version_check_accepts_matching_tag() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "packaging/check_release_version.py", "v0.2.1"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "release versions match: 0.2.1" in result.stdout


def test_release_version_check_rejects_mismatched_tag() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "packaging/check_release_version.py", "v9.9.9"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "does not match" in result.stderr
