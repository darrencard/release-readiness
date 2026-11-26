# Inputs

Every file is optional except `release.json`. A missing file leaves its criterion open. Column names are case-insensitive. Dates are YYYY-MM-DD.

## release.json

```json
{
  "name": "Acme Invoice Chaser 1.0",
  "owner": "Marcus Lee",
  "as_of": "2026-11-20",
  "commit": "9b81d07a55e2",
  "ai_feature": true,
  "illustrative": false,
  "owners": {"ci": "Nadia Flores", "bugs": "Marcus Lee", "flags": "Nadia Flores", "rollback": "Lena Okafor", "evals": "Sam Patel"},
  "rollback": {"plan": "Turn off invoice_chaser, then redeploy 3.8.2.", "owner": "Lena Okafor", "tested_on": "2026-11-10"},
  "policy": {
    "max_open_bugs": {"blocker": 0, "critical": 0, "major": 3},
    "untriaged_blocks": true,
    "rollback_test_max_age_days": 30,
    "max_initial_rollout_percent": 100,
    "min_eval_cases": 50,
    "eval_max_age_days": 7
  }
}
```

`name`, `owner` and `as_of` are required. `commit` is needed for CI to pass. `owners` and `policy` are optional; the values above are the defaults. A short SHA matches its full form.

## ci.csv

| Column | Required | Notes |
|---|---|---|
| check | yes | The check name |
| conclusion | yes | `success` passes. Anything else (failure, pending, cancelled, skipped, neutral) is open |
| required | no | `yes` (default) or `no`. Only required checks count |
| commit | yes, to pass | The SHA the check ran on. A check with no commit cannot be tied to the release |
| url, owner | no | Shown in the reason when the check fails |

`from_gh.py` writes this file from the GitHub Checks API.

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
| passed | yes | Cases passed. The pass rate is computed, never read |
| threshold | yes | 0.95 or 95% |
| run_at | yes | When the eval ran |
| commit | no | When given, it must match the release commit |
| owner | no | |
