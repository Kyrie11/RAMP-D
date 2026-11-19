# A5/3b-6 acceptance and next gate

## Goal and source baseline
A55 uploaded archive and identical manuscript. A55 server: 625 Python, 3 CTest, 159 math, 190 adapter/protocol, 29 finite; scoped only. No manuscript changes. Do not train on new simulation labels yet.

## Changes
- `a56_guard`: exact grid, finite declared joint detector/clearance/observation cases. Preserve correlations and the controller memory; classify MUST/MAY/NEVER phase change; group by public observation; fail closed on budget exhaustion or unsupported controller transition. Does not generate complete physical Post or enforce SC on all physical successors. `a54_signal`: optional explicit bounded green extension; no forced uncomfortable switch on exhaustion.
- `a56_motion`: exact rational straight constant-jerk reference; reject negative speed at interior extrema; smooth 1/3/1 s brake from 10 m/s to rest (25 m); rigid reference-point transform, net-gap IDM reference and flat no-slip friction diagnostic. Numerical references, not certificates. Waymax smooth-stop probe uses the exact path sampled as ego state actions; does not change official follower policy or Waymax source. Route sampling and yaw limitations remain.
- SUMO probe: explicit semi-implicit Euler, roster events, deceleration and drain checks, independent experiment switches for comfort and detector range. Stop feasibility is an experimental sufficient screen for upstream fronts, not a hardware guarantee; still separate logical directional lanes. Unresolved green extension -> REVIEW, no silent forced switch.
- ROADWork raw visual semantics: annotation SHA binding to prior alignment, separate train/val, raw tags/attributes and missingness preserved, inferred video hash overlap (not complete grouping), train-only empirical image composition; no legal, event, metric labels. Work directory must be empty.
- 511 summary: exclusive duration bins, count conservation and interval quantiles. Report lifecycle only, not TIM; no sampling or unique incident claims. Timeline `normal_flow` now T7-T0, explicit occurrence and unknown when missing; RCT/ICT unchanged.

## Actual old runtime re-audit
Waymax 2.5 s, AA zero, ego delta 9.3750038 m, follower speed delta 3.6103363 m/s, first follower equal, min gap 7.9320679 m, max trapezoid residual 1.66893e-6 m. Official IDM acceleration approx -3.312616 m/s2 vs independently calculated net-gap -3.778391. 1 m route sampling is a plausible discrepancy mechanism (not measured internal distance in installed runtime). No real WOMD intervention or curved follower verification.
SUMO 1800 ticks / 20 switches replayed, 27 entries (15/12), 26 rear clears (14/12), no opposing occupancy or red entry. 69 inserted, 48 remain; one pending implied by input/log, one current resource occupant. Four emergency braking warnings (8 m/s2), 16 sampled excessive decel intervals; comfort and drain not passed. Roster inferred from old trace, not independent proof of completeness. No physical single-lane certificate.
ROADWork inventory: 7416 images, 82018 raw, 82017 usable bounding boxes, 1 degenerate. 12 sampled image/mask decodes only; no vocabulary/mask semantics verified. New extraction tested on fixtures only.
511NY: 3074794 rows, road proxy 1222863; negative report lifetime 123315/428681 planned-work rows. Exclude negatives, not absolute values; unknown close not necessarily censoring. Quantile brackets from full report. No source CSV available locally.

## Run order
```
python scripts/verify_release.py
bash scripts/validate_phase6c_a5_3b6.sh
export RAMPD_INTERVAL_LIB="$PWD/build_phase6c_a5_3b6/librampd_interval.so"
mkdir -p reports
```
Then run smooth-stop Waymax (60 steps), SUMO baseline vs comfort (6000 steps, identical seed/default range), raw semantics extraction. See accompanying roadmap. No CARLA start required. Keep REVIEW or ERROR reports and raw logs. Runtime success does not establish real-scene proof or causal truth.

## Local acceptance
- The exported archive was unpacked and integrity-checked: 290 published hashes / 189 source files.
- 29 finite tests passed; 199 independent adapter/protocol tests passed from an unpacked release (includes 9 new cases).
- Direct native CMake configure failed because the environment lacks official MPFR/GMP development files. No fallback or native pass was claimed. Full 634-or-more Python regression remains server-pending.
- Updated real Waymax and SUMO runtime, real ROADWork semantic extraction remain server-pending; 511 summary and old runtime re-audit actually executed against provided reports.
