# Phase 6C A59/1b-0Q (A71): three parallel tracks — implementation, falsification and explicit acceptance boundary

Date: 2026-11-24. Baseline: A59/1b-0P (A70), v0.9.20, latest user paper and November 10 historical 21k-line engineering record. New release v0.9.21. This is a **conditional software/evidence milestone**, not an SC, road safety or eight-label certification. All downstream UNKNOWN outcomes are preserved.

## 1. Source-derived history and what changed in A71

The long historical engineering Markdown documents: Waymax synthetic two-car IDM on a real TFExample loader with official IDM lookahead and dimensions, not a logged human counterfactual; SUMO a logical alternating directional corridor with four `baseline/dense/slow_reaction/lower_friction_proxy` profiles, three seeds, signal clearance and stop-reserve guard; 511NY streaming ~3.07 million REPORT records with report timestamps and DST/negative-lifetime quarantine; ROADWork 69 grouped COCO visual templates with dataset image/annotation SHA and original-scene splits. The uploaded old A58 archive contains 12 vehicle/roster traces but only 3 valid controller summaries because other runs reused work/output paths. None of these establishes a *physical single-lane* construction site, true rule-effective instant, real message receipt, a production verified agent response model, or a complete SC task-tail policy. Historical run results are **not** new A71 simulator experiments.

**Actual new implementations**:

| Track | New source modules and CLI | New independent evidence | Remaining blockers |
|---|---|---|---|
| Mathematics | `a71_native_polygon_geometry.py`, `a71_audit_native_polygons.py`, `a71_review_native_polygon_archive_offline.py` | Exact-rational 6D Native tube projection vs declared polygon, conservative rotating-body radius, far polygon separable and near polygon MAY from four uploaded A70 certificate payloads | In this environment no MPFR replay; on-server replay mandatory. Does NOT cover 2D actual geometry registration, legal enter/stay/exit, other actors, observation or terminal rank |
| Physics/CARLA | `a71_carla_factor_pairs.py`, `a71_compare_carla_brake.py` | Current real 0.15 pure brake and historical 0.15 combined brake controlled contrast; difference isolated to *actually executed* steer command; inertia of nonexecuted CLI flags excluded | Deterministic simulator, no friction/latency/contact interval, no physically guaranteed brake envelope |
| Physics/SUMO | Instrumented `probe_sumo_alternating.py`, `a71_sumo_tls_evidence.py`, `a71_review_sumo_tls.py`, `a71_run_sumo_matrix.sh` | Every simulated tick records `COMMAND_READBACK`, `POST_STEP_READBACK`, controller phase/version, exact tick and TLS mapping; freshly run 12 simulations preserve original outputs | **Not run here**: SUMO/TraCI missing. The TraCI signal getter is NOT roadside actuation/ACK or physical barrier; geometry remains two distinct directed edges, not physical shared lane |
| Physics/Waymax | `a71_waymax_counterfactual_audit.py`, `a71_review_waymax_idm.py` | Independent off-line comparison of A/AA/B official IDM diagnostic runs, verifies matched initial worlds, no first-step future leakage, deterministic repeat, gap and effect | **Not run here**: Waymax not installed here; synthetic two-car route cannot be passed off as human intervention, curved interaction or full agent disturbance support |
| Evidence/511NY | `a71_normalize_511ny_csv.py`, `a71_event_auxiliary.py`, `a71_export_auxiliary_sources.py` | Stream real CSV report rows after DST-aware time parsing, strict road-agency proxy and lifetime quarantine, report-only source provenance | No user-supplied actual CSV in this turn; row identity NOT unique physical incident, missing sensor onset, closure execution, GPS resource polygons |
| Evidence/ROADWork | `a71_event_auxiliary.py`, `a71_export_auxiliary_sources.py` | Convert historical **actual grouped visual template schema**, maintain original image family and bounding box semantics, empty annotation ≠ absence of construction | No actual user template JSONL supplied in this turn; no calibrated camera-to-map geometry, exact road closure or authority timestamp |
| Evidence/supervision | All A71 outputs | Every adapter retains source semantic role and `formal_label_masks=0` for all eight official labels | M11 independent teacher, M13 formal label factories and provenance family split validation pending global closure |

## 2. CARLA 0.15 same-brake, different steering: independent physical comparison

Actual uploaded Tesla Model3 CARLA 0.9.16 Town06 samples: same trigger speed about 4.893 m/s, same road 48/lane -6, same recorded PhysicsControl/environment, `brake=0.15` in both; pure `steer=0`, combined `steer=0.03` for 0.15 s. Both recorded 26 approach and 40 control frames. The historical capture script records inactive steer CLI settings `0.08/0.8s` for pure braking, despite ZERO applied steering. A naive declared-config equality would give a spurious protocol mismatch: A71 compares actual executed control and limits the intervention to steer. Distinguish observational matching from true randomized causal intervention.

| Quantity | Pure 0.15 brake | Combined 0.15 brake + steer 0.03 |
|---|---:|---:|
| Peak signed longitudinal acceleration | about -18.085 m/s² | about -23.408 m/s² |
| Peak deceleration while planar speed >= 1 m/s | about 2.286 m/s² | about 2.380 m/s² |
| Sampled path after control | about 6.597 m | about 6.570 m |
| Max abs yaw rate | 0.00054 rad/s | 0.07490 rad/s |
| Smallest sampled lane margin | about 0.568 m | about 0.480 m |

The extreme peaks arise near the stop, not during >1 m/s travel. They may involve contact/speed-clamp/physics solver response. As the data is only one run per condition and no wheel torque / longitudinal tire force measured, it is incorrect to identify *actual* saturation, delay bounds or guaranteed deceleration. Past 0.30/0.45 combined arms peak around -26.927 m/s² while travelling ~2.8 m/s and stop after 0.35 s; comparing maximum peak values across different speed regimes is not system identification. Do **not** update the paper bicycle safety constraints from these values.

Next physical program: 2×3 factorial, all six cells at brake `{0.15,0.30,0.45}` and steer `{0,0.03}`, three repeats/cell, fixed CARLA actor/model/site/weather/delta. Separate moving-speed bin (>=1 m/s), transition bin, near-stop (<1 m/s); report command issue, physical wheel angle, acceleration, yaw, distance, stop time, late/zero-speed solver. Then vary speed 5/10/15 separately, tire friction separately, step delta/substeps separately; no one-factor mixing. Bounded residual support requires clearly defined domain and independent holds, not just min/max observed values. Historical max brake torque 700 N·m per wheel and tire friction=3.5 are simulator configuration, not measured road friction.

## 3. Mathematics: what is and is not proved

RAMP-D paper includes 6D continuous bicycle `(px,py,psi,v,a,delta)` with public control `(j,omega_delta)`, exact clock cut points, and a finite-completion SC predecessor requiring both full `SafeTube` and all observation-merged posteriors to have a common nonanticipative control/strict rank decrease to a real accepting terminal policy.

A70 **did** create and replay 4 Native MPFR/Picard ego tubes for two declared hidden worlds and two time slabs in its local environment. These are meaningful *model-relative* 6D ego derivative inclusion witnesses. The A71 workhere independently verified certificate SHA and applied exact-rational polygon separation to their recorded 6D tube fields. This offline check is **not** independent numeric replay; new server `a71_audit_native_polygons.py` rejects any certificate without actual replay via the existing `replay_certificate` helper.

For any vehicle point in a length `L`, width `W` rectangle and body-reference offset `(ox,oy)`, every world-frame point differs from vehicle reference center in each coordinate by at most `R=|ox|+|oy|+(L+W)/2` across all headings. For any polygon edge normal `n`, a conservative projection radius is `(|nx|+|ny|)R`. If a strict exact-rational gap separates the native position-interval projection expanded by that radius from ALL declared polygon vertices, there is no possible footprint-polygon contact in that entire **validated** native segment, conditional on the polygon coordinates being correct. This proof works for nonconvex polygons by using their convex-hull support (more conservative). If no separation axis exists, output `MAY_INTERSECT`; this is not a witness of collision, only an unproven exclusion.

Crucial limits: resource authorization cannot be proved solely by polygon disjointness; real enter/stay/exit and capacity/direction are unproved if contact is possible. Clock effectivity and ACK are not retroactive. Native model derivative disturbance is still not bounded against all CARLA / real-world actuation regimes; and other actors, public observation completeness, `K_term^SC`, terminal rank, task-tail are absent. The seven listed logical counterexamples are not all end-to-end certified by the new polygon gate. Full `CERTIFIED` and all `L_viability`, `L_margin`, `L_deadline` masks must remain false.

A71 math acceptance: (i) server full A70 native bridge + 4 world/slabs replays, (ii) far declared resource conditional exclusion, (iii) near declared resource UNKNOWN, (iv) missing/tampered hash, wrong hidden identity/clock/ACK cannot pass, (v) no label authorization. The genuine future A59/1b-1 must compose *all actors' 6D or validated proxy tubes*, general geometric resource graph, precise traffic authority/physical ACK and public observation support, then construct and independently replay accepting SC tail with strict rank. No regression from 1D separation to false polygon certification.

## 4. Traffic and SUMO / Waymax independence and realism

SUMO script `a71_run_sumo_matrix.sh /new/output/root` runs 4 traffic profiles × 3 seeds, never reuses work directories or overwrites reports. 12 controller reports and 12 separate signal traces become available for offline replay. Note: changing seed with sigma/speedDev zero may yield identical vehicle populations; source-defined profile differences remain the intended stress levels. Compare `--require-comfort` stop-reserve guard and departure/arrival rosters to avoid interpreting no sampled collision as permission correctness. The SUMO experiment is a logical bidirectional contract, NOT a physical shared one-lane polygon.

Waymax official IDM uses log route policy under synthetic actor insertion; separate exact numerical checks should evaluate gap error and control conversions; a paired change to the lead car under the same pre-step state may illustrate *model-relative* follower response but is not logged human counterfactual support. Next instrument on real WOMD scenario IDs and study perturbed route/road topology/visible actor response under declared assumptions.

CARLA/SUMO synchrony remains unrun: require a common OpenDRIVE↔SUMO net geometry registration, 0.05↔0.1 fixed ratio, exactly one CARLA tick master, actor-ID mapping, unique signal authority and persistent frame/command ACK provenance. No TLS getter by itself demonstrates roadside physical state.

## 5. 511NY/ROADWork data roles and trustworthy losses

511NY input is historical government report table: its `create_time`/`close_time` indicate administrative report lifetime (with timezone ambiguity), **not** the time of actual rule deployment or vehicle receipt. The normalized CSV and auxiliary conversion explicitly leave all effectivity, receipt and metric polygon fields null. ROADWork image COCO bounding boxes are pixel observations, even with scene-family isolation; they are not exact road polygons or incident-rule authority. Both can be useful *auxiliary* labels, not clean formal safety or causal labels.

Eight formal losses production plan, evidence-dependent not one global all-or-nothing source:

| Loss | Next useful auxiliary source | Required formal evidence |
|---|---|---|
| `L_event` | 511NY reported type/time, SUMO constructed event time | Explicit declared truth timeline, authority, effectivity, issue, receipt, ACK and uncertainty domain |
| `L_joint` | AV2/WOMD logged joint tracks, Waymax synthetic IDM paired worlds | Source-tagged actor identities, real-vs-synthetic domain, valid support or falsifiable response envelope |
| `L_occupancy` | AV2/WOMD dynamic map + tracks, ROADWork 2D workzone cues | Calibrated metric map resource geometry + time-continuous tube/footprint coverage |
| `L_observation` | ROADWork visual objects, CARLA camera/LiDAR planned | Actual visible/occluded timing, censored silence, messaging send/receive grounded |
| `L_causal` | Paired SUMO/Waymax/CARLA simulations | Same exogenous seed, consistent pre-intervention hidden state, real intervention and full downstream re-simulation |
| `L_viability` | Independent M11 teacher over complete support | Positive SC accepting tail OR complete finite-policy-class negative proof; no single failed rollout negatives |
| `L_margin` | MPFR/native tubes with calibrated disturbances | Full continuous-time conservative signed margin and resource constraints |
| `L_deadline` | Realistic event clock, confirmed ACK, policy reach | Certificate-backed information/resource/commitment deadlines |

An auxiliary factual report may eventually authorize a *narrow factual head* separately, but is never silently promoted to formal safe-SC `L_event` or `L_occupancy`. A71 releases ZERO formally certified labels.

## 6. M1–M13 acceptance (no false convergence)

| M | Status at A71 | Independent next evidence |
|---|---|---|
| M1 MPFR/Picard | A70 two-world four-slabs native historical; A71 exact-rational polygon conditional | Rerun actual native backend, general all-agent mixed Post |
| M2 exact Traffic time | A61/A70 declared event splits, A71 simulated tick readback capture | Real effectivity/receipt/ACK chain, mix of simulator clocks |
| M3 ego physics | 5m/s steering/braking/combined logs, new brake pair | Model error domain, friction, true control delay and validated residual enclosure |
| M4 reactive agents | Official Waymax synthetic IDM earlier, new offline audit | Real-scenario response and full plausible agent support |
| M5 continuous resource geometry | A71 conservative declared polygon far/near | Authoritative metric polygons, all actor tubes + continuous enter/stay/exit |
| M6 rules/capacity Guard | Existing Guard controller/initial occupancy gates | Protocol authority and full capacity/direction for all worlds |
| M7 command interlock | A70 ACK/pre-slab logic and A71 TraCI getter | Real physical interlock controller and failure latching |
| M8 hidden protocol | A70 two hidden worlds, model-limited | Complete allowed hidden-state successor enumeration and merging |
| M9 public observations | Model-prefix grouping only | Sensor visibility, true receive timing and silence censorship |
| M10 SC task completion | conditional rank checks only | True finite task-accepting terminal policy with reachability |
| M11 independent teacher | audit skeleton, no complete oracle | Separate full-support/negative exhaustive oracle |
| M12 simulator realism | 3 CARLA brake arms and one pure/combined pair, historical SUMO | New 12-run SUMO logs; Waymax new independent live; CARLA/SUMO live sync |
| M13 eight losses | safe AUX adapters + eight zero formal masks | Signed evidence, stratified domain labels, complete trustworthy label factory |

## 7. What ran HERE and what must run on user's server

HERE: A71 29/29 pure tests, A58 19/19 pure, A59 11/11 pure; existing uploaded 4 Native certificate bytes hashed and evaluated against far/near declared polygons but NOT natively replayed here; actual pure/combined CARLA 0.15 raw JSON pair checked. The old A70 baseline had 940/940 tests, but those are HISTORICAL, not newly rerun in this release. No CARLA server, SUMO TraCI, Waymax simulator or 511NY/ROADWork raw bulk files available here. Final A71 server gate requires full native rebuild and all old+new tests; do not mark this gate passed until files are uploaded. No M1–M13 global pass and no training mask authorized.
