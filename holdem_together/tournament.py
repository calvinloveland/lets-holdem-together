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

    def next_dealer(current: int, stack_list: list[int]) -> int:
        """Find the next dealer seat, skipping busted players."""
        for i in range(1, cfg.seats + 1):
            candidate = (current + i) % cfg.seats
            if stack_list[candidate] > 0:
                return candidate
        # Fallback (shouldn't happen if game isn't over)
        return (current + 1) % cfg.seats

    for h in range(match_config.hands):
        # Check if only one player remains
        players_with_chips = sum(1 for s in stacks if s > 0)
        if players_with_chips <= 1:
            break
            
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
        dealer = next_dealer(dealer, stacks)

    chips_won = [stacks[i] - cfg.starting_stack for i in range(cfg.seats)]
    return MatchResult(
        seed=seed,
        hands=len(hands),  # Actual number of hands played (may end early if one player left)
        seats=match_config.seats,
        final_stacks=stacks,
        chips_won=chips_won,
        hand_results=hands,
    )
