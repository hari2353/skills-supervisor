"""Typed swarm: consensus, reviewer tie-break, bounded rounds."""

from __future__ import annotations

import pytest

from skills_supervisor.swarm import Proposal, Role, TypedSwarm


def agent(role: Role, answer: str, confidence: float = 0.8, trace=None):
    def run(task: str, round_no: int) -> Proposal:
        if trace is not None:
            trace.append((role, round_no))
        return Proposal(role, answer, confidence, f"{role.value} says {answer}")
    return run


def test_unanimous_consensus_in_one_round() -> None:
    swarm = TypedSwarm({
        Role.RESEARCHER: agent(Role.RESEARCHER, "Deploy it"),
        Role.CODER: agent(Role.CODER, "deploy it"),
        Role.REVIEWER: agent(Role.REVIEWER, " Deploy  it "),
    })
    result = swarm.run("ship?")
    assert result.consensus is True
    assert result.answer == "Deploy it"
    assert result.rounds == 1
    assert result.conflicts == ()


def test_majority_wins() -> None:
    swarm = TypedSwarm({
        Role.RESEARCHER: agent(Role.RESEARCHER, "A", 0.9),
        Role.CODER: agent(Role.CODER, "B", 0.6),
        Role.REVIEWER: agent(Role.REVIEWER, "B", 0.7),
    })
    result = swarm.run("pick")
    assert result.consensus is True
    assert result.answer == "B"
    assert result.conflicts == ("a",)


def test_reviewer_wins_exact_tie() -> None:
    trace = []
    swarm = TypedSwarm({
        Role.RESEARCHER: agent(Role.RESEARCHER, "A", 0.9, trace),
        Role.CODER: agent(Role.CODER, "B", 0.9, trace),
        Role.REVIEWER: agent(Role.REVIEWER, "B", 0.1, trace),
    })
    result = swarm.run("pick")
    assert result.consensus is False
    assert result.answer == "B"
    assert result.rounds == 2
    assert len(trace) == 6


def test_confidence_breaks_tie_without_reviewer() -> None:
    swarm = TypedSwarm({
        Role.RESEARCHER: agent(Role.RESEARCHER, "A", 0.9),
        Role.CODER: agent(Role.CODER, "B", 0.4),
    }, quorum=2)
    result = swarm.run("pick")
    assert result.consensus is False
    assert result.answer == "A"


def test_single_role_is_non_consensus() -> None:
    swarm = TypedSwarm({Role.RESEARCHER: agent(Role.RESEARCHER, "only")}, quorum=2)
    result = swarm.run("pick")
    assert result.consensus is False
    assert result.answer == "only"
    assert result.rounds == 2


def test_low_confidence_cannot_reach_quorum() -> None:
    swarm = TypedSwarm({
        Role.RESEARCHER: agent(Role.RESEARCHER, "A", 0.2),
        Role.CODER: agent(Role.CODER, "A", 0.3),
    }, quorum=2, min_confidence=0.5)
    result = swarm.run("pick")
    assert result.consensus is False
    assert result.rounds == 2


def test_invalid_proposal_rejected() -> None:
    with pytest.raises(ValueError):
        Proposal(Role.CODER, "", 0.5)
    with pytest.raises(ValueError):
        Proposal(Role.CODER, "x", 1.2)
