from __future__ import annotations

from dataclasses import dataclass

from .engine import HandResult, TableConfig, simulate_hand


@dataclass(frozen=True)
class MatchConfig:
    hands: int = 50
    seats: int = 6
    starting_stack: int = 1000
    small_blind: int = 10
    big_blind: int = 20


@dataclass(frozen=True)
class MatchResult:
    seed: int
    hands: int
    seats: int
    final_stacks: list[int]
    chips_won: list[int]
    hand_results: list[HandResult]


def run_match(
    *,
    bot_codes: list[str],
    seed: int,
    match_config: MatchConfig,
    bot_decide,
    make_state_for_actor,
) -> MatchResult:
    if len(bot_codes) != match_config.seats:
        raise ValueError("bot_codes length must equal match_config.seats")

    cfg = TableConfig(
        seats=match_config.seats,
        starting_stack=match_config.starting_stack,
        small_blind=match_config.small_blind,
        big_blind=match_config.big_blind,
    )

    stacks = [cfg.starting_stack for _ in range(cfg.seats)]
    dealer = 0
    hands: list[HandResult] = []

    for h in range(match_config.hands):
        hand_seed = seed + h * 10_007
        hr = simulate_hand(
            bot_codes,
            seed=hand_seed,
            config=cfg,
            dealer_seat=dealer,
            initial_stacks=stacks,
            bot_decide=bot_decide,
            make_state_for_actor=make_state_for_actor,
        )
        hands.append(hr)
        stacks = hr.final_stacks
        dealer = (dealer + 1) % cfg.seats

    chips_won = [stacks[i] - cfg.starting_stack for i in range(cfg.seats)]
    return MatchResult(
        seed=seed,
        hands=match_config.hands,
        seats=match_config.seats,
        final_stacks=stacks,
        chips_won=chips_won,
        hand_results=hands,
    )
