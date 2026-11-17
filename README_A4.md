# Phase6C-A4 mathematical gate patch

Start with [A4 audit and runbook](docs/PHASE6C_A4_MATH_GATE_20261117.md) and [public supervision sources](docs/SUPERVISION_PUBLIC_DATASET_AUDIT_20261117.md). This is a fail-closed engineering patch retaining all existing Phase6C-A3/A2/data modules. A4 adds SC support/time inheritance binding, separate finite certificate checker, dependency-free finite game cross-check, targeted MPFR-dependent tests, and stricter Phase4 native CTest gating.

```bash
python scripts/verify_release.py
bash scripts/validate_phase6c_a4.sh
# after native math gate, and with pyarrow installed:
MAX_RECORDS=5 bash scripts/validate_phase6b.sh
MAX_RECORDS=5 bash scripts/validate_phase6c.sh
```

Do not claim `full_support_certified=True`: the physical/protocol/terminal replay providers for realistic scenarios have not been integrated. Keep a clean unpack directory; never delete an existing source tree just to make the integrity manifest pass.
