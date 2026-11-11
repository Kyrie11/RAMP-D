# Phase 3 acceptance record

The acceptance command is:

```bash
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase3.sh
```

The command runs the Phase 1A–1D regression and Phase 2 finite invariant
acceptance first, then builds the deterministic `A -> L`, `L -> L` public
backup graph fixture, saves and replays its JSON graph, and writes a packaged
report under `reports/RAMP-D_Phase3_server_report.zip`.

Required Phase 3 fields in `acceptance_summary.json` are:

- `public_backup_graph_built=true`;
- `public_backup_graph_status="BACKUP_GRAPH_SYNTHESIZED"`;
- `executable_nodes=2` for the fixture;
- `all_children_retained=true`;
- `common_control_violations=0`;
- `certificate_replay=true`;
- `concrete_safety_certified=false`;
- `manuscript_dependencies=false`;
- `requires_dataset=false`, `requires_sumo=false`, and `requires_carla=false`.

The report must describe tube execution as absent or dynamics-only. It must
not call the graph a full RAMP-D `CERTIFIED` result.
