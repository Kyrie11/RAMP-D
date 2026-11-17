# A5 follow-on: eight supervision signals, intervention design and public data

The uploaded manuscript defines **eight** losses (`event`, `joint`, `occupancy`, `observation`, `viability`, `margin`, `deadline`, `causal`). The label mask is *not* a solver negative; unknown means not supervised.

| Signal | Source / immediate implementation contract | No-label / caveat |
|---|---|---|
| `L_joint` | Actual logged WOMD Scenario/AV2 Motion joint actor states, valid time masks, actual ego prefix; later reactive simulation for alternative prefixes | **No** real unseen-action trajectories. Proposed CV ADE/FDE is not the official challenge metric |
| `L_event` | Timestamped external activation/effectivity and controller-generated actuation/issue in SUMO/CARLA; WOMD signal states for auxiliary status | Motion snapshots lack authoritative rule issue/delivery/effectivity |
| `L_occupancy` | Box/vehicle geometry and resource *polygons*, full time intersection, resource monitor; fully typed missing-shape masking | AV2-MF does not publish dependable per-track physical dimensions; no hard geometry proof by fabricated class mean |
| `L_observation` | CARLA visibility+occlusion/sensor timestamps and SUMO publication/delivery; model right-censoring | Motion `observed` is history/validity split, **not** guaranteed awareness or message receipt |
| `L_viability` | Positive: replayed task-acceptance policy. Negative: complete finite contingent-game search relative to named finite class | CEGAR failed candidate and numerical UNKNOWN are **not** negative |
| `L_margin` | Verified Picard/swept separation + explicitly declared constraint-distance normalization; conservative lower bound | No nominal TTC or sampled closeness as certified margin |
| `L_deadline` | Complete timing/controller clock, option windows and schedule oracle under the **same** public prefix for `T_sep,+` and `D_defer` | Not mean network latency or stopping-time alone; unresolved sign remains UNKNOWN |
| `L_causal` | Fixed initial joint state/agent model/seed/protocol realization, paired `do(ego_prefix=A/B)` with reactive other agents; source domain indicator | These are **simulator counterfactuals**, not ground-truth real-world potential outcomes |

## Recommended public research protocols

1. **Waymo Open Sim Agents Challenge** (Montali et al., NeurIPS Datasets & Benchmarks 2023): benchmark generative *joint* future rollouts over WOMD logged history with realism features (kinematic, interaction, map). Standard example requests 32 joint rollouts over an 8-second horizon. Useful to learn and evaluate a reactive-agent *model*; it does not supply experimentally observed alternate-ego-action labels. Paper: https://waymo.com/research/the-waymo-open-sim-agents-challenge/ ; official tutorial: https://colab.research.google.com/github/waymo-research/waymo-open-dataset/blob/master/tutorial/tutorial_sim_agents.ipynb
2. **Waymax** (Gulino et al., NeurIPS 2023): use WOMD scenarios for closed-loop actor interventions; *log replay agents do not react* to modified ego trajectories, whereas IDM-based path-following agents can respond. Include log-replay as NONCAUSAL sanity control, not a causal training target. https://waymo.com/research/waymax/ and https://github.com/waymo-research/waymax
3. **TrafficSim: Learning to Simulate Realistic Multi-Agent Behaviors** (Suo et al., CVPR 2021): learned joint social behavior under closed-loop rollout and interaction consistency, supporting paired simulator evaluation as a scientifically conventional research design, but it is not a theorem of real causal identifiability. https://openaccess.thecvf.com/content/CVPR2021/html/Suo_TrafficSim_Learning_To_Simulate_Realistic_Multi-Agent_Behaviors_CVPR_2021_paper.html
4. **CARLA 0.9.16 + SUMO 1.20**: single synchronous tick owner, fixed delta, deterministic traffic-manager seed on each reset. Before use, check that the official Town04 network and mappings correspond to the launched CARLA map and that traffic simulator versions are compatible. https://carla.readthedocs.io/en/latest/adv_traffic_manager/ ; https://carla.readthedocs.io/en/0.9.12/adv_sumo/
5. **WOMD v1.3.1**: Scenario protobuf provides `dynamic_map_states`, `tracks`, `sdc_track_index`, `tracks_to_predict` indices, `sdc_paths`. `training_20s` and regular overlapping 9s windows need provenance de-duplication, not random sample splitting. https://waymo.com/intl/en-ca/open/download/ and https://github.com/waymo-research/waymo-open-dataset/blob/master/src/waymo_open_dataset/protos/scenario.proto
6. **AV2 Motion Forecasting**: 250k 11s scenarios with focal vs scored vs AV identity and own local map files. Train+val are necessary for supervised fitting and validation; test future generally withheld. No 1TB standalone Map Change corpus required at the current A5 gate. https://argoverse.github.io/user-guide/tasks/motion_forecasting.html

## Paired intervention operational checklist

- Persist scenario ID, original dataset split, initial state+map digest, complete agent roster and actor geometries, vehicle model calibration, protocol/clock event-seed realization, simulator version and co-sim sync settings, and both ego prefix digests.
- Reset the simulator for each `do(A)` and `do(B)` branch; reseed/clone exogenous processes and replay the same event tape. Verify unchanged external events and allow ego changes to affect actuation **only** via modeled causal traffic-flow/controller channels.
- Run the *same reactive* other-agent policy with fixed random numbers or matched stochastic seeds. Record actor responses, all clock timestamps, policy intervention metadata, collision/resource constraints, model conformance and any failed resets. Check pre-intervention prefixes identical.
- Store `domain=simulator_intervention` and never mix paired labels as `domain=logged_real_counterfactual`. Use held-out scenario seeds/maps for simulated generalization; transfer across sim-to-real remains an assumption to test empirically.
- For WOSAC, follow its original rollout realism and collision/offroad metrics separately; do not call its score an oracle for RAMP-D safe-continuation/ICG.
