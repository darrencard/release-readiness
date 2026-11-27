# Changelog

## 0.3.2, 2026-11-27

- Scorecard fix round: a check row has no picture, so its name takes the picture column too and stays on one line; the share ("6 of 7 ready") prints once, in the frame head beside "Checks" with its bar, and the "All checks" row is gone, as /update does; the figure column prints in one case, numerals and capitals ("2 MAJOR OPEN · UNTIL 2026-09-19"), as /update. Tests for each.
- The page's picture is now the scorecard, in the grammar of the outcome scorecard on dacard.ai/update: one frame of HTML rows split by hairlines. The first row is a share bar of the checks that are ready ("6 of 7 ready", with the call's word); then one row per check in the order they run, each with its figure and its word: hold in ink, ready to ship muted, as text. The waived check carries the person who OK'd it in brass (a person mark and the role, no box) and the date the waiver runs out on its figure line ("2 major open · until 2026-09-19"). The aria-label is the call. Labels and words render 12px Geist Mono, names 14px Geist; no text in any SVG, no viewBox, no boxed chip. The row of gates (wide and tall SVGs) and its boxed panel are gone, and the check word under the lede is text, not a chip.
- svgkit 1.2.0, vendored byte-identical from landing-loop 78784ef (the commit that last changed `tools/svgkit.py`; rollout recipe at c6c47e7) and pinned in `VENDORED.json`.
- Tests copied from the rollout recipe: no text inside an SVG, no scaled picture, only the 12px and 14px sizes in the frame, no box in the frame and no chip before the engineers' fold, no legacy svgkit primitive (rendered with DeprecationWarning as an error), one frame with the share row and one row per check with each figure line printed exactly, brass only on the waiver's approver, the aria-label equal to the call, and nothing drawn that the page does not print.
- Plain words in the README and SKILL.md: project, the project file, and the landing brief defined once as a one-page plan: what good looks like, by when, at what cost. SKILL.md tells Claude to use the user's own word if they say bet. Keys, file names and flags (`--bet`) are unchanged.

## 0.3.1, 2026-11-27

- The HTML page follows the Landing Loop sample anatomy: the shared header (mark, DACARD, skill, date, version, blue Illustrative tag), the call as the heading ("Acme quote drafting v1.0 is ready to ship, with one waiver."), the check word, the signature picture, one next step with the brief's decider in brass and a due date, then every check beside the waiver, the build plan holds, the plan behind the release and what is worth knowing, in two columns. Check ids, stored labels and reasons, notes as computed, the record key, exit codes and the evidence ledger fold under "For your engineers".
- The signature picture: a row of gates, one per check. Ready to ship is an outline with a tick, hold is solid ink, and the waived check carries the approver's name and the waiver's end date in brass. A 720 wide variant for desktop and a 340 wide one for phones; the aria-label states the call. Drawn with svgkit, vendored byte-identical from landing-loop and pinned in `VENDORED.json` under `landing-loop`.
- The Illustrative tag is blue (#74A5DA), not grey.
- Public copy in plain words, on the page and in the Markdown twin: code checks, quality tests, undo plan, first release stage, build plan, target, project file, and a waiver defined at first use. The record keeps its own words: check labels, reasons and `next_step` are stored as before.
- Design fix round 2: no text below 11px at any width (the page raises the vendored template's and svgkit's 10 and 10.5px labels as it writes its CSS; both files stay byte-identical). Below 980px the picture's panel drops its side padding and frame, so the 720 and 340 wide gates draw at full size down to a 375px phone. The header prints the plain name, Release readiness; the code name moves to the engineers' fold, on the page and in the Markdown twin. Public copy prints none of record, bet, the bar, PRD, ARR or tokens. Tests for each.
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
