"""Shared paths and helpers for the tests. Standard library only."""

from __future__ import annotations

import json
import shutil
import subprocess  # noqa: S404  (runs this repo's own scripts with a fixed argument list)
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SKILL = ROOT / "skills" / "release-readiness"
SCRIPTS = SKILL / "scripts"
# Test fixtures: two illustrative Acme releases and saved gh output. The published sample is in examples/acme.
FIXTURES = HERE / "fixtures"
GH = FIXTURES / "gh"
SAMPLE = ROOT / "examples" / "acme"
INPUTS = ("ci", "bugs", "flags", "evals")

sys.path.insert(0, str(SCRIPTS))


def copy_fixture(name: str, dest: Path) -> Path:
    """Copy a fixture to a scratch directory so a test can change one input."""
    target = dest / name
    shutil.copytree(FIXTURES / name, target)
    return target


def paths(fixture: Path, **skip: bool) -> dict[str, Path | None]:
    """The input paths for decide(), with any input passed as skip=True left out."""
    out: dict[str, Path | None] = {k: None if skip.get(k) else fixture / f"{k}.csv" for k in INPUTS}
    out["brief"] = None if skip.get("brief") else fixture / "brief.md"
    return out


def edit_release(fixture: Path, **changes: object) -> None:
    path = fixture / "release.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(changes)
    path.write_text(json.dumps(data), encoding="utf-8")


def run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / name), *args], capture_output=True, text=True, check=False)  # noqa: S603
