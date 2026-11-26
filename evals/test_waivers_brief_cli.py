#!/usr/bin/env python3
"""Waivers, the landing brief, the rollback trigger, and the quick-start commands.

Usage:
  python3 -m unittest discover -s evals -v
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import FIXTURES, GH, copy_fixture, edit_release, paths, run_script

import from_gh
import readiness
from readiness import InputError, decide
from validate import check

WAIVER = {"criterion": "bugs", "reason": "#2210 affects 3 accounts, all on manual chasing", "approved_by": "Dana Cole", "expires": "2026-11-27"}


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="rr-w-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def fixture(self, name: str) -> Path:
        return copy_fixture(name, self.work)

    def call(self, fx: Path, **skip: bool) -> dict:
        return decide(fx / "release.json", **paths(fx, **skip))

    def one_open(self, name: str, **changes: object) -> Path:
        """The ready release with only the bugs criterion open (one critical bug)."""
        fx = self.fixture(name)
        (fx / "bugs.csv").write_text("id,title,severity,state,owner\n2210,Paid invoice chased,critical,open,Ravi Menon\n", encoding="utf-8")
        if changes:
            edit_release(fx, **changes)
        return fx


class Waivers(Base):
    def test_a_valid_waiver_turns_the_last_open_criterion_into_a_go_with_a_waiver(self) -> None:
        d = self.call(self.one_open("acme-ready", waivers=[WAIVER]))
        self.assertEqual(d["decision"], "go")
        self.assertEqual(d["open"], [])
        self.assertEqual([w["id"] for w in d["waived"]], ["bugs"])
        self.assertEqual(d["met"], 5)
        text = readiness.report(d)
        self.assertIn("**Decision: go, with 1 waiver.** 5 of 6 criteria are met", text)
        self.assertIn("| Open bugs within the severity limits | waived |", text)
        self.assertIn("Dana Cole", text)

    def test_a_waiver_never_rescues_a_release_with_another_open_criterion(self) -> None:
        d = self.call(FIXTURES / "acme-held")
        fx = self.fixture("acme-held")
        edit_release(fx, waivers=[WAIVER])
        w = self.call(fx)
        self.assertEqual(w["decision"], "no-go")
        self.assertEqual([o["id"] for o in w["open"]], ["ci", "evals"])
        self.assertEqual(len(d["open"]), 3)

    def test_a_waiver_that_does_not_count_says_why(self) -> None:
        cases = {
            "cannot waive it": {**WAIVER, "approved_by": "Priya Shah"},
            "expired on": {**WAIVER, "expires": "2026-11-19"},
            "beyond the 14-day limit": {**WAIVER, "expires": "2027-01-31"},
            "needs a reason": {**WAIVER, "reason": ""},
            "needs an expiry": {**WAIVER, "expires": ""},
            "no such criterion": {**WAIVER, "criterion": "vibes"},
            "is met": {**WAIVER, "criterion": "flags"},
        }
        for why, waiver in cases.items():
            with self.subTest(why=why):
                d = self.call(self._fresh(waiver))
                self.assertEqual(d["decision"], "no-go")
                self.assertIn(why, " ".join(d["waiver_problems"]))
                self.assertIn(why, readiness.report(d))

    def _fresh(self, waiver: dict) -> Path:
        work = Path(tempfile.mkdtemp(prefix="rr-wf-", dir=self.work))
        fx = copy_fixture("acme-ready", work)
        (fx / "bugs.csv").write_text("id,title,severity,state,owner\n2210,Paid invoice chased,critical,open,Ravi Menon\n", encoding="utf-8")
        edit_release(fx, waivers=[waiver])
        return fx

    def test_the_policy_can_forbid_waivers(self) -> None:
        d = self.call(self.one_open("acme-ready", waivers=[WAIVER], policy={"allow_waivers": False, "max_initial_rollout_percent": 25}))
        self.assertEqual(d["decision"], "no-go")
        self.assertIn("does not allow waivers", d["waiver_problems"][0])

    def test_a_draft_must_name_the_waiver_and_may_not_say_all_criteria_met(self) -> None:
        d = self.call(self.one_open("acme-ready", waivers=[WAIVER]))
        good = "Quote Assistant 2.4 is a go with 1 waiver: 5 of 6 criteria are met. The critical bug #2210 is waived by Dana Cole until 2026-11-27."
        self.assertEqual(check(d, good), [])
        rules = [e["rule"] for e in check(d, "Quote Assistant 2.4 is a go: all criteria are met.")]
        self.assertEqual(sorted(rules), ["all-met-claim", "waiver-missing"])


class BriefAndTrigger(Base):
    def test_a_missing_landing_brief_is_open(self) -> None:
        fx = self.fixture("acme-ready")
        edit_release(fx, brief={})
        d = self.call(fx)
        self.assertEqual([o["id"] for o in d["open"]], ["brief"])
        self.assertEqual(len(d["open"][0]["reasons"]), 5)

    def test_a_brief_with_no_day_one_source_is_open(self) -> None:
        fx = self.fixture("acme-ready")
        edit_release(fx, brief={"metric": "m", "target": "t", "owner": "o", "review_on": "2026-12-18"})
        d = self.call(fx)
        self.assertIn("brief.source is empty", d["open"][0]["reasons"][0])

    def test_a_review_date_on_or_before_the_as_of_date_is_open(self) -> None:
        fx = self.fixture("acme-ready")
        edit_release(fx, brief={"metric": "m", "target": "t", "source": "s", "owner": "o", "review_on": "2026-11-20"})
        self.assertEqual([o["id"] for o in self.call(fx)["open"]], ["brief"])

    def test_the_policy_can_drop_the_brief_and_the_report_says_so(self) -> None:
        fx = self.fixture("acme-ready")
        edit_release(fx, brief={}, policy={"require_brief": False, "max_initial_rollout_percent": 25})
        d = self.call(fx)
        self.assertEqual((d["decision"], d["total"]), ("go", 5))
        self.assertIn("require_brief: false (default true)", d["policy_changes"])
        self.assertIn("require\\_brief: false (default true)", readiness.report(d))

    def test_a_rollback_with_no_trigger_is_open(self) -> None:
        fx = self.fixture("acme-ready")
        edit_release(fx, rollback={"plan": "Flag off.", "owner": "Lena Okafor", "tested_on": "2026-11-12"})
        d = self.call(fx)
        self.assertIn("rollback.trigger is empty", d["open"][0]["reasons"][0])


class Visibility(Base):
    def test_every_loosened_policy_value_is_shown(self) -> None:
        d = self.call(FIXTURES / "acme-ready")
        self.assertEqual(
            d["policy_changes"],
            [
                'max_open_bugs: {"blocker": 0, "critical": 0, "major": 2} (default {"blocker": 0, "critical": 0, "major": 3})',
                "max_initial_rollout_percent: 25 (default 100)",
            ],
        )

    def test_a_failing_check_that_is_not_required_is_noted_but_does_not_block(self) -> None:
        d = self.call(FIXTURES / "acme-ready")
        self.assertEqual(d["decision"], "go")
        self.assertIn("visual-diff", readiness.report(d))


class QuickStart(Base):
    def test_demo_runs_the_held_example_with_no_other_input(self) -> None:
        proc = run_script("readiness.py", "--demo", "--out", str(self.work / "demo"))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("**Decision: no-go.** 3 of 6 criteria are met. 3 are open.", proc.stdout)

    def test_init_writes_a_template_that_cannot_run_until_filled_in(self) -> None:
        path = self.work / "run" / "release.json"
        self.assertEqual(run_script("readiness.py", "--init", str(path)).returncode, 0)
        self.assertEqual(run_script("readiness.py", "--init", str(path)).returncode, 2)
        with self.assertRaises(InputError) as ctx:
            decide(path, None, None, None, None)
        self.assertIn("template values", str(ctx.exception))

    def test_json_prints_the_decision(self) -> None:
        proc = run_script("readiness.py", "--demo", "--json", "--out", str(self.work / "j"))
        self.assertEqual(json.loads(proc.stdout)["decision"], "no-go")


class GateExample(unittest.TestCase):
    def test_the_actions_gate_calls_real_scripts_with_real_flags(self) -> None:
        from helpers import SKILL

        text = (SKILL / "examples" / "release-gate.yml").read_text(encoding="utf-8")
        for script in ("from_gh.py", "readiness.py"):
            self.assertIn(f"tools/release-readiness/scripts/{script}", text)
            self.assertTrue((SKILL / "scripts" / script).exists())
        for flag in ("--release", "--ci", "--bugs", "--flags", "--evals", "--out", "--repo", "--ref"):
            self.assertIn(flag, text)
        self.assertNotIn("@v", text.replace("# v", ""))


class CommitStatuses(unittest.TestCase):
    def test_statuses_map_to_check_conclusions(self) -> None:
        runs = from_gh.status_runs(from_gh.parse_ndjson((GH / "statuses.ndjson").read_text(encoding="utf-8")))
        rows = {r["check"]: r["conclusion"] for r in from_gh.ci_rows(runs)}
        self.assertEqual(rows, {"buildkite/e2e": "pending", "ci/circleci: build": "success", "jenkins/deploy-preview": "failure"})

    def test_statuses_and_check_runs_are_read_together(self) -> None:
        work = Path(tempfile.mkdtemp(prefix="rr-st-"))
        try:
            args = ["--check-runs-json", str(GH / "check-runs.ndjson"), "--statuses-json", str(GH / "statuses.ndjson")]
            proc = run_script("from_gh.py", *args, "--commit", "9b81d07a55e2f0c4", "--out", str(work))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("7 checks", proc.stdout)
            held = FIXTURES / "acme-held"
            d = decide(held / "release.json", work / "ci.csv", None, None, None)
            ci = " ".join(next(o for o in d["open"] if o["id"] == "ci")["reasons"])
            self.assertIn("jenkins/deploy-preview", ci)
            self.assertNotIn("names no commit", ci)
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
