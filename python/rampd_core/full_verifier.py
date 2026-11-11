"""Phase 4 finite-support protocol verifier.

The verifier is deliberately three-valued.  It can certify only when the
caller supplies complete branch supports and independently replayable
continuous/resource evidence.  Missing evidence, unsupported models, budget
exhaustion, and a wide tube all remain ``UNKNOWN``.  A counterexample is
accepted only through a caller-provided witness checker bound to the same
protocol transition, public action and support.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from typing import Callable, Mapping

from .protocol import ProtocolAutomaton, ProtocolTransition, branch_temporal_status
from .observations import ObservationModel, ObservationBranch, PosteriorResult
from .belief import SupportAtom, BeliefCell


def _public_observation_time(transition: ProtocolTransition):
    """Return the earliest time at which this observation is public.

    ``change`` is an environment clock; it is not automatically an ego
    observation.  A message branch becomes public at receipt, and when the
    contract also supplies a local-first-observation clock we conservatively
    wait until that clock as well.  Silence uses the local clock when one is
    declared.  A non-point availability window cannot be collapsed to its
    lower endpoint without inventing a decision instant, so it is returned as
    unresolved by the caller.
    """
    clocks = transition.clocks
    windows = [clocks.change]
    if transition.message is not None:
        if clocks.receipt is None:
            return None, "PUBLIC_OBSERVATION_RECEIPT_CLOCK_MISSING"
        windows.append(clocks.receipt)
    if clocks.local is not None:
        windows.append(clocks.local)
    if any(window.lo != window.hi for window in windows):
        return None, "PUBLIC_OBSERVATION_TIME_INTERVAL_REQUIRES_REFINEMENT"
    return max(window.lo for window in windows), "PUBLIC_OBSERVATION_TIME_PROVED"


class VerifyStatus:
    CERTIFIED = "CERTIFIED"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class BranchCheck:
    status: str
    reason: str
    support: tuple[SupportAtom, ...] = ()
    counterexample: dict | None = None

    def __post_init__(self):
        if self.status not in {VerifyStatus.CERTIFIED, VerifyStatus.COUNTEREXAMPLE, VerifyStatus.UNKNOWN}:
            raise ValueError("invalid branch result")
        object.__setattr__(self, "support", tuple(self.support))


@dataclass(frozen=True)
class VerificationTask:
    state_id: str
    time: Fraction
    support: tuple[SupportAtom, ...]
    path: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerificationResult:
    status: str
    assurance_scope: str
    reason: str
    processed_tasks: int
    pending_tasks: int
    unresolved: tuple[str, ...] = ()
    counterexample: dict | None = None
    protocol_digest: str = ""
    policy_digest: str = ""
    model_digest: str = ""
    observation_digest: str = ""
    contract_digest: str = ""

    def to_dict(self):
        return {"status": self.status, "assurance_scope": self.assurance_scope,
                "reason": self.reason, "processed_tasks": self.processed_tasks,
                "pending_tasks": self.pending_tasks, "unresolved": list(self.unresolved),
                "counterexample": self.counterexample, "protocol_digest": self.protocol_digest,
                "policy_digest": self.policy_digest, "model_digest": self.model_digest,
                "observation_digest": self.observation_digest,
                "contract_digest": self.contract_digest}


@dataclass(frozen=True)
class FullVerifierContract:
    automaton: ProtocolAutomaton
    observations: ObservationModel
    initial_support: tuple[SupportAtom, ...]
    targets: tuple[BeliefCell, ...] = ()
    terminal_state_ids: tuple[str, ...] = ()
    scope: str = "PHASE4_EXPLICIT_PROTOCOL_SUPPORT"
    max_tasks: int = 1000
    max_path_length: int = 100
    policy_digest: str = ""
    model_digest: str = ""
    observation_digest: str = ""

    def __post_init__(self):
        if not self.initial_support:
            raise ValueError("initial joint support must be nonempty")
        if int(self.max_tasks) <= 0 or int(self.max_path_length) <= 0:
            raise ValueError("verification budgets must be positive")
        unknown = set(self.terminal_state_ids) - {s.state_id for s in self.automaton.states}
        if unknown:
            raise ValueError("terminal state is not in automaton")
        object.__setattr__(self, "initial_support", tuple(self.initial_support))
        object.__setattr__(self, "targets", tuple(self.targets))
        if len({c.cell_id for c in self.targets}) != len(self.targets):
            raise ValueError("target cell ids must be unique")
        object.__setattr__(self, "terminal_state_ids", tuple(sorted(set(self.terminal_state_ids))))
        if not isinstance(self.policy_digest, str) or not isinstance(self.model_digest, str):
            raise ValueError("policy_digest and model_digest must be strings")
        expected_observation_digest = self.observations.digest()
        if self.observation_digest and self.observation_digest != expected_observation_digest:
            raise ValueError("observation model digest mismatch")
        object.__setattr__(self, "observation_digest", expected_observation_digest)

    @property
    def digest(self):
        def atom(a):
            return {"id": a.atom_id,
                    "ego": [[x.lo, x.hi] for x in a.ego.as_tuple()],
                    "other": [[k, v.lo, v.hi] for k, v in a.other],
                    "mode": [list(x) for x in a.mode]}
        payload = {
            "protocol": self.automaton.digest(),
            "observations": self.observation_digest,
            "initial_support": [atom(a) for a in self.initial_support],
            "targets": [{"id": c.cell_id, "policy_node_id": c.policy_node_id,
                         "atoms": [atom(a) for a in c.atoms]}
                        for c in self.targets],
            "terminal_state_ids": self.terminal_state_ids,
            "scope": self.scope, "policy": self.policy_digest,
            "model": self.model_digest,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return "verifier-contract-sha256:" + hashlib.sha256(raw).hexdigest()


class FullSupportVerifier:
    def __init__(self, contract: FullVerifierContract,
                 branch_checker: Callable[[VerificationTask, ProtocolTransition, object], BranchCheck] | None = None,
                 terminal_checker: Callable[[VerificationTask], BranchCheck] | None = None,
                 action_for_state: Callable[[str], object] | None = None,
                 counterexample_checker: Callable[[VerificationTask, ProtocolTransition, object, BranchCheck], bool] | None = None,
                 interval_branch_checker: Callable[[VerificationTask, ProtocolTransition, object], BranchCheck] | None = None):
        self.contract = contract
        self.branch_checker = branch_checker
        self.terminal_checker = terminal_checker
        self.action_for_state = action_for_state
        self.counterexample_checker = counterexample_checker
        # A non-point event window is never collapsed to an endpoint. Phase 5
        # may provide an independent whole-window certificate here.
        self.interval_branch_checker = interval_branch_checker

    def _unknown(self, reason, processed, pending, unresolved, *, counterexample=None):
        return VerificationResult(VerifyStatus.UNKNOWN, self.contract.scope, reason, processed, pending,
                                  tuple(unresolved), counterexample,
                                  self.contract.automaton.digest(), self.contract.policy_digest,
                                  self.contract.model_digest, self.contract.observation_digest,
                                  self.contract.digest)

    def verify(self) -> VerificationResult:
        if not self.contract.model_digest:
            return self._unknown("MODEL_CONTRACT_DIGEST_MISSING", 0, 1, ())
        ledger = self.contract.automaton.coverage()
        missing_nonterminal = tuple(x for x in ledger.missing_states
                                    if x not in self.contract.terminal_state_ids)
        if missing_nonterminal:
            return self._unknown("PROTOCOL_BRANCH_COVERAGE_INCOMPLETE", 0, 1,
                                 tuple("MISSING_STATE:" + x for x in missing_nonterminal))
        q = deque([VerificationTask(self.contract.automaton.initial_state_id, Fraction(0),
                                    self.contract.initial_support)])
        seen = set()
        unresolved = []
        target_map = {c.cell_id: c for c in self.contract.targets}
        processed = 0
        while q:
            if processed >= self.contract.max_tasks:
                return self._unknown("VERIFICATION_BUDGET_EXHAUSTED", processed, len(q), unresolved)
            task = q.popleft(); processed += 1
            def atom_key(atom):
                return (atom.atom_id, tuple((x.lo, x.hi) for x in atom.ego.as_tuple()),
                        tuple((k, v.lo, v.hi) for k, v in atom.other), atom.mode)
            key = (task.state_id, task.time, tuple(sorted(atom_key(a) for a in task.support)))
            if key in seen:
                return self._unknown("RECURSIVE_SUPPORT_NOT_TERMINATED", processed, len(q), unresolved)
            seen.add(key)
            if len(task.path) > self.contract.max_path_length:
                return self._unknown("PATH_LENGTH_BUDGET_EXHAUSTED", processed, len(q), unresolved)
            if task.state_id in self.contract.terminal_state_ids:
                if self.terminal_checker is None:
                    return self._unknown("TERMINAL_EVIDENCE_MISSING", processed, len(q), unresolved)
                checked = self.terminal_checker(task)
                if checked.status == VerifyStatus.COUNTEREXAMPLE:
                    if self.counterexample_checker is None or not self.counterexample_checker(task, None, None, checked):
                        unresolved.append("TERMINAL:COUNTEREXAMPLE_REPLAY_MISSING")
                        continue
                    return VerificationResult(VerifyStatus.COUNTEREXAMPLE, self.contract.scope,
                                              checked.reason, processed, len(q), tuple(unresolved),
                                              checked.counterexample, self.contract.automaton.digest(),
                                              self.contract.policy_digest, self.contract.model_digest,
                                              self.contract.observation_digest, self.contract.digest)
                if checked.status != VerifyStatus.CERTIFIED:
                    unresolved.append("TERMINAL:" + checked.reason)
                continue
            transitions = self.contract.automaton.enumerate_successors(task.state_id, at_time=task.time)
            if not transitions:
                return self._unknown("NO_TIME_COMPATIBLE_PROTOCOL_BRANCH", processed, len(q), unresolved)
            branches = []
            action = self.action_for_state(task.state_id) if self.action_for_state else None
            for tr in transitions:
                temporal, why = branch_temporal_status(tr)
                if temporal != "PROVED":
                    unresolved.append(f"{tr.transition_id}:{why}")
                    continue
                # Never collapse an interval to its lower endpoint. A Phase
                # 5 caller may instead provide an independent whole-window
                # certificate through interval_branch_checker.
                if tr.clocks.change.lo != tr.clocks.change.hi:
                    if self.interval_branch_checker is None:
                        unresolved.append(f"{tr.transition_id}:EVENT_TIME_INTERVAL_REQUIRES_REFINEMENT")
                        continue
                    checked = self.interval_branch_checker(task, tr, action)
                else:
                    if self.branch_checker is None:
                        unresolved.append(f"{tr.transition_id}:CONTINUOUS_EVIDENCE_MISSING")
                        continue
                    checked = self.branch_checker(task, tr, action)
                if checked.status == VerifyStatus.COUNTEREXAMPLE:
                    if self.counterexample_checker is None or not self.counterexample_checker(task, tr, action, checked):
                        unresolved.append(f"{tr.transition_id}:COUNTEREXAMPLE_REPLAY_MISSING")
                        continue
                    return VerificationResult(VerifyStatus.COUNTEREXAMPLE, self.contract.scope,
                                              checked.reason, processed, len(q), tuple(unresolved),
                                              checked.counterexample, self.contract.automaton.digest(),
                                              self.contract.policy_digest, self.contract.model_digest,
                                              self.contract.observation_digest, self.contract.digest)
                if checked.status != VerifyStatus.CERTIFIED:
                    unresolved.append(f"{tr.transition_id}:{checked.reason}")
                    continue
                if not checked.support:
                    unresolved.append(f"{tr.transition_id}:EMPTY_POSTERIOR_SUPPORT")
                    continue
                # Silence is an observation branch, not hidden-state
                # information.  Unless an explicit publication/delivery
                # deadline contract proves exclusion, a checker cannot drop
                # a hidden mode merely because no report was received.
                if tr.silence and not tr.silence_exclusion_proved:
                    source_modes = {a.mode for a in task.support}
                    successor_modes = {a.mode for a in checked.support}
                    if not source_modes.issubset(successor_modes):
                        unresolved.append(
                            f"{tr.transition_id}:SILENCE_REMOVES_HIDDEN_HISTORY_WITHOUT_PROOF")
                        continue
                branches.append(ObservationBranch(tr.transition_id, tr.observation, checked.support))
            if not branches:
                continue
            posterior = self.contract.observations.aggregate(tuple(branches))
            if posterior.status != "PROVED":
                unresolved.append(posterior.reason)
                continue
            status, why, children = self.contract.observations.check_single_target(posterior, self.contract.targets)
            if self.contract.targets and status != "PROVED":
                unresolved.append(why)
                continue
            target_by_obs = dict(children)
            for observation, support in posterior.by_observation:
                target_cell_id = target_by_obs.get(observation)
                target_cell = target_map.get(target_cell_id) if target_cell_id is not None else None
                matching = [tr for tr in transitions if tr.observation == observation]
                child_state_ids = {tr.target_state_id for tr in matching}
                if len(child_state_ids) != 1:
                    unresolved.append(f"{observation}:PUBLIC_CHILD_AMBIGUOUS")
                    continue
                child_state = next(iter(child_state_ids))
                # The next public decision time is determined by the
                # observation clocks, not by the physical change clock alone.
                # Routing at change.lo would let an ego act on an event before
                # its message receipt/local observation and violate
                # nonanticipativity.
                public_times = []
                for tr in matching:
                    public_time, public_reason = _public_observation_time(tr)
                    if public_time is None:
                        unresolved.append(f"{observation}:{public_reason}")
                        continue
                    public_times.append(public_time)
                if len(public_times) != len(matching) or len(set(public_times)) != 1:
                    unresolved.append(f"{observation}:PUBLIC_TIME_AMBIGUOUS")
                    continue
                next_time = public_times[0]
                if next_time <= task.time:
                    unresolved.append(f"{observation}:NONADVANCING_EVENT_TIME")
                    continue
                if target_cell is not None and target_cell.policy_node_id != child_state:
                    unresolved.append(f"{observation}:TARGET_PROTOCOL_CONTEXT_MISMATCH")
                    continue
                q.append(VerificationTask(child_state, next_time, support,
                                          task.path + (child_state,)))
        if unresolved:
            return self._unknown("UNRESOLVED_OBLIGATIONS", processed, len(q), unresolved)
        return VerificationResult(VerifyStatus.CERTIFIED, self.contract.scope,
                                  "ALL_PROTOCOL_BRANCHES_AND_TERMINALS_PROVED", processed, 0,
                                  (), None, self.contract.automaton.digest(), self.contract.policy_digest,
                                  self.contract.model_digest, self.contract.observation_digest,
                                  self.contract.digest)


def policy_digest(value: Mapping[str, object]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "policy-sha256:" + hashlib.sha256(raw).hexdigest()
