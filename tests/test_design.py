from rapid_ad.design import build_design


def test_smoke_count_and_unique_ids():
    cases = build_design("smoke", [0])
    assert len(cases) == 6
    assert len({c["case_id"] for c in cases}) == len(cases)


def test_core_count_and_factor_balance():
    cases = build_design("core", [0])
    assert len(cases) == 16
    assert sum(bool(c["control_transition"]) for c in cases) == 8
    assert sum(bool(c["evidence_gap"]) for c in cases) == 8


def test_all_count_and_order_levels():
    cases = build_design("all", [0])
    assert len(cases) == 32
    assert {c["gap_timing"] for c in cases} == {"none", "pre", "overlap", "post"}


def test_seeds_create_replicates():
    cases = build_design("smoke", [0, 1])
    assert len(cases) == 12
    assert len({c["case_id"] for c in cases}) == 12
