#!/usr/bin/env python3
"""Read CI checks and open bugs from GitHub through the gh CLI, and write ci.csv and bugs.csv.

Usage:
  python3 scripts/from_gh.py --repo OWNER/NAME --ref <sha|branch|tag> --out run/
      [--label bug] [--milestone "1.4"] [--required "test" --required "lint"]

  Offline, from saved gh output (what the tests use):
  python3 scripts/from_gh.py --check-runs-json runs.json --issues-json issues.json --commit <sha> --out run/

It only reads. It calls gh with fixed arguments (never a shell) and makes no other network call.
Check runs come from the GitHub Checks API; legacy commit statuses are not read in v0.1.
Severity comes from issue labels such as severity:critical, sev1 or P0. An issue with no severity
label is written with an empty severity, and readiness.py counts it as untriaged.

Text from GitHub (titles, check names) is written as data. Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess  # noqa: S404  (gh is called with a fixed argument list, never through a shell)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from readiness import normalise_severity  # noqa: E402  (the shared severity map, beside this file)

CI_COLUMNS = ["check", "conclusion", "required", "commit", "url", "owner"]
BUG_COLUMNS = ["id", "title", "severity", "state", "owner", "url"]


class GhError(Exception):
    """gh is missing, not signed in, or returned something unexpected."""


def run_gh(args: list[str]) -> str:
    if shutil.which("gh") is None:
        raise GhError("gh is not installed. Install it, or pass ci.csv and bugs.csv to readiness.py instead.")
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if proc.returncode != 0:
        raise GhError(f"gh {' '.join(args[:2])} failed: {proc.stderr.strip() or 'no message'}")
    return proc.stdout


def parse_ndjson(text: str) -> list[dict]:
    text = text.strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    if text.startswith("{") and '"check_runs"' in text.split("\n", 1)[0]:
        return json.loads(text)["check_runs"]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def ci_rows(check_runs: list[dict], required: set[str] | None = None) -> list[dict]:
    """One row per check run. A run still in progress is written as pending. Only the latest run per name counts."""
    latest: dict[str, dict] = {}
    for run in check_runs:
        name = str(run.get("name", "")).strip()
        if not name:
            continue
        prev = latest.get(name)
        if prev is None or str(run.get("started_at") or "") >= str(prev.get("started_at") or ""):
            latest[name] = run
    rows = []
    for name in sorted(latest):
        run = latest[name]
        status = str(run.get("status", "")).lower()
        conclusion = str(run.get("conclusion") or "").lower() if status == "completed" else "pending"
        rows.append(
            {
                "check": name,
                "conclusion": conclusion or "pending",
                "required": "yes" if required is None or name in required else "no",
                "commit": str(run.get("head_sha", "")),
                "url": str(run.get("html_url", "")),
                "owner": "",
            }
        )
    return rows


def bug_rows(issues: list[dict]) -> list[dict]:
    rows = []
    for issue in issues:
        labels = [str(lab.get("name", "")) if isinstance(lab, dict) else str(lab) for lab in issue.get("labels") or []]
        severity = next((s for s in (normalise_severity(lab) for lab in labels) if s), "")
        assignees = [str(a.get("login", "")) if isinstance(a, dict) else str(a) for a in issue.get("assignees") or []]
        rows.append(
            {
                "id": str(issue.get("number", "")),
                "title": str(issue.get("title", "")),
                "severity": severity,
                "state": str(issue.get("state", "open")).lower(),
                "owner": ", ".join(a for a in assignees if a),
                "url": str(issue.get("url", "")),
            }
        )
    return rows


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read CI checks and open bugs from GitHub through gh.")
    ap.add_argument("--repo", help="OWNER/NAME")
    ap.add_argument("--ref", help="the release commit SHA, branch or tag")
    ap.add_argument("--label", default="bug", help="the label that marks a bug (default: bug)")
    ap.add_argument("--milestone", help="only issues in this milestone")
    ap.add_argument("--required", action="append", help="a required check name; repeat. Default: every check is required")
    ap.add_argument("--check-runs-json", type=Path, help="saved check runs, instead of calling gh")
    ap.add_argument("--issues-json", type=Path, help="saved issues, instead of calling gh")
    ap.add_argument("--commit", help="the release commit, with the saved JSON options")
    ap.add_argument("--out", type=Path, default=Path("run"))
    args = ap.parse_args(argv)
    required = set(args.required) if args.required else None
    try:
        if args.check_runs_json or args.issues_json:
            runs = parse_ndjson(args.check_runs_json.read_text(encoding="utf-8")) if args.check_runs_json else None
            issues = json.loads(args.issues_json.read_text(encoding="utf-8")) if args.issues_json else None
            sha = args.commit or ""
        else:
            if not args.repo or not args.ref:
                ap.error("--repo and --ref are required unless you pass saved JSON")
            sha = run_gh(["api", f"repos/{args.repo}/commits/{args.ref}", "--jq", ".sha"]).strip()
            jq = ".check_runs[] | {name, status, conclusion, head_sha, html_url, started_at}"
            runs = parse_ndjson(run_gh(["api", f"repos/{args.repo}/commits/{sha}/check-runs", "--paginate", "--jq", jq]))
            cmd = ["issue", "list", "--repo", args.repo, "--state", "open", "--label", args.label]
            cmd += ["--json", "number,title,labels,assignees,url,state", "--limit", "1000"]
            if args.milestone:
                cmd += ["--milestone", args.milestone]
            issues = json.loads(run_gh(cmd) or "[]")
    except (GhError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if runs is not None:
        write_csv(args.out / "ci.csv", CI_COLUMNS, ci_rows(runs, required))
        print(f"wrote {args.out / 'ci.csv'}: {len(ci_rows(runs, required))} checks")
    if issues is not None:
        write_csv(args.out / "bugs.csv", BUG_COLUMNS, bug_rows(issues))
        print(f"wrote {args.out / 'bugs.csv'}: {len(issues)} open issues labelled {args.label}")
    if sha:
        print(f"release commit: {sha}  (put this in release.json as commit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
