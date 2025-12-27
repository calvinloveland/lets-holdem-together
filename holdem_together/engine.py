from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from .game_state import normalize_action
from .poker_eval import best_of_7, compare_best_of_7


@dataclass(frozen=True)
class TableConfig:
    seats: int = 6
    starting_stack: int = 1000
    small_blind: int = 10
    big_blind: int = 20
    max_actions_per_street: int = 200


@dataclass
class PlayerState:
    stack: int
    folded: bool = False
    all_in: bool = False
    hole_cards: list[str] | None = None


@dataclass
class HandResult:
    seed: int
    dealer_seat: int
    board: list[str]
    hole_cards: list[list[str] | None]
    actions: list[dict[str, Any]]
    delta_stacks: list[int]
    final_stacks: list[int]
    winners: list[int]
    side_pots: list[dict[str, Any]]


def _make_deck() -> list[str]:
    ranks = "23456789TJQKA"
    suits = "cdhs"
    return [r + s for r in ranks for s in suits]


def _next_active_seat(seats: int, start: int, is_active) -> int | None:
    for i in range(1, seats + 1):
        s = (start + i) % seats
        if is_active(s):
            return s
    return None


def _iter_order(seats: int, start: int):
    for i in range(seats):
        yield (start + i) % seats


def _count_in_hand(players: list[PlayerState]) -> int:
    return sum(1 for p in players if not p.folded and (p.hole_cards is not None))


def _compute_side_pots(contrib_total: list[int], eligible: list[bool]) -> list[dict[str, Any]]:
    # Standard side pot construction.
    # contrib_total includes folded players (their chips stay in pots),
    # eligible marks who can win (not folded).
    levels = sorted({c for c in contrib_total if c > 0})
    pots: list[dict[str, Any]] = []
    prev = 0
    for lvl in levels:
        involved = [i for i, c in enumerate(contrib_total) if c >= lvl]
        if not involved:
            continue
        size = (lvl - prev) * len(involved)
        elig = [i for i in involved if eligible[i]]
        pots.append({"amount": size, "eligible_seats": elig})
        prev = lvl
    return pots


def simulate_hand(
    bot_codes: list[str],
    seed: int,
    config: TableConfig | None = None,
    dealer_seat: int = 0,
    initial_stacks: list[int] | None = None,
    bot_decide=None,
    make_state_for_actor=None,
) -> HandResult:
    """Simulate a single multi-player no-limit Hold'em hand.

    This engine is intentionally minimal but real:
    - blinds
    - betting rounds with fold/check/call/raise
    - all-in and side pots
    - showdown via 7-card evaluator

    `bot_decide(code, game_state) -> dict` and `make_state_for_actor(...) -> dict`
    are injected by the web layer so we can keep this module pure.
    """

    if config is None:
        config = TableConfig(seats=len(bot_codes))
    if len(bot_codes) != config.seats:
        raise ValueError("bot_codes length must equal config.seats")

    rng = random.Random(seed)
    deck = _make_deck()
    rng.shuffle(deck)

    if initial_stacks is None:
        initial_stacks = [config.starting_stack for _ in range(config.seats)]
    if len(initial_stacks) != config.seats:
        raise ValueError("initial_stacks length must equal config.seats")

    players = [PlayerState(stack=int(initial_stacks[i])) for i in range(config.seats)]

    # Deal hole cards.
    for seat in range(config.seats):
        players[seat].hole_cards = [deck.pop(), deck.pop()]

    actions: list[dict[str, Any]] = []
    contrib_total = [0 for _ in range(config.seats)]

    def post_blind(seat: int, kind: str, amount: int) -> None:
        pay = min(amount, players[seat].stack)
        players[seat].stack -= pay
        contrib_total[seat] += pay
        if players[seat].stack == 0:
            players[seat].all_in = True
        actions.append({"street": "preflop", "seat": seat, "type": kind, "amount": pay})

    # Blinds
    sb_seat = _next_active_seat(config.seats, dealer_seat, lambda s: players[s].stack > 0)
    bb_seat = None if sb_seat is None else _next_active_seat(config.seats, sb_seat, lambda s: players[s].stack > 0)

    if sb_seat is None or bb_seat is None:
        # everyone busted except one
        final_stacks = [p.stack for p in players]
        return HandResult(
            seed=seed,
            dealer_seat=dealer_seat,
            board=[],
            hole_cards=[p.hole_cards for p in players],
            actions=actions,
            delta_stacks=[0 for _ in players],
            final_stacks=final_stacks,
            winners=[i for i, p in enumerate(players) if p.stack > 0],
            side_pots=[],
        )

    post_blind(sb_seat, "post_sb", config.small_blind)
    post_blind(bb_seat, "post_bb", config.big_blind)

    board: list[str] = []

    def betting_round(street: str, first_to_act: int, initial_bet: int, initial_last_raise: int) -> None:
        nonlocal actions

        contributed_street = [0 for _ in range(config.seats)]
        # initialize with blinds already in contrib_total during preflop
        if street == "preflop":
            contributed_street[sb_seat] = min(config.small_blind, config.starting_stack)
            contributed_street[bb_seat] = min(config.big_blind, config.starting_stack)

        current_bet = initial_bet
        last_raise = initial_last_raise

        acted_since_raise = [False for _ in range(config.seats)]

        def in_hand(seat: int) -> bool:
            p = players[seat]
            return (not p.folded) and (p.hole_cards is not None) and (not p.all_in)

        # Preflop special: big blind should be allowed to act if no raise.
        # We'll treat the blind posters as not yet acted.

        idx = first_to_act
        action_count = 0
        while True:
            if _count_in_hand(players) <= 1:
                return

            # End condition: everyone who can act has acted, and all bets are matched.
            all_matched = True
            all_acted = True
            for s in range(config.seats):
                p = players[s]
                if p.folded or p.hole_cards is None:
                    continue
                if not p.all_in:
                    if contributed_street[s] != current_bet:
                        all_matched = False
                    if not acted_since_raise[s]:
                        all_acted = False
            if all_matched and all_acted:
                return

            # Find next seat who can act.
            seat = None
            for _ in range(config.seats):
                if in_hand(idx):
                    seat = idx
                    break
                idx = (idx + 1) % config.seats
            if seat is None:
                return

            to_call = max(0, current_bet - contributed_street[seat])
            p = players[seat]

            legal: list[dict[str, Any]] = [{"type": "fold"}]
            if to_call == 0:
                legal.append({"type": "check"})
            else:
                legal.append({"type": "call", "amount": min(to_call, p.stack)})

            if p.stack > to_call:
                min_total = current_bet + max(last_raise, config.big_blind) if current_bet > 0 else config.big_blind
                min_total = max(min_total, current_bet + 1)
                max_total = contributed_street[seat] + p.stack
                if max_total >= min_total:
                    legal.append({"type": "raise", "min": int(min_total), "max": int(max_total)})

            if bot_decide is None or make_state_for_actor is None:
                raise ValueError("bot_decide and make_state_for_actor must be provided")

            game_state = make_state_for_actor(
                seed=seed,
                street=street,
                dealer_seat=dealer_seat,
                actor_seat=seat,
                hole_cards=players[seat].hole_cards or [],
                board_cards=board,
                stacks=[pl.stack for pl in players],
                contributed_this_street=contributed_street,
                contributed_total=contrib_total,
                action_history=actions,
                legal_actions=legal,
                active_seats=[i for i, pl in enumerate(players) if (not pl.folded) and (pl.hole_cards is not None)],
            )

            raw_action = bot_decide(bot_codes[seat], game_state)
            ok, _, norm = normalize_action(raw_action)
            if not ok or norm is None:
                norm = {"type": "check"} if to_call == 0 else {"type": "call"}

            atype = norm["type"]

            def apply_call() -> None:
                nonlocal to_call
                pay = min(to_call, p.stack)
                p.stack -= pay
                contributed_street[seat] += pay
                contrib_total[seat] += pay
                if p.stack == 0:
                    p.all_in = True
                actions.append({"street": street, "seat": seat, "type": "call", "amount": pay})

            if atype == "fold":
                p.folded = True
                acted_since_raise[seat] = True
                actions.append({"street": street, "seat": seat, "type": "fold"})
            elif atype == "check":
                if to_call != 0:
                    apply_call()
                else:
                    acted_since_raise[seat] = True
                    actions.append({"street": street, "seat": seat, "type": "check"})
            elif atype == "call":
                apply_call()
                acted_since_raise[seat] = True
            elif atype == "raise":
                # amount is interpreted as total contribution for this street
                raise_to_req = int(norm.get("amount", 0))
                # clamp to legal
                ra = next((a for a in legal if a["type"] == "raise"), None)
                if ra is None:
                    apply_call() if to_call > 0 else actions.append({"street": street, "seat": seat, "type": "check"})
                    acted_since_raise[seat] = True
                else:
                    raise_to = max(int(ra["min"]), min(int(ra["max"]), raise_to_req))
                    if raise_to <= current_bet:
                        raise_to = int(ra["min"])
                    pay = raise_to - contributed_street[seat]
                    pay = min(pay, p.stack)
                    prev_bet = current_bet
                    p.stack -= pay
                    contributed_street[seat] += pay
                    contrib_total[seat] += pay
                    current_bet = max(current_bet, contributed_street[seat])
                    last_raise = max(1, current_bet - prev_bet)
                    if p.stack == 0:
                        p.all_in = True
                    # reset acted flags
                    for s in range(config.seats):
                        acted_since_raise[s] = False
                    acted_since_raise[seat] = True
                    actions.append(
                        {"street": street, "seat": seat, "type": "raise", "to": current_bet, "amount": pay}
                    )
            else:
                # fallback
                if to_call == 0:
                    actions.append({"street": street, "seat": seat, "type": "check"})
                else:
                    apply_call()
                acted_since_raise[seat] = True

            action_count += 1
            if action_count >= config.max_actions_per_street:
                # Force-close the round to prevent infinite loops.
                return

            idx = (seat + 1) % config.seats

    # Determine first to act preflop: left of big blind.
    first_preflop = _next_active_seat(config.seats, bb_seat, lambda s: not players[s].folded)
    assert first_preflop is not None

    betting_round("preflop", first_preflop, initial_bet=config.big_blind, initial_last_raise=config.big_blind)

    def deal_board(n: int) -> None:
        # burn 1
        deck.pop()
        for _ in range(n):
            board.append(deck.pop())

    # If hand not ended, run flop/turn/river.
    if _count_in_hand(players) > 1:
        deal_board(3)
        first_postflop = _next_active_seat(config.seats, dealer_seat, lambda s: not players[s].folded and not players[s].all_in)
        if first_postflop is not None:
            betting_round("flop", first_postflop, initial_bet=0, initial_last_raise=config.big_blind)

    if _count_in_hand(players) > 1:
        deal_board(1)
        first_postflop = _next_active_seat(config.seats, dealer_seat, lambda s: not players[s].folded and not players[s].all_in)
        if first_postflop is not None:
            betting_round("turn", first_postflop, initial_bet=0, initial_last_raise=config.big_blind)

    if _count_in_hand(players) > 1:
        deal_board(1)
        first_postflop = _next_active_seat(config.seats, dealer_seat, lambda s: not players[s].folded and not players[s].all_in)
        if first_postflop is not None:
            betting_round("river", first_postflop, initial_bet=0, initial_last_raise=config.big_blind)

    # Award pots.
    eligible = [(not p.folded) and (p.hole_cards is not None) for p in players]
    pot_total = sum(contrib_total)

    # If everyone but one folded, give entire pot to remaining.
    remaining = [i for i, ok in enumerate(eligible) if ok]
    winners: list[int] = []
    side_pots = _compute_side_pots(contrib_total, eligible)

    if len(remaining) == 1:
        w = remaining[0]
        players[w].stack += pot_total
        winners = [w]
    else:
        # showdown: compare best_of_7 among eligible
        # Build 7-card sets
        board5 = board + [deck.pop() for _ in range(max(0, 5 - len(board)))]  # safety; should be 5
        board5 = board5[:5]

        def best_for(seat: int) -> list[str]:
            hc = players[seat].hole_cards or []
            return hc + board5

        # Award each side pot separately.
        for pot in side_pots:
            elig_seats = pot["eligible_seats"]
            if not elig_seats:
                continue
            best = elig_seats[0]
            tied = [best]
            for s in elig_seats[1:]:
                cmp = compare_best_of_7(best_for(s), best_for(best))
                if cmp > 0:
                    best = s
                    tied = [s]
                elif cmp == 0:
                    tied.append(s)
            share = pot["amount"] // len(tied)
            rem = pot["amount"] % len(tied)
            for i, s in enumerate(tied):
                players[s].stack += share + (1 if i < rem else 0)
            pot["winner_seats"] = tied

        # winners = those with most chips gained this hand among eligible
        winners = [i for i, ok in enumerate(eligible) if ok]

    final_stacks = [p.stack for p in players]
    delta = [final_stacks[i] - int(initial_stacks[i]) for i in range(config.seats)]

    return HandResult(
        seed=seed,
        dealer_seat=dealer_seat,
        board=board,
        hole_cards=[p.hole_cards for p in players],
        actions=actions,
        delta_stacks=delta,
        final_stacks=final_stacks,
        winners=winners,
        side_pots=side_pots,
    )
