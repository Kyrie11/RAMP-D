# Phase7A follow-up (same development version)

Scope: factual learning corrections, future-only scheduled rule proposals, independent discrete event-clock likelihood. No complete REA, SC proof, closed-loop incident response, or event-head training authorization.

- Fixed 10Hz query times for newly generated features v2. Actual source sampling timestamps are target metadata; accept approximate alignment up to 0.02 s (pilot choice), reject larger deviation. Old v1 cache retained for checkpoint replay, regenerate for new timing experiments. Factual candidate is an offline logged path, not measured controls or online information.
- Initialize residual output to zero in training (legacy option available), include epoch zero in selection, report ADE versus CV separately from NLL. Model constructor/checkpoint format unchanged. Do not infer learned response from query sensitivity.
- Scheduled rule replay adds distinct publication/receipt per recipient, exact rational clock, no-event alternative, future-only generation relative to reused logged history. A missing delivery is not awareness, physical state, or a negative event. New proposal uses a nearby direction-aligned centerline with downstream extent; no lane polygon, legality, or resource proof. All physical/joint/event training masks remain off. Old overlay examples before decision time are diagnostic only.
- Event-clock categorical likelihood is an isolated primitive for exact/interval/right-censored discrete outcomes; the final bin denotes outside horizon (can include never). No raw timestamp imputation or event network training in this step.
- Visual BEV is offline QA, not model input; logged future displayed only as a diagnostic. Full resource polygons and closed-loop A/AA/B are still required.

See the release runbook and evidence report for acceptance and commands. Native remains independently required. No math/C++ algorithm changes.
