from __future__ import annotations

import functools
import random
from typing import Any

from .poker_eval import HandStrength, best_of_7, rank_5, _compare_hand_strength


def _current_made_hand(hole_cards: list[str], board_cards: list[str]) -> HandStrength:
    cards = hole_cards + board_cards
    if len(cards) >= 5:
        # Best 5-card hand from available known cards.
        best: HandStrength | None = None
        import itertools

        for combo in itertools.combinations(cards, 5):
            hs = rank_5(list(combo))
            if best is None:
                best = hs
            else:
                # compare via tuple of (category_index, rank)
                order = {
                    "high_card": 0,
                    "pair": 1,
                    "two_pair": 2,
                    "three_of_a_kind": 3,
                    "straight": 4,
                    "flush": 5,
                    "full_house": 6,
                    "four_of_a_kind": 7,
                    "straight_flush": 8,
                }
                a = (order[hs.category], hs.rank)
                b = (order[best.category], best.rank)
                if a > b:
                    best = hs
        assert best is not None
        return best

    # Not enough cards for a real 5-card evaluation.
    # Return a simple high-card snapshot.
    ranks = []
    for c in cards:
        r = c[0]
        ranks.append("23456789TJQKA".index(r) + 2)
    ranks.sort(reverse=True)
    return HandStrength(category="high_card", rank=tuple(ranks))


def _make_deck_excluding(exclude: set[str]) -> list[str]:
    ranks = "23456789TJQKA"
    suits = "cdhs"
    deck = [r + s for r in ranks for s in suits]
    return [c for c in deck if c not in exclude]


@functools.lru_cache(maxsize=50_000)
def _equity_cached(
    hole: tuple[str, str],
    board: tuple[str, ...],
    opponents: int,
    samples: int,
    seed: int,
) -> float:
    if opponents <= 0:
        return 1.0
    known = set(hole) | set(board)
    deck = _make_deck_excluding(known)
    rng = random.Random(seed)

    wins = 0.0
    need_board = 5 - len(board)
    # Pre-compute how many cards we need per sample
    cards_per_sample = need_board + opponents * 2
    
    for _ in range(samples):
        # Use sample() instead of shuffle() - only pick what we need
        drawn = rng.sample(deck, cards_per_sample)
        
        runout = list(board) + drawn[:need_board]
        hero7 = tuple(hole) + tuple(runout)
        hero_best = best_of_7(hero7)

        hero_beats_all = True
        hero_ties = True
        idx = need_board
        for _ in range(opponents):
            opp_hole = (drawn[idx], drawn[idx + 1])
            idx += 2
            opp7 = opp_hole + tuple(runout)
            opp_best = best_of_7(opp7)
            
            cmp = _compare_hand_strength(hero_best, opp_best)
            if cmp < 0:
                hero_beats_all = False
                hero_ties = False
                break
            if cmp != 0:
                hero_ties = False

        if hero_beats_all and not hero_ties:
            wins += 1.0
        elif hero_beats_all and hero_ties:
            wins += 0.5

    return float(wins / samples) if samples > 0 else 0.0


def estimate_equity(
    hole_cards: list[str],
    board_cards: list[str],
    opponents: int,
    *,
    seed: int,
    samples: int = 100,
) -> float:
    """Estimate win equity via Monte Carlo simulation.
    
    100 samples provides a reasonable estimate with ~3-5% standard error,
    sufficient for bot decision-making while keeping computation fast.
    """
    if len(hole_cards) != 2:
        return 0.0
    return _equity_cached(tuple(hole_cards), tuple(board_cards), opponents, samples, seed)


def make_bot_visible_state(
    *,
    seed: int,
    street: str,
    dealer_seat: int,
    actor_seat: int,
    hole_cards: list[str],
    board_cards: list[str],
    stacks: list[int],
    contributed_this_street: list[int],
    contributed_total: list[int],
    action_history: list[dict[str, Any]],
    legal_actions: list[dict[str, Any]],
    active_seats: list[int],
    equity_samples: int = 100,
) -> dict[str, Any]:
    pot = int(sum(contributed_total))
    made = _current_made_hand(hole_cards, board_cards)

    opp = max(0, len([s for s in active_seats if s != actor_seat]))
    equity = estimate_equity(hole_cards, board_cards, opp, seed=seed + actor_seat * 101, samples=equity_samples)

    return {
        "hand_id": f"hand-{seed}",
        "street": street,
        "actor_seat": actor_seat,
        "dealer_seat": dealer_seat,
        "hole_cards": hole_cards,
        "board_cards": board_cards,
        "stacks": stacks,
        "contributed_this_street": contributed_this_street,
        "contributed_total": contributed_total,
        "pot": pot,
        "side_pots": [],
        "action_history": action_history,
        "legal_actions": legal_actions,
        "hand_strength": {
            "category": made.category,
            "rank": list(made.rank),
            "equity_estimate": equity,
        },
    }


def normalize_action(action: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any] | None]:
    if not isinstance(action, dict) or "type" not in action:
        return False, "Action must be a dict with key `type`.", None

    t = action.get("type")
    if t in ("fold", "check", "call"):
        return True, None, {"type": t}

    if t == "raise":
        amt = action.get("amount")
        if not isinstance(amt, int) or amt <= 0:
            return False, "Raise action must include positive integer `amount`.", None
        return True, None, {"type": "raise", "amount": int(amt)}

    return False, f"Unknown action type: {t}", None
