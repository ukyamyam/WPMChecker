from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_python_module_entrypoint_shows_cli_help() -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "backend")

    result = subprocess.run(
        [sys.executable, "-m", "wpmchecker", "--help"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert "Stage 4/5: WebSocket backend" in result.stdout
