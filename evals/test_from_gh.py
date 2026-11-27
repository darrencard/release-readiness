#!/usr/bin/env python3
"""The GitHub reader: check runs and issues from gh become ci.csv and bugs.csv that readiness.py can call.

Usage:
  python3 -m unittest discover -s evals -v

No test calls GitHub. They read saved gh output from evals/fixtures/gh/.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import FIXTURES, GH, run_script

import from_gh
from readiness import decide


class Reader(unittest.TestCase):
    def setUp(self) -> None:
        self.runs = from_gh.parse_ndjson((GH / "check-runs.ndjson").read_text(encoding="utf-8"))
        self.issues = json.loads((GH / "issues.json").read_text(encoding="utf-8"))

    def test_the_latest_run_of_a_check_wins_and_a_running_check_is_pending(self) -> None:
        rows = {r["check"]: r for r in from_gh.ci_rows(self.runs)}
        self.assertEqual(sorted(rows), ["e2e", "integration-tests", "lint", "unit-tests"])
        self.assertEqual(rows["integration-tests"]["conclusion"], "failure")
        self.assertEqual(rows["e2e"]["conclusion"], "pending")
        self.assertTrue(all(r["required"] == "yes" for r in rows.values()))

    def test_only_named_checks_are_required_when_given(self) -> None:
        rows = {r["check"]: r["required"] for r in from_gh.ci_rows(self.runs, {"unit-tests", "lint"})}
        self.assertEqual(rows, {"e2e": "no", "integration-tests": "no", "lint": "yes", "unit-tests": "yes"})

    def test_severity_comes_from_labels(self) -> None:
        rows = {r["id"]: r for r in from_gh.bug_rows(self.issues)}
        self.assertEqual(rows["2210"]["severity"], "critical")
        self.assertEqual(rows["2214"]["severity"], "major")
        self.assertEqual(rows["2230"]["severity"], "")
        self.assertEqual(rows["2210"]["owner"], "ravi-acme")
        self.assertEqual(rows["2210"]["state"], "open")

    def test_a_check_runs_payload_and_a_json_array_both_parse(self) -> None:
        self.assertEqual(len(from_gh.parse_ndjson(json.dumps({"check_runs": self.runs}))), 5)
        self.assertEqual(len(from_gh.parse_ndjson(json.dumps(self.runs))), 5)
        self.assertEqual(from_gh.parse_ndjson(""), [])

    def test_a_missing_gh_says_to_use_csv(self) -> None:
        with mock.patch.object(from_gh.shutil, "which", return_value=None), self.assertRaises(from_gh.GhError) as ctx:
            from_gh.run_gh(["api", "user"])
        self.assertIn("ci.csv", str(ctx.exception))


class EndToEnd(unittest.TestCase):
    def test_saved_gh_output_feeds_a_hold_naming_ci_and_bugs(self) -> None:
        work = Path(tempfile.mkdtemp(prefix="rr-gh-"))
        try:
            proc = run_script(
                "from_gh.py",
                "--check-runs-json",
                str(GH / "check-runs.ndjson"),
                "--issues-json",
                str(GH / "issues.json"),
                "--commit",
                "9b81d07a55e2f0c4",
                "--out",
                str(work),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            held = FIXTURES / "acme-held"
            d = decide(held / "release.json", work / "ci.csv", work / "bugs.csv", held / "flags.csv", held / "evals.csv", held / "brief.md")
            by_id = {o["id"]: " ".join(o["reasons"]) for o in d["holds"]}
            self.assertEqual(sorted(by_id), ["bugs", "ci", "evals"])
            self.assertIn("integration-tests", by_id["ci"])
            self.assertIn("'e2e' is pending", by_id["ci"])
            self.assertIn("#2230 (no owner)", by_id["bugs"])
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
