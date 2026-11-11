import math

import pytest

from rampd_core.forecast import (
    PredictionProposal, ProposalStatus, ProposalSet, hard_support_from_prediction,
    proposal_only,
)


def _rows(offset):
    return [
        (offset, 0.0, -1.0, -1.0, 0.0, 1.0, 0.0),
        (offset + 1.0, 0.0, -0.5, -0.5, 0.1, 1.0, 0.0),
    ]


def test_mtr_adapter_preserves_all_parameters_without_claiming_a_tube():
    proposal = PredictionProposal.from_mtr_row(
        "other", "mode-0", "frame", 0.0, 0.1, _rows(0.0), 0.6,
        model_version="mtr-test", nms_applied=False)
    assert proposal.positions[0] == (0.0, 0.0)
    assert proposal.scales[0] == (math.exp(-1.0), math.exp(-1.0))
    assert proposal.rho[1] == 0.1
    result = proposal_only((proposal,), source="MTR")
    assert result.status is ProposalStatus.PROPOSAL_ONLY
    assert result.proposal_set.complete_modes is True
    hard = hard_support_from_prediction(result.proposal_set)
    assert hard.status is ProposalStatus.UNKNOWN_UNBOUNDED_TAIL


def test_nms_or_top_k_is_explicitly_incomplete_and_only_changes_ordering():
    modes = tuple(PredictionProposal.from_mtr_row(
        "other", f"mode-{i}", "frame", 0.0, 0.1, _rows(float(i)), 1.0 - 0.1 * i,
        model_version="mtr-test", nms_applied=(i == 0)) for i in range(3))
    all_modes = ProposalSet("other", "frame", modes, "MTR", complete_modes=False)
    top = all_modes.top_k(1)
    assert len(top.proposals) == 1
    assert top.complete_modes is False
    assert [p.mode_id for p in all_modes.ranked()] == ["mode-0", "mode-1", "mode-2"]


@pytest.mark.parametrize("bad", [
    [(0, 0, 0, 0, 0, 0)],
    [(0, 0, 0, 0, 2, 0, 0)],
    [(0, 0, float("nan"), 0, 0, 0, 0)],
])
def test_mtr_shape_correlation_and_finite_checks_are_fail_closed(bad):
    with pytest.raises(ValueError):
        PredictionProposal.from_mtr_row("other", "mode", "frame", 0, 0.1, bad, 0.5)


def test_proposal_set_digest_changes_when_a_mode_or_completeness_changes():
    p = PredictionProposal.from_mtr_row("other", "mode", "frame", 0, 0.1, _rows(0), 0.5)
    a = ProposalSet("other", "frame", (p,), "MTR", complete_modes=True)
    b = ProposalSet("other", "frame", (p,), "MTR", complete_modes=False)
    assert a.digest() != b.digest()
