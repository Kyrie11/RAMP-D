#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/phase5_$(date -u +%Y%m%dT%H%M%SZ)}"
PYTHON_BIN="${PYTHON_BIN:-python}"
mkdir -p "$REPORT_DIR"
export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"

REPORT_DIR="$REPORT_DIR/phase4_regression" PYTHON_BIN="$PYTHON_BIN" \
  bash "$ROOT/scripts/validate_phase4.sh" "$@"

"$PYTHON_BIN" -m pytest -q "$ROOT/tests/test_phase5_cegar.py" \
  --junitxml="$REPORT_DIR/phase5_pytest.xml" | tee "$REPORT_DIR/phase5_pytest.log"

"$PYTHON_BIN" - <<'PY' "$REPORT_DIR/phase5_examples.json"
import json, pathlib, sys
from fractions import Fraction as Q
from rampd_core.belief import SupportAtom
from rampd_core.cegar import (ContractVersion, EvidenceRegistry, QueueItem,
    ResumableVerificationQueue, classify_counterexample, split_time_window)
from rampd_core.full_verifier import BranchCheck, VerifyStatus
from rampd_core.interval import Interval
from rampd_core.model import StateBounds
from rampd_core.protocol import TimeWindow

atom = SupportAtom("a", StateBounds(Interval(0, 2), *(Interval(0, 0) for _ in range(5))))
branch = BranchCheck(VerifyStatus.COUNTEREXAMPLE, "abstract", (atom,), {"replayable": True})
concrete = classify_counterexample("task", "transition", "action", branch, lambda *args: True)
spurious = classify_counterexample("task", "transition", "action", branch, lambda *args: False)
left, right = split_time_window(TimeWindow(Q(1), Q(3)))
registry = EvidenceRegistry(ContractVersion("c", "p", resource_digest="r1"))
ref = registry.register({"source": "a"})
invalidated = registry.synchronize(ContractVersion("c", "p", resource_digest="r2"))
queue = ResumableVerificationQueue("c", generation=1)
queue.push(QueueItem("root", {"state": "start"}))
out = {"status": "PHASE5_EXAMPLES_PASS",
       "counterexample": {"concrete": concrete.kind.value, "spurious": spurious.kind.value},
       "time_split": {"left": [str(left.lo), str(left.hi)], "right": [str(right.lo), str(right.hi)]},
       "evidence_invalidated": invalidated,
       "evidence_valid_after_digest_change": registry.valid(ref),
       "queue_checkpoint_bound": queue.checkpoint()["contract_digest"] == "c",
       "full_support_certified": False, "current_scene_verified": False,
       "real_datasets_used": False, "simulators_used": False}
pathlib.Path(sys.argv[1]).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
PY

"$PYTHON_BIN" - <<'PY' "$REPORT_DIR/phase5_acceptance_summary.json"
from pathlib import Path
import json, sys, xml.etree.ElementTree as ET
p = Path(sys.argv[1]).parent
root = ET.parse(p / "phase5_pytest.xml").getroot()
cases = list(root.iter("testcase"))
counts = {"tests": len(cases), "errors": sum(c.find("error") is not None for c in cases),
          "failures": sum(c.find("failure") is not None for c in cases),
          "skipped": sum(c.find("skipped") is not None for c in cases)}
examples = json.loads((p / "phase5_examples.json").read_text())
if counts["tests"] < 20 or any(counts[x] for x in ("errors", "failures", "skipped")):
    raise SystemExit("incomplete Phase 5 test gate: " + str(counts))
if examples.get("status") != "PHASE5_EXAMPLES_PASS" or examples.get("evidence_valid_after_digest_change"):
    raise SystemExit("invalid Phase 5 example gate")
summary = {"status": "PHASE5_LOCAL_PASS", "phase": "5", "python": counts,
           "three_valued_semantics_retained": True, "concrete_spurious_split": True,
           "event_time_refinement": True, "support_cell_refinement": True,
           "observation_nonanticipativity": True, "master_problem_revision": True,
           "evidence_digest_invalidation": True, "resumable_queue_checkpoint": True,
           "assurance_scope": "PHASE5_CEGAR_EXPLICIT_PROTOCOL_SUPPORT",
           "full_support_certified": False, "concrete_safety_certified": False,
           "current_scene_verified": False, "real_datasets_used": False,
           "simulators_used": False, "phase6_data_required": False}
Path(sys.argv[1]).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY
"$PYTHON_BIN" "$ROOT/scripts/package_report_phase5.py" --report "$REPORT_DIR" \
  --output "$ROOT/reports/RAMP-D_Phase5_server_report.zip"
echo "PHASE5_LOCAL_PASS report=$REPORT_DIR"
