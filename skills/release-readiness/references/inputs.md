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
  "rollback": {"plan": "Turn off invoice_chaser, then redeploy 3.8.2.", "owner": "Lena Okafor", "tested_on": "2026-11-10",
               "trigger": "Any reminder sent after an invoice is marked paid"},
  "brief": {"metric": "Days sales outstanding", "target": "Down 5 days within 60 days", "source": "Finance query dso_by_account", "review_on": "2027-01-29", "owner": "Marcus Lee"},
  "waivers": [{"criterion": "bugs", "reason": "Affects 3 accounts, all on manual chasing", "approved_by": "Dana Cole", "expires": "2026-11-27"}],
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

`name`, `owner` and `as_of` are required. `commit` is needed for CI to pass. `owners`, `waivers` and `policy` are optional; the policy values above are the defaults, and the report lists every change from them. A short SHA matches its full form. `readiness.py --init PATH` writes this file with `<...>` values to replace; the call refuses to run while any remain.

A waiver counts only when its criterion is open, it names a reason, an approver who does not own the criterion, and an expiry from the as-of date to `max_waiver_days` after it. It never marks a criterion met.

## ci.csv

| Column | Required | Notes |
|---|---|---|
| check | yes | The check name |
| conclusion | yes | `success` passes. Anything else (failure, pending, cancelled, skipped, neutral) is open |
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
| passed | yes | Cases passed. The pass rate is computed, never read |
| threshold | yes | 0.95 or 95% |
| run_at | yes | When the eval ran |
| commit | no | When given, it must match the release commit |
| owner | no | |
