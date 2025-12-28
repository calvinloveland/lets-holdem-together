from __future__ import annotations

import functools
import itertools
from dataclasses import dataclass

RANKS = "23456789TJQKA"
SUITS = "cdhs"  # clubs, diamonds, hearts, spades

# Pre-computed lookup tables for speed
_RANK_VALUES = {r: i + 2 for i, r in enumerate(RANKS)}
_VALID_SUITS = frozenset(SUITS)


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

# Pre-compute category ordering for comparisons
_CATEGORY_ORDER = {cat: i for i, cat in enumerate(_CATEGORY)}


def _rank_value(r: str) -> int:
    return _RANK_VALUES[r]


# Pre-compute all 52 card parses
_CARD_CACHE: dict[str, tuple[int, str]] = {}
for _r in RANKS:
    for _s in SUITS:
        _card = _r + _s
        _CARD_CACHE[_card] = (_RANK_VALUES[_r], _s)


def parse_card(card: str) -> tuple[int, str]:
    result = _CARD_CACHE.get(card)
    if result is not None:
        return result
    raise ValueError(f"Invalid card: {card}")


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


@functools.lru_cache(maxsize=500_000)
def _rank_5_cached(cards: tuple[str, ...]) -> HandStrength:
    parsed = [_CARD_CACHE[c] for c in cards]
    ranks = sorted((r for r, _ in parsed), reverse=True)
    suits = [s for _, s in parsed]
    is_flush = suits[0] == suits[1] == suits[2] == suits[3] == suits[4]

    counts: dict[int, int] = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1

    groups = sorted(((cnt, r) for r, cnt in counts.items()), reverse=True)
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


def rank_5(cards: list[str]) -> HandStrength:
    # Use cached version with tuple
    return _rank_5_cached(tuple(sorted(cards)))


@functools.lru_cache(maxsize=100_000)
def _best_of_7_cached(cards7: tuple[str, ...]) -> HandStrength:
    if len(cards7) != 7:
        raise ValueError("best_of_7 requires 7 cards")
    best: HandStrength | None = None
    best_rank: tuple[int, tuple[int, ...]] | None = None
    
    for combo in itertools.combinations(cards7, 5):
        hs = _rank_5_cached(tuple(sorted(combo)))
        hs_rank = (_CATEGORY_ORDER[hs.category], hs.rank)
        if best_rank is None or hs_rank > best_rank:
            best = hs
            best_rank = hs_rank
    assert best is not None
    return best


def best_of_7(cards7: tuple[str, ...] | list[str]) -> HandStrength:
    if isinstance(cards7, list):
        cards7 = tuple(cards7)
    return _best_of_7_cached(cards7)


def _compare_hand_strength(a: HandStrength, b: HandStrength) -> int:
    ai = _CATEGORY_ORDER[a.category]
    bi = _CATEGORY_ORDER[b.category]
    if ai != bi:
        return 1 if ai > bi else -1
    if a.rank != b.rank:
        return 1 if a.rank > b.rank else -1
    return 0


def compare_best_of_7(cards7_a: list[str], cards7_b: list[str]) -> int:
    return _compare_hand_strength(best_of_7(cards7_a), best_of_7(cards7_b))
