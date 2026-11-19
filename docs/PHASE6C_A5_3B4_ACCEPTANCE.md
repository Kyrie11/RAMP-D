# RAMP-D A5/3b-4 | 2026-11-18 | Release 0.9.9

## Scope and baseline
A5/3b-2 is the last server-accepted native baseline (566 Python tests, 3 CTests). The uploaded A5/3b-3 report contains only an ERROR summary and an empty release_integrity.log; no native or Python result. The uploaded source ZIP independently passes SHA256 integrity (262 files, 169 sources). Do not infer why the server failed without stderr. New gate captures stderr and failing stage; do not edit hashes or overwrite an old checkout to force acceptance. The paper snapshot is unchanged.

## Goals and implementation
- Fix extracted ROADWork directory reading (annotations/, images/, gtFine/) as well as ZIPs. GPS train/val metadata checks, all image/mask path existence, bounded image/mask dimension and scalar ID checks, contact sheet. Real archives not accessible here; synthetic fixtures only. No pixel accuracy claim.
- Exact finite persistent hidden history compiler (a54_message_mission.py): declared schedule and message worlds, exact grid, public arrival content/time, shared silence, immutable hidden histories, root meet and source-mode-conditioned physical rule schedules. A53Mission verifies a declared candidate task, not an inferred complete real-world model or general feedback planner. New native tests are mandatory.
- Generalize incumbent proof (a53b_occupancy.py): strict initial overlap via fixed material point; at fixed heading, rectangle configuration-space occupancy is a convex Minkowski polygon, monotone projections on its facet axes imply prefix occupancy. This is sufficient, not necessary. Strict initial interior proof retained; still no arbitrary rotating/curved polygon entry event solver.
- a54_signal.py: exact grid timing plan, green/yellow/red clearance, opposing entry inhibited, contiguous complete clearance plus red minimum; MUTCD 4A.03 / 4F.17 / 4O.02. Desired indications, not physical signal ACK. Engineering parameters required; no universal red time. No crash/failure flash mode or actual sensor/controller integration.
- a53b_interlock.py: immutable clearance duration per accepted request; no mid-lifecycle silent parameter change. Physical evidence still external, not certified by this state machine.
- a53b_incident.py: explicit serial or parallel dispatch profile, independent issue/publication/effective/receipt/local clocks, missing observations remain unknown. No fabricated status times or distributions.
- probe_waymax_dynamics.py: synthetic independent reference for official discrete acceleration/curvature update, float32 tolerance, arc comparison, zero-speed crossing flag. No local installed Waymax execution, no counterfactual labels. Current uploaded real log replay: 13 valid actors, 168→181 valid history knots, zero future knots, seven zero field max differences; this is copying, not dynamic integration accuracy.

## Executed tests before native build
- 166 isolated data/rule/protocol/finite compiler/data layout tests PASS (dependency-free runner; no native arithmetic substituted).
- 29 finite/time/release/CTest contract tests PASS; 13 separately executed SC discrete tests PASS. Groups overlap, no total by addition.
- Direct pytest on native-import modules failed collection because no native interval library in this environment. CMake requires MPFR/GMP development files; no official headers available. Native CTest, new native geometry/mission replay, and full regression not executed here. No substitute headers or skipped gate allowed.
- ROADWork extracted-tree synthetic fixtures compare archive metadata, missing mask rejected. Real server data pending. Waymax numerical runtime pending; WOSAC not executed. No CARLA/SUMO run.
- Gate floor is last accepted 566 full Python tests, plus mandatory named suites, no failures/skips, 3 CTests. Success is limited to declared models.

## Server commands (new empty directory)
```
python scripts/verify_release.py
bash scripts/validate_phase6c_a5_3b4.sh
python scripts/audit_roadwork.py --root /data0/senzeyu2/dataset/ROADWork --samples-per-split 6 --output reports/a5_3b4_roadwork.json --plot reports/a5_3b4_roadwork.png
python scripts/probe_waymax_dynamics.py --output reports/waymax_discrete_dynamics.json
```
A5_3B4_SCOPED_GATE_PASS is expected ONLY if original numeric and all new tests pass. The actual server report and error stage are authoritative. Keep 3b2 as accepted reference. No simulator startup yet.

## Unfinished guarantees
Physical response envelope coverage, arbitrary entry/stay/exit and moving polygon occupancy, exact guard/observation-conditioned support and dynamic messages, unknown/new actor coverage, real terminal SC mission, complete oracle supervision, counterfactual generation, all eight training losses and training remain incomplete. No true-world safety certification or full real-scene task claim.
