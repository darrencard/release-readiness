"""The Landing Loop record: one JSON file per bet, landing/<bet-slug>.json, shared by the loop's skills and the Leader Report.

release-readiness is step 03 Build. It reads `spec` (02 Spec) and writes only its own key, `release`. It reads no key
later in the record order, and keeps every other key exactly as it found it, so a key it read stays byte-identical.
Every figure written carries value, unit, source, window (from, to) and as_of.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

SCHEMA = "landing-loop/1"
KEY = "release"
# The record order (landing-loop tools/sample.py). A skill reads only keys before its own.
ORDER = ("portfolio", "decisions", "spec", "release", "cost", "evals", "landed", "signals", "postmortem", "board_qa")
READS = ("spec",)
MAX_RECORD_BYTES = 2_000_000


class RecordError(ValueError):
    """A loop record that cannot be used. Nothing is written when this is raised."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def path_for(folder: Path, bet: str) -> Path:
    return folder / "landing" / f"{bet}.json"


def load(folder: Path, bet: str) -> dict[str, Any] | None:
    """The record as it stands, or None when there is none yet. Refused if it is not a landing-loop/1 record for this bet."""
    p = path_for(folder, bet)
    if not p.exists():
        return None
    if p.stat().st_size > MAX_RECORD_BYTES:
        raise RecordError(f"{p} is over {MAX_RECORD_BYTES:,} bytes, so it is not a loop record.")
    try:
        record = json.loads(p.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecordError(f"{p} is not valid JSON ({exc}). Fix it or move it; it is never overwritten.") from None
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise RecordError(f"{p} is not a {SCHEMA} record. It is left as it is.")
    if record.get("bet") != bet:
        raise RecordError(f"{p} is the record for {record.get('bet')!r}, not {bet!r}. It is left as it is.")
    return record


def upstream(record: dict[str, Any] | None) -> dict[str, Any]:
    """Only the keys this skill may read: those before `release` in the record order."""
    return {k: record[k] for k in READS if record and k in record}


def figure(value: float | int, unit: str, source: str, window_from: str, window_to: str, as_of: str) -> dict[str, Any]:
    """One figure in the loop's shape. No figure without a source."""
    if not source:
        raise RecordError("a figure has no source. Every figure in the loop record needs one.")
    return {"value": value, "unit": unit, "source": source, "window": {"from": window_from, "to": window_to}, "as_of": as_of}


def write(folder: Path, bet: str, brief_path: Path | None, release: dict[str, Any]) -> Path:
    """Write the `release` key in its place in the record order. Every other key is kept as it was found."""
    p = path_for(folder, bet)
    record = load(folder, bet)
    if record is None:
        record = {"schema": SCHEMA, "bet": bet}
        if brief_path is not None:
            # Relative to the working folder, so the record reads the same on any machine.
            rel = Path(os.path.relpath(brief_path.resolve(), folder.resolve())).as_posix()
            record["brief"] = {"path": rel, "sha256": sha256(brief_path)}
    if KEY in record:
        out = {**record, KEY: release}  # replaced where it stands
    else:
        later = set(ORDER[ORDER.index(KEY) + 1 :])
        out = {}
        for k, v in record.items():
            if k in later and KEY not in out:
                out[KEY] = release
            out[k] = v
        out.setdefault(KEY, release)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p
