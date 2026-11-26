# Go or no-go, every gap owned

A free Claude skill that makes the release call from your CI, bugs, flags, rollback plan and evals, and names who owns each thing still open.

**Why it matters:** a release with one open criterion is not ready, however good the rest looks. This skill makes that rule explicit: every criterion must be met, code computes every figure, and a release note that calls a held release ready does not pass.

## Install: paste this into Claude Code

```text
Install the release-readiness skill from https://github.com/darrencard/release-readiness by copying its skills/release-readiness folder to ~/.claude/skills/release-readiness, then run its tests with python3 -m unittest discover -s evals. Then check whether my next release is ready: read CI and open bugs for OWNER/REPO through gh, ask me for the flags, the rollback plan and, if it has an AI feature, the eval results, and give me the go or no-go with every open criterion and its owner.
```

Replace `OWNER/REPO`. No GitHub? Give it CSV exports instead (formats in [inputs.md](skills/release-readiness/references/inputs.md)).

## What it checks

| Criterion | Met when |
|---|---|
| CI | Every required check passed on the release commit |
| Bugs | Open bugs are within the limit per severity (default: 0 blocker, 0 critical, 3 major); an untriaged bug blocks |
| Flags | Every change sits behind a flag with an off switch, an owner and a capped starting rollout |
| Rollback | A written plan, an owner and a rehearsal in the last 30 days |
| Evals (AI features) | Every eval meets its threshold on enough cases, recently, on the release commit |

A missing input never counts as met. It leaves its criterion open, with an owner.

## What you get

- **One call.** Go only when every criterion is met.
- **The open list.** Each open criterion, why it is open and who owns it.
- **An evidence ledger.** Every count, pass rate and age, with the file it came from.
- **A draft check.** `validate.py` blocks a go claim on a no-go, a dropped criterion or owner, and any number the call did not compute.

## Worked example

Two illustrative releases from Acme, an invented invoicing company for trades businesses, are in [evals/fixtures](evals/fixtures). Quote Assistant 2.4 is a go. Invoice Chaser 1.0 is a no-go: 2 of 5 criteria met, with a failing integration check, an open critical bug and a tone eval at 91.0% against a 95.0% threshold, each with its owner.

## Run it by hand

```bash
cd skills/release-readiness
python3 scripts/from_gh.py --repo OWNER/REPO --ref <sha> --out run/
python3 scripts/readiness.py --release run/release.json --ci run/ci.csv --bugs run/bugs.csv --flags run/flags.csv --evals run/evals.csv --out run/
```

Python 3.11 or later, standard library only. Runs locally; the only network call is `gh`, when you ask for it. Exit code 0 is go, 1 is no-go, 2 is an input error.

## Tests

```bash
python3 -m unittest discover -s evals -v
```

MIT licensed. Built by [Dacard](https://www.dacard.ai).
