from __future__ import annotations

import itertools
from dataclasses import dataclass

RANKS = "23456789TJQKA"
SUITS = "cdhs"  # clubs, diamonds, hearts, spades


@dataclass(frozen=True)
class HandStrength:
    category: str
    rank: tuple[int, ...]


_CATEGORY = [
    "high_card",
    "pair",
    "two_pair",
    "three_of_a_kind",
    "straight",
    "flush",
    "full_house",
    "four_of_a_kind",
    "straight_flush",
]


def _rank_value(r: str) -> int:
    return RANKS.index(r) + 2


def parse_card(card: str) -> tuple[int, str]:
    if len(card) != 2:
        raise ValueError(f"Invalid card: {card}")
    r, s = card[0], card[1]
    if r not in RANKS or s not in SUITS:
        raise ValueError(f"Invalid card: {card}")
    return _rank_value(r), s


def _is_straight(ranks_desc: list[int]) -> tuple[bool, int]:
    # ranks_desc is unique ranks sorted desc
    if len(ranks_desc) < 5:
        return False, 0
    # wheel
    if ranks_desc[:4] == [14, 5, 4, 3] and 2 in ranks_desc:
        return True, 5
    for i in range(len(ranks_desc) - 4):
        window = ranks_desc[i : i + 5]
        if window[0] - window[4] == 4 and len(set(window)) == 5:
            return True, window[0]
    return False, 0


def rank_5(cards: list[str]) -> HandStrength:
    parsed = [parse_card(c) for c in cards]
    ranks = sorted((r for r, _ in parsed), reverse=True)
    suits = [s for _, s in parsed]
    is_flush = len(set(suits)) == 1

    counts = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1

    groups = sorted(((cnt, r) for r, cnt in counts.items()), reverse=True)
    # groups sorted by count then rank desc
    unique_ranks_desc = sorted(counts.keys(), reverse=True)
    is_straight, top = _is_straight(unique_ranks_desc)

    if is_flush and is_straight:
        return HandStrength("straight_flush", (top,))

    if groups[0][0] == 4:
        quad = groups[0][1]
        kicker = max(r for r in unique_ranks_desc if r != quad)
        return HandStrength("four_of_a_kind", (quad, kicker))

    if groups[0][0] == 3 and len(groups) > 1 and groups[1][0] >= 2:
        trips = groups[0][1]
        pair = max(r for cnt, r in groups[1:] if cnt >= 2)
        return HandStrength("full_house", (trips, pair))

    if is_flush:
        return HandStrength("flush", tuple(sorted(ranks, reverse=True)))

    if is_straight:
        return HandStrength("straight", (top,))

    if groups[0][0] == 3:
        trips = groups[0][1]
        kickers = sorted([r for r in unique_ranks_desc if r != trips], reverse=True)[:2]
        return HandStrength("three_of_a_kind", (trips, *kickers))

    if groups[0][0] == 2:
        pairs = sorted([r for cnt, r in groups if cnt == 2], reverse=True)
        if len(pairs) >= 2:
            hi, lo = pairs[0], pairs[1]
            kicker = max(r for r in unique_ranks_desc if r not in (hi, lo))
            return HandStrength("two_pair", (hi, lo, kicker))
        pair = pairs[0]
        kickers = sorted([r for r in unique_ranks_desc if r != pair], reverse=True)[:3]
        return HandStrength("pair", (pair, *kickers))

    return HandStrength("high_card", tuple(sorted(ranks, reverse=True)))


def best_of_7(cards7: list[str]) -> HandStrength:
    if len(cards7) != 7:
        raise ValueError("best_of_7 requires 7 cards")
    best: HandStrength | None = None
    for combo in itertools.combinations(cards7, 5):
        hs = rank_5(list(combo))
        if best is None:
            best = hs
            continue
        if _compare_hand_strength(hs, best) > 0:
            best = hs
    assert best is not None
    return best


def _compare_hand_strength(a: HandStrength, b: HandStrength) -> int:
    ai = _CATEGORY.index(a.category)
    bi = _CATEGORY.index(b.category)
    if ai != bi:
        return 1 if ai > bi else -1
    if a.rank != b.rank:
        return 1 if a.rank > b.rank else -1
    return 0


def compare_best_of_7(cards7_a: list[str], cards7_b: list[str]) -> int:
    return _compare_hand_strength(best_of_7(cards7_a), best_of_7(cards7_b))
