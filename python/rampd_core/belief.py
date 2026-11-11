"""Finite joint belief-support abstraction for RAMP-D Phase 2.

A BeliefCell is one information state (one support), not one hidden physical
state. Its support is a union of SupportAtom boxes indexed by discrete modes.
Splitting an atom refines this representation but does not create a new
observation or a new policy node.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from .interval import Interval
from .model import StateBounds


def _pairs(mapping_or_pairs):
    items = mapping_or_pairs.items() if isinstance(mapping_or_pairs, Mapping) else mapping_or_pairs
    out = tuple(sorted((str(k), v) for k, v in items))
    if len({k for k, _ in out}) != len(out):
        raise ValueError("duplicate keys")
    return out


@dataclass(frozen=True)
class SupportAtom:
    atom_id: str
    ego: StateBounds
    other: tuple[tuple[str, Interval], ...] = ()
    mode: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        if not self.atom_id:
            raise ValueError("atom_id must be nonempty")
        other = _pairs(self.other)
        mode = _pairs(self.mode)
        if any(not isinstance(v, Interval) for _, v in other):
            raise TypeError("other-state coordinates must be Interval")
        if any(not isinstance(v, str) or not v for _, v in mode):
            raise ValueError("mode values must be nonempty strings")
        object.__setattr__(self, "other", other)
        object.__setattr__(self, "mode", mode)

    @property
    def mode_dict(self):
        return dict(self.mode)

    @property
    def other_dict(self):
        return dict(self.other)


@dataclass(frozen=True)
class BeliefCell:
    """A single information-state support represented as a union of boxes."""
    cell_id: str
    atoms: tuple[SupportAtom, ...]
    actions: tuple[object, ...] = ()
    policy_node_id: str | None = None

    def __post_init__(self):
        if not self.cell_id:
            raise ValueError("cell_id must be nonempty")
        atoms = tuple(self.atoms)
        if not atoms:
            raise ValueError("belief support must be nonempty")
        if len({a.atom_id for a in atoms}) != len(atoms):
            raise ValueError("atom ids must be unique within a belief cell")
        if self.policy_node_id is None:
            object.__setattr__(self, "policy_node_id", self.cell_id)
        if not self.policy_node_id:
            raise ValueError("policy_node_id must be nonempty")
        actions = tuple(self.actions)
        action_ids = [getattr(a, "action_id", None) for a in actions]
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("candidate action ids must be unique within a cell")
        object.__setattr__(self, "atoms", atoms)
        object.__setattr__(self, "actions", actions)
