#!/usr/bin/env python3
"""Check a draft release note, Slack post or summary against readiness.json before anyone sends it.

Usage:
  python3 scripts/validate.py --readiness run/readiness.json --draft draft.md

Exit code: 0 clean, 1 the draft overclaims or leaves something out, 2 the inputs could not be read.

Rules (each one blocks):
  ready-claim-on-hold    The release holds and the draft says it is ready, cleared or a go.
  held-check-missing     The release holds and the draft does not name a held check.
  owner-missing          The release holds and the draft does not name a held check's owner.
  waiver-missing         A check is waived and the draft does not name it and its approver.
  all-ready-claim        A check is waived and the draft says every check is ready.
  status-word            The draft says landed, watch or stalled. Those are the bet's words, and only did-it-land sets them.
  figure-not-computed    The draft prints a number, or a multiplier such as 3x, that is not in readiness.json.

The model may reword the draft. It may not change the call, drop a held check or invent a number.
Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

GO_PATTERNS = [
    r"\bready to (?:ship|release|launch|go|deploy)\b",
    r"\bready for (?:release|launch|production|ga)\b",
    r"\bgreen[- ]?light(?:ed)?\b",
    r"\bcleared (?:to|for)\b",
    r"\bgood to go\b",
    r"\bdecision:?\s*\**\s*go\b",
    r"\bit'?s a go\b",
    r"\bis a go\b",
    r"\bgo for (?:launch|release)\b",
    r"\ball (?:the |\d+ )?checks (?:are )?(?:ready|met|green|passing)\b",
    r"\bshipping (?:today|now|this week)\b",
]
NEGATIONS = re.compile(r"\b(?:not|isn'?t|aren'?t|no|never|cannot|can'?t|until)\b[^.!?\n]{0,24}$", re.IGNORECASE)
# "3 of 6 checks are ready to ship" counts checks; it does not call the release ready.
COUNTED = re.compile(r"\b\d+ of \d+ checks? (?:are |is )?$", re.IGNORECASE)
STATUS_WORDS = re.compile(r"\b(?:landed|watch|stalled)\b", re.IGNORECASE)
KEYWORDS = {
    "ci": ("ci", "check"),
    "bugs": ("bug",),
    "flags": ("flag",),
    "rollback": ("rollback", "roll back"),
    "brief": ("brief", "metric", "target"),
    "evals": ("eval",),
    "spec": ("spec",),
}
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")
MULTIPLIER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?x\b", re.IGNORECASE)


def go_claims(text: str) -> list[str]:
    hits = []
    for pattern in GO_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            before = text[max(0, m.start() - 40) : m.start()]
            if not NEGATIONS.search(before) and not COUNTED.search(before):
                hits.append(m.group(0))
    return hits


def allowed_numbers(d: dict) -> set[str]:
    texts = [str(d["ready"]), str(d["total"]), str(len(d["holds"])), str(len(d.get("waived") or [])), d["release"], d["commit"], d["as_of"]]
    texts += [w["expires"] for w in d.get("waived") or []]
    if d.get("brief"):
        texts += [d["brief"]["bar"], d["brief"]["by"]]
    for c in d["checks"]:
        texts += c["reasons"]
        for f in c["figures"]:
            texts += [str(f["value"]), f["label"], f["window_from"], f["window_to"]]
    found = set()
    for t in texts:
        found.update(canonical(n) for n in NUMBER.findall(str(t)))
    return found


def canonical(n: str) -> str:
    return n.rstrip("0").rstrip(".") if "." in n else n.lstrip("0") or "0"


def check(d: dict, draft: str) -> list[dict]:
    errors = []
    lower = draft.lower()
    if d["readiness"] != "ready to ship":
        for hit in go_claims(draft):
            errors.append({"rule": "ready-claim-on-hold", "detail": f"The release holds, and the draft says '{hit}'."})
        for o in d["holds"]:
            if not any(k in lower for k in KEYWORDS.get(o["id"], (o["id"],))) and o["label"].lower() not in lower:
                errors.append({"rule": "held-check-missing", "detail": f"The draft does not name the held check: {o['label']}."})
            if o["owner"].lower() not in lower:
                errors.append({"rule": "owner-missing", "detail": f"The draft does not name {o['owner']}, who owns: {o['label']}."})
    waived = d.get("waived") or []
    for w in waived:
        if not any(k in lower for k in KEYWORDS.get(w["id"], (w["id"],))) or w["approved_by"].lower() not in lower:
            errors.append({"rule": "waiver-missing", "detail": f"Name the waived check ({w['label']}) and its approver, {w['approved_by']}."})
    if waived:
        for m in re.finditer(r"\ball (?:the |\d+ )?checks (?:are |were )?(?:ready|met|green|passing)\b", draft, re.IGNORECASE):
            errors.append({"rule": "all-ready-claim", "detail": f"The draft says '{m.group(0)}', and {len(waived)} waived checks still hold."})
    for m in STATUS_WORDS.finditer(draft):
        errors.append(
            {"rule": "status-word", "detail": f"The draft says '{m.group(0)}'. Landed, watch and stalled are the bet's status, set only by did-it-land."}
        )
    allowed = allowed_numbers(d)
    for n in NUMBER.findall(draft):
        if canonical(n) not in allowed:
            errors.append({"rule": "figure-not-computed", "detail": f"The draft prints {n}, which is not in readiness.json."})
    for m in MULTIPLIER.finditer(draft):
        errors.append({"rule": "figure-not-computed", "detail": f"The draft prints {m.group(0)}; readiness.json computes no multiplier."})
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check a draft against readiness.json.")
    ap.add_argument("--readiness", required=True, type=Path)
    ap.add_argument("--draft", required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        d = json.loads(args.readiness.read_text(encoding="utf-8"))
        draft = args.draft.read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors = check(d, draft)
    for e in errors:
        print(f"{e['rule']}: {e['detail']}")
    print(f"{len(errors)} errors" if errors else "0 errors: the draft matches the check")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
