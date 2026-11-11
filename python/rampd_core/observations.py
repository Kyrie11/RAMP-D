"""Explicit observation branches and whole-posterior aggregation."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from .belief import SupportAtom, BeliefCell
from .protocol import ProtocolTransition
from .invariant import support_subset_cell


@dataclass(frozen=True)
class ObservationBranch:
    transition_id: str
    observation: str
    atoms: tuple[SupportAtom, ...]

    def __post_init__(self):
        if not self.transition_id or not self.observation or not self.atoms:
            raise ValueError("observation branch needs transition, label and support")
        if len({a.atom_id for a in self.atoms}) != len(self.atoms):
            raise ValueError("duplicate posterior atom id")


@dataclass(frozen=True)
class PosteriorResult:
    status: str
    by_observation: tuple[tuple[str, tuple[SupportAtom, ...]], ...]
    reason: str
    covered_transition_ids: tuple[str, ...] = ()

    @property
    def mapping(self):
        return dict(self.by_observation)


@dataclass(frozen=True)
class ObservationModel:
    """Finite relation from protocol transitions to all allowed observations."""

    allowed_labels: tuple[str, ...]
    require_silence: bool = True
    version: str = "phase4-observation-v1"

    def __post_init__(self):
        if not isinstance(self.require_silence, bool):
            raise TypeError("require_silence must be bool")
        labels = tuple(sorted(set(self.allowed_labels)))
        if not labels or any(not x for x in labels):
            raise ValueError("observation labels must be nonempty")
        if self.require_silence and "silence" not in labels:
            raise ValueError("silence must be represented explicitly")
        object.__setattr__(self, "allowed_labels", labels)

    def aggregate(self, branches: tuple[ObservationBranch, ...]) -> PosteriorResult:
        branches = tuple(branches)
        if not branches:
            return PosteriorResult("UNKNOWN", (), "NO_OBSERVATION_BRANCHES")
        grouped = {}
        seen = set()
        for branch in sorted(branches, key=lambda x: (x.observation, x.transition_id)):
            if branch.observation not in self.allowed_labels:
                return PosteriorResult("UNKNOWN", (), "OBSERVATION_LABEL_OUTSIDE_MODEL")
            if branch.transition_id in seen:
                return PosteriorResult("UNKNOWN", (), "DUPLICATE_TRANSITION_BRANCH")
            seen.add(branch.transition_id)
            grouped.setdefault(branch.observation, []).extend(branch.atoms)
        result = []
        for label in sorted(grouped):
            atoms = grouped[label]
            # Preserve distinct hidden supports.  A repeated atom from two
            # protocol histories is harmless only if its content is identical.
            unique = {}
            for atom in atoms:
                old = unique.get(atom.atom_id)
                if old is not None and old != atom:
                    return PosteriorResult("UNKNOWN", (), "CONFLICTING_DUPLICATE_POSTERIOR_ATOM")
                unique[atom.atom_id] = atom
            result.append((label, tuple(unique[k] for k in sorted(unique))))
        return PosteriorResult("PROVED", tuple(result), "WHOLE_POSTERIOR_AGGREGATED",
                               tuple(sorted(seen)))

    def check_single_target(self, posterior: PosteriorResult, targets: tuple[BeliefCell, ...]):
        if posterior.status != "PROVED":
            return "UNKNOWN", posterior.reason, ()
        target_map = {c.cell_id: c for c in targets}
        children = []
        for label, atoms in posterior.by_observation:
            candidates = [c for c in targets if support_subset_cell(atoms, c)]
            if not candidates:
                return "UNKNOWN", f"POSTERIOR_NOT_IN_ONE_TARGET:{label}", tuple(children)
            child = min(candidates, key=lambda c: c.cell_id)
            children.append((label, child.cell_id))
        return "PROVED", "EACH_WHOLE_POSTERIOR_HAS_ONE_TARGET", tuple(children)

    def digest(self):
        raw = json.dumps({"version": self.version, "allowed_labels": self.allowed_labels,
                          "require_silence": self.require_silence}, sort_keys=True).encode()
        return "observation-sha256:" + hashlib.sha256(raw).hexdigest()
