"""Conservative box refinement without inventing new observations/policy nodes."""
from __future__ import annotations
from dataclasses import replace
from .belief import BeliefCell, SupportAtom
from .interval import Interval
from .model import StateBounds

EGO_DIMS = ("px", "py", "psi", "v", "a", "delta")


def _bisect_interval(x: Interval):
    mid = x.lo / 2.0 + x.hi / 2.0
    if not (x.lo < mid < x.hi):
        raise ValueError("no representable binary64 midpoint; cell cannot be bisected")
    return Interval(x.lo, mid), Interval(mid, x.hi)


def split_support_atom(cell: BeliefCell, atom_id: str, dimension: str) -> BeliefCell:
    """Bisect one support box while preserving the same belief/policy node.

    The two closed children overlap at the midpoint and their union is exactly
    the parent interval. Existing action/tube evidence is invalidated because
    its source partition changed. This operation does NOT assert that the
    two halves are observationally distinguishable.
    """
    matches = [a for a in cell.atoms if a.atom_id == atom_id]
    if len(matches) != 1:
        raise KeyError(f"atom {atom_id!r} not found exactly once")
    atom = matches[0]
    if dimension in EGO_DIMS:
        idx = EGO_DIMS.index(dimension)
        left_i, right_i = _bisect_interval(atom.ego.as_tuple()[idx])
        left_state = list(atom.ego.as_tuple()); right_state = list(atom.ego.as_tuple())
        left_state[idx] = left_i; right_state[idx] = right_i
        left_ego, right_ego = StateBounds(*left_state), StateBounds(*right_state)
        left = SupportAtom(atom.atom_id + ".L", left_ego, atom.other, atom.mode)
        right = SupportAtom(atom.atom_id + ".R", right_ego, atom.other, atom.mode)
    else:
        other = atom.other_dict
        if dimension not in other:
            raise KeyError(f"dimension {dimension!r} not present in atom")
        left_i, right_i = _bisect_interval(other[dimension])
        left_other = dict(other); right_other = dict(other)
        left_other[dimension] = left_i; right_other[dimension] = right_i
        left = SupportAtom(atom.atom_id + ".L", atom.ego, tuple(left_other.items()), atom.mode)
        right = SupportAtom(atom.atom_id + ".R", atom.ego, tuple(right_other.items()), atom.mode)
    new_atoms = []
    for a in cell.atoms:
        if a.atom_id == atom_id:
            new_atoms.extend((left, right))
        else:
            new_atoms.append(a)
    return BeliefCell(cell.cell_id, tuple(new_atoms), actions=(),
                      policy_node_id=cell.policy_node_id)
