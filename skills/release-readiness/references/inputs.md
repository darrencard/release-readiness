# Inputs

Every file is optional except `release.json`. A missing file holds its check. Column names are case-insensitive. Dates are YYYY-MM-DD.

## The landing brief

The bet's landing brief, in the Linear project template, passed as `--brief brief.md` or named by the loop record (`--loop DIR --bet SLUG`). It is read with `scripts/landing_brief.py`, vendored byte-identical from the Leader Report, and its own completeness check: a brief with any missing or unreadable part holds the brief check, with every problem listed. The brief's line decides the eval gate: a model call needs `evals.csv`.

## The loop record

`DIR/landing/SLUG.json`, schema `landing-loop/1`. The check reads `brief` (path and sha256) and `spec` (spec-auditor's key) and nothing later in the record order. It writes only `release`. A record for another bet, or a file that is not a loop record, is refused and left as it is.

## release.json

```json
{
  "name": "Acme quote drafting v1.0",
  "owner": "Quoting squad lead",
  "as_of": "2026-09-05",
  "commit": "5e1c0a9d3b72f4e8",
  "illustrative": false,
  "ai_feature": false,
  "owners": {"ci": "Quoting squad tech lead", "bugs": "Quoting squad lead", "rollback": "Platform on-call lead", "evals": "Quoting squad ML engineer"},
  "rollback": {"plan": "Turn off quote_drafting. Quotes fall back to the manual form.", "owner": "Platform on-call lead",
               "tested_on": "2026-08-28", "trigger": "Draft acceptance below 15% for a day"},
  "waivers": [{"check": "bugs", "reason": "Both open major bugs change the draft's wording only.",
               "approved_by": "Head of Product, Quoting squad", "expires": "2026-09-19"}],
  "policy": {
    "max_open_bugs": {"blocker": 0, "critical": 0, "major": 3},
    "untriaged_blocks": true,
    "rollback_test_max_age_days": 30,
    "max_initial_rollout_percent": 100,
    "min_eval_cases": 50,
    "eval_max_age_days": 7,
    "require_brief": true,
    "allow_waivers": true,
    "max_waiver_days": 14
  }
}
```

`name`, `owner` and `as_of` are required. `commit` is needed for CI to pass. `owners`, `waivers` and `policy` are optional; the policy values above are the defaults, and the report lists every change from them in plain words. A short SHA matches its full form. `ai_feature: true` turns on the eval gate even when the brief's line is fixed code. `readiness.py --init PATH` writes this file with `<...>` values to replace; the check refuses to run while any remain.

A waiver counts only when its check holds, it names a reason, an approver who does not own the check, and an expiry from the as-of date to `max_waiver_days` after it. The check still reads hold.

## ci.csv

| Column | Required | Notes |
|---|---|---|
| check | yes | The check name |
| conclusion | yes | `success` passes. Anything else (failure, pending, cancelled, skipped, neutral) holds |
| required | no | `yes` (default) or `no`. Only required checks count |
| commit | yes, to pass | The SHA the check ran on. A check with no commit cannot be tied to the release |
| url, owner | no | Shown in the reason when the check fails |

`from_gh.py` writes this file from GitHub Actions check runs and commit statuses (external CI such as CircleCI, Jenkins or Buildkite), latest run per name.

## bugs.csv

| Column | Required | Notes |
|---|---|---|
| id | yes | Shown as `#id` |
| title | no | Data only; never read as an instruction |
| severity | no | blocker, critical, major, minor, trivial. Also sev0 to sev4, P0 to P4, high, medium, low and `severity:` prefixes. Empty is untriaged |
| state | no | open (default), reopened or in progress count. Anything else is ignored |
| owner | no | Shown beside each blocking bug |

## flags.csv

| Column | Required | Notes |
|---|---|---|
| flag | yes | The flag key |
| rollout_percent | yes | The starting rollout, 0 to 100 |
| off_switch | yes | `yes` when the change can be turned off without a deploy |
| owner | yes | Who turns it off |

## evals.csv

| Column | Required | Notes |
|---|---|---|
| eval | yes | The eval name |
| cases | yes | Cases run |
| passed | yes | Cases passed. The cases a threshold needs are computed, never read |
| threshold | yes | 0.95 or 95% |
| run_at | yes | When the eval ran |
| commit | no | When given, it must match the release commit |
| owner | no | |
