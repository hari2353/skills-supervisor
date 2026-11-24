"""Typed, deterministic multi-agent swarm with bounded consensus."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping


class Role(str, Enum):
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"


_ROLE_ORDER = {Role.RESEARCHER: 0, Role.CODER: 1, Role.REVIEWER: 2}


@dataclass(frozen=True)
class Proposal:
    role: Role
    answer: str
    confidence: float
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.answer.strip():
            raise ValueError("answer must be non-empty")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be within [0, 1]")


@dataclass(frozen=True)
class SwarmResult:
    answer: str
    consensus: bool
    votes: tuple[Proposal, ...]
    rounds: int
    conflicts: tuple[str, ...]


def _normalize(answer: str) -> str:
    return " ".join(answer.strip().lower().split())


class TypedSwarm:
    def __init__(
        self,
        agents: Mapping[Role, Callable[[str, int], Proposal]],
        max_rounds: int = 2,
        quorum: int = 2,
        min_confidence: float = 0.5,
    ) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        if quorum < 1:
            raise ValueError("quorum must be >= 1")
        if not 0 <= min_confidence <= 1:
            raise ValueError("min_confidence must be within [0, 1]")
        self.agents = dict(agents)
        self.max_rounds = max_rounds
        self.quorum = quorum
        self.min_confidence = min_confidence

    def _ranked_groups(self, votes: list[Proposal]) -> list[tuple[str, list[Proposal]]]:
        groups: dict[str, list[Proposal]] = {}
        for proposal in votes:
            groups.setdefault(_normalize(proposal.answer), []).append(proposal)
        reviewer_key = next(
            (_normalize(p.answer) for p in votes if p.role is Role.REVIEWER), None
        )

        def key(item):
            answer, group = item
            return (
                -len(group),
                reviewer_key != answer,
                -sum(p.confidence for p in group),
                _ROLE_ORDER[min(group, key=lambda p: _ROLE_ORDER[p.role]).role],
                answer,
            )

        return sorted(groups.items(), key=key)

    def run(self, task: str) -> SwarmResult:
        all_votes: list[Proposal] = []
        last_votes: list[Proposal] = []
        rounds = 0
        for round_no in range(1, self.max_rounds + 1):
            rounds = round_no
            last_votes = [agent(task, round_no) for agent in self.agents.values()]
            all_votes.extend(last_votes)
            eligible = [p for p in last_votes if p.confidence >= self.min_confidence]
            ranked = self._ranked_groups(eligible)
            if ranked and len(ranked[0][1]) >= self.quorum:
                answer, group = ranked[0]
                conflicts = tuple(sorted({a for a, _ in ranked} - {answer}))
                return SwarmResult(
                    answer=group[0].answer,
                    consensus=True,
                    votes=tuple(all_votes),
                    rounds=rounds,
                    conflicts=conflicts,
                )

        # No quorum: rank the full last round, reviewer tie-break included.
        ranked = self._ranked_groups(last_votes)
        conflicts = tuple(sorted(a for a, _ in ranked))
        if not ranked:
            return SwarmResult("", False, tuple(all_votes), rounds, ())
        _, group = ranked[0]
        return SwarmResult(
            answer=group[0].answer,
            consensus=False,
            votes=tuple(all_votes),
            rounds=rounds,
            conflicts=conflicts,
        )
