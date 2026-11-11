# Phase 2 target-server acceptance

The user's previously accepted server environment is Python 3.10.20, GCC
9.4.0, CMake/CTest 3.18.0, and official MPFR header/runtime 4.0.2. These
versions are sufficient for Phase 2; no new C++ ABI or MPFR symbol is added.

Upload `RAMP-D_Phase2.zip`, unpack it as `/home/senzeyu2/code/RAMP-D`, and
activate the existing Python 3.10 environment. Then run:

```bash
python -m pip install -r requirements-test.txt
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase2.sh
```

Do not reuse a Phase 1C or stale Phase 1D build directory. The script uses a
clean `build_phase1d/` and checks that all three CTest tests are discovered.
If `/usr/include/mpfr.h` is missing, install the official package:

```bash
sudo apt-get update
sudo apt-get install -y libmpfr-dev libgmp-dev
```

No SUMO/CARLA process, dataset, GPU, or additional Python ML package is
required for Phase 2.

For the optional native sanitizer run:

```bash
cmake -S . -B build_phase2_sanitize \
  -DCMAKE_BUILD_TYPE=Debug -DRAMPD_BUILD_TESTS=ON -DRAMPD_SANITIZE=ON
cmake --build build_phase2_sanitize --parallel 2
(cd build_phase2_sanitize && ctest --output-on-failure)
```

A valid target summary must state `LOCAL_ACCEPTANCE_PASS`,
`official_mpfr_headers_used=true`, 3 native tests, 129 Python tests, zero
skips/failures/errors, Phase 1B/1C/1D regression success, Phase 2 finite game
fixed-point convergence, and candidate-certificate replay success. It must
also explicitly state:

```json
{
  "phase2_assurance_scope": "FINITE_ABSTRACTION_ONLY",
  "concrete_safety_certified": false
}
```

The report package is `reports/RAMP-D_Phase2_server_report.zip`. The Phase 2
demo uses a synthetic finite-game evidence verifier; it is not a physical
safety proof. Production evidence replay must be integrated in Phase 4.
