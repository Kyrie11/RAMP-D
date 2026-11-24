#!/usr/bin/env bash
# Twelve genuinely fresh logical SUMO trials; never reuse or erase A58 evidence.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:?specify a NEW, NONEXISTENT output directory}"
if [ -e "$OUT" ]; then echo "REFUSE_EXISTING_MATRIX_ROOT: $OUT" >&2; exit 4; fi
mkdir -p "$OUT" || exit 4
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
failed=0
for profile in baseline dense slow_reaction lower_friction_proxy; do
  for seed in 17 23 41; do
    key="sumo_${profile}_${seed}"
    echo "[A71/SUMO] $key"
    python "$ROOT/scripts/probe_sumo_alternating.py" \
       --traffic-profile "$profile" --seed "$seed" --steps 9000 \
       --work "$OUT/${key}.work" --output "$OUT/${key}.json" \
       --stop-reserve-guard --reaction-s 0.5 --extra-stop-m 1.0 \
       --max-green-extension-s 20 --require-drain --require-comfort \
       >"$OUT/${key}.console.log" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then failed=$((failed+1)); fi
    if [ -f "$OUT/${key}.work/signal_trace.jsonl" ] && [ -f "$OUT/${key}.json" ]; then
      python "$ROOT/scripts/a71_review_sumo_tls.py" \
        --summary "$OUT/${key}.json" \
        --trace "$OUT/${key}.work/signal_trace.jsonl" \
        --output "$OUT/${key}.signal_review.json" \
        >"$OUT/${key}.signal_console.log" 2>&1 || failed=$((failed+1))
    else
      echo "MISSING_SIGNAL_TRACE:$key" >> "$OUT/missing.log"
      failed=$((failed+1))
    fi
  done
done
python - "$OUT" "$failed" <<'PY'
import json,sys,pathlib
p=pathlib.Path(sys.argv[1]);bad=int(sys.argv[2]);
report={'schema':'rampd.a71.sumo_fresh_campaign.v1',
 'status':'DESCRIPTIVE_LOGICAL_SUMO_CAMPAIGN_READBACK_PASS' if bad==0 else 'REVIEW',
 'run_summaries':len(list(p.glob('sumo_*.json')))-len(list(p.glob('sumo_*.signal_review.json'))),
 'signal_audits':len(list(p.glob('sumo_*.signal_review.json'))),'failed_checks':bad,
 'physical_shared_lane_verified':False,'carla_sumo_live_cosim_verified':False,
 'traffic_guard_authority_verified':False,'full_sc_certified':False}
(p/'a71_campaign.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
PY
[ "$failed" -eq 0 ] || exit 4
