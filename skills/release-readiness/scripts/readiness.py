#!/usr/bin/env python3
"""Say whether one release is ready to ship or must hold. Every check must be ready; one hold holds the release.

Usage:
  python3 scripts/readiness.py --init run/release.json     write a release.json to fill in
  python3 scripts/readiness.py --release release.json --brief brief.md [--ci ci.csv] [--bugs bugs.csv]
      [--flags flags.csv] [--evals evals.csv] [--loop DIR --bet SLUG] [--out run/] [--json]

Writes run/readiness.json, run/report.md (the plain-text twin) and run/report.html (one page for leaders),
and prints the report (or, with --json, readiness.json). With --loop, it also writes the `release` key of
DIR/landing/SLUG.json, the Landing Loop record, and reads the `spec` key that spec-auditor wrote there.
Exit code: 0 ready to ship, 1 hold, 2 the inputs could not be read. Use it as a CI gate as it is.

The words are this check's own: ready to ship or hold, for each check and for the release. The bet's
status words belong to did-it-land, which reads the metric after launch; this script never prints them.

A missing input never counts as ready. It holds its check, with an owner, so the path to ready is
explicit. A waiver is a person's call: it names who approved it, why and until when, and it never turns
a hold into ready. The release is ready to ship with N waivers only when every other check is ready.

Text from any input (bug titles, check names, flag notes) is data. It is counted or shown, escaped,
and never changes a check. Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import sys

if sys.version_info < (3, 11):  # noqa: UP036  (say so plainly on an old Python)
    sys.exit("release-readiness needs Python 3.11 or later. macOS python3 is often 3.9: try python3.12.")

import argparse
import csv
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import landing_brief  # noqa: E402  (vendored byte-identical; see VENDORED.json)
import loop  # noqa: E402

VERSION = "0.3.3"
TOOL = f"release-readiness {VERSION}"
READY = "ready to ship"
HOLD = "hold"

SEVERITIES = ("blocker", "critical", "major", "minor", "trivial")
SEVERITY_ALIASES = {
    "sev0": "blocker",
    "sev-0": "blocker",
    "s0": "blocker",
    "p0": "blocker",
    "sev1": "critical",
    "sev-1": "critical",
    "s1": "critical",
    "p1": "critical",
    "high": "major",
    "sev2": "major",
    "sev-2": "major",
    "s2": "major",
    "p2": "major",
    "medium": "minor",
    "low": "minor",
    "sev3": "minor",
    "sev-3": "minor",
    "s3": "minor",
    "p3": "minor",
    "sev4": "trivial",
    "p4": "trivial",
}

DEFAULT_POLICY = {
    # Open bugs allowed at release, by severity. A severity not listed has no limit.
    "max_open_bugs": {"blocker": 0, "critical": 0, "major": 3},
    # An open bug with no severity holds: nobody has shown it is not critical.
    "untriaged_blocks": True,
    # The rollback must have been rehearsed within this many days of the as-of date.
    "rollback_test_max_age_days": 30,
    # Every flag must start at or below this rollout percentage.
    "max_initial_rollout_percent": 100,
    # The eval gate, for a feature whose brief says the line is a model call.
    "min_eval_cases": 50,
    "eval_max_age_days": 7,
    # The release needs a complete landing brief, read with the brief's own parser.
    "require_brief": True,
    # A check may be waived by a named approver who does not own it, until a date. Set false to forbid.
    "allow_waivers": True,
    # A waiver may run at most this many days past the as-of date, so it cannot stand in for a fix.
    "max_waiver_days": 14,
}

CHECKS = {
    "ci": "CI passes on the release commit",
    "bugs": "Open bugs within the severity limits",
    "flags": "Every change behind a flag with an off switch",
    "rollback": "Rollback written, owned, rehearsed, with a trigger threshold",
    "brief": "Landing brief complete, and its date still ahead",
    "evals": "Eval gate passes on the release commit",
    "spec": "Spec holds from spec-auditor are closed",
}

# spec-auditor finding -> the check here that tests the same thing. A hold with no check here stays open until spec-auditor passes it.
SPEC_CLOSED_BY = {"rollback": "rollback", "eval-plan": "evals", "rollout": "flags"}

TEMPLATE = {
    "name": "<product and version>",
    "owner": "<release owner: owns any check below without its own owner>",
    "as_of": "<YYYY-MM-DD, the day of the check>",
    "commit": "<release commit SHA>",
    "ai_feature": False,
    "owners": {"ci": "", "bugs": "", "flags": "", "rollback": "", "brief": "", "evals": "", "spec": ""},
    "rollback": {
        "plan": "<how to undo it>",
        "owner": "<name>",
        "tested_on": "<YYYY-MM-DD last rehearsal>",
        "trigger": "<the threshold that starts a rollback, such as errors above 2%>",
    },
    "waivers": [],
    "policy": {},
}

YES = {"yes", "y", "true", "1"}
HAS_NUMBER = re.compile(r"\d")


class InputError(Exception):
    """An input file is missing a column, a value or a date the call needs."""


@dataclass
class Figure:
    id: str
    label: str
    value: int | float
    unit: str
    source: str
    window_from: str
    window_to: str


@dataclass
class Check:
    id: str
    label: str
    ready: bool
    owner: str
    reasons: list[str] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def fig(self, fid: str, label: str, value: int | float, unit: str, source: str, frm: str, to: str) -> None:
        self.figures.append(Figure(f"{self.id}.{fid}", label, value, unit, source, frm, to))


# ---------------------------------------------------------------- reading


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise InputError(f"{path}: file not found")
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in rows]


def need(row: dict[str, str], col: str, where: str) -> str:
    value = row.get(col, "")
    if value == "":
        raise InputError(f"{where}: column '{col}' is empty or missing")
    return value


def parse_date(value: str, where: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise InputError(f"{where}: '{value}' is not a YYYY-MM-DD date") from exc


def parse_int(value: str, where: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise InputError(f"{where}: '{value}' is not a whole number") from exc


def parse_fraction(value: str, where: str) -> Fraction:
    """A threshold such as 0.95 or 95%, kept exact so 0.95 never compares as 0.9499999."""
    text = value.strip()
    is_pct = text.endswith("%")
    try:
        number = Fraction(Decimal(text.rstrip("%").strip()))
    except (InvalidOperation, ValueError) as exc:
        raise InputError(f"{where}: '{value}' is not a number") from exc
    return number / 100 if is_pct or number > 1 else number


def pct(value: Fraction) -> str:
    """A share as a percentage to at most one decimal place, rounded half up: 95%, 99.5%."""
    tenths = (value * 1000 + Fraction(1, 2)).__floor__()
    return f"{tenths // 10}%" if tenths % 10 == 0 else f"{tenths // 10}.{tenths % 10}%"


def normalise_severity(raw: str) -> str:
    key = raw.strip().lower()
    for prefix in ("severity:", "severity/", "severity-", "sev:", "sev/"):
        if key.startswith(prefix):
            key = key[len(prefix) :].strip()
            if key.isdigit():
                key = "sev" + key
    if key in SEVERITIES:
        return key
    return SEVERITY_ALIASES.get(key, "")


def load_release(path: Path) -> dict:
    if not path.exists():
        raise InputError(f"{path}: file not found")
    try:
        release = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: not valid JSON ({exc.msg})") from exc
    for key in ("name", "owner", "as_of"):
        if not str(release.get(key, "")).strip():
            raise InputError(f"{path}: '{key}' is required")
    left = placeholders(release)
    if left:
        raise InputError(f"{path}: still has template values to fill in: {', '.join(left)}")
    release["as_of_date"] = parse_date(str(release["as_of"]), f"{path} as_of")
    release["as_of"] = release["as_of_date"].isoformat()
    policy = dict(DEFAULT_POLICY)
    policy.update(release.get("policy") or {})
    release["policy"] = policy
    return release


def placeholders(value: object, at: str = "") -> list[str]:
    """Paths in release.json that still hold a <...> value from the --init template."""
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in placeholders(v, f"{at}.{k}" if at else str(k))]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in placeholders(v, f"{at}[{i}]")]
    text = str(value).strip()
    return [at] if text.startswith("<") and text.endswith(">") else []


def owner_for(release: dict, check: str) -> str:
    owners = release.get("owners") or {}
    return str(owners.get(check) or release["owner"]).strip()


def plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def same_commit(a: str, b: str) -> bool:
    """True when one SHA is a prefix of the other, so a short SHA matches its full form."""
    return a.startswith(b) or b.startswith(a)


def posix(path: Path) -> str:
    return path.as_posix()


# ---------------------------------------------------------------- checks


def check_ci(release: dict, path: Path | None) -> Check:
    c = Check("ci", CHECKS["ci"], False, owner_for(release, "ci"))
    if path is None:
        c.reasons.append("No CI input. Run from_gh.py or pass --ci ci.csv.")
        return c
    rows = read_csv(path)
    src, day = posix(path), release["as_of"]
    commit = str(release.get("commit", "")).strip().lower()
    required = []
    for i, row in enumerate(rows, start=2):
        where = f"{path.name} row {i}"
        name = need(row, "check", where)
        if row.get("required", "yes").lower() not in YES:
            if row.get("conclusion", "").lower() not in {"success", "skipped", "neutral"}:
                c.notes.append(f"Check '{name}' is {row.get('conclusion') or 'blank'} but not required, so it does not hold the release ({where}).")
            continue
        required.append((i, name, need(row, "conclusion", where).lower(), row.get("commit", "").lower(), row.get("owner", "")))
    passed = [r for r in required if r[2] == "success"]
    c.fig("required", "Required checks", len(required), "checks", src, day, day)
    c.fig("passed", "Required checks passing", len(passed), "checks", src, day, day)
    if not required:
        c.reasons.append("No required checks found, so CI cannot be shown to pass.")
    for i, name, conclusion, _, check_owner in required:
        if conclusion != "success":
            who = f" (owner: {check_owner})" if check_owner and check_owner.lower() != c.owner.lower() else ""
            c.reasons.append(f"Check '{name}' is {conclusion}, not success ({path.name} row {i}){who}.")
    if not commit:
        c.reasons.append("release.json names no commit, so the checks cannot be tied to this release.")
    else:
        for i, name, _, sha, _ in required:
            if not sha:
                c.reasons.append(f"Check '{name}' names no commit, so it cannot be tied to this release ({path.name} row {i}).")
            elif not same_commit(sha, commit):
                c.reasons.append(f"Check '{name}' ran on {sha[:12]}, not the release commit {commit[:12]} ({path.name} row {i}).")
    c.ready = not c.reasons
    return c


def check_bugs(release: dict, path: Path | None) -> Check:
    c = Check("bugs", CHECKS["bugs"], False, owner_for(release, "bugs"))
    if path is None:
        c.reasons.append("No bug input. Run from_gh.py or pass --bugs bugs.csv.")
        return c
    policy = release["policy"]
    limits = {k.lower(): int(v) for k, v in (policy.get("max_open_bugs") or {}).items()}
    rows = read_csv(path)
    src, day = posix(path), release["as_of"]
    counts = dict.fromkeys((*SEVERITIES, "untriaged"), 0)
    by_sev: dict[str, list[str]] = {k: [] for k in counts}
    for i, row in enumerate(rows, start=2):
        where = f"{path.name} row {i}"
        if row.get("state", "open").lower() not in {"open", "opened", "reopened", "in progress"}:
            continue
        sev = normalise_severity(row.get("severity", "")) or "untriaged"
        counts[sev] += 1
        who = row.get("owner") or "no owner"
        by_sev[sev].append(f"#{need(row, 'id', where)} ({who})")
    for sev, n in counts.items():
        c.fig(f"open.{sev}", f"Open {sev} bugs", n, "bugs", src, day, day)
    for sev, limit in limits.items():
        if sev in counts and counts[sev] > limit:
            c.reasons.append(f"{plural(counts[sev], f'open {sev} bug')} against a limit of {limit}: {', '.join(by_sev[sev])}.")
    if policy.get("untriaged_blocks", True) and counts["untriaged"]:
        c.reasons.append(f"{plural(counts['untriaged'], 'open bug')} with no severity, so none can be ruled out: {', '.join(by_sev['untriaged'])}.")
    c.ready = not c.reasons
    return c


def check_flags(release: dict, path: Path | None) -> Check:
    c = Check("flags", CHECKS["flags"], False, owner_for(release, "flags"))
    if path is None:
        c.reasons.append("No flag input. Pass --flags flags.csv.")
        return c
    limit = int(release["policy"].get("max_initial_rollout_percent", 100))
    rows = read_csv(path)
    src, day = posix(path), release["as_of"]
    with_off, top = 0, 0
    for i, row in enumerate(rows, start=2):
        where = f"{path.name} row {i}"
        name = need(row, "flag", where)
        off = row.get("off_switch", "").lower() in YES
        with_off += off
        if not off:
            c.reasons.append(f"Flag '{name}' has no off switch ({where}).")
        if not row.get("owner"):
            c.reasons.append(f"Flag '{name}' has no owner ({where}).")
        rollout = parse_int(need(row, "rollout_percent", where), where)
        top = max(top, rollout)
        if rollout > limit:
            c.reasons.append(f"Flag '{name}' starts at {rollout}%, above the {limit}% limit ({where}).")
    c.fig("total", "Flags in this release", len(rows), "flags", src, day, day)
    c.fig("off_switch", "Flags with an off switch", with_off, "flags", src, day, day)
    if rows:
        c.fig("top_rollout", "Largest starting rollout", top, "%", src, day, day)
    else:
        c.reasons.append("No flags listed, so no change can be switched off without a deploy.")
    c.ready = not c.reasons
    return c


def check_rollback(release: dict, source: str) -> Check:
    c = Check("rollback", CHECKS["rollback"], False, owner_for(release, "rollback"))
    plan = release.get("rollback") or {}
    if not plan:
        c.reasons.append("release.json has no rollback section.")
        return c
    if not str(plan.get("plan", "")).strip():
        c.reasons.append("No written rollback plan (rollback.plan is empty).")
    if not str(plan.get("owner", "")).strip():
        c.reasons.append("Nobody owns the rollback (rollback.owner is empty).")
    trigger = str(plan.get("trigger", "")).strip()
    if not trigger:
        c.reasons.append("No signal is named to start a rollback (rollback.trigger is empty).")
    elif not HAS_NUMBER.search(trigger):
        c.reasons.append("The rollback trigger has no threshold. Say what number starts it, such as errors above 2%.")
    tested = str(plan.get("tested_on", "")).strip()
    max_age = int(release["policy"]["rollback_test_max_age_days"])
    if not tested:
        c.reasons.append("The rollback has never been rehearsed (rollback.tested_on is empty).")
    else:
        age = (release["as_of_date"] - parse_date(tested, f"{source} rollback.tested_on")).days
        c.fig("test_age_days", "Days since the rollback was rehearsed", age, "days", source, tested[:10], release["as_of"])
        if age < 0:
            c.reasons.append(f"rollback.tested_on {tested} is after the as-of date {release['as_of']}.")
        elif age > max_age:
            c.reasons.append(f"The rollback was last rehearsed {age} days ago, beyond the {max_age}-day limit.")
    c.ready = not c.reasons
    return c


def read_brief(path: Path | None) -> tuple[landing_brief.Brief | None, list[str]]:
    """The brief, through the landing-brief skill's own parser and its own completeness check."""
    if path is None:
        return None, ["No landing brief. Pass --brief brief.md, or --loop with a record that names one."]
    if not path.exists():
        raise InputError(f"{path}: file not found")
    try:
        return landing_brief.parse(path.read_text(encoding="utf-8")), []
    except landing_brief.BriefError as exc:
        lines = [ln.strip() for ln in str(exc).splitlines() if ln.strip()]
        problems = lines[1:] or [lines[0]]
        return None, [f"The landing brief cannot be used: {p}" for p in problems]


def check_brief(release: dict, path: Path | None, brief: landing_brief.Brief | None, problems: list[str], record_brief: dict | None) -> Check:
    c = Check("brief", CHECKS["brief"], False, owner_for(release, "brief"))
    c.reasons += problems
    if brief is not None and path is not None:
        days = (parse_date(brief.by, f"{path.name} By") - release["as_of_date"]).days
        c.fig("days_to_date", "Days from this check to the brief's date", days, "days", posix(path), release["as_of"], brief.by)
        if days <= 0:
            c.reasons.append(f"The brief's date, {brief.by}, is not after this check ({release['as_of']}), so the bar can no longer be met in time.")
    if record_brief and record_brief.get("sha256") and path is not None and path.exists():
        found = loop.sha256(path)
        if found != record_brief["sha256"]:
            c.reasons.append(
                f"The brief changed after the loop record opened (sha256 {found[:12]}, record {str(record_brief['sha256'])[:12]}). Use the record's brief."
            )
    c.ready = not c.reasons
    return c


def check_evals(release: dict, path: Path | None) -> Check:
    c = Check("evals", CHECKS["evals"], False, owner_for(release, "evals"))
    if path is None:
        c.reasons.append("This is an AI feature (a model call) and there is no eval input. Pass --evals evals.csv.")
        return c
    policy = release["policy"]
    min_cases = int(policy["min_eval_cases"])
    max_age = int(policy["eval_max_age_days"])
    commit = str(release.get("commit", "")).strip().lower()
    rows = read_csv(path)
    src = posix(path)
    passing = 0
    for n, row in enumerate(rows, start=1):
        where = f"{path.name} row {n + 1}"
        name = need(row, "eval", where)
        cases = parse_int(need(row, "cases", where), where)
        passed = parse_int(need(row, "passed", where), where)
        threshold = parse_fraction(need(row, "threshold", where), where)
        if cases <= 0 or passed < 0 or passed > cases:
            raise InputError(f"{where}: passed must be between 0 and cases, and cases above 0")
        run_at = row.get("run_at", "")[:10]
        if run_at:
            parse_date(run_at, where)
        day = run_at or release["as_of"]
        needed = math.ceil(threshold * cases)
        c.fig(f"{n}.cases", f"{name}: cases run", cases, "cases", src, day, day)
        c.fig(f"{n}.passed", f"{name}: cases passed", passed, "cases", src, day, day)
        c.fig(f"{n}.needed", f"{name}: cases its {pct(threshold)} threshold needs", needed, "cases", src, day, day)
        before = len(c.reasons)
        if passed < needed:
            c.reasons.append(f"Eval '{name}': {passed} of {cases} cases passed; its {pct(threshold)} threshold needs {needed}.")
        if cases < min_cases:
            c.reasons.append(f"Eval '{name}' has {cases} cases, fewer than the {min_cases} the gate needs.")
        if not run_at:
            c.reasons.append(f"Eval '{name}' has no run_at date ({where}).")
        else:
            age = (release["as_of_date"] - parse_date(run_at, where)).days
            if age > max_age:
                c.reasons.append(f"Eval '{name}' ran {age} days before the as-of date, beyond the {max_age}-day limit.")
        sha = row.get("commit", "").lower()
        if commit and sha and not same_commit(sha, commit):
            c.reasons.append(f"Eval '{name}' ran on {sha[:12]}, not the release commit {commit[:12]}.")
        passing += len(c.reasons) == before
    day = release["as_of"]
    c.fig("total", "Evals in the gate", len(rows), "evals", src, day, day)
    c.fig("passing", "Evals passing the gate", passing, "evals", src, day, day)
    if not rows:
        c.reasons.append("The eval file lists no evals.")
    c.ready = not c.reasons
    return c


def check_spec(release: dict, spec: dict | None, record_path: str, others: dict[str, Check]) -> tuple[Check, list[dict]]:
    """Each hold spec-auditor raised closes only when the check here that tests the same thing is ready to ship."""
    c = Check("spec", CHECKS["spec"], False, owner_for(release, "spec"))
    if not spec:
        c.reasons.append("The loop record has no spec key. Run spec-auditor on the spec first (02 Spec).")
        return c, []
    spec_as_of = str(spec.get("as_of", ""))[:10] or release["as_of"]
    by_tool = " ".join(str(x) for x in (spec.get("tool", "spec-auditor"), spec.get("version", "")) if x)
    src = f"{record_path}, spec key ({by_tool}, {spec_as_of})"
    rows = []
    for h in spec.get("holds") or []:
        sid = str(h.get("check", "")).strip()
        msg = str(h.get("message", "")).strip()
        by = SPEC_CLOSED_BY.get(sid)
        closed = bool(by and by in others and others[by].ready)
        rows.append({"finding": sid, "message": msg, "closed_by": by, "closed": closed})
        if not by:
            c.reasons.append(f"Spec hold '{sid}' ({msg}) has no release check that closes it. Fix the spec and run spec-auditor again.")
        elif by not in others:
            c.reasons.append(f"Spec hold '{sid}' ({msg}) stays open: no {by} check runs for this release.")
        elif not closed:
            c.reasons.append(f"Spec hold '{sid}' ({msg}) stays open: the {by} check holds.")
    c.fig("holds", "Holds spec-auditor raised", len(rows), "findings", src, spec_as_of, release["as_of"])
    c.fig("closed", "Spec holds closed by a ready check", sum(r["closed"] for r in rows), "findings", src, spec_as_of, release["as_of"])
    c.ready = not c.reasons
    return c, rows


# ---------------------------------------------------------------- the call


def decide(
    release_path: Path,
    ci: Path | None = None,
    bugs: Path | None = None,
    flags: Path | None = None,
    evals: Path | None = None,
    brief: Path | None = None,
    loop_dir: Path | None = None,
    bet: str | None = None,
) -> dict:
    release = load_release(release_path)
    record = None
    record_path = ""
    if loop_dir is not None:
        if not bet:
            found = sorted((loop_dir / "landing").glob("*.json"))
            if len(found) != 1:
                raise InputError("--loop needs --bet, the bet's slug, such as quote-drafting (the folder does not hold exactly one record)")
            bet = found[0].stem
        try:
            record = loop.load(loop_dir, bet)
        except loop.RecordError as exc:
            raise InputError(str(exc)) from exc
        record_path = posix(loop.path_for(loop_dir, bet))
        if brief is None and record and (record.get("brief") or {}).get("path"):
            brief = loop_dir / record["brief"]["path"]
    read = loop.upstream(record)
    parsed, problems = read_brief(brief)
    ai_feature = bool(release.get("ai_feature")) or (parsed is not None and parsed.line == "model call")
    checks = [check_ci(release, ci), check_bugs(release, bugs), check_flags(release, flags), check_rollback(release, posix(release_path))]
    if release["policy"].get("require_brief", True):
        checks.append(check_brief(release, brief, parsed, problems, (record or {}).get("brief")))
    if ai_feature:
        checks.append(check_evals(release, evals))
    spec_rows: list[dict] = []
    if loop_dir is not None:
        spec_check, spec_rows = check_spec(release, read.get("spec"), record_path, {c.id: c for c in checks})
        checks.append(spec_check)
    total = len(checks)
    ready = sum(c.ready for c in checks)
    waived, problems_w = apply_waivers(release, checks, release_path.name)
    word = READY if total > 0 and ready + len(waived) == total else HOLD
    d = {
        "tool": TOOL,
        "release": release["name"],
        "commit": release.get("commit", ""),
        "as_of": release["as_of"],
        "owner": release["owner"],
        "bet": bet,
        "ai_feature": ai_feature,
        "illustrative": bool(release.get("illustrative")),
        "readiness": word,
        "ready": ready,
        "total": total,
        "holds": [{"id": c.id, "label": c.label, "owner": c.owner, "reasons": c.reasons} for c in checks if not c.ready and c.id not in waived],
        "waived": [{"id": c.id, "label": c.label, "owner": c.owner, "reasons": c.reasons, **waived[c.id]} for c in checks if c.id in waived],
        "waiver_problems": problems_w,
        "policy_changes": policy_changes(release),
        "checks": [{**asdict(c), "readiness": READY if c.ready else HOLD} for c in checks],
        "spec_holds": spec_rows,
        "brief": brief_summary(parsed, brief),
        "decides": parsed.decides if parsed else release["owner"],
    }
    d["next_step"] = next_step(d)
    return d


def brief_summary(b: landing_brief.Brief | None, path: Path | None) -> dict | None:
    if b is None or path is None:
        return None
    better = "higher" if b.higher_is_better else "lower"
    return {"path": posix(path), "metric": b.metric, "bar": b.bar_text, "better": better, "by": b.by, "line": b.line, "decides": b.decides}


def next_step(d: dict) -> str:
    if d["readiness"] == HOLD:
        return "Close each held check with its owner, then run this check again. Nothing ships on a hold."
    after = ""
    if d["brief"]:
        b = d["brief"]
        after = f" After launch, did-it-land reads {b['metric'].lower()} against the {b['bar']} bar set for {b['by']}."
    if d["waived"]:
        first = min(w["expires"] for w in d["waived"])
        return f"Ship, and close each waived check before its waiver runs out (the first on {first}).{after}"
    return f"Ship.{after}"


def apply_waivers(release: dict, checks: list[Check], source: str) -> tuple[dict[str, dict], list[str]]:
    """Valid waivers by check id, and why each other waiver does not count.

    A waiver counts only when the check holds, waivers are allowed, a reason and an approver are named, the
    approver does not own the check, and it has not run out. A waiver never turns a hold into ready: the report
    shows the check as hold, waived, with its reasons and the person who made the call.
    """
    by_id = {c.id: c for c in checks}
    valid: dict[str, dict] = {}
    problems: list[str] = []
    for n, w in enumerate(release.get("waivers") or [], start=1):
        cid = str(w.get("check", "")).strip()
        approver = str(w.get("approved_by", "")).strip()
        expires = str(w.get("expires", "")).strip()
        label = f"Waiver {n} ({cid or 'no check'})"
        if not release["policy"].get("allow_waivers", True):
            problems.append(f"{label}: the policy does not allow waivers.")
        elif cid not in by_id:
            problems.append(f"{label}: no such check in this release.")
        elif by_id[cid].ready:
            problems.append(f"{label}: the check is ready to ship, so the waiver is not needed.")
        elif not str(w.get("reason", "")).strip() or not approver:
            problems.append(f"{label}: a waiver needs a reason and an approver.")
        elif approver.lower() == by_id[cid].owner.lower():
            problems.append(f"{label}: {approver} owns this check and cannot waive it.")
        elif not expires:
            problems.append(f"{label}: a waiver needs an expiry date.")
        elif (days := (parse_date(expires, f"{source} waivers[{n}].expires") - release["as_of_date"]).days) < 0:
            problems.append(f"{label}: ran out on {expires}.")
        elif days > int(release["policy"].get("max_waiver_days", 14)):
            problems.append(f"{label}: runs {days} days, beyond the {release['policy'].get('max_waiver_days', 14)}-day limit for a waiver.")
        else:
            valid[cid] = {"reason": str(w["reason"]).strip(), "approved_by": approver, "expires": expires[:10]}
    return valid, problems


def policy_changes(release: dict) -> list[str]:
    """Every policy value the release changes from the default, in plain words, so a looser or tighter gate is visible."""

    def say(v: object) -> str:
        return ("yes" if v else "no") if isinstance(v, bool) else str(v)

    out = []
    for key, default in DEFAULT_POLICY.items():
        value = release["policy"].get(key, default)
        if key == "max_open_bugs" and isinstance(value, dict):
            for sev in sorted({*default, *value}, key=lambda s: SEVERITIES.index(s) if s in SEVERITIES else 99):
                if value.get(sev) != default.get(sev):
                    was = default.get(sev, "no limit")
                    out.append(f"open {sev} bugs allowed: {value.get(sev, 'no limit')} (default {was})")
        elif value != default:
            out.append(f"{key.replace('_', ' ')}: {say(value)} (default {say(default)})")
    return out


# ---------------------------------------------------------------- the record key


def as_figure(f: dict, as_of: str) -> dict[str, Any]:
    return loop.figure(f["value"], f["unit"], f["source"], f["window_from"], f["window_to"], as_of)


def release_key(d: dict, release_path: str) -> dict[str, Any]:
    """The `release` key of the loop record. Every figure is value, unit, source, window and as_of."""
    day = d["as_of"]
    waived = {w["id"]: w for w in d["waived"]}
    checks = []
    for c in d["checks"]:
        entry = {
            "id": c["id"],
            "label": c["label"],
            "readiness": c["readiness"],
            "owner": c["owner"],
            "reasons": c["reasons"],
            "figures": {f["id"].split(".", 1)[1]: as_figure(f, day) for f in c["figures"]},
        }
        if c["id"] in waived:
            w = waived[c["id"]]
            entry["waiver"] = {"approved_by": w["approved_by"], "reason": w["reason"], "expires": w["expires"]}
        checks.append(entry)
    src = f"{TOOL}: count of the checks above; {release_path}"
    return {
        "tool": TOOL,
        "as_of": day,
        "release": d["release"],
        "commit": d["commit"],
        "readiness": d["readiness"],
        "counts": {
            "ready": loop.figure(d["ready"], "checks ready to ship", src, day, day, day),
            "waived": loop.figure(len(d["waived"]), "checks on hold under a waiver", src, day, day, day),
            "hold": loop.figure(len(d["holds"]), "checks on hold", src, day, day, day),
            "total": loop.figure(d["total"], "checks", src, day, day, day),
        },
        "checks": checks,
        "spec_holds": d["spec_holds"],
        "decides": d["decides"],
        "next_step": d["next_step"],
        "illustrative": d["illustrative"],
    }


# ---------------------------------------------------------------- the report


def cell(text: str) -> str:
    """Escape a value for a Markdown table cell, so text from an input cannot break the table or add markup."""
    out = str(text).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    for ch in "<>`*_[]":
        out = out.replace(ch, "\\" + ch)
    return out


def shown(f: dict) -> str:
    """A figure as value and unit: 4 checks, 10%, 8 days."""
    v = f"{f['value']:,}" if isinstance(f["value"], int) else f"{f['value']:,.10g}"
    if f["unit"] == "%":
        return f"{v}%"
    unit = f["unit"][:-1] if f["value"] == 1 and f["unit"].endswith("s") else f["unit"]
    return f"{v} {unit}"


def window(f: dict) -> str:
    return f["window_from"] if f["window_from"] == f["window_to"] else f"{f['window_from']} to {f['window_to']}"


def headline(d: dict) -> str:
    """The call in one sentence, as the report and the page both print it."""
    if d["readiness"] == READY and not d["waived"]:
        return f"Ready to ship. All {d['total']} checks are ready to ship."
    if d["readiness"] == READY:
        n = len(d["waived"])
        held = "1 check holds" if n == 1 else f"{n} checks hold"
        return f"Ready to ship, with {plural(n, 'waiver')}. {d['ready']} of {d['total']} checks are ready to ship; {held} under a waiver."
    n = len(d["holds"])
    return f"Hold. {d['ready']} of {d['total']} checks are ready to ship; {'1 check holds' if n == 1 else f'{n} checks hold'}."


# ---------------------------------------------------------------- plain words
#
# Public copy, on the page and in the Markdown twin, uses plain words (the Landing Loop design spec, 2026-11-27).
# The record keeps its own words: check labels, reasons and next_step are stored as computed above. File names,
# flags and check ids print only under "For your engineers".

PLAIN_LABELS = {
    "ci": "Code checks pass on the version being released",
    "bugs": "Open bugs within the severity limits",
    "flags": "Every change can be switched off",
    "rollback": "Undo plan written, owned and rehearsed, with a point to undo at",
    "brief": "Landing brief complete, and its date still ahead",
    "evals": "Quality tests pass on the version being released",
    "spec": "Build plan holds from spec-auditor are closed",
}
SHORT = {
    "ci": "Code checks",
    "bugs": "Open bugs",
    "flags": "Off switch",
    "rollback": "Undo plan",
    "brief": "Brief",
    "evals": "Quality tests",
    "spec": "Build plan",
}
WAIVER_MEANS = "A waiver is a named person's OK to ship despite a failed check, with an expiry date."
BRIEF_MEANS = "the landing brief, a one-page plan: what good looks like, by when, at what cost"

# Order matters: the longer phrase first.
WORDS = (
    (r"\s*(?:Run from_gh\.py or pass|Pass) --[\w-]+ [\w.]+(?:, or --loop with a record that names one)?\.", " Add the export and run the check again."),
    (r"\s*\((?:[^()]*\.(?:csv|json)\b[^()]*|[a-z_]+\.[a-z_]+ is empty)\)", ""),
    (r"\bCheck '([^']+)' is failure but not required", r"The '\1' code check failed, but it is not required"),
    (r"\bCheck '([^']+)' is failure, not success", r"The '\1' code check failed"),
    (r"\bCheck '([^']+)' is (\w+)", r"The '\1' code check is \2"),
    (r"\bCheck '", "Code check '"),
    (r"\brelease\.json\b", "the release file"),
    (r"\bthe release commit\b", "the version being released"),
    (r"\bThe rollback trigger has no threshold\b", "The undo plan names no point to undo at"),
    (r"\bNo signal is named to start a rollback\b", "The undo plan names no point to undo at"),
    (r"\bstarts a rollback\b", "means undo"),
    (r"\bstart a rollback\b", "undo"),
    (r"\btrigger threshold\b", "point to undo at"),
    (r"\brollback plan\b", "undo plan"),
    (r"\bNobody owns the rollback\b", "Nobody owns the undo plan"),
    (r"\bThe rollback\b", "The undo plan"),
    (r"\brollback\b", "undo plan"),
    (r"\brollout\b", "first release stage"),
    (r"\bthe eval gate\b", "the quality tests"),
    (r"\bThe eval gate does\b", "Quality tests do"),
    (r"\beval gate\b", "quality tests"),
    (r"\beval plan\b", "quality test plan"),
    (r"\bno eval input\b", "no quality test results"),
    (r"\bThe eval file lists no evals\b", "The quality test results list no tests"),
    (r"\bEval '", "Quality test '"),
    (r"\bevals\b", "quality tests"),
    (r"\beval\b", "quality test"),
    (r"\bSpec hold\b", "Build plan hold"),
    (r"\bspec holds?\b", lambda m: m.group(0).replace("spec", "build plan")),
    (r"\bthe spec\b", "the build plan"),
    (r"\b[Ss]pec\b(?!-auditor)", lambda m: "Build plan" if m.group(0)[0] == "S" else "build plan"),
    (r"\bthe loop record has no spec key\b", "the project file has no build plan check"),
    (r"\bThe loop record\b", "The project file"),
    (r"\bthe loop record\b", "the project file"),
    (r"\bthe bar\b", "the target"),
    (r"\bbar\b", "target"),
    (r"\bthe brief's line is fixed code\b", "the landing brief says fixed code, not an AI model, does this work"),
    (r"\bCI\b", "code checks"),
    (r" \(02 Build plan\)", ""),
    (r" \(sha256 [0-9a-f]+, record [0-9a-f]+\)", ""),
)

POLICY_WORDS = {
    "max initial rollout percent": "largest first release stage, in percent",
    "untriaged blocks": "an open bug with no severity holds the release",
    "rollback test max age days": "days allowed since the undo plan was rehearsed",
    "min eval cases": "fewest cases a quality test needs",
    "eval max age days": "days allowed since the quality tests ran",
    "require brief": "landing brief required",
    "allow waivers": "waivers allowed",
    "max waiver days": "longest a waiver may run, in days",
}


def plain(text: str) -> str:
    """Public copy for a stored sentence: plain words, no file names or flags."""
    for pattern, to in WORDS:
        text = re.sub(pattern, to, text)
    return text


def plain_policy(change: str) -> str:
    for key, words in POLICY_WORDS.items():
        if change.startswith(key + ":"):
            return words + change[len(key) :]
    return change


def worth_knowing(d: dict) -> list[str]:
    """Notes for the public copy, in plain words."""
    items = [plain(n) for c in d["checks"] for n in c["notes"]] + [plain(n) for n in d["waiver_problems"]]
    items += [f"Policy changed from the default: {plain_policy(p)}" for p in d["policy_changes"]]
    if not d["ai_feature"]:
        items.append("Quality tests do not apply: the landing brief says fixed code, not an AI model, does this work.")
    return items


def verdict(d: dict) -> str:
    """The page's heading: the call as one plain sentence."""
    name = d["release"]
    if d["readiness"] == READY and not d["waived"]:
        return f"{name} is ready to ship."
    if d["readiness"] == READY:
        n = len(d["waived"])
        return f"{name} is ready to ship, with {'one waiver' if n == 1 else f'{n} waivers'}."
    n = len(d["holds"])
    return f"{name} must hold: {'one check fails' if n == 1 else f'{n} checks fail'}."


def plain_next_step(d: dict) -> str:
    """The one step, in plain words, from the same facts as next_step."""
    after = ""
    if d["brief"]:
        b = d["brief"]
        after = f" After launch, did-it-land reads {b['metric'].lower()} against the {b['bar']} target, due {b['by']}."
    if d["readiness"] == HOLD:
        names = [PLAIN_LABELS.get(o["id"], o["label"]) for o in d["holds"]]
        what = names[0].lower() if len(names) == 1 else ", ".join(SHORT.get(o["id"], o["label"]).lower() for o in d["holds"])
        return f"Fix what fails ({what}) with each owner, then run this check again. Nothing ships on a hold."
    if d["waived"]:
        first = min(w["expires"] for w in d["waived"])
        what = ", ".join(SHORT.get(w["id"], w["label"]).lower() for w in d["waived"])
        return f"Ship it, then fix what the waiver covers ({what}) before it runs out on {first}.{after}"
    return f"Ship it.{after}"


def due(d: dict) -> str:
    """When the next step is due: a waiver's end, else the day of the check."""
    if d["readiness"] == READY and d["waived"]:
        return min(w["expires"] for w in d["waived"])
    return d["as_of"]


def report(d: dict) -> str:
    """The Markdown twin of the page, in the same plain words, with the engineering detail at the end."""
    lines = [f"# Release readiness: {cell(d['release'])}", ""]
    if d["illustrative"]:
        lines += ["*Illustrative: sample data, not a real release.*", ""]
    lines += [f"Checked {d['as_of']}. Release owner: {cell(d['owner'])}.", ""]
    first, rest = headline(d).split(". ", 1)
    lines.append(f"**{first}.** {rest}")
    if d["waived"]:
        lines += ["", WAIVER_MEANS]
    lines += ["", "## What to do next", "", f"{cell(plain_next_step(d))} Decides: {cell(d['decides'])}. Due: {due(d)}."]
    if d["holds"]:
        lines += ["", "## Checks that hold", "", "| Check | Owner | Why it holds |", "|---|---|---|"]
        for o in d["holds"]:
            lines.append(f"| {cell(PLAIN_LABELS.get(o['id'], o['label']))} | {cell(o['owner'])} | {'<br>'.join(cell(plain(r)) for r in o['reasons'])} |")
    if d["waived"]:
        lines += ["", "## Waivers, each a person's call", "", "| Check | Owner | Approved by | Expires | Reason | Holds because |", "|---|---|---|---|---|---|"]
        for w in d["waived"]:
            why = "<br>".join(cell(plain(r)) for r in w["reasons"])
            label = PLAIN_LABELS.get(w["id"], w["label"])
            lines.append(f"| {cell(label)} | {cell(w['owner'])} | {cell(w['approved_by'])} | {cell(w['expires'])} | {cell(w['reason'])} | {why} |")
    waived_ids = {w["id"] for w in d["waived"]}
    lines += ["", "## Every check", "", "| Check | Check word | Owner |", "|---|---|---|"]
    for c in d["checks"]:
        word = f"{HOLD}, waived" if c["id"] in waived_ids else c["readiness"]
        lines.append(f"| {cell(PLAIN_LABELS.get(c['id'], c['label']))} | {word} | {cell(c['owner'])} |")
    if d["spec_holds"]:
        lines += ["", "## Build plan holds from spec-auditor", "", "| What spec-auditor said | Closed by | Closed |", "|---|---|---|"]
        for h in d["spec_holds"]:
            by = SHORT.get(h["closed_by"], h["closed_by"]) if h["closed_by"] else "no check here"
            lines.append(f"| {cell(plain(h['message']))} | {cell(by)} | {'yes' if h['closed'] else 'no'} |")
    notes = worth_knowing(d)
    if notes:
        lines += ["", "## Worth knowing", ""] + [f"- {cell(n)}" for n in notes]
    lines += ["", "## For your engineers", ""]
    eng = [f"Skill: {TOOL}.", f"Commit {d['commit'] or 'not named'}.", f"Check ids: {', '.join(c['id'] for c in d['checks'])}."]
    if d["bet"]:
        eng.append(f"Writes the `release` key of `landing/{d['bet']}.json` and no other key.")
    eng.append("readiness.py exits 0 on ready to ship, 1 on hold and 2 when an input cannot be read, so it can gate a CI job.")
    lines += [f"- {cell(x) if '`' not in x else x}" for x in eng]
    raw = [n for c in d["checks"] for n in c["notes"]] + d["waiver_problems"] + [f"Policy changed from the default: {p}" for p in d["policy_changes"]]
    if not d["ai_feature"]:
        raw.append("The eval gate does not apply: the brief's line is fixed code and release.json does not mark an AI feature.")
    if raw:
        lines += ["", "Notes as computed:", ""] + [f"- {cell(n)}" for n in raw]
    if d["spec_holds"]:
        lines += [
            "",
            "Spec holds as stored: " + "; ".join(f"{cell(h['finding'])} closed by {cell(h['closed_by'] or 'no check')}" for h in d["spec_holds"]) + ".",
        ]
    lines += ["", "### Evidence ledger", "", "| ID | Figure | Value | Window | Source |", "|---|---|---|---|---|"]
    for c in d["checks"]:
        for f in c["figures"]:
            lines.append(f"| {cell(f['id'])} | {cell(f['label'])} | {cell(shown(f))} | {window(f)} | {cell(f['source'])} |")
    lines += ["", f"Computed by {TOOL}. Every figure comes from the source named beside it."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Say whether one release is ready to ship or must hold.")
    ap.add_argument("--release", type=Path, help="release.json: name, owner, as_of, commit, rollback, waivers, policy")
    ap.add_argument("--init", type=Path, metavar="PATH", help="write a release.json template to PATH and stop")
    ap.add_argument("--brief", type=Path, help="the bet's landing brief (Markdown, the Linear project template)")
    ap.add_argument("--loop", type=Path, metavar="DIR", help="working folder holding landing/<bet>.json: reads spec, writes release")
    ap.add_argument("--bet", help="the bet's slug, with --loop (default: the only record in DIR/landing)")
    ap.add_argument("--json", action="store_true", help="print readiness.json instead of the report")
    ap.add_argument("--ci", type=Path, help="ci.csv: check, conclusion, required, commit, url, owner")
    ap.add_argument("--bugs", type=Path, help="bugs.csv: id, title, severity, state, owner")
    ap.add_argument("--flags", type=Path, help="flags.csv: flag, rollout_percent, off_switch, owner")
    ap.add_argument("--evals", type=Path, help="evals.csv: eval, cases, passed, threshold, run_at, commit, owner")
    ap.add_argument("--out", type=Path, default=Path("run"), help="directory for readiness.json, report.md and report.html")
    args = ap.parse_args(argv)
    if args.init:
        if args.init.exists():
            print(f"error: {args.init} exists; not overwriting it", file=sys.stderr)
            return 2
        args.init.parent.mkdir(parents=True, exist_ok=True)
        args.init.write_text(json.dumps(TEMPLATE, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.init}: replace every <...> value, then run readiness.py --release {args.init} --brief <brief.md>")
        return 0
    if not args.release:
        ap.error("pass --release or --init")
    try:
        d = decide(args.release, args.ci, args.bugs, args.flags, args.evals, args.brief, args.loop, args.bet)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    import render_html  # beside this file

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "readiness.json").write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    text = report(d)
    (args.out / "report.md").write_text(text, encoding="utf-8")
    (args.out / "report.html").write_text(render_html.page(d), encoding="utf-8")
    if args.loop:
        brief_path = Path(d["brief"]["path"]) if d["brief"] else args.brief
        loop.write(args.loop, d["bet"], brief_path, release_key(d, posix(args.release)))
    print(json.dumps(d, indent=2, ensure_ascii=False) if args.json else text, end="\n" if args.json else "")
    return 0 if d["readiness"] == READY else 1


if __name__ == "__main__":
    sys.exit(main())
