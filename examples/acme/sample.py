#!/usr/bin/env python3
"""Regenerate the committed Acme sample: release-readiness.html, release-readiness.md and the release key of landing/quote-drafting.json.

Inputs, all illustrative (Acme is an invented company): the canonical briefs in briefs/ (copied unchanged from the
landing-loop repo), the release check's inputs in inputs/ (release.json and the CI, bug, flag and eval CSVs), and
upstream/quote-drafting.json, the loop record filtered to the keys release-readiness reads (schema, bet, brief and
spec-auditor's spec key, copied unchanged). The same inputs give the same bytes, so a test can check it.

Usage, from the repo root (Python 3.11 or later, standard library only):
  python3 examples/acme/sample.py [--into DIR]

--into writes the outputs somewhere else (the test uses it); paths inside the outputs stay the same.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path("examples/acme")
sys.path.insert(0, str(ROOT / "skills" / "release-readiness" / "scripts"))

import readiness  # noqa: E402

BET = "quote-drafting"
STEM = "release-readiness"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--into", help="output folder (default examples/acme)")
    args = p.parse_args(argv)
    into = Path(args.into).resolve() if args.into else ROOT / HERE
    with tempfile.TemporaryDirectory() as tmp:
        # Run inside a copy laid out like the repo, so every path written into the outputs is the same wherever they go.
        work = Path(tmp) / HERE
        for part in ("briefs", "inputs"):
            shutil.copytree(ROOT / HERE / part, work / part)
        # Start from the record as spec-auditor left it: release-readiness reads spec and writes only release.
        (work / "landing").mkdir(parents=True)
        shutil.copy(ROOT / HERE / "upstream" / f"{BET}.json", work / "landing" / f"{BET}.json")
        os.chdir(tmp)
        try:
            inputs = HERE / "inputs"
            code = readiness.main(
                [
                    "--release", str(inputs / "release.json"),
                    "--ci", str(inputs / "ci.csv"),
                    "--bugs", str(inputs / "bugs.csv"),
                    "--flags", str(inputs / "flags.csv"),
                    "--evals", str(inputs / "evals.csv"),
                    "--loop", str(HERE),
                    "--bet", BET,
                    "--out", "run",
                ]
            )  # fmt: skip
        finally:
            os.chdir(ROOT)
        (into / "landing").mkdir(parents=True, exist_ok=True)
        shutil.copy(work / "landing" / f"{BET}.json", into / "landing" / f"{BET}.json")
        shutil.copy(Path(tmp) / "run" / "report.html", into / f"{STEM}.html")
        shutil.copy(Path(tmp) / "run" / "report.md", into / f"{STEM}.md")
    print(f"sample: wrote {STEM}.html, {STEM}.md and landing/{BET}.json to {into}")
    return 0 if code in (0, 1) else code


if __name__ == "__main__":
    sys.exit(main())
