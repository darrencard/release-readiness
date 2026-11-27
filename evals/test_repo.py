#!/usr/bin/env python3
"""House rules for every file in the repository: wording, versions, the vendored files and the README commands.

Usage:
  python3 -m unittest discover -s evals -v
"""

from __future__ import annotations

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
        self.assertIn('<span class="ill">Illustrative</span>', (SAMPLE / "release-readiness.html").read_text(encoding="utf-8"))


class Versions(unittest.TestCase):
    def test_every_version_field_is_0_3_0(self) -> None:
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        skill = re.search(r'version: "([^"]+)"', (SKILL / "SKILL.md").read_text(encoding="utf-8")).group(1)
        self.assertEqual({plugin, project, skill, readiness.VERSION}, {"0.3.0"})

    def test_the_changelog_has_a_dated_entry_for_this_version(self) -> None:
        self.assertIn("## 0.3.0, 2026-11-26", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))


class Vendored(unittest.TestCase):
    def test_vendored_files_match_their_pinned_hashes(self) -> None:
        pins = json.loads((SKILL / "VENDORED.json").read_text(encoding="utf-8"))
        self.assertRegex(pins["commit"], r"^[0-9a-f]{40}$")
        for rel, pin in pins["files"].items():
            with self.subTest(file=rel):
                self.assertEqual(hashlib.sha256((SKILL / rel).read_bytes()).hexdigest(), pin["sha256"])

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
        want = ["Try it on Acme", "Install", "Reads and writes", "The record key", "Limits"]
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
        block = self.text.split("## The record key", 1)[1].split("```json", 1)[1].split("```", 1)[0]
        example = json.loads(block)
        sample = json.loads((SAMPLE / "landing" / "quote-drafting.json").read_text(encoding="utf-8"))["release"]
        self.assertLessEqual(set(example["release"]), set(sample))
        self.assertEqual(example["release"]["readiness"], sample["readiness"])


if __name__ == "__main__":
    unittest.main()
