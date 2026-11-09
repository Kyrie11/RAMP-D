# Server deployment and acceptance

Upload RAMP-D_Phase1B.zip to /home/senzeyu2/code/ first. Preserve the old project:

```bash
cd /home/senzeyu2/code
cp -a RAMP-D "RAMP-D_Phase1A_backup_$(date +%Y%m%d_%H%M%S)"
unzip -o RAMP-D_Phase1B.zip -d RAMP-D
cd RAMP-D
```

This is a full source release. The new build tree is build_phase1b/; the old
build/ can remain for diagnosis but must not be loaded by the new wrapper.

Install dependencies on Ubuntu/Debian (or use an equivalent user prefix):

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake libmpfr-dev libgmp-dev
python --version
python -m pip install -r requirements-test.txt
```

Run in the intended active Python 3.10 environment:

```bash
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase1b.sh
python scripts/package_report.py
```

Upload reports/RAMP-D_Phase1B_server_report.zip in the next conversation.
The report packager works for failed runs too. On failure, do not remove failing
tests, change tolerances or convert UNKNOWN to success; return the full logs.

Expected official-header run summary:

```text
3 / 3 native CTest cases pass
71 passed (Python tests)
Demo: VALIDATED, exact_horizon_covered="1", witness_replay=true
Audit: 20480 state-vector checks, containment_misses=0
acceptance_summary.json: LOCAL_ACCEPTANCE_PASS
```

A failure before dependency discovery may have only a validation.log; return it.
A missing mpfr.h/libmpfr should be fixed by installing the official development
files, not by copying a guessed header or restoring the old Boost backend.

To manually retest the old Phase 1A CTest issue:

```bash
ctest --version
(cd build && ctest -N && ctest --output-on-failure)
```

This does not replace the NEW Phase 1B regression run.

## No simulation requirements in this phase

Do not start SUMO or CARLA. No AV2/WOMD directory is accessed. The user's headless
SUMO 1.20 / CARLA 0.9.16 arrangement is retained for a later simulator phase.

## Next development gate

After target acceptance, proceed to Phase 1C's quality/width-driven adaptive
refinement and conservatism measurement. The failure-only bisection already in
1B is a correctness fallback, not the completed adaptive accuracy module.
Then implement Phase 1D swept-footprint mapping before using tubes for collision
or resource predicates. Keep all current tests as mandatory regressions.
