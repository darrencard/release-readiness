#!/usr/bin/env python3
"""Check a draft release note, Slack post or summary against decision.json before anyone sends it.

Usage:
  python3 scripts/validate.py --decision run/decision.json --draft draft.md

Exit code: 0 clean, 1 the draft overclaims or leaves something out, 2 the inputs could not be read.

Rules (each one blocks):
  go-claim-on-no-go      The decision is no-go and the draft says the release is ready, cleared or a go.
  open-criterion-missing The decision is no-go and the draft does not name an open criterion.
  owner-missing          The decision is no-go and the draft does not name an open criterion's owner.
  figure-not-computed    The draft prints a number, or a multiplier such as 3x, that is not in decision.json.

The model may reword the draft. It may not change the call, drop an open criterion or invent a number.
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
    r"\ball (?:the )?criteria (?:are )?met\b",
    r"\bshipping (?:today|now|this week)\b",
]
NEGATIONS = re.compile(r"\b(?:not|isn'?t|aren'?t|no|never|cannot|can'?t|until)\b[^.!?\n]{0,24}$", re.IGNORECASE)
KEYWORDS = {"ci": ("ci", "check"), "bugs": ("bug",), "flags": ("flag",), "rollback": ("rollback", "roll back"), "evals": ("eval",)}
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")
MULTIPLIER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?x\b", re.IGNORECASE)


def go_claims(text: str) -> list[str]:
    hits = []
    for pattern in GO_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            if not NEGATIONS.search(text[max(0, m.start() - 40) : m.start()]):
                hits.append(m.group(0))
    return hits


def allowed_numbers(d: dict) -> set[str]:
    texts = [str(d["met"]), str(d["total"]), str(len(d["open"])), d["release"], d["commit"], d["as_of"]]
    for c in d["criteria"]:
        texts += c["reasons"]
        for f in c["figures"]:
            texts += [f["value"], f["label"]]
    found = set()
    for t in texts:
        found.update(canonical(n) for n in NUMBER.findall(str(t)))
    return found


def canonical(n: str) -> str:
    return n.rstrip("0").rstrip(".") if "." in n else n.lstrip("0") or "0"


def check(d: dict, draft: str) -> list[dict]:
    errors = []
    lower = draft.lower()
    if d["decision"] != "go":
        for hit in go_claims(draft):
            errors.append({"rule": "go-claim-on-no-go", "detail": f"The decision is no-go, and the draft says '{hit}'."})
        for o in d["open"]:
            if not any(k in lower for k in KEYWORDS.get(o["id"], (o["id"],))) and o["label"].lower() not in lower:
                errors.append({"rule": "open-criterion-missing", "detail": f"The draft does not name the open criterion: {o['label']}."})
            if o["owner"].lower() not in lower:
                errors.append({"rule": "owner-missing", "detail": f"The draft does not name {o['owner']}, who owns: {o['label']}."})
    allowed = allowed_numbers(d)
    for n in NUMBER.findall(draft):
        if canonical(n) not in allowed:
            errors.append({"rule": "figure-not-computed", "detail": f"The draft prints {n}, which is not in decision.json."})
    for m in MULTIPLIER.finditer(draft):
        errors.append({"rule": "figure-not-computed", "detail": f"The draft prints {m.group(0)}; decision.json computes no multiplier."})
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check a draft against decision.json.")
    ap.add_argument("--decision", required=True, type=Path)
    ap.add_argument("--draft", required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        d = json.loads(args.decision.read_text(encoding="utf-8"))
        draft = args.draft.read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors = check(d, draft)
    for e in errors:
        print(f"{e['rule']}: {e['detail']}")
    print(f"{len(errors)} errors" if errors else "0 errors: the draft matches the decision")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
