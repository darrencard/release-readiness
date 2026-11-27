#!/usr/bin/env python3
"""Waivers, the landing brief, the rollback trigger, and the command line.

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

WAIVER = {"check": "bugs", "reason": "#2210 affects 3 accounts, all on manual chasing", "approved_by": "Head of Product, Invoicing squad", "expires": "2026-11-27"}


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
        """The ready release with only the bugs check held (one critical bug)."""
        fx = self.fixture(name)
        (fx / "bugs.csv").write_text("id,title,severity,state,owner\n2210,Paid invoice chased,critical,open,Invoicing squad engineer\n", encoding="utf-8")
        if changes:
            edit_release(fx, **changes)
        return fx


class Waivers(Base):
    def test_a_valid_waiver_lets_the_last_held_check_ship_and_it_still_reads_hold(self) -> None:
        d = self.call(self.one_open("acme-ready", waivers=[WAIVER]))
        self.assertEqual(d["readiness"], "ready to ship")
        self.assertEqual(d["holds"], [])
        self.assertEqual([w["id"] for w in d["waived"]], ["bugs"])
        self.assertEqual(d["ready"], 5)
        self.assertEqual(next(c for c in d["checks"] if c["id"] == "bugs")["readiness"], "hold")
        text = readiness.report(d)
        self.assertIn("**Ready to ship, with 1 waiver.** 5 of 6 checks are ready to ship; 1 check holds under a waiver.", text)
        self.assertIn("| Open bugs within the severity limits | hold, waived |", text)
        self.assertIn("Head of Product, Invoicing squad", text)

    def test_a_waiver_never_rescues_a_release_with_another_held_check(self) -> None:
        d = self.call(FIXTURES / "acme-held")
        fx = self.fixture("acme-held")
        edit_release(fx, waivers=[WAIVER])
        w = self.call(fx)
        self.assertEqual(w["readiness"], "hold")
        self.assertEqual([o["id"] for o in w["holds"]], ["ci", "evals"])
        self.assertEqual(len(d["holds"]), 3)

    def test_a_waiver_that_does_not_count_says_why(self) -> None:
        cases = {
            "cannot waive it": {**WAIVER, "approved_by": "Lead, Quoting squad"},
            "ran out on": {**WAIVER, "expires": "2026-11-19"},
            "beyond the 14-day limit": {**WAIVER, "expires": "2027-01-31"},
            "needs a reason": {**WAIVER, "reason": ""},
            "needs an expiry": {**WAIVER, "expires": ""},
            "no such check": {**WAIVER, "check": "vibes"},
            "is ready to ship": {**WAIVER, "check": "flags"},
        }
        for why, waiver in cases.items():
            with self.subTest(why=why):
                d = self.call(self._fresh(waiver))
                self.assertEqual(d["readiness"], "hold")
                self.assertIn(why, " ".join(d["waiver_problems"]))
                self.assertIn(why, readiness.report(d))

    def _fresh(self, waiver: dict) -> Path:
        work = Path(tempfile.mkdtemp(prefix="rr-wf-", dir=self.work))
        fx = copy_fixture("acme-ready", work)
        (fx / "bugs.csv").write_text("id,title,severity,state,owner\n2210,Paid invoice chased,critical,open,Invoicing squad engineer\n", encoding="utf-8")
        edit_release(fx, waivers=[waiver])
        return fx

    def test_the_policy_can_forbid_waivers(self) -> None:
        d = self.call(self.one_open("acme-ready", waivers=[WAIVER], policy={"allow_waivers": False, "max_initial_rollout_percent": 25}))
        self.assertEqual(d["readiness"], "hold")
        self.assertIn("does not allow waivers", d["waiver_problems"][0])

    def test_a_draft_must_name_the_waiver_and_may_not_say_all_checks_ready(self) -> None:
        d = self.call(self.one_open("acme-ready", waivers=[WAIVER]))
        good = "Quote Assistant 2.4 is ready to ship with 1 waiver: 5 of 6 checks are ready. The critical bug #2210 is waived by Head of Product, Invoicing squad until 2026-11-27."
        self.assertEqual(check(d, good), [])
        rules = [e["rule"] for e in check(d, "Quote Assistant 2.4 is ready to ship: all checks are ready.")]
        self.assertEqual(sorted(rules), ["all-ready-claim", "waiver-missing"])


class BriefAndTrigger(Base):
    def brief(self, fx: Path, old: str, new: str) -> None:
        path = fx / "brief.md"
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    def test_no_landing_brief_holds(self) -> None:
        d = self.call(FIXTURES / "acme-ready", brief=True)
        self.assertEqual([o["id"] for o in d["holds"]], ["brief"])
        self.assertIn("No landing brief", d["holds"][0]["reasons"][0])

    def test_the_brief_parser_lists_every_missing_part(self) -> None:
        fx = self.fixture("acme-ready")
        self.brief(fx, "- **Non-goals:** No pricing advice. No change to the quote PDF.\n", "")
        self.brief(fx, "- **By:** 2026-12-18\n", "")
        reasons = " ".join(self.call(fx)["holds"][0]["reasons"])
        self.assertIn("by is missing", reasons)
        self.assertIn("non goals is missing", reasons)

    def test_a_brief_date_on_or_before_the_check_holds(self) -> None:
        fx = self.fixture("acme-ready")
        self.brief(fx, "2026-12-18", "2026-11-20")
        d = self.call(fx)
        self.assertEqual([o["id"] for o in d["holds"]], ["brief"])
        self.assertIn("not after this check", d["holds"][0]["reasons"][0])

    def test_the_policy_can_drop_the_brief_and_the_report_says_so(self) -> None:
        fx = self.fixture("acme-ready")
        edit_release(fx, policy={"require_brief": False, "max_initial_rollout_percent": 25, "max_open_bugs": {"blocker": 0, "critical": 0, "major": 2}})
        d = self.call(fx, brief=True)
        self.assertEqual((d["readiness"], d["total"]), ("ready to ship", 5))
        self.assertIn("require brief: no (default yes)", d["policy_changes"])
        self.assertIn("require brief: no (default yes)", readiness.report(d))

    def test_a_rollback_with_no_trigger_or_no_threshold_holds(self) -> None:
        fx = self.fixture("acme-ready")
        edit_release(fx, rollback={"plan": "Flag off.", "owner": "Platform on-call lead", "tested_on": "2026-11-12"})
        self.assertIn("rollback.trigger is empty", self.call(fx)["holds"][0]["reasons"][0])
        edit_release(fx, rollback={"plan": "Flag off.", "owner": "Platform on-call lead", "tested_on": "2026-11-12", "trigger": "If it looks bad"})
        self.assertIn("no threshold", self.call(fx)["holds"][0]["reasons"][0])


class Visibility(Base):
    def test_every_changed_policy_value_is_shown_in_plain_words(self) -> None:
        d = self.call(FIXTURES / "acme-ready")
        self.assertEqual(d["policy_changes"], ["open major bugs allowed: 2 (default 3)", "max initial rollout percent: 25 (default 100)"])

    def test_a_failing_check_that_is_not_required_is_noted_but_does_not_hold(self) -> None:
        d = self.call(FIXTURES / "acme-ready")
        self.assertEqual(d["readiness"], "ready to ship")
        self.assertIn("visual-diff", readiness.report(d))


class CommandLine(Base):
    def test_init_writes_a_template_that_cannot_run_until_filled_in(self) -> None:
        path = self.work / "run" / "release.json"
        self.assertEqual(run_script("readiness.py", "--init", str(path)).returncode, 0)
        self.assertEqual(run_script("readiness.py", "--init", str(path)).returncode, 2)
        with self.assertRaises(InputError) as ctx:
            decide(path)
        self.assertIn("template values", str(ctx.exception))

    def test_json_prints_the_check(self) -> None:
        fx = FIXTURES / "acme-held"
        args = ["--release", str(fx / "release.json"), "--brief", str(fx / "brief.md"), "--ci", str(fx / "ci.csv"), "--json", "--out", str(self.work / "j")]
        proc = run_script("readiness.py", *args)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["readiness"], "hold")

    def test_loop_needs_a_bet_unless_the_folder_holds_exactly_one_record(self) -> None:
        fx = FIXTURES / "acme-ready"
        args = ["--release", str(fx / "release.json"), "--brief", str(fx / "brief.md"), "--loop", str(self.work), "--out", str(self.work / "o")]
        proc = run_script("readiness.py", *args)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--loop needs --bet", proc.stderr)
        (self.work / "landing").mkdir()
        (self.work / "landing" / "only-bet.json").write_text('{"schema": "landing-loop/1", "bet": "only-bet"}', encoding="utf-8")
        run_script("readiness.py", *args)
        self.assertIn("release", json.loads((self.work / "landing" / "only-bet.json").read_text(encoding="utf-8")))


class GateExample(unittest.TestCase):
    def test_the_actions_gate_calls_real_scripts_with_real_flags(self) -> None:
        from helpers import SKILL

        text = (SKILL / "references" / "release-gate.yml").read_text(encoding="utf-8")
        for script in ("from_gh.py", "readiness.py"):
            self.assertIn(f"tools/release-readiness/scripts/{script}", text)
            self.assertTrue((SKILL / "scripts" / script).exists())
        for flag in ("--release", "--brief", "--ci", "--bugs", "--flags", "--evals", "--out", "--repo", "--ref"):
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
            d = decide(held / "release.json", work / "ci.csv", brief=held / "brief.md")
            ci = " ".join(next(o for o in d["holds"] if o["id"] == "ci")["reasons"])
            self.assertIn("jenkins/deploy-preview", ci)
            self.assertNotIn("names no commit", ci)
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
