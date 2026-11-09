# Phase 1D target-server acceptance

The target server's Phase 1C report recorded Python 3.10.20, GCC 9.4.0,
CMake/CTest 3.18.0, and official MPFR header/runtime 4.0.2. Those versions
are sufficient for this release; the new `mpfr_sqrt` symbol is part of MPFR
and does not require an upgrade.

Upload `RAMP-D_Phase1D.zip`, unpack it as `/home/senzeyu2/code/RAMP-D`, and
activate the existing Python 3.10 environment. Then run:

```bash
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase1d.sh
python scripts/package_report.py
```

Do not reuse the Phase 1C build directory or library. This release uses ABI 3
and builds into `build_phase1d/`. If `/usr/include/mpfr.h` is missing, install
the official package:

```bash
sudo apt-get update
sudo apt-get install -y libmpfr-dev libgmp-dev
```

No Python package upgrade should be needed if the existing test dependencies
remain installed. The project requires Python >=3.10, pytest >=7,<10, and
mpmath >=1.2,<1.4 as recorded in `requirements-test.txt`.

A valid target summary must state `LOCAL_ACCEPTANCE_PASS`,
`official_mpfr_headers_used=true`, 3 native tests, at least 109 Python tests,
zero skips/failures/errors, Phase 1C benchmark regression success, Phase 1D
oriented-axis separation plus witness replay, and zero footprint-audit misses.
The package report is `reports/RAMP-D_Phase1D_server_report.zip`.
