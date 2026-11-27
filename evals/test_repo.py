#!/usr/bin/env python3
"""House rules for every file in the repository: wording, versions, the vendored files and the README commands.

Usage:
  python3 -m unittest discover -s evals -v
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import tomllib
import unittest

from helpers import ROOT, SAMPLE, SKILL

import landing_brief
import readiness

SKIP = {".git", ".ruff_cache", ".pytest_cache", "__pycache__", "vendor"}
TEXT = [p for p in ROOT.rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".json", ".toml", ".yml", ".csv", ".html"} and not SKIP & set(p.parts)]
TEXT = [p for p in TEXT if p.name != "landing_brief.py"]  # vendored byte-identical; its words are the parser's own
BANNED = re.compile(r"\b(AI-powered|unlock|supercharge|seamless|robust|get started|sign up)\b|\bleverag(?:e|es|ed|ing) (?:the|our|your|this|it)\b", re.I)
AMERICAN = re.compile(r"\b(behavior|organization|prioritize|license(?!d)|color|favorite|normalize)\b")
# Files that quote a banned or American word in order to block it.
ALLOWED = {"test_repo.py"}


class Wording(unittest.TestCase):
    def test_no_em_or_en_dashes(self) -> None:
        for p in TEXT:
            text = p.read_text(encoding="utf-8")
            self.assertNotIn(chr(0x2014), text, p)
            self.assertNotIn(chr(0x2013), text, p)

    def test_no_banned_words(self) -> None:
        for p in TEXT:
            if p.name in ALLOWED:
                continue
            m = BANNED.search(p.read_text(encoding="utf-8"))
            self.assertIsNone(m, f"{p}: {m and m.group(0)}")

    def test_british_spelling_in_prose(self) -> None:
        for p in [*ROOT.glob("*.md"), SKILL / "SKILL.md", *(SKILL / "references").glob("*.md"), SAMPLE / "release-readiness.md"]:
            text = p.read_text(encoding="utf-8")
            if text.startswith("---\n"):
                text = text.split("\n---\n", 1)[1]  # SKILL.md frontmatter keys are the format's own
            m = AMERICAN.search(text)
            self.assertIsNone(m, f"{p}: {m and m.group(0)}")

    def test_the_sample_data_says_it_is_illustrative(self) -> None:
        self.assertTrue(json.loads((SAMPLE / "inputs" / "release.json").read_text(encoding="utf-8"))["illustrative"])
        self.assertIn("Illustrative", (SAMPLE / "briefs" / "quote-drafting.md").read_text(encoding="utf-8"))
        page = (SAMPLE / "release-readiness.html").read_text(encoding="utf-8")
        self.assertIn('<span class="sk-ill">Illustrative</span>', page)
        self.assertIn(":root{--ill:#74A5DA}", page, "the Illustrative tag is blue")


class Skill(unittest.TestCase):
    def test_the_description_fits_the_skill_format(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        description = re.search(r"^description: (.*)$", text, re.M).group(1)
        self.assertLess(len(description), 1024)

    def test_every_entry_script_checks_python_before_anything_else(self) -> None:
        vendored = set(json.loads((SKILL / "VENDORED.json").read_text(encoding="utf-8"))["files"])
        scripts = [p for p in (SKILL / "scripts").glob("*.py") if f"scripts/{p.name}" not in vendored] + [SAMPLE / "sample.py"]
        for path in sorted(scripts):
            text = path.read_text(encoding="utf-8")
            if '__name__ == "__main__"' not in text:
                continue
            with self.subTest(script=path.name):
                check = text.find("sys.version_info < (3, 11)")
                self.assertGreater(check, 0)
                self.assertIn("try python3.12", text)
                body = text[text.find('"""', 3) + 3 :]
                for io_call in ("read_text(", "write_text(", "open("):
                    first = text.find(io_call, len(text) - len(body))
                    self.assertTrue(first == -1 or first > check, f"{path.name}: {io_call} before the version check")


class Story(unittest.TestCase):
    """The Acme sample tells the same story as the rest of the loop and names only the Acme org chart's roles."""

    ROLES = {"Head of Product, Quoting squad", "Lead, Quoting squad", "Tech lead, Quoting squad", "Product manager, Quoting squad"}

    def test_the_rollback_trigger_is_the_one_decided_for_quote_drafting(self) -> None:
        plan = json.loads((SAMPLE / "inputs" / "release.json").read_text(encoding="utf-8"))["rollback"]
        # decision-record's D-0004, decided 2026-08-10 after the spec hold of 2026-08-03: wrong-price quotes over 2%, owned by the tech lead.
        self.assertIn("Wrong-price quotes pass 2%", plan["trigger"])
        self.assertEqual(plan["owner"], "Tech lead, Quoting squad")

    def test_only_the_acme_org_chart_roles_own_or_approve(self) -> None:
        for folder in (SAMPLE / "inputs", ROOT / "evals" / "fixtures" / "acme-ready", ROOT / "evals" / "fixtures" / "acme-held"):
            release = json.loads((folder / "release.json").read_text(encoding="utf-8"))
            people = {release["owner"], *release["owners"].values(), release["rollback"]["owner"], *(w["approved_by"] for w in release.get("waivers", []))}
            for name in sorted(folder.glob("*.csv")):
                with name.open(encoding="utf-8", newline="") as fh:
                    people |= {row["owner"] for row in csv.DictReader(fh) if row.get("owner")}
            with self.subTest(folder=folder.name):
                self.assertLessEqual(people, self.ROLES)
        page = (SAMPLE / "release-readiness.md").read_text(encoding="utf-8")
        self.assertNotRegex(page, r"(?i)on-call|ML engineer|VP Product|Invoicing squad")


class Versions(unittest.TestCase):
    def test_every_version_field_is_0_3_2(self) -> None:
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        skill = re.search(r'version: "([^"]+)"', (SKILL / "SKILL.md").read_text(encoding="utf-8")).group(1)
        self.assertEqual({plugin, project, skill, readiness.VERSION}, {"0.3.4"})

    def test_the_changelog_has_a_dated_entry_for_this_version(self) -> None:
        self.assertIn("## 0.3.4, 2026-11-27", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))


class Vendored(unittest.TestCase):
    def test_vendored_files_match_their_pinned_hashes(self) -> None:
        pins = json.loads((SKILL / "VENDORED.json").read_text(encoding="utf-8"))
        self.assertRegex(pins["commit"], r"^[0-9a-f]{40}$")
        for rel, pin in pins["files"].items():
            with self.subTest(file=rel):
                self.assertEqual(hashlib.sha256((SKILL / rel).read_bytes()).hexdigest(), pin["sha256"])

    def test_svgkit_matches_its_landing_loop_pin(self) -> None:
        pin = json.loads((SKILL / "VENDORED.json").read_text(encoding="utf-8"))["landing-loop"]
        self.assertEqual(pin["commit"], "78784efd2ecd5282f6ec264e545ce2075e459be2")
        self.assertEqual(set(pin["files"]), {"scripts/vendor/svgkit.py"})
        for rel, info in pin["files"].items():
            digest = hashlib.sha256((SKILL / rel).read_bytes()).hexdigest()
            self.assertEqual(digest, info["sha256"], f"{rel} changed. Copy it again from landing-loop at the pinned commit and update VENDORED.json.")

    def test_the_brief_parser_is_the_contract_one(self) -> None:
        digest = hashlib.sha256((SKILL / "scripts" / "landing_brief.py").read_bytes()).hexdigest()
        self.assertTrue(digest.startswith("2d13573543c74ebe"))

    def test_the_parser_refuses_a_broken_brief_and_lists_every_problem(self) -> None:
        with self.assertRaises(landing_brief.BriefError) as ctx:
            landing_brief.parse("## Landing brief\n\n- **Metric:** Activation\n- **Bar:** soon\n")
        self.assertIn("problem is missing", str(ctx.exception))
        self.assertIn("by is missing", str(ctx.exception))


class Readme(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_the_sections_come_in_the_loop_order(self) -> None:
        heads = [h for h in re.findall(r"^## (.+)$", self.text, re.M)]
        want = ["Try it on Acme", "Install", "Reads and writes", "The project file key", "Limits"]
        self.assertEqual([h for h in heads if h in want], want)
        self.assertLess(self.text.index("```text"), self.text.index("## Try it on Acme"))

    def test_the_sample_command_is_the_one_the_test_runs(self) -> None:
        self.assertIn("python3 examples/acme/sample.py", self.text)

    def test_install_lines_and_maturity(self) -> None:
        self.assertIn("/plugin marketplace add darrencard/landing-loop", self.text)
        self.assertIn("/plugin install release-readiness@landing-loop", self.text)
        self.assertIn("Not yet run on a real team's data.", self.text)
        self.assertIn("MIT", self.text)

    def test_the_json_example_is_the_sample_key_shape(self) -> None:
        block = self.text.split("## The project file key", 1)[1].split("```json", 1)[1].split("```", 1)[0]
        example = json.loads(block)
        sample = json.loads((SAMPLE / "landing" / "quote-drafting.json").read_text(encoding="utf-8"))["release"]
        self.assertLessEqual(set(example["release"]), set(sample))
        self.assertEqual(example["release"]["readiness"], sample["readiness"])


if __name__ == "__main__":
    unittest.main()
