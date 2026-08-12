from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .surface import PublicMember

_TOOL = Path(__file__).resolve().parents[3] / "tools" / "dts-surface" / "index.mjs"


def extract(path: Path) -> set[PublicMember]:
    proc = subprocess.run(["node", str(_TOOL), str(path)], capture_output=True, text=True, check=False)
    if proc.returncode:
        raise RuntimeError(f"dts-surface failed: {proc.stderr.strip()}")
    return {PublicMember(**member) for member in json.loads(proc.stdout)}
