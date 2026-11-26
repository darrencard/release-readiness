#!/usr/bin/env python3
"""A draft may reword the call. It may not overclaim, drop an open criterion or owner, or invent a number.

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

HELD_DRAFT = """Invoice Chaser 1.0 is a no-go as of 2026-11-20: 3 of 6 criteria are met.

- CI: integration-tests is failing. Nadia Flores owns it.
- Bugs: 1 critical bug is open (#2210). Marcus Lee owns it.
- Evals: chase-message-tone passes 91.0% against a 95.0% threshold. Sam Patel owns it.

It is not ready to ship until all three are met.
"""


def rules(errors: list[dict]) -> list[str]:
    return [e["rule"] for e in errors]


class Validate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.held = decide(FIXTURES / "acme-held" / "release.json", **paths(FIXTURES / "acme-held"))
        cls.ready = decide(FIXTURES / "acme-ready" / "release.json", **paths(FIXTURES / "acme-ready"))

    def test_an_accurate_no_go_draft_passes(self) -> None:
        self.assertEqual(check(self.held, HELD_DRAFT), [])

    def test_a_go_claim_on_a_no_go_is_blocked(self) -> None:
        for claim in ("We are ready to ship.", "Green light for Friday.", "Decision: go", "All criteria met.", "It's a go."):
            with self.subTest(claim=claim):
                self.assertIn("go-claim-on-no-go", rules(check(self.held, HELD_DRAFT + claim)))

    def test_a_negated_claim_is_not_a_go_claim(self) -> None:
        self.assertEqual(check(self.held, HELD_DRAFT + "We are not ready to release. It isn't cleared for launch."), [])

    def test_dropping_an_open_criterion_or_its_owner_is_blocked(self) -> None:
        draft = HELD_DRAFT.replace("- Evals: chase-message-tone passes 91.0% against a 95.0% threshold. Sam Patel owns it.\n", "")
        self.assertEqual(sorted(rules(check(self.held, draft))), ["open-criterion-missing", "owner-missing"])

    def test_an_invented_number_is_blocked(self) -> None:
        errors = check(self.held, HELD_DRAFT + "Tone should reach 98% by Friday.")
        self.assertEqual(rules(errors), ["figure-not-computed"])
        self.assertIn("98", errors[0]["detail"])

    def test_a_go_draft_only_needs_its_numbers_to_be_computed(self) -> None:
        draft = "Quote Assistant 2.4 is a go: all 6 criteria are met. Line items pass 97.0% of 400 cases."
        self.assertEqual(check(self.ready, draft), [])
        self.assertEqual(rules(check(self.ready, draft + " That is 3x better.")), ["figure-not-computed"])

    def test_the_cli_exits_1_on_an_overclaim(self) -> None:
        work = Path(tempfile.mkdtemp(prefix="rr-val-"))
        try:
            (work / "decision.json").write_text(json.dumps(self.held), encoding="utf-8")
            (work / "draft.md").write_text(HELD_DRAFT + "Good to go.", encoding="utf-8")
            proc = run_script("validate.py", "--decision", str(work / "decision.json"), "--draft", str(work / "draft.md"))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("go-claim-on-no-go", proc.stdout)
            (work / "draft.md").write_text(HELD_DRAFT, encoding="utf-8")
            proc = run_script("validate.py", "--decision", str(work / "decision.json"), "--draft", str(work / "draft.md"))
            self.assertEqual(proc.returncode, 0, proc.stdout)
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
