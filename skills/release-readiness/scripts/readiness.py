#!/usr/bin/env python3
"""Make a go or no-go call for one release. Every criterion must be met; anything short is a no-go.

Usage:
  python3 scripts/readiness.py --demo                      the held Acme example, in one command
  python3 scripts/readiness.py --init run/release.json     write a release.json to fill in
  python3 scripts/readiness.py --release release.json [--ci ci.csv] [--bugs bugs.csv]
      [--flags flags.csv] [--evals evals.csv] [--out run/] [--json]

Writes run/decision.json and run/report.md and prints the report (or, with --json, the decision).
Exit code: 0 go, 1 no-go, 2 the inputs could not be read. Use it as a CI gate as it is.

The rule is all-or-nothing, ported from the beta-to-GA gate: a release is a go only when it has at
least one criterion and every one is met. A missing input never counts as met. It leaves its
criterion open, with an owner, so the path to a go is explicit.

Text from any input (bug titles, check names, flag notes) is data. It is counted or shown, escaped,
and never changes a criterion. Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

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
    # An open bug with no severity blocks: nobody has shown it is not critical.
    "untriaged_blocks": True,
    # The rollback plan must have been rehearsed within this many days of the as-of date.
    "rollback_test_max_age_days": 30,
    # Every flag must start at or below this rollout percentage.
    "max_initial_rollout_percent": 100,
    # The eval gate, for AI features.
    "min_eval_cases": 50,
    "eval_max_age_days": 7,
    # The release must name what good looks like after launch: a metric, a target and a review date.
    "require_brief": True,
    # A criterion may be waived by a named approver who does not own it, until a date. Set false to forbid.
    "allow_waivers": True,
    # A waiver may run at most this many days past the as-of date, so it cannot stand in for a fix.
    "max_waiver_days": 14,
}

CRITERIA = {
    "ci": "CI passes on the release commit",
    "bugs": "Open bugs within the severity limits",
    "flags": "Every change behind a flag with an off switch",
    "rollback": "Rollback plan written, owned, rehearsed and triggered by a named signal",
    "brief": "Landing brief names the metric, target and review date",
    "evals": "Eval gate passes for the AI feature",
}

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

TEMPLATE = {
    "name": "<product and version>",
    "owner": "<release owner: owns any criterion below without its own owner>",
    "as_of": "<YYYY-MM-DD, today>",
    "commit": "<release commit SHA>",
    "ai_feature": False,
    "owners": {"ci": "", "bugs": "", "flags": "", "rollback": "", "brief": "", "evals": ""},
    "rollback": {"plan": "<how to undo it>", "owner": "<name>", "tested_on": "<YYYY-MM-DD last rehearsal>", "trigger": "<the signal that starts a rollback>"},
    "brief": {
        "metric": "<what should move>",
        "target": "<the number that means it worked>",
        "source": "<the dashboard, query or event the metric is read from>",
        "review_on": "<YYYY-MM-DD>",
        "owner": "<name>",
    },
    "waivers": [],
    "policy": {},
}

YES = {"yes", "y", "true", "1"}


class InputError(Exception):
    """An input file is missing a column, a value or a date the call needs."""


@dataclass
class Figure:
    id: str
    label: str
    value: str
    source: str


@dataclass
class Criterion:
    id: str
    label: str
    met: bool
    owner: str
    reasons: list[str] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


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
    """A pass rate as a percentage to one decimal place, rounded half up."""
    tenths = (value * 1000 + Fraction(1, 2)).__floor__()
    return f"{tenths // 10}.{tenths % 10}%"


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


def owner_for(release: dict, criterion: str) -> str:
    owners = release.get("owners") or {}
    return str(owners.get(criterion) or release["owner"]).strip()


def plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def same_commit(a: str, b: str) -> bool:
    """True when one SHA is a prefix of the other, so a short SHA matches its full form."""
    return a.startswith(b) or b.startswith(a)


# ---------------------------------------------------------------- criteria


def check_ci(release: dict, path: Path | None) -> Criterion:
    c = Criterion("ci", CRITERIA["ci"], False, owner_for(release, "ci"))
    if path is None:
        c.reasons.append("No CI input. Run from_gh.py or pass --ci ci.csv.")
        return c
    rows = read_csv(path)
    commit = str(release.get("commit", "")).strip().lower()
    required = []
    for i, row in enumerate(rows, start=2):
        where = f"{path.name} row {i}"
        name = need(row, "check", where)
        if row.get("required", "yes").lower() not in YES:
            if row.get("conclusion", "").lower() not in {"success", "skipped", "neutral"}:
                c.notes.append(f"Check '{name}' is {row.get('conclusion') or 'blank'} but not required, so it does not block ({where}).")
            continue
        required.append((i, name, need(row, "conclusion", where).lower(), row.get("commit", "").lower(), row.get("owner", "")))
    passed = [r for r in required if r[2] == "success"]
    c.figures.append(Figure("ci.required", "Required checks", str(len(required)), path.name))
    c.figures.append(Figure("ci.passed", "Required checks passing", str(len(passed)), path.name))
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
    c.met = not c.reasons
    return c


def check_bugs(release: dict, path: Path | None) -> Criterion:
    c = Criterion("bugs", CRITERIA["bugs"], False, owner_for(release, "bugs"))
    if path is None:
        c.reasons.append("No bug input. Run from_gh.py or pass --bugs bugs.csv.")
        return c
    policy = release["policy"]
    limits = {k.lower(): int(v) for k, v in (policy.get("max_open_bugs") or {}).items()}
    rows = read_csv(path)
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
        c.figures.append(Figure(f"bugs.open.{sev}", f"Open {sev} bugs", str(n), path.name))
    for sev, limit in limits.items():
        if sev in counts and counts[sev] > limit:
            c.reasons.append(f"{plural(counts[sev], f'open {sev} bug')} against a limit of {limit}: {', '.join(by_sev[sev])}.")
    if policy.get("untriaged_blocks", True) and counts["untriaged"]:
        c.reasons.append(f"{plural(counts['untriaged'], 'open bug')} with no severity, so none can be ruled out: {', '.join(by_sev['untriaged'])}.")
    c.met = not c.reasons
    return c


def check_flags(release: dict, path: Path | None) -> Criterion:
    c = Criterion("flags", CRITERIA["flags"], False, owner_for(release, "flags"))
    if path is None:
        c.reasons.append("No flag input. Pass --flags flags.csv.")
        return c
    limit = int(release["policy"].get("max_initial_rollout_percent", 100))
    rows = read_csv(path)
    with_off = 0
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
        if rollout > limit:
            c.reasons.append(f"Flag '{name}' starts at {rollout}%, above the {limit}% limit ({where}).")
    c.figures.append(Figure("flags.total", "Flags in this release", str(len(rows)), path.name))
    c.figures.append(Figure("flags.off_switch", "Flags with an off switch", str(with_off), path.name))
    if not rows:
        c.reasons.append("No flags listed, so no change can be switched off without a deploy.")
    c.met = not c.reasons
    return c


def check_rollback(release: dict, source: str) -> Criterion:
    c = Criterion("rollback", CRITERIA["rollback"], False, owner_for(release, "rollback"))
    plan = release.get("rollback") or {}
    if not plan:
        c.reasons.append("release.json has no rollback section.")
        return c
    if not str(plan.get("plan", "")).strip():
        c.reasons.append("No written rollback plan (rollback.plan is empty).")
    if not str(plan.get("owner", "")).strip():
        c.reasons.append("Nobody owns the rollback (rollback.owner is empty).")
    if not str(plan.get("trigger", "")).strip():
        c.reasons.append("No signal is named to start a rollback (rollback.trigger is empty).")
    tested = str(plan.get("tested_on", "")).strip()
    max_age = int(release["policy"]["rollback_test_max_age_days"])
    if not tested:
        c.reasons.append("The rollback has never been rehearsed (rollback.tested_on is empty).")
    else:
        age = (release["as_of_date"] - parse_date(tested, f"{source} rollback.tested_on")).days
        c.figures.append(Figure("rollback.test_age_days", "Days since the rollback was rehearsed", str(age), source))
        if age < 0:
            c.reasons.append(f"rollback.tested_on {tested} is after the as-of date {release['as_of']}.")
        elif age > max_age:
            c.reasons.append(f"The rollback was last rehearsed {age} days ago, beyond the {max_age}-day limit.")
    c.met = not c.reasons
    return c


def check_brief(release: dict, source: str) -> Criterion:
    c = Criterion("brief", CRITERIA["brief"], False, owner_for(release, "brief"))
    brief = release.get("brief") or {}
    fields = (
        ("metric", "what should move"),
        ("target", "the number that means it worked"),
        ("source", "where the metric is read on day one (a dashboard, query or event)"),
        ("owner", "who reads the result"),
    )
    for key, why in fields:
        if not str(brief.get(key, "")).strip():
            c.reasons.append(f"The landing brief does not say {why} (brief.{key} is empty).")
    review = str(brief.get("review_on", "")).strip()
    if not review:
        c.reasons.append("The landing brief has no review date (brief.review_on is empty).")
    else:
        days = (parse_date(review, f"{source} brief.review_on") - release["as_of_date"]).days
        c.figures.append(Figure("brief.review_in_days", "Days from the as-of date to the review", str(days), source))
        if days <= 0:
            c.reasons.append(f"The review date {review} is not after the as-of date {release['as_of']}.")
    c.met = not c.reasons
    return c


def check_evals(release: dict, path: Path | None) -> Criterion:
    c = Criterion("evals", CRITERIA["evals"], False, owner_for(release, "evals"))
    if path is None:
        c.reasons.append("This is an AI feature and there is no eval input. Pass --evals evals.csv.")
        return c
    policy = release["policy"]
    min_cases = int(policy["min_eval_cases"])
    max_age = int(policy["eval_max_age_days"])
    commit = str(release.get("commit", "")).strip().lower()
    rows = read_csv(path)
    passing = 0
    for n, row in enumerate(rows, start=1):
        where = f"{path.name} row {n + 1}"
        name = need(row, "eval", where)
        cases = parse_int(need(row, "cases", where), where)
        passed = parse_int(need(row, "passed", where), where)
        threshold = parse_fraction(need(row, "threshold", where), where)
        if cases <= 0 or passed < 0 or passed > cases:
            raise InputError(f"{where}: passed must be between 0 and cases, and cases above 0")
        rate = Fraction(passed, cases)
        c.figures.append(Figure(f"evals.{n}.pass_rate", f"{name} pass rate ({passed} of {cases})", pct(rate), path.name))
        c.figures.append(Figure(f"evals.{n}.threshold", f"{name} threshold", pct(threshold), path.name))
        before = len(c.reasons)
        if rate < threshold:
            c.reasons.append(f"Eval '{name}' passes {pct(rate)} ({passed} of {cases}), below its {pct(threshold)} threshold.")
        if cases < min_cases:
            c.reasons.append(f"Eval '{name}' has {cases} cases, fewer than the {min_cases} the gate needs.")
        run_at = row.get("run_at", "")
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
    c.figures.append(Figure("evals.total", "Evals in the gate", str(len(rows)), path.name))
    c.figures.append(Figure("evals.passing", "Evals passing the gate", str(passing), path.name))
    if not rows:
        c.reasons.append("The eval file lists no evals.")
    c.met = not c.reasons
    return c


# ---------------------------------------------------------------- decision


def decide(release_path: Path, ci: Path | None, bugs: Path | None, flags: Path | None, evals: Path | None) -> dict:
    release = load_release(release_path)
    criteria = [
        check_ci(release, ci),
        check_bugs(release, bugs),
        check_flags(release, flags),
        check_rollback(release, release_path.name),
    ]
    if release["policy"].get("require_brief", True):
        criteria.append(check_brief(release, release_path.name))
    if release.get("ai_feature"):
        criteria.append(check_evals(release, evals))
    total = len(criteria)
    met = sum(c.met for c in criteria)
    waived, problems = apply_waivers(release, criteria, release_path.name)
    go = total > 0 and met + len(waived) == total
    return {
        "release": release["name"],
        "commit": release.get("commit", ""),
        "as_of": release["as_of"],
        "owner": release["owner"],
        "ai_feature": bool(release.get("ai_feature")),
        "illustrative": bool(release.get("illustrative")),
        "decision": "go" if go else "no-go",
        "met": met,
        "total": total,
        "open": [{"id": c.id, "label": c.label, "owner": c.owner, "reasons": c.reasons} for c in criteria if not c.met and c.id not in waived],
        "waived": [{"id": c.id, "label": c.label, "owner": c.owner, "reasons": c.reasons, **waived[c.id]} for c in criteria if c.id in waived],
        "waiver_problems": problems,
        "policy_changes": policy_changes(release),
        "criteria": [asdict(c) for c in criteria],
    }


def apply_waivers(release: dict, criteria: list[Criterion], source: str) -> tuple[dict[str, dict], list[str]]:
    """Valid waivers by criterion id, and why each other waiver does not count.

    A waiver counts only when the criterion is open, waivers are allowed, a reason and an approver are
    named, the approver does not own the criterion, and it has not expired. A waiver never marks a
    criterion met: the report shows it as waived, with its reasons.
    """
    by_id = {c.id: c for c in criteria}
    valid: dict[str, dict] = {}
    problems: list[str] = []
    for n, w in enumerate(release.get("waivers") or [], start=1):
        cid = str(w.get("criterion", "")).strip()
        approver = str(w.get("approved_by", "")).strip()
        expires = str(w.get("expires", "")).strip()
        label = f"Waiver {n} ({cid or 'no criterion'})"
        if not release["policy"].get("allow_waivers", True):
            problems.append(f"{label}: the policy does not allow waivers.")
        elif cid not in by_id:
            problems.append(f"{label}: no such criterion in this release.")
        elif by_id[cid].met:
            problems.append(f"{label}: the criterion is met, so the waiver is not needed.")
        elif not str(w.get("reason", "")).strip() or not approver:
            problems.append(f"{label}: a waiver needs a reason and an approver.")
        elif approver.lower() == by_id[cid].owner.lower():
            problems.append(f"{label}: {approver} owns this criterion and cannot waive it.")
        elif not expires:
            problems.append(f"{label}: a waiver needs an expiry date.")
        elif (days := (parse_date(expires, f"{source} waivers[{n}].expires") - release["as_of_date"]).days) < 0:
            problems.append(f"{label}: expired on {expires}.")
        elif days > int(release["policy"].get("max_waiver_days", 14)):
            problems.append(f"{label}: runs {days} days, beyond the {release['policy'].get('max_waiver_days', 14)}-day limit for a waiver.")
        else:
            valid[cid] = {"reason": str(w["reason"]).strip(), "approved_by": approver, "expires": expires}
    return valid, problems


def policy_changes(release: dict) -> list[str]:
    """Every policy value the release changes from the default, so a loosened gate is visible."""
    out = []
    for key, default in DEFAULT_POLICY.items():
        value = release["policy"].get(key, default)
        if value != default:
            out.append(f"{key}: {json.dumps(value)} (default {json.dumps(default)})")
    return out


def cell(text: str) -> str:
    """Escape a value for a Markdown table cell, so text from an input cannot break the table or add markup."""
    out = str(text).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    for ch in "<>`*_[]":
        out = out.replace(ch, "\\" + ch)
    return out


def report(d: dict) -> str:
    lines = [f"# Release readiness: {cell(d['release'])}", ""]
    if d["illustrative"]:
        lines += ["*Illustrative: sample data, not a real release.*", ""]
    lines += [f"As of {d['as_of']}. Commit {cell(d['commit'] or 'not named')}. Release owner: {cell(d['owner'])}.", ""]
    if d["decision"] == "go" and not d["waived"]:
        lines.append(f"**Decision: go.** All {d['total']} criteria are met.")
    elif d["decision"] == "go":
        lines.append(f"**Decision: go, with {plural(len(d['waived']), 'waiver')}.** {d['met']} of {d['total']} criteria are met; the rest are waived.")
    else:
        lines.append(f"**Decision: no-go.** {d['met']} of {d['total']} criteria are met. {len(d['open'])} are open.")
        lines += ["", "## Open criteria", "", "| Criterion | Owner | Why it is open |", "|---|---|---|"]
        for o in d["open"]:
            lines.append(f"| {cell(o['label'])} | {cell(o['owner'])} | {'<br>'.join(cell(r) for r in o['reasons'])} |")
    if d["waived"]:
        lines += ["", "## Waived criteria", "", "| Criterion | Owner | Approved by | Expires | Reason | Still open because |", "|---|---|---|---|---|---|"]
        for w in d["waived"]:
            why = "<br>".join(cell(r) for r in w["reasons"])
            lines.append(f"| {cell(w['label'])} | {cell(w['owner'])} | {cell(w['approved_by'])} | {cell(w['expires'])} | {cell(w['reason'])} | {why} |")
    waived_ids = {w["id"] for w in d["waived"]}
    lines += ["", "## All criteria", "", "| Criterion | State | Owner |", "|---|---|---|"]
    for c in d["criteria"]:
        state = "met" if c["met"] else "waived" if c["id"] in waived_ids else "open"
        lines.append(f"| {cell(c['label'])} | {state} | {cell(c['owner'])} |")
    notes = [n for c in d["criteria"] for n in c["notes"]] + d["waiver_problems"]
    notes += [f"Policy changed from the default: {p}" for p in d["policy_changes"]]
    if notes:
        lines += ["", "## Notes", ""] + [f"- {cell(n)}" for n in notes]
    lines += ["", "## Evidence ledger", "", "| ID | Figure | Value | Source |", "|---|---|---|---|"]
    for c in d["criteria"]:
        for f in c["figures"]:
            lines.append(f"| {cell(f['id'])} | {cell(f['label'])} | {cell(f['value'])} | {cell(f['source'])} |")
    if not d["ai_feature"]:
        lines += ["", "The eval gate does not apply: release.json does not mark this as an AI feature."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Make a go or no-go call for one release.")
    ap.add_argument("--release", type=Path, help="release.json: name, owner, as_of, commit, rollback, brief, waivers, policy")
    ap.add_argument("--demo", action="store_true", help="run on the held Acme example (illustrative)")
    ap.add_argument("--init", type=Path, metavar="PATH", help="write a release.json template to PATH and stop")
    ap.add_argument("--json", action="store_true", help="print decision.json instead of the report")
    ap.add_argument("--ci", type=Path, help="ci.csv: check, conclusion, required, commit, url, owner")
    ap.add_argument("--bugs", type=Path, help="bugs.csv: id, title, severity, state, owner")
    ap.add_argument("--flags", type=Path, help="flags.csv: flag, rollout_percent, off_switch, owner")
    ap.add_argument("--evals", type=Path, help="evals.csv: eval, cases, passed, threshold, run_at, commit, owner")
    ap.add_argument("--out", type=Path, default=Path("run"), help="directory for decision.json and report.md")
    args = ap.parse_args(argv)
    if args.init:
        if args.init.exists():
            print(f"error: {args.init} exists; not overwriting it", file=sys.stderr)
            return 2
        args.init.parent.mkdir(parents=True, exist_ok=True)
        args.init.write_text(json.dumps(TEMPLATE, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.init}: replace every <...> value, then run readiness.py --release {args.init}")
        return 0
    if args.demo:
        ex = EXAMPLES / "acme-held"
        args.release = ex / "release.json"
        args.ci, args.bugs, args.flags, args.evals = (ex / f"{k}.csv" for k in ("ci", "bugs", "flags", "evals"))
    if not args.release:
        ap.error("pass --release, --demo or --init")
    try:
        d = decide(args.release, args.ci, args.bugs, args.flags, args.evals)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "decision.json").write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    text = report(d)
    (args.out / "report.md").write_text(text, encoding="utf-8")
    print(json.dumps(d, indent=2) if args.json else text, end="\n" if args.json else "")
    return 0 if d["decision"] == "go" else 1


if __name__ == "__main__":
    sys.exit(main())
