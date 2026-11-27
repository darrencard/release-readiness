#!/usr/bin/env python3
"""The Landing Loop record and the Acme sample: own key only, read keys byte-identical, every figure sourced.

Usage:
  python3 -m unittest discover -s evals -v
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import subprocess  # noqa: S404  (runs this repo's own sample script with a fixed argument list)
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import FIXTURES, SAMPLE

import loop
import readiness
import render_html
import svgkit

BET = "quote-drafting"
UPSTREAM = SAMPLE / "upstream" / f"{BET}.json"
STATUS = re.compile(r"\b(?:landed|watch|stalled)\b", re.IGNORECASE)


def figures_in(obj: object, at: str = "") -> list[tuple[str, dict]]:
    """Every figure-shaped entry (a dict with value) inside a key, with its path."""
    if isinstance(obj, dict):
        if "value" in obj:
            return [(at, obj)]
        return [p for k, v in obj.items() for p in figures_in(v, f"{at}.{k}")]
    if isinstance(obj, list):
        return [p for i, v in enumerate(obj) for p in figures_in(v, f"{at}[{i}]")]
    return []


def visible_text(page: str) -> str:
    """What a reader sees: the page without its stylesheet and tags."""
    return re.sub(r"<[^>]+>", " ", re.sub(r"<style>.*?</style>", "", page, flags=re.S))


class Sample(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="rr-sample-"))
        proc = subprocess.run([sys.executable, str(SAMPLE / "sample.py"), "--into", str(cls.tmp)], capture_output=True, text=True, check=False)  # noqa: S603
        assert proc.returncode == 0, proc.stderr  # noqa: S101
        cls.record = json.loads((cls.tmp / "landing" / f"{BET}.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_sample_command_reproduces_the_committed_files_byte_for_byte(self) -> None:
        for name in ("release-readiness.html", "release-readiness.md", f"landing/{BET}.json"):
            with self.subTest(file=name):
                self.assertEqual((self.tmp / name).read_bytes(), (SAMPLE / name).read_bytes())

    def test_it_writes_only_its_own_key_and_leaves_every_read_key_byte_identical(self) -> None:
        upstream_text = UPSTREAM.read_text(encoding="utf-8")
        upstream = json.loads(upstream_text)
        self.assertEqual(list(self.record), [*upstream, "release"])
        rest = {k: v for k, v in self.record.items() if k != "release"}
        self.assertEqual(json.dumps(rest, indent=2, ensure_ascii=False) + "\n", upstream_text)

    def test_the_upstream_file_is_the_landing_loop_record_filtered_to_the_keys_it_reads(self) -> None:
        upstream = json.loads(UPSTREAM.read_text(encoding="utf-8"))
        self.assertEqual(list(upstream), ["schema", "bet", "brief", "spec"])
        self.assertEqual(upstream["brief"]["sha256"], loop.sha256(SAMPLE / upstream["brief"]["path"]))

    def test_the_acme_story_holds(self) -> None:
        r = self.record["release"]
        self.assertEqual((r["as_of"], r["readiness"]), ("2026-09-05", "ready to ship"))
        bugs = next(c for c in r["checks"] if c["id"] == "bugs")
        self.assertEqual(bugs["readiness"], "hold")
        self.assertEqual(bugs["waiver"]["approved_by"], "Head of Product, Quoting squad")
        self.assertEqual([h["closed"] for h in r["spec_holds"]], [True, True])
        self.assertTrue(r["illustrative"])

    def test_every_figure_carries_value_unit_source_window_and_as_of(self) -> None:
        found = figures_in(self.record["release"])
        self.assertGreater(len(found), 20)
        for at, f in found:
            with self.subTest(figure=at):
                self.assertEqual(set(f), {"value", "unit", "source", "window", "as_of"})
                self.assertIsInstance(f["value"], int | float)
                self.assertTrue(f["unit"] and f["source"] and f["as_of"])
                self.assertTrue(f["window"]["from"] and f["window"]["to"])

    def test_no_bet_status_word_in_its_key_page_or_twin(self) -> None:
        page = (SAMPLE / "release-readiness.html").read_text(encoding="utf-8")
        texts = {
            "release key": json.dumps(self.record["release"]),
            "page": visible_text(page),
            "twin": (SAMPLE / "release-readiness.md").read_text(encoding="utf-8"),
        }
        for name, text in texts.items():
            with self.subTest(output=name):
                self.assertIsNone(STATUS.search(text))

    def test_check_words_are_only_ready_to_ship_or_hold(self) -> None:
        r = self.record["release"]
        self.assertEqual({r["readiness"], *(c["readiness"] for c in r["checks"])} - {"ready to ship", "hold"}, set())

    def test_the_page_uses_no_status_colour_and_brass_only_for_a_persons_call(self) -> None:
        page = (SAMPLE / "release-readiness.html").read_text(encoding="utf-8")
        body = page.split("</style>", 1)[1]
        # Green only beside the word landed, red only beside stalled: this page prints neither word, so it paints neither colour.
        for token in ("--landed", "--watch", "--stalled", 'class="st ', "sk-st", "rd landed", "ac landed"):
            self.assertNotIn(token, body)
        css = page.split("<style>", 1)[1].split("</style>", 1)[0]
        page_css = css[css.index("main.solo{margin-left:0}") :]
        self.assertNotRegex(page_css, r"--(?:landed|watch|stalled)")
        brass = re.findall(r"[^}]*var\(--brass[^}]*}", page_css)
        self.assertTrue(brass and all(r.lstrip("}").lstrip().startswith((".next", ".wv")) for r in brass), "brass is only who decides and who waived")
        for svg in svgkit.visuals_in(page):
            for m in re.finditer(r'<text[^>]*color:var\(--brass\)[^>]*>([^<]*)</text>', svg):
                self.assertRegex(m.group(1), r"^(?:Waived by |UNTIL )")
        self.assertIn('class="sk-ill"', body)

    def test_the_page_follows_the_sample_anatomy(self) -> None:
        body = (SAMPLE / "release-readiness.html").read_text(encoding="utf-8").split('<main class="solo">', 1)[1]
        order = ['class="sk-hdr"', "<h1>Acme quote drafting v1.0 is ready to ship, with one waiver.</h1>", 'class="rw"', 'class="sk-wide"', "What to do next", 'class="cols"', "For your engineers"]
        at = [body.index(x) for x in order]
        self.assertEqual(at, sorted(at))
        self.assertEqual(body.count('<div class="next">'), 1)
        self.assertIn('<span class="o">Head of Product, Quoting squad</span><span class="d">2026-09-19</span>', body)
        self.assertIn("<details><summary>For your engineers</summary>", body)

    def test_the_visual_draws_only_figures_the_page_prints(self) -> None:
        page = (SAMPLE / "release-readiness.html").read_text(encoding="utf-8")
        visuals = svgkit.visuals_in(page)
        self.assertEqual(len(visuals), 2, "the wide and the tall variant")
        self.assertEqual(svgkit.unprinted(page), [])
        for svg in visuals:
            texts = svgkit.texts_in(svg)
            self.assertEqual(svg.count('fill="var(--t1)"') >= 1, True)
            self.assertIn("Waived by Head of Product, Quoting squad", texts)
            self.assertIn("UNTIL 2026-09-19", texts)

    def test_the_visual_states_the_answer(self) -> None:
        page = (SAMPLE / "release-readiness.html").read_text(encoding="utf-8")
        for svg in svgkit.visuals_in(page):
            self.assertIn('role="img"', svg)
            label = re.search(r'aria-label="([^"]+)"', svg).group(1)
            self.assertEqual(
                label,
                "Acme quote drafting v1.0 is ready to ship: 6 of 7 checks are ready to ship; "
                "open bugs holds under a waiver from Head of Product, Quoting squad until 2026-09-19.",
            )
        held = readiness.decide(FIXTURES / "acme-held" / "release.json", *(FIXTURES / "acme-held" / f"{k}.csv" for k in ("ci", "bugs", "flags", "evals")), FIXTURES / "acme-held" / "brief.md")
        label = re.search(r'aria-label="([^"]+)"', render_html.gates(held, "wide")).group(1)
        self.assertTrue(label.endswith("must hold: 3 of 6 checks are ready to ship, and code checks, open bugs and quality tests hold."), label)
        self.assertEqual(render_html.gates(held, "wide").count('fill="var(--t1)"'), 3, "one solid gate per held check")

    def test_public_copy_uses_plain_words(self) -> None:
        page = (SAMPLE / "release-readiness.html").read_text(encoding="utf-8")
        twin = (SAMPLE / "release-readiness.md").read_text(encoding="utf-8")
        for name, public in (("page", svgkit.page_text(page.split("For your engineers", 1)[0]).lower()), ("twin", twin.split("## For your engineers", 1)[0].lower())):
            with self.subTest(output=name):
                for word in (r"\bbets?\b", "eval", "rollback", "rollout", r"\bbar\b", r"\.csv", r"\.json", r"(?<![-|])--[a-z]", r"\bci\b", "commit", "holdout", "traces"):
                    self.assertIsNone(re.search(word, public), word)
                self.assertIsNone(re.search(r"\bspec\b(?!-auditor)", public), "spec only in spec-auditor's name")
        self.assertIn("the landing brief, a one-page plan: what good looks like, by when, at what cost", page)
        self.assertIn("A waiver is a named person's OK to ship despite a failed check, with an expiry date.", twin)

    def test_the_page_is_self_contained(self) -> None:
        page = (SAMPLE / "release-readiness.html").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"<(?:script|link|img)\b", page))
        self.assertNotIn("http://", page.split("</style>", 1)[1].replace(' xmlns="http://www.w3.org/2000/svg"', ""))


class Record(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="rr-loop-"))
        shutil.copytree(SAMPLE / "briefs", self.work / "briefs")
        (self.work / "landing").mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def run_loop(self, record: dict | None) -> tuple[int, dict]:
        if record is not None:
            (self.work / "landing" / f"{BET}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        ins = SAMPLE / "inputs"
        args = ["--release", str(ins / "release.json"), "--loop", str(self.work), "--bet", BET, "--out", str(self.work / "run")]
        for k in ("ci", "bugs", "flags", "evals"):
            args += [f"--{k}", str(ins / f"{k}.csv")]
        with contextlib.redirect_stdout(io.StringIO()):
            code = readiness.main(args)
        return code, json.loads((self.work / "landing" / f"{BET}.json").read_text(encoding="utf-8"))

    def upstream(self) -> dict:
        return json.loads(UPSTREAM.read_text(encoding="utf-8"))

    def test_later_keys_are_never_read_and_are_kept_as_found(self) -> None:
        base, _ = self.run_loop(self.upstream())
        first = json.loads((self.work / "run" / "readiness.json").read_text(encoding="utf-8"))
        later = {**self.upstream(), "cost": {"budget_status": "ignore me"}, "landed": {"status": "stalled"}, "board_qa": [1]}
        code, out = self.run_loop(later)
        second = json.loads((self.work / "run" / "readiness.json").read_text(encoding="utf-8"))
        self.assertEqual((base, code), (0, 0))
        self.assertEqual(first, second)
        self.assertEqual(list(out), ["schema", "bet", "brief", "spec", "release", "cost", "landed", "board_qa"])
        for k in ("cost", "landed", "board_qa", "spec", "brief"):
            self.assertEqual(out[k], later[k], k)

    def test_a_rerun_replaces_its_key_in_place(self) -> None:
        _, once = self.run_loop(self.upstream())
        _, twice = self.run_loop(None)
        self.assertEqual(once, twice)

    def test_no_spec_key_holds_the_spec_check(self) -> None:
        rec = {k: v for k, v in self.upstream().items() if k != "spec"}
        code, out = self.run_loop(rec)
        self.assertEqual((code, out["release"]["readiness"]), (1, "hold"))
        spec = next(c for c in out["release"]["checks"] if c["id"] == "spec")
        self.assertIn("Run spec-auditor", spec["reasons"][0])

    def test_a_spec_hold_with_no_release_check_stays_open(self) -> None:
        rec = self.upstream()
        rec["spec"]["holds"].append({"check": "problem", "message": "The problem is not stated."})
        code, out = self.run_loop(rec)
        self.assertEqual(code, 1)
        self.assertIn("no release check that closes it", " ".join(next(c for c in out["release"]["checks"] if c["id"] == "spec")["reasons"]))

    def test_a_brief_edited_after_the_record_opened_holds(self) -> None:
        brief = self.work / "briefs" / f"{BET}.md"
        brief.write_text(brief.read_text(encoding="utf-8").replace("2026-11-15", "2026-12-15"), encoding="utf-8")
        code, out = self.run_loop(self.upstream())
        self.assertEqual(code, 1)
        self.assertIn("changed after the loop record opened", " ".join(next(c for c in out["release"]["checks"] if c["id"] == "brief")["reasons"]))

    def test_a_record_for_another_bet_is_refused_and_left_alone(self) -> None:
        rec = {**self.upstream(), "bet": "payment-links"}
        path = self.work / "landing" / f"{BET}.json"
        path.write_text(json.dumps(rec), encoding="utf-8")
        ins = SAMPLE / "inputs"
        with contextlib.redirect_stdout(io.StringIO()):
            code = readiness.main(["--release", str(ins / "release.json"), "--loop", str(self.work), "--bet", BET, "--out", str(self.work / "run")])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), rec)

    def test_a_new_record_names_its_brief_relative_to_the_folder(self) -> None:
        fx = FIXTURES / "acme-ready"
        shutil.copy(fx / "brief.md", self.work / "briefs" / "ready.md")
        with contextlib.redirect_stdout(io.StringIO()):
            readiness.main(
                [
                    "--release",
                    str(fx / "release.json"),
                    "--brief",
                    str(self.work / "briefs" / "ready.md"),
                    "--loop",
                    str(self.work),
                    "--bet",
                    "ready",
                    "--out",
                    str(self.work / "run"),
                ]
            )
        rec = json.loads((self.work / "landing" / "ready.json").read_text(encoding="utf-8"))
        self.assertEqual(rec["brief"]["path"], "briefs/ready.md")
        self.assertEqual(list(rec), ["schema", "bet", "brief", "release"])


if __name__ == "__main__":
    unittest.main()
