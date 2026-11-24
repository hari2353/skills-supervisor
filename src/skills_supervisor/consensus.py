"""Self-consistency voting (Wang et al., 2022) for the consensus swarm.

Cross-pollinated from ucbrise/clipper's model-selection idea and the
self-consistency literature: sample several answers, then take the majority
vote instead of trusting a single greedy decode. Deterministic and offline.
"""

from __future__ import annotations

from collections import Counter


def _normalize(value: str, normalize) -> str:
    if normalize is None:
        return value
    return normalize(value)


def majority_vote(
    answers: list[str],
    *,
    normalize=None,
    weights: list[float] | None = None,
) -> dict:
    """Return the majority winner of ``answers`` with counts and agreement."""
    if not answers:
        raise ValueError("answers must be non-empty")
    if weights is not None and len(weights) != len(answers):
        raise ValueError("weights must match answers length")
    if weights is not None and any(w < 0 for w in weights):
        raise ValueError("weights must be >= 0")

    normalized = [_normalize(answer, normalize) for answer in answers]
    counts: Counter[str] = Counter()
    weight_by_key: dict[str, float] = {}
    for key, weight in zip(normalized, weights or [1.0] * len(answers)):
        counts[key] += 1
        weight_by_key[key] = weight_by_key.get(key, 0.0) + (weight if weights else 1.0)

    # Tie-break: highest weight, then highest count, then first occurrence.
    first_index = {key: normalized.index(key) for key in counts}
    winner = max(
        counts,
        key=lambda key: (weight_by_key[key], counts[key], -first_index[key]),
    )
    total_weight = sum(weights) if weights else float(len(answers))
    winner_weight = weight_by_key[winner]
    return {
        "winner": winner,
        "original": answers[normalized.index(winner)],
        "counts": dict(counts),
        "agreement": round(counts[winner] / len(answers), 4),
        "weight_share": round(winner_weight / total_weight, 4) if total_weight else 0.0,
        "total": len(answers),
    }


def self_consistency(samples: list[list[str]], *, threshold: float = 0.5) -> dict:
    """Vote over multiple sampled answer sets and report whether consensus holds."""
    if not samples or any(not sample for sample in samples):
        raise ValueError("samples must be a non-empty list of non-empty lists")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be in [0, 1]")
    votes = [majority_vote(sample)["winner"] for sample in samples]
    result = majority_vote(votes)
    result["consensus"] = result["agreement"] >= threshold
    return result
