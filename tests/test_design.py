from rapid_ad.design import build_design


def test_smoke_has_unique_ids_and_all_gap_order_types():
    cases = build_design("smoke", [0])
    assert len(cases) == 14
    assert len({c["case_id"] for c in cases}) == 14
    assert {c["gap_timing"] for c in cases} == {"none", "pre", "overlap", "post"}


def test_core_is_full_factorial():
    cases = build_design("core", [0])
    assert len(cases) == 32
    assert len({c["case_id"] for c in cases}) == 32
    assert sum(c["control_transition"] for c in cases) == 16
    assert sum(not c["control_transition"] for c in cases) == 16
    for gap in ("none", "pre", "overlap", "post"):
        assert sum(c["gap_timing"] == gap for c in cases) == 8
    for task in ("go_to_stop", "stop_to_go"):
        assert sum(c["task"] == task for c in cases) == 16


def test_go_to_stop_uses_margin_target_not_fixed_distance():
    cases = build_design("core", [0])
    g2s = [c for c in cases if c["task"] == "go_to_stop"]
    assert {c["phase_margin_target_m"] for c in g2s} == {5.0, 1.5}
    assert all(c["transition_distance_m"] is None for c in g2s)


def test_seeds_create_paired_replicates():
    cases = build_design("core", [0, 1])
    assert len(cases) == 64
    assert len({c["case_id"] for c in cases}) == 64
    ids0 = {c["case_id"] for c in cases if c["seed"] == 0}
    ids1 = {c["case_id"] for c in cases if c["seed"] == 1}
    assert len(ids0) == len(ids1) == 32


def test_gap_schedule_is_event_relative_and_none_is_unmasked():
    from rapid_ad.timing import evidence_gap_active, estimate_time_to_anchor_s

    tau = estimate_time_to_anchor_s(6.0, 5.0, 6.2, 0.0, 0.1, 3.0)
    assert 0.0 < tau < 1.0
    assert evidence_gap_active(enabled=True, timing="pre", now_s=0.0, anchor_time_s=None, time_to_anchor_s=0.8, duration_s=1.0)
    assert not evidence_gap_active(enabled=True, timing="pre", now_s=1.0, anchor_time_s=1.0, time_to_anchor_s=0.0, duration_s=1.0)
    assert evidence_gap_active(enabled=True, timing="overlap", now_s=1.0, anchor_time_s=1.0, time_to_anchor_s=0.0, duration_s=1.0)
    assert evidence_gap_active(enabled=True, timing="post", now_s=1.4, anchor_time_s=1.0, time_to_anchor_s=0.0, duration_s=1.0)
    assert not evidence_gap_active(enabled=True, timing="post", now_s=2.0, anchor_time_s=1.0, time_to_anchor_s=0.0, duration_s=1.0)
    assert not evidence_gap_active(enabled=True, timing="none", now_s=1.0, anchor_time_s=1.0, time_to_anchor_s=0.0, duration_s=1.0)
