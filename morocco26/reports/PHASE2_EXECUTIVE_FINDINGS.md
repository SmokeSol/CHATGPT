# MOROCCO//26 — Phase-2 executive findings

**Run status:** frozen mechanism experiment, not a 2026 forecast  
**Protocol:** `M26-PHASE2-ABC-D-001` v1.1.1  
**Protocol hash:** `0b519444cd6edacae29c8c777ecc14de0b948276c6217054cafdc1e74f131421`  
**Run-ledger hash:** `d826930154db1fd7eb805c81bfb5f3d7e53e24704efde7e958618adf6f8678b2`

## Decision

**PASS_TO_BOUNDED_D_PILOT.** All 15 blocking gates pass. The national 2026 forecast remains blocked until the full 92-local and 12-regional replay and holdout benchmark exist.

## What was executed

- Four real 2021 constituency anchors and 14 seats.
- 2,880 weighted synthetic elector cells.
- Seven arms and 96 universes per arm/applicable constituency.
- Models A, B, C0 and C executed; D prepared but not executed.
- 4,624 run-ledger rows and 1,536 paired C/C0 seed cells.

## Scientific results

| Test | Result | Interpretation |
|---|---:|---|
| 2021 seat replay | 14/14 | pilot allocator anchor reproduced |
| baseline turnout error | 0.0000 pp | exact aggregate calibration |
| party-share calibration RMSE | 0.019582 pp | below 0.20 pp gate |
| null C−C0 drift | 0.0000 pp | common-random-number ablation valid |
| current-prior network reach | 1.334347× | propagation is detectable |
| current-prior dose monotonicity | 0.849252 | mechanism responds to dose |
| current-prior materiality | **0.011352 pp** | below 0.05 pp threshold; non-material |
| positive-control reach | 3.904684× | causal plumbing activates |
| positive-control materiality | 0.305580 pp | detectable only under deliberate stress |
| maximum turnout MCSE | 0.043323 pp | numerical precision passes |
| maximum split-half drift | 0.222302 pp | convergence passes |

## Most important learning

A plausible story about candidate networks or social propagation is not enough to infer a seat effect. Under the bounded current assumptions, social diffusion increases exposure but adds almost nothing to aggregate vote shares beyond the same direct intervention applied without a network.

The post-pilot power envelope tests 27 regimes. Only one crosses 0.05 percentage point, none reaches a 10-point change in seat probability, and the maximum mean target-party increment is 0.052043 point. The correct next action is to estimate real diffusion and network-portability parameters, not to tune the simulation until it produces dramatic seat changes.

## Political use during the campaign

MOROCCO//26 can already distinguish three statements:

1. an event is politically salient;
2. an event reaches additional people through networks;
3. that additional reach is large enough to alter a local cutoff.

The frozen pilot supports statement 2 for the tested mechanisms but not statement 3 under current priors.

## Next gate

Run Model D as bounded aggregate cognition delegates, test schema compliance and prompt/model stability, then score it against B and C on a frozen holdout. In parallel, complete the 92-circumscription Seat Margin Map and candidate/network evidence graph. Model D is killed if it does not add measurable value.
