# Phase 2 acceptance record

## Current delivery status

Implemented locally. The finite abstract information-state fixed-point tests
and the full Phase 1A-1D regression suite pass in the local bootstrap build.
Target-server acceptance using the user's official MPFR 4.0.2 development
headers is pending. Phase 2 uses Python orchestration and the already-validated
Phase 1D MPFR interval backend; no new C++ ABI is introduced.

## Implemented

- Explicit rear-axle-centre reference convention and a nominal CommonRoad BMW
  320i benchmark profile; friction is left unset until scenario calibration.
- Joint `SupportAtom` representation: six-dimensional ego box, optional other
  continuous boxes, and discrete protocol/resource/monitor/agent modes.
- `BeliefCell` as one complete information-state support (union of atoms),
  never as one hidden state.
- `ActionWitness` with one common `(jerk, steering_rate)` action and exactly
  one transition record per source atom.
- Per-atom evidence verdict and required external evidence replay callback.
- Observation posterior aggregation across every source atom compatible with
  the same observation label.
- Conservative posterior coverage by one retained belief cell.
- Safe initial cell filtering, robust predecessor, simultaneous greatest
  fixed-point elimination, deterministic witnesses, and finite termination.
- Support-box bisection that preserves the same policy node and invalidates
  stale transition evidence.
- Versioned JSON fixed-point candidate certificate and deterministic replay.
- Finite abstract game demo and scaling microbenchmark.

## Local test results

| Test | Result |
|---|---:|
| C++ CTest | 3/3 passed |
| Python pytest (all phases) | 129 passed, 0 failed, 0 skipped |
| Phase 2 finite game demo | retained A,L; fixed point converged; replay passed |
| Phase 2 benchmark | 50, 100, 250, 500, 1,000, 2,000 cells; all exact finite fixtures converged |
| ASan + UBSan | see target-server validation (native code unchanged from Phase 1D) |

The local AddressSanitizer + UndefinedBehaviorSanitizer build also passed all
3 native tests. The local build uses a temporary declaration-only MPFR header with the real
runtime because the local container lacks the official development header.
This is not target-server acceptance. The target server must rebuild against
its official MPFR 4.0.2 headers as in Phase 1D.

## Assurance boundary

The output is `S_in_candidate` with `assurance_scope=FINITE_ABSTRACTION_ONLY`
and `certified=false`. This is deliberate. The finite algorithm is exact for
the supplied abstract transition game, but the evidence verifier and the
concrete abstraction-coverage argument must be integrated with the full
protocol/tube/resource verifier in Phase 4 before the paper's concrete
conditional-safety theorem can be invoked.

The demo evidence verifier is a deterministic in-memory fixture. It tests the
algorithm contract only and is not a physical safety proof. A production
verifier must replay evidence references against validated continuous-time
tubes, protocol branches, resource monitors, and complete observation support.

## Known conservative limitations

- Posterior box coverage currently requires each successor box to fit inside
  one target atom box with the same discrete mode. A box covered only by the
  union of multiple partial target boxes is unresolved and should be refined.
- The finite solver consumes candidate common actions; it does not synthesize
  continuous feedback gains. That is Phase 3.
- The evidence callback must establish complete branch coverage and hard
  safety over the whole source support, not just endpoint membership.
- The abstraction builder and sound observation-cell construction are not yet
  connected to AV2/WOMD or simulator protocols.

## Target-server acceptance gates

1. Official MPFR headers/runtime detected; use the existing Python 3.10,
   GCC 9.4, CMake/CTest 3.18, MPFR 4.0.2 environment.
2. Three native CTest cases discovered and passed.
3. All Python tests pass with zero skips/errors/failures.
4. Phase 1B Picard witness replay, Phase 1C adaptive-width regression, and
   Phase 1D separation witness replay all pass.
5. Phase 2 demo retains exactly `A` and `L`, and candidate certificate replay
   succeeds with the same evidence verifier.
6. Tampered result or `certified=true` claim is rejected.
7. Finite-game benchmark sizes 50/100/250/500 all converge and retain all
   self-invariant fixture cells.
8. Summary explicitly says `concrete_safety_certified=false`.

## Simulator and dataset requirements

None for Phase 2. No AV2, WOMD, SUMO, CARLA, GPU, or headless simulator
process is required. The phase is an abstract fixed-point algorithm test.
