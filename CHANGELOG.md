# Changelog

## 0.3.1, 2026-11-27

- The HTML page follows the Landing Loop sample anatomy: the shared header (mark, DACARD, skill, date, version, blue Illustrative tag), the call as the heading ("Acme quote drafting v1.0 is ready to ship, with one waiver."), the check word, the signature picture, one next step with the brief's decider in brass and a due date, then every check beside the waiver, the build plan holds, the plan behind the release and what is worth knowing, in two columns. Check ids, stored labels and reasons, notes as computed, the record key, exit codes and the evidence ledger fold under "For your engineers".
- The signature picture: a row of gates, one per check. Ready to ship is an outline with a tick, hold is solid ink, and the waived check carries the approver's name and the waiver's end date in brass. A 720 wide variant for desktop and a 340 wide one for phones; the aria-label states the call. Drawn with svgkit, vendored byte-identical from landing-loop and pinned in `VENDORED.json` under `landing-loop`.
- The Illustrative tag is blue (#74A5DA), not grey.
- Public copy in plain words, on the page and in the Markdown twin: code checks, quality tests, undo plan, first release stage, build plan, target, project file, and a waiver defined at first use. The record keeps its own words: check labels, reasons and `next_step` are stored as before.
- Tests: the picture draws only printed figures, states the call in its aria-label, and the page paints no status colour (it prints neither landed nor stalled); brass is only who decides and who waived; public copy uses the plain words; the vendored svgkit matches its pin.

## 0.3.0, 2026-11-26

- The Acme sample tells the loop's story: the rollback trigger is the one decided on 2026-08-10 (wrong-price quotes over 2%, decision-record's D-0004), owned by the tech lead. Samples and fixtures name only the Acme org chart's four roles.
- `validate.py` no longer counts a longer owner name as naming a shorter one ("Tech lead, Quoting squad" does not name "Lead, Quoting squad").
- Every entry script checks for Python 3.11 before it reads or writes anything. The SKILL.md description is under 1,024 characters.
- Step 03 (Build) of the Landing Loop. `--loop DIR --bet SLUG` reads the bet's `landing/<bet>.json`, reads the brief it names and spec-auditor's `spec` key, and writes only the `release` key, in its place in the record order. Every other key stays byte-identical, and no key later in the order is read.
- The words are this check's own: ready to ship or hold, for each check and for the release. go and no-go are gone, and landed, watch and stalled never print.
- The landing brief is read with the Leader Report's `landing_brief.py`, vendored byte-identical (sha256 `2d13573543c74ebe...`), and its own completeness check. The brief's line turns on the eval gate. A brief changed after the record opened holds.
- New `spec` check: each spec hold closes only through the release check that tests the same thing (rollback, eval-plan, rollout).
- Every figure is value, unit, source, window and as_of, computed in code. The eval gate records cases run, passed and needed; pass rate stays eval-kit's figure.
- A rollback trigger needs a threshold. Policy changes print in plain words.
- One self-contained HTML page in the Leader Report style, with the Markdown twin. Brass marks a person's call (a waiver, its approver, who decides); no status colours.
- Acme sample: `python3 examples/acme/sample.py` rebuilds `examples/acme/release-readiness.html`, its twin and the record from `examples/acme/upstream/`, and a test checks the bytes.
- `validate.py --readiness` blocks a ready claim on a hold and any bet status word.

## 0.1.0, 2026-11-26

- First version: a go or no-go call from CI, bugs, flags, rollback, brief and evals, with waivers and the draft check.
