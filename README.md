# Go or no-go, every gap owned

A free Claude skill that makes the release call from your CI, bugs, flags, rollback plan, landing brief and evals, and names who owns each thing still open.

**Why it matters:** a release with one open criterion is not ready, however good the rest looks. This skill makes that rule explicit: every criterion must be met or waived by a named approver, code computes every figure, and a release note that calls a held release ready does not pass.

## Install: paste this into Claude Code

```text
Install the release-readiness skill from https://github.com/darrencard/release-readiness by copying its skills/release-readiness folder to ~/.claude/skills/release-readiness, and show me its demo with python3 scripts/readiness.py --demo. Then check whether my next release is ready: read CI, commit statuses, branch protection and open bugs for OWNER/REPO through gh, ask me for the flags, the rollback plan and its trigger, the landing brief and, if it has an AI feature, the eval results, and give me the go or no-go with every open criterion and its owner.
```

Replace `OWNER/REPO`. No GitHub? Give it CSV exports instead (formats in [inputs.md](skills/release-readiness/references/inputs.md)). The demo runs in under a second with no setup.

## What you see

From the demo, an illustrative Acme release:

```text
**Decision: no-go.** 3 of 6 criteria are met. 3 are open.

| Criterion                            | Owner        | Why it is open                                                       |
|--------------------------------------|--------------|----------------------------------------------------------------------|
| CI passes on the release commit      | Nadia Flores | Check 'integration-tests' is failure, not success (ci.csv row 3).    |
| Open bugs within the severity limits | Marcus Lee   | 1 open critical bug against a limit of 0: #2210 (Ravi Menon).        |
| Eval gate passes for the AI feature  | Sam Patel    | Eval 'chase-message-tone' passes 91.0% (182 of 200), below its 95.0% threshold. |
```

Below that: every criterion's state, any waivers, notes (non-required checks failing, policy changes from the default) and an evidence ledger with the source file of each figure.

## What it checks

| Criterion | Met when |
|---|---|
| CI | Every required check passed on the release commit, from Actions and external CI |
| Bugs | Open bugs are within the limit per severity (default: 0 blocker, 0 critical, 3 major); an untriaged bug blocks |
| Flags | Every change sits behind a flag with an off switch, an owner and a capped starting rollout |
| Rollback | A written plan, an owner, a named trigger and a rehearsal in the last 30 days |
| Landing brief | The metric that should move, where it is read on day one, the target and a review date |
| Evals (AI features) | Every eval meets its threshold on enough cases, recently, on the release commit |

A missing input never counts as met. It leaves its criterion open, with an owner. A waiver needs a reason, an approver who does not own the criterion and an expiry within 14 days, and it never marks a criterion met.

## Use it as a CI gate

```bash
python3 scripts/readiness.py --release run/release.json --ci run/ci.csv --bugs run/bugs.csv --flags run/flags.csv --evals run/evals.csv --json
```

Exit code 0 is go, 1 is no-go, 2 is an input error. Python 3.11 or later, standard library only. It runs locally; the only network call is `gh`, when you ask for it. `--init run/release.json` writes a template to fill in. A ready-made GitHub Actions gate is in [release-gate.yml](skills/release-readiness/examples/release-gate.yml).

## Tests

```bash
python3 -m unittest discover -s evals -v
```

MIT licensed. Built by [Dacard](https://www.dacard.ai).
