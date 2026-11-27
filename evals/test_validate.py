#!/usr/bin/env python3
"""A draft may reword the call. It may not overclaim, drop a held check or owner, use a bet status word, or invent a number.

Usage:
  python3 -m unittest discover -s evals -v
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import FIXTURES, paths, run_script

from readiness import decide
from validate import check

HELD_DRAFT = """Invoice Chaser 1.0 holds as of 2026-11-20: 3 of 6 checks are ready to ship.

- CI: integration-tests is failing. Nadia Flores owns it.
- Bugs: 1 critical bug is open (#2210). Marcus Lee owns it.
- Evals: chase-message-tone passed 182 of 200 cases; its threshold needs 190. Sam Patel owns it.

It is not ready to ship until all three are fixed.
"""


def rules(errors: list[dict]) -> list[str]:
    return [e["rule"] for e in errors]


class Validate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.held = decide(FIXTURES / "acme-held" / "release.json", **paths(FIXTURES / "acme-held"))
        cls.ready = decide(FIXTURES / "acme-ready" / "release.json", **paths(FIXTURES / "acme-ready"))

    def test_an_accurate_hold_draft_passes(self) -> None:
        self.assertEqual(check(self.held, HELD_DRAFT), [])

    def test_a_ready_claim_on_a_hold_is_blocked(self) -> None:
        for claim in ("We are ready to ship.", "Green light for Friday.", "Decision: go", "All checks are ready.", "It's a go."):
            with self.subTest(claim=claim):
                self.assertIn("ready-claim-on-hold", rules(check(self.held, HELD_DRAFT + claim)))

    def test_a_bet_status_word_is_blocked(self) -> None:
        for claim in ("The bet has landed.", "Watch this one.", "Quote drafting stalled."):
            with self.subTest(claim=claim):
                self.assertIn("status-word", rules(check(self.ready, claim)))

    def test_a_negated_claim_is_not_a_go_claim(self) -> None:
        self.assertEqual(check(self.held, HELD_DRAFT + "We are not ready to release. It isn't cleared for launch."), [])

    def test_dropping_a_held_check_or_its_owner_is_blocked(self) -> None:
        draft = HELD_DRAFT.replace("- Evals: chase-message-tone passed 182 of 200 cases; its threshold needs 190. Sam Patel owns it.\n", "")
        self.assertEqual(sorted(rules(check(self.held, draft))), ["held-check-missing", "owner-missing"])

    def test_an_invented_number_is_blocked(self) -> None:
        errors = check(self.held, HELD_DRAFT + "Tone should reach 98% by Friday.")
        self.assertEqual(rules(errors), ["figure-not-computed"])
        self.assertIn("98", errors[0]["detail"])

    def test_a_ready_draft_only_needs_its_numbers_to_be_computed(self) -> None:
        draft = "Quote Assistant 2.4 is ready to ship: all 6 checks are ready. Line items passed 388 of 400 cases."
        self.assertEqual(check(self.ready, draft), [])
        self.assertEqual(rules(check(self.ready, draft + " That is 3x better.")), ["figure-not-computed"])

    def test_the_cli_exits_1_on_an_overclaim(self) -> None:
        work = Path(tempfile.mkdtemp(prefix="rr-val-"))
        try:
            (work / "readiness.json").write_text(json.dumps(self.held), encoding="utf-8")
            (work / "draft.md").write_text(HELD_DRAFT + "Good to go.", encoding="utf-8")
            proc = run_script("validate.py", "--readiness", str(work / "readiness.json"), "--draft", str(work / "draft.md"))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("ready-claim-on-hold", proc.stdout)
            (work / "draft.md").write_text(HELD_DRAFT, encoding="utf-8")
            proc = run_script("validate.py", "--readiness", str(work / "readiness.json"), "--draft", str(work / "draft.md"))
            self.assertEqual(proc.returncode, 0, proc.stdout)
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
