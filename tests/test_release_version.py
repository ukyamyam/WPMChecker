from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


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


@pytest.mark.parametrize(
    ("field", "expected_error"),
    [
        ("top-level", "electron/package-lock.json=9.9.9"),
        ("root-package", 'electron/package-lock.json packages[""]=9.9.9'),
    ],
)
def test_release_version_check_rejects_each_mismatched_package_lock_field(
    tmp_path: Path, field: str, expected_error: str
) -> None:
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "packaging/check_release_version.py",
        "pyproject.toml",
        "electron/package.json",
        "electron/package-lock.json",
        "backend/wpmchecker/__init__.py",
    ):
        source = root / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    lock_path = tmp_path / "electron/package-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if field == "top-level":
        lock["version"] = "9.9.9"
    else:
        lock["packages"][""]["version"] = "9.9.9"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "packaging/check_release_version.py", "v0.2.1"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert expected_error in result.stderr
