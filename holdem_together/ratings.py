from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class EloConfig:
    k_factor: float = 24.0


def _expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def update_elo_pairwise(
    ratings: list[float],
    scores: list[float],
    *,
    cfg: EloConfig | None = None,
) -> list[float]:
    """Update ratings from a multi-player result via pairwise Elo.

    `scores` should be higher-is-better (e.g., chips won). Ties are supported.

    Returns new ratings list.
    """

    if cfg is None:
        cfg = EloConfig()
    if len(ratings) != len(scores):
        raise ValueError("ratings and scores must have same length")

    n = len(ratings)
    new = list(ratings)

    # Pairwise updates. To reduce order dependence, accumulate deltas then apply.
    deltas = [0.0 for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if scores[i] > scores[j]:
                s_i, s_j = 1.0, 0.0
            elif scores[i] < scores[j]:
                s_i, s_j = 0.0, 1.0
            else:
                s_i, s_j = 0.5, 0.5

            e_i = _expected_score(new[i], new[j])
            e_j = 1.0 - e_i

            deltas[i] += cfg.k_factor * (s_i - e_i)
            deltas[j] += cfg.k_factor * (s_j - e_j)

    # Normalize by opponents count so k_factor remains meaningful with variable table size.
    denom = max(1.0, float(n - 1))
    return [float(new[i] + deltas[i] / denom) for i in range(n)]


def clamp_rating(r: float) -> float:
    if math.isnan(r) or math.isinf(r):
        return 1500.0
    return float(max(100.0, min(4000.0, r)))
