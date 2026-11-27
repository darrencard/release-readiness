# Release readiness: ready to ship, or hold

```text
Install the release-readiness skill from https://github.com/darrencard/release-readiness: clone it, find a Python 3.11 or later on this machine (macOS python3 is often 3.9), run python3 examples/acme/sample.py and show me the page it writes. Then check my next release: read its landing brief and landing/<bet>.json record, read CI checks, commit statuses, branch protection and open bugs for OWNER/REPO through gh (or take my CSV exports), ask me only for the flags, the rollback plan and its trigger, the eval results and the release commit, and tell me ready to ship or hold with the owner of every held check.
```

A free Claude skill that says whether one release is **ready to ship** or must **hold**, check by check, and names who owns each hold.

**Why it matters:** one open check is enough to hold a release, however good the rest looks. Code computes every figure from your CI, bugs, flags, rollback plan, evals and landing brief. A waiver is a person's call, named, with a reason and an end date, and it never turns a hold into ready.

## Try it on Acme

Acme is invented: invoicing software for trades businesses. Every figure is illustrative. From the repository root, on Python 3.11 or later:

```bash
python3 examples/acme/sample.py
```

It rebuilds [examples/acme/release-readiness.html](examples/acme/release-readiness.html), its [Markdown twin](examples/acme/release-readiness.md) and the `release` key of [examples/acme/landing/quote-drafting.json](examples/acme/landing/quote-drafting.json) in under a second. The release is Acme's quote drafting v1.0, checked on 2026-09-05, two days before it shipped:

```text
Ready to ship, with 1 waiver. 6 of 7 checks are ready to ship; 1 check holds under a waiver.

| Open bugs within the severity limits | hold, waived | Lead, Quoting squad |
  2 open major bugs against a limit of 1. Approved by Head of Product, Quoting squad, until 2026-09-19.
| Spec holds from spec-auditor are closed | ready to ship | Lead, Quoting squad |
  rollback closed by the rollback check; eval-plan closed by the evals check.
```

A test checks the command reproduces the committed files byte for byte.

## Install

In Claude Code, with the Landing Loop:

```text
/plugin marketplace add darrencard/landing-loop
/plugin install release-readiness@landing-loop
```

On its own: clone this repository and copy `skills/release-readiness` into `~/.claude/skills/release-readiness`. Python 3.11 or later, standard library only. Nothing else to install. The only network call is `gh`, when you ask for GitHub data.

## Reads and writes

Step 03 (Build) of the Landing Loop.

| Reads | Writes |
|---|---|
| The landing brief the record names, parsed by the Leader Report's `landing_brief.py` (vendored byte-identical) with its own completeness check | The `release` key of `landing/<bet>.json`, and no other key |
| The record's `spec` key: each hold spec-auditor raised closes only when the check here that tests the same thing is ready | One HTML page in the Leader Report style, and its Markdown twin |
| CI checks, commit statuses, branch protection and open bugs, live through `gh` (`from_gh.py`); CSV exports as the fallback | `readiness.json`, which `validate.py` checks a release note against |
| `release.json` (owners, rollback, waivers, policy), `flags.csv` and, for a model call, `evals.csv` | |

It reads no key later in the record order. The words are this check's own: **ready to ship** or **hold**, for each check and for the release. Landed, watch and stalled are the bet's status, and only did-it-land sets them after launch.

| Check | Ready to ship when |
|---|---|
| CI | Every required check passed on the release commit |
| Bugs | Open bugs are within the limit per severity (default 0 blocker, 0 critical, 3 major); an untriaged bug holds |
| Flags | Every change sits behind a flag with an off switch, an owner and a capped starting rollout |
| Rollback | A written plan, an owner, a trigger with a threshold, and a rehearsal in the last 30 days |
| Brief | The brief parses complete, and its date is still ahead |
| Evals | When the brief's line is a model call: every eval has enough cases, ran this week on the release commit, and passed at least the cases its threshold needs |
| Spec | Every hold from spec-auditor is closed by a ready check here |

## The record key

```json
{
  "release": {
    "tool": "release-readiness 0.3.0",
    "as_of": "2026-09-05",
    "release": "Acme quote drafting v1.0",
    "commit": "5e1c0a9d3b72f4e8",
    "readiness": "ready to ship",
    "counts": {
      "ready": {"value": 6, "unit": "checks ready to ship", "source": "release-readiness 0.3.0: count of the checks above; examples/acme/inputs/release.json",
                "window": {"from": "2026-09-05", "to": "2026-09-05"}, "as_of": "2026-09-05"}
    },
    "checks": [
      {"id": "bugs", "readiness": "hold", "owner": "Lead, Quoting squad",
       "reasons": ["2 open major bugs against a limit of 1: #3101 (Tech lead, Quoting squad), #3104 (Tech lead, Quoting squad)."],
       "figures": {"open.major": {"value": 2, "unit": "bugs", "source": "examples/acme/inputs/bugs.csv",
                                  "window": {"from": "2026-09-05", "to": "2026-09-05"}, "as_of": "2026-09-05"}},
       "waiver": {"approved_by": "Head of Product, Quoting squad", "reason": "Both open major bugs change the draft's wording only.", "expires": "2026-09-19"}}
    ],
    "spec_holds": [{"finding": "rollback", "closed_by": "rollback", "closed": true}],
    "decides": "Head of Product, Quoting squad"
  }
}
```

## Limits

- It says whether this commit is ready to ship, not whether the bet will work. did-it-land reads that after launch.
- The eval gate records cases run, passed and needed at release. The pass rate of record is eval-kit's `evals` key, which comes later in the loop.
- Flags, the rollback plan and eval results come from files you give it. No Leader Report collector reads check runs or bug severity at a commit, so `from_gh.py` is this skill's own reader, and other trackers come in as CSV.
- A spec hold with no matching release check (a missing problem statement, say) stays open until spec-auditor passes the spec.

Not yet run on a real team's data.

Run the tests: `python3 -m unittest discover -s evals`. Use it as a CI gate: [references/release-gate.yml](skills/release-readiness/references/release-gate.yml) exits 1 on a hold.

MIT licence. Made by [Dacard](https://www.dacard.ai). GitHub is a trademark of GitHub, Inc.; this skill is not affiliated with or endorsed by GitHub.

Claude and Claude Code are trademarks of Anthropic, PBC. These skills are independent and not affiliated with or endorsed by Anthropic.
