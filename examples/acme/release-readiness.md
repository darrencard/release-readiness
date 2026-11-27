# Release readiness: Acme quote drafting v1.0

*Illustrative: sample data, not a real release.*

Checked 2026-09-05. Commit 5e1c0a9d3b72f4e8. Release owner: Lead, Quoting squad. Bet: quote-drafting.

**Ready to ship, with 1 waiver.** 6 of 7 checks are ready to ship; 1 check holds under a waiver.

## Waivers, each a person's call

| Check | Owner | Approved by | Expires | Reason | Holds because |
|---|---|---|---|---|---|
| Open bugs within the severity limits | Lead, Quoting squad | Head of Product, Quoting squad | 2026-09-19 | Both open major bugs change the draft's wording only. Prices come from the price book in fixed code. Fixes ship in v1.0.1. | 2 open major bugs against a limit of 1: #3101 (Tech lead, Quoting squad), #3104 (Tech lead, Quoting squad). |

## Every check

| Check | Check word | Owner |
|---|---|---|
| CI passes on the release commit | ready to ship | Tech lead, Quoting squad |
| Open bugs within the severity limits | hold, waived | Lead, Quoting squad |
| Every change behind a flag with an off switch | ready to ship | Tech lead, Quoting squad |
| Rollback written, owned, rehearsed, with a trigger threshold | ready to ship | Tech lead, Quoting squad |
| Landing brief complete, and its date still ahead | ready to ship | Head of Product, Quoting squad |
| Eval gate passes on the release commit | ready to ship | Tech lead, Quoting squad |
| Spec holds from spec-auditor are closed | ready to ship | Lead, Quoting squad |

## Spec holds from 02 Spec

| Finding | What spec-auditor said | Closed by | Closed |
|---|---|---|---|
| rollback | The rollback plan has no trigger threshold. | rollback | yes |
| eval-plan | The eval plan has no time it runs. | evals | yes |

## Next step

Ship, and close each waived check before its waiver runs out (the first on 2026-09-19). After launch, did-it-land reads quote draft acceptance rate against the 40% bar set for 2026-11-15. Decides: Head of Product, Quoting squad.

## Notes

- Check 'visual-diff' is failure but not required, so it does not hold the release (ci.csv row 7).
- Policy changed from the default: open major bugs allowed: 1 (default 3)
- Policy changed from the default: max initial rollout percent: 25 (default 100)

## Evidence ledger

| ID | Figure | Value | Window | Source |
|---|---|---|---|---|
| ci.required | Required checks | 5 checks | 2026-09-05 | examples/acme/inputs/ci.csv |
| ci.passed | Required checks passing | 5 checks | 2026-09-05 | examples/acme/inputs/ci.csv |
| bugs.open.blocker | Open blocker bugs | 0 bugs | 2026-09-05 | examples/acme/inputs/bugs.csv |
| bugs.open.critical | Open critical bugs | 0 bugs | 2026-09-05 | examples/acme/inputs/bugs.csv |
| bugs.open.major | Open major bugs | 2 bugs | 2026-09-05 | examples/acme/inputs/bugs.csv |
| bugs.open.minor | Open minor bugs | 1 bug | 2026-09-05 | examples/acme/inputs/bugs.csv |
| bugs.open.trivial | Open trivial bugs | 0 bugs | 2026-09-05 | examples/acme/inputs/bugs.csv |
| bugs.open.untriaged | Open untriaged bugs | 0 bugs | 2026-09-05 | examples/acme/inputs/bugs.csv |
| flags.total | Flags in this release | 1 flag | 2026-09-05 | examples/acme/inputs/flags.csv |
| flags.off\_switch | Flags with an off switch | 1 flag | 2026-09-05 | examples/acme/inputs/flags.csv |
| flags.top\_rollout | Largest starting rollout | 10% | 2026-09-05 | examples/acme/inputs/flags.csv |
| rollback.test\_age\_days | Days since the rollback was rehearsed | 8 days | 2026-08-28 to 2026-09-05 | examples/acme/inputs/release.json |
| brief.days\_to\_date | Days from this check to the brief's date | 71 days | 2026-09-05 to 2026-11-15 | examples/acme/briefs/quote-drafting.md |
| evals.1.cases | quote-text-accurate: cases run | 200 cases | 2026-09-04 | examples/acme/inputs/evals.csv |
| evals.1.passed | quote-text-accurate: cases passed | 186 cases | 2026-09-04 | examples/acme/inputs/evals.csv |
| evals.1.needed | quote-text-accurate: cases its 90% threshold needs | 180 cases | 2026-09-04 | examples/acme/inputs/evals.csv |
| evals.2.cases | no-invented-prices: cases run | 150 cases | 2026-09-04 | examples/acme/inputs/evals.csv |
| evals.2.passed | no-invented-prices: cases passed | 150 cases | 2026-09-04 | examples/acme/inputs/evals.csv |
| evals.2.needed | no-invented-prices: cases its 100% threshold needs | 150 cases | 2026-09-04 | examples/acme/inputs/evals.csv |
| evals.total | Evals in the gate | 2 evals | 2026-09-05 | examples/acme/inputs/evals.csv |
| evals.passing | Evals passing the gate | 2 evals | 2026-09-05 | examples/acme/inputs/evals.csv |
| spec.holds | Holds spec-auditor raised | 2 findings | 2026-08-03 to 2026-09-05 | examples/acme/landing/quote-drafting.json, spec key (spec-auditor 0.3.1, 2026-08-03) |
| spec.closed | Spec holds closed by a ready check | 2 findings | 2026-08-03 to 2026-09-05 | examples/acme/landing/quote-drafting.json, spec key (spec-auditor 0.3.1, 2026-08-03) |

Computed by release-readiness 0.3.0. Every figure comes from the source named beside it.
