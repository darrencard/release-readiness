# Changelog

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
