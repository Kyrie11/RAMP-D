# A57 server run and next gates

Unpack in a new empty checkout; do not overwrite previous reports or modify the manifest. Use installed `mfrp`, no CARLA process required. SUMO probe starts its own headless process. Each run needs fresh work directory.

```bash
conda activate mfrp
python scripts/verify_release.py
bash scripts/validate_phase6c_a5_3b7.sh
export RAMPD_INTERVAL_LIB="$PWD/build_phase6c_a5_3b7/librampd_interval.so"
mkdir -p reports/a57
WOMD=/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/tf_example/validation/validation_tfexample.tfrecord-00000-of-00150
for n in 30 60 120; do
  python scripts/probe_waymax_response.py --tf-example-file "$WOMD" --profile smooth-stop --steps 60 --lookahead-points "$n" --output "reports/a57/waymax_${n}.json" --plot "reports/a57/waymax_${n}.png" || echo "REVIEW Waymax $n"
done
python scripts/probe_waymax_response.py --tf-example-file "$WOMD" --profile smooth-stop --steps 60 --lookahead-points 120 --ego-length 6 --follower-length 4.5 --initial-offset 15.75 --output reports/a57/waymax_size.json || echo 'REVIEW Waymax size'
python scripts/probe_sumo_alternating.py --work reports/a57/sumo_base --steps 6000 --seed 17 --require-drain --output reports/a57/sumo_base.json --plot reports/a57/sumo_base.png
python scripts/probe_sumo_alternating.py --work reports/a57/sumo_old --steps 6000 --seed 17 --comfort-guard --max-green-extension-s 20 --require-drain --require-comfort --output reports/a57/sumo_old.json --plot reports/a57/sumo_old.png || echo 'REVIEW old comfort'
python scripts/probe_sumo_alternating.py --work reports/a57/sumo_reserve --steps 6000 --seed 17 --stop-reserve-guard --max-green-extension-s 20 --require-drain --require-comfort --output reports/a57/sumo_reserve.json --plot reports/a57/sumo_reserve.png || echo 'REVIEW reserve'
python scripts/audit_a57_runtime.py --waymax reports/a57/waymax_30.json --sumo-control reports/a57/sumo_base.json --control-work reports/a57/sumo_base --sumo-comfort reports/a57/sumo_reserve.json --comfort-work reports/a57/sumo_reserve --output reports/a57/independent_runtime.json || echo 'REVIEW independent audit'
```

Do not continue after native gate failure. Keep all REVIEW/ERROR artifacts. Inspect source-based instrumentation outputs (private API may vary). If A/A or raw speed update fails, stop before behavior inference. Resolution sweep and size variation are diagnostic, not a monotonic improvement theorem. For every sample inspect internal raw acceleration, geometry gap, lead speed; assert no artificial clipping used as a fix. Compare queue/throughput and exhaustion for stop-reserve vs old guard; require zero sampled excessive braking for strict fixture acceptance, no new opposing occupancy or red entry, 70/70 complete. If extension exhausted, do not increase blindly; design stop/go and downstream clearance separately.

For raw CSV and annotations, substitute actual path (not assumed):
```bash
python scripts/audit_a57_511ny.py --csv /path/to/511NY_Events.csv --output reports/a57/511ny_quality.json
python scripts/audit_a57_roadwork.py --annotations /path/to/annotations.zip --output reports/a57/roadwork.json --work reports/a57/roadwork_aux
```
ROADWork annotation audit already executed locally; optional server reproduction. No need upload full CSV or full video. Return report ZIP, simulator JSONs with raw traces/logs, and new 511 quality report; group manifest can remain on server (sample few JSONL records).

M1 native MPFR preserve; M2 exact time and event split improved only; M3 nominal reference/control and frame tests, cross-simulator pending; M4 declared envelope Post, coverage/injection pending; M5 rectangular SAT/exit diagnostic, arbitrary geometry and topology pending; M6 guard support generation, full capacity/rule verification pending; M7 barrier latch declared, real registry pending; M8 explicit guard & public labels, full protocol relation pending; M9 actual observations pending; M10 SC and task-tail integration pending; M11 independent teacher pending; M12 numerical and logical runtime evidence, model behavior and co-sim pending; M13 schema and source audit, full production pending. No promotion to unconditional PASS.

Next sequence: (1) finish native A57 and run behavior/comfort regressions, fix failures; (2) A57 continuation: native Post -> actual dynamic protocol/message observation relation + general exit/topology/SC, prove support coverage; (3) A5/3c-1 synchronized CARLA/SUMO physical geometry, identity, coordinates, control ownership; (4) A5/3c-2 actual barrier deployment/removal with acknowledgement, persistent fault state, safe recovery; (5) A5/3c-3 four reactive incidents and observation timing; (6) A5/4 real task SC/tail/teachers; (7) production paired supervision and training then ICAPS ablations. National Highways optional, no new large downloads required.
