# Remaining research gates (RAMP-D)

M1 native arithmetic: preserve original strict MPFR gate. M2 time and dynamic event ordering: exact Fraction endpoint state. M3 ego model: rear/center transform and jerk control, stop, friction, curvature; cross-simulator error budgets. M4 full actor support: physically validated envelopes, participant injection and deletion. M5 geometry: continuous SAT, general resource and exit guards, interval subdivision. M6 permissions and capacity: correlated occupancy, entry/stay/exit. M7 authority: guard/controller versions, actual barrier registry, intrusion and command acknowledgment. M8 hidden protocol and messages: full joint guard physical Post with endpoint causality, non-FIFO/drop/visibility support. M9 observations: actual public sensor/queue history, no hidden-ID split. M10 online SC and tail policy: public common control, terminal proof. M11 independent viability, margin, deadline teacher: UNKNOWN masked. M12 simulator behavior: Waymax IDM forward and route audits, SUMO comfort/drain, then CARLA/SUMO physics; MOBIL and learned joint response later. M13 supervision: provenance, splits, frame, clocks, action IDs, masks and certificates.

## Sequence
1. A56 server gate and new runtime tests; inspect any failure before expansion. No training labels.
2. Joint physical Post and dynamic guard integrated with mission (finite reachable relation, then intervals, adaptive subdivision), full message/observation support, exit guard. Close SUMO comfort and drain separately.
3. CARLA/SUMO first physical single-lane control and planned closure; validate mapping, owner/tick, geometry and barrier acknowledgments. Then breakdown and other incident types; TIM clocks independent of communication and authority.
4. Real scene online SC/terminal tail and independent teacher.
5. Waymax WOMD paired response, SUMO lane changes/MOBIL, WOSAC and learning-based response only after usable baseline; eight supervision production with independent audit.
6. REA/RuleNet training and ICAPS evaluation.

## Data
511NY report create/close do not identify physical duration or TIM stages. Use quality-filtered report-row distributions for a separate reporting mechanism; actual scenario times generated and recorded. National Highways latest April 2014 carriageway-impact CSV + definitions optional, older snapshots likely overlapping; verify actual period. ROADWork provides visual objects/attributes and scene cues; validate official vocabulary and group split before training; no pixel-to-metre or authority time assumption. No new large dataset needed.

## Commands
```
python scripts/probe_waymax_response.py --tf-example-file /data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/tf_example/validation/validation_tfexample.tfrecord-00000-of-00150 --profile smooth-stop --steps 60 --output reports/a56_waymax_smooth.json --plot reports/a56_waymax_smooth.png
python scripts/probe_sumo_alternating.py --work reports/sumo_a56_control --steps 6000 --seed 17 --require-drain --output reports/a56_sumo_control.json --plot reports/a56_sumo_control.png
python scripts/probe_sumo_alternating.py --work reports/sumo_a56_comfort --steps 6000 --seed 17 --comfort-guard --max-green-extension-s 20 --require-drain --require-comfort --output reports/a56_sumo_comfort.json --plot reports/a56_sumo_comfort.png
python scripts/extract_roadwork_semantics.py --root /data0/senzeyu2/dataset/ROADWork --alignment reports/a55_roadwork.json --work reports/roadwork_a56_semantics --output reports/a56_roadwork_semantics.json
```
Use old A55 alignment JSON or regenerate it with `audit_roadwork.py` if missing. Keep the report and small JSONL sample; not full visual dataset. `audit_a55_runtime.py` intentionally only accepts baseline constant-control A55 inputs, not new comfort/smooth profiles. The 511 histogram summary already generated from uploaded report; no raw CSV re-scan required.
