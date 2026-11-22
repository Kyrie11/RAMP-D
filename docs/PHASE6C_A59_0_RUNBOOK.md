# A59/0 server runbook — install separate, preserve A58 results

Use a fresh release checkout. Do not copy this archive *over* `/home/senzeyu2/code/RAMP-D` or rewrite its `MANIFEST.sha256`.

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A59_0
unzip -q RAMP-D_Phase6C_A59_0.zip -d /home/senzeyu2/code/RAMP-D_A59_0
cd /home/senzeyu2/code/RAMP-D_A59_0
python scripts/verify_release.py
bash scripts/validate_phase6c_a59_0.sh
```

This executes the existing A58 mathematical gates and **five new server native A59 tests**, plus the new pure tests; requires MPFR/GMP C++ dev files and Python 3.10. The expected full repository minimum is **695 tests**, CTest 3, A58 pure 19, native 6, A59 pure 11, native 5, no skips/errors. In this assistant environment the new native tests were written and syntax-checked but **not run**. Never ignore a native failure as a PASS. The summary must have status `CONDITIONAL_A59_BOUNDARY_TESTS_PASS` and all task/full-world flags false.

Reaudit the old uploaded A58 archive without running SUMO or installing the MPFR C++ backend:

```bash
python scripts/audit_a59_uploaded_a58.py --zip /path/to/a58.zip \
  --output reports/a59_0/forensic_uploaded_a58.json || true
```

The exit code **4 is expected** until the nine absent successful control summaries are repaired. The audit remains useful and records a scoped trace report for every run. To rerun missing profiles, use **new, empty** work and result paths; never overwrite the old 12 runs. For example:

```bash
mkdir -p reports/a59_resimulation
for profile in baseline dense slow_reaction lower_friction_proxy; do
  for seed in 17 23 41; do
    work="reports/a59_resimulation/${profile}_${seed}_work"
    out="reports/a59_resimulation/${profile}_${seed}.json"
    if [ -e "$work" ] || [ -e "$out" ]; then
      echo "REVIEW_EXISTING_PATH: $work $out"; continue
    fi
    python scripts/probe_sumo_alternating.py \
      --traffic-profile "$profile" --seed "$seed" --work "$work" \
      --steps 9000 --stop-reserve-guard --reaction-s 0.5 \
      --extra-stop-m 1.0 --max-green-extension-s 20 \
      --require-drain --require-comfort --output "$out" \
      || echo "REVIEW_SIMULATION: $profile $seed"
  done
done
```

Do **not** replace the `|| echo REVIEW` construct with a forced PASS. Scan `sumo.log` for actual warnings and use raw trace forensic replay before declaring any *scoped* audit accepted. New strict summary audit:

```bash
PYTHONPATH=python python - <<'PY'
from pathlib import Path
from rampd_core.a58_sumo_audit import audit_runs
for profile in ['baseline','dense','slow_reaction','lower_friction_proxy']:
    paths=[Path(f'reports/a59_resimulation/{profile}_{seed}.json') for seed in [17,23,41]]
    if not all(p.exists() for p in paths):
        print(profile,'REVIEW_MISSING_FILES');continue
    r=audit_runs(paths,expected_profile=profile,require_stop_reserve=True)
    print(profile,r['status'])
PY
```

Read-only CARLA metadata after a **target actor has actually been created in an isolated test town**:

```bash
python scripts/dump_a58_carla_vehicle_params.py \
  --host 127.0.0.1 --port 2000 --output reports/a59_0/carla_params.json
```

If `REVIEW_NO_VEHICLE_ACTOR` persists, create a Tesla Model 3 *only in an isolated CARLA test world* using your existing controlled actor-spawn workflow, then rerun with `--actor-id <real actor id>`. The probe never spawns, ticks or drives actors. Submit actor JSON and 5/10/15 m/s repeated action-response logs including command/actual time, road friction config, body pose, yaw rate, speed, accel, `max_steer_angle`, steering curve, wheel brake torque/radius/mass and bbox. Do not submit private account data or full video data for this stage. Never treat input blueprint geometry as measured brake capability.
