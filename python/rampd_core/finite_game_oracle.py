"""Dependency-free, exact finite public-observation game cross-check.

This is a *finite game test oracle*, not a certified physical-state model.
Here an observation identifies a complete posterior-support cell ID, already
merged across indistinguishable hidden histories. External sound coverage is a
separate obligation, never inferred from this graph's adjacency lists.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Mapping


@dataclass(frozen=True)
class FiniteGame:
    cells: tuple[str, ...]
    safe: frozenset[str]
    terminals: frozenset[str]
    # cell -> tuple of candidate public actions; action = tuple of (obs, next_support_id)
    actions: Mapping[str, tuple[tuple[tuple[str, str], ...], ...]]
    step: Fraction
    terminal_time: Mapping[str, Fraction]

    def __post_init__(self):
        if not self.cells or len(self.cells) != len(set(self.cells)):
            raise ValueError('cells must be unique and nonempty')
        known = set(self.cells)
        if not self.safe <= known or not self.terminals <= self.safe:
            raise ValueError('safe and terminal sets inconsistent')
        if self.step <= 0 or set(self.terminal_time) != set(self.terminals):
            raise ValueError('positive step and complete terminal completion times required')
        if any(t < 0 for t in self.terminal_time.values()):
            raise ValueError('terminal time must be nonnegative')
        if set(self.actions) - known:
            raise ValueError('unknown action owner')
        for _, candidates in self.actions.items():
            for action in candidates:
                observations = [o for o, _ in action]
                if not action or len(set(observations)) != len(action):
                    raise ValueError('each action must list a nonempty, unique public observation partition')
                if any(not o or child not in known for o, child in action):
                    raise ValueError('invalid observation/child')


def forward_ranks(game: FiniteGame, horizon: int):
    """Least fixed-horizon rank via set iteration, plus exact completion bound."""
    if horizon < 0:
        raise ValueError('negative horizon')
    ranks = {s: 0 for s in game.terminals}
    times = dict(game.terminal_time)
    for k in range(1, horizon + 1):
        additions = {}
        for cell in game.safe - ranks.keys():
            possible = [game.step + max(times[child] for _, child in action)
                        for action in game.actions.get(cell, ())
                        if all(child in ranks for _, child in action)]
            if possible:
                additions[cell] = min(possible)
        for cell, duration in additions.items():
            ranks[cell] = k
            times[cell] = duration
    return ranks, times


def recursive_winner(game: FiniteGame, cell: str, horizon: int) -> bool:
    """Independent bounded AND-OR reachability semantics, no rank table."""
    if horizon < 0:
        return False

    @lru_cache(None)
    def wins(state: str, budget: int) -> bool:
        if state not in game.safe:
            return False
        if state in game.terminals:
            return True
        if budget == 0:
            return False
        return any(all(wins(next_state, budget - 1) for _, next_state in action)
                   for action in game.actions.get(state, ()))

    return wins(cell, horizon)
