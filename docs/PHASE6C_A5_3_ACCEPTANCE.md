# Phase 6C-A5/3a — acceptance and scope

## 1. Baseline
Uploaded A5/2 server gate: 3 native, 29 finite, 88 label, 131 mathematical, 495 full pytest; static declared model only. All three real-world completeness flags false. Uploaded logged labels: WOMD 20+20 scenes from the first shard of each split, AV2 both skipped (PyArrow/pandas engine compatibility or availability); 71,086 joint valid knots, 46 auxiliary signal-change brackets (9 scenes). No occupancy/proof labels generated.

## 2. Objectives and modifications
- E1: exact endpoint public helper replays native witness before reading field. No change to C++ numerical kernel or rational enclosure theorem.
- E2: absolute-time, time-unrolled protocol + independently bound root/model/goal/schedule, entire candidate mission graph, exact worst completion, complete declared posterior union at every public node. Reject unknown modes/monitors/messages/guards rather than invent a transition.
- E3: fixed external permission schedule, half-open epochs, restrictive meet on *closed* physical step, including a switch at the endpoint. Opposite directions have no common approved direction. This may reject feasible crossing; it never establishes exact time-dependent feasibility by this check alone.
- E4: align factual sample timestamps; read AV2 via PyArrow directly, preserve integer nanoseconds; deterministic spread across selected WOMD shards; separate joint-aligned size counts and total target sizes; raw input fingerprints, overlap comparability and environment metadata. Smoke only, not full dedup or occupancy production.
- Reference work-zone and traffic-actuated alternating access controllers: external request/physical deployment/issue/receipt separate; known detector counts, hysteresis, min/max timing, drain and sampled empty interval; reopen after explicit removal acknowledgment. No continuous-clearance proof and no real simulator commands yet.
- Waymax v1.3.1 TFExample probe (one logged state + one log playback step; optional image). Not a counterfactual rollout. Never mix Scenario and TFExample as independent training samples.

## 3. Actual local tests
29 finite/time/CTest discovery tests passed; 112 dependency-free label/protocol/schedule/controller tests passed (overlapping with full suites); 13 SC discrete carrier tests passed. Native new mission cases include two depths/early acceptance, resource closure far/near, switch exactly at boundary, reverse permission, root/posterior/depth tamper, digest tamper, exact endpoint witness tamper. These must run on the server with MPFR/GMP dev installed. Local environment lacks native development headers; no full new gate pass claimed. Real Waymax/data/CARLA/SUMO not run here. See gate logs for actual outcomes, not expected results.

## 4. Restrictions / remaining work
Ego-only dynamically scheduled but spatially static resource boxes, fixed external schedule, no uncertain/branch-dependent schedule or moving actor envelope, no full information derivation, no messages/local-awareness semantics, no within-step segmented dynamic propagation, no general online SC rank/remaining-budget integration. Entire declared mission must be supplied; acceptance is not real-world full-support certification. Controller samples do not certify between-tick emptiness or physical barriers. Not all eight teacher heads implemented. Model completeness outside declared world remains false.

## 5. Server gate
`python scripts/verify_release.py`; `bash scripts/validate_phase6c_a5_3.sh`. Success `A5_3_SCOPED_GATE_PASS` only if native 3 tests, every mandatory suite and full regression with >=495 tests all pass without skips. Run independent label smoke and Waymax probe per README. Return report folders, label JSON and probe JSON/optional plot. No CARLA/SUMO required this round.
