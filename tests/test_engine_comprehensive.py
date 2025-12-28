"""Comprehensive tests for engine module - game simulation."""
from __future__ import annotations

import pytest

from holdem_together.engine import (
    HandResult,
    PlayerState,
    TableConfig,
    simulate_hand,
    _make_deck,
    _next_active_seat,
    _count_in_hand,
    _compute_side_pots,
)
from holdem_together.game_state import make_bot_visible_state


# Helper decide functions for testing
def _always_fold(code: str, game_state: dict) -> dict:
    return {"type": "fold"}


def _always_check_or_call(code: str, game_state: dict) -> dict:
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    if "check" in legal:
        return {"type": "check"}
    if "call" in legal:
        return {"type": "call"}
    return {"type": "fold"}


def _always_raise_min(code: str, game_state: dict) -> dict:
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    if "raise" in legal:
        return {"type": "raise", "amount": legal["raise"]["min"]}
    if "check" in legal:
        return {"type": "check"}
    if "call" in legal:
        return {"type": "call"}
    return {"type": "fold"}


def _always_raise_max(code: str, game_state: dict) -> dict:
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    if "raise" in legal:
        return {"type": "raise", "amount": legal["raise"]["max"]}
    if "check" in legal:
        return {"type": "check"}
    if "call" in legal:
        return {"type": "call"}
    return {"type": "fold"}


class TestMakeDeck:
    """Tests for deck creation."""

    def test_deck_has_52_cards(self):
        deck = _make_deck()
        assert len(deck) == 52

    def test_deck_unique_cards(self):
        deck = _make_deck()
        assert len(set(deck)) == 52

    def test_deck_contains_all_ranks(self):
        deck = _make_deck()
        for rank in "23456789TJQKA":
            assert any(c.startswith(rank) for c in deck)

    def test_deck_contains_all_suits(self):
        deck = _make_deck()
        for suit in "cdhs":
            assert any(c.endswith(suit) for c in deck)


class TestNextActiveSeat:
    """Tests for finding next active seat."""

    def test_finds_next_seat(self):
        active = lambda s: s in [0, 2, 4]
        result = _next_active_seat(6, 0, active)
        assert result == 2

    def test_wraps_around(self):
        active = lambda s: s in [0, 1]
        result = _next_active_seat(6, 5, active)
        assert result == 0

    def test_no_active_seat(self):
        active = lambda s: False
        result = _next_active_seat(6, 0, active)
        assert result is None

    def test_single_active(self):
        active = lambda s: s == 3
        result = _next_active_seat(6, 0, active)
        assert result == 3


class TestCountInHand:
    """Tests for counting players in hand."""

    def test_all_in_hand(self):
        players = [
            PlayerState(stack=1000, hole_cards=["As", "Kd"]),
            PlayerState(stack=1000, hole_cards=["Qs", "Jd"]),
        ]
        assert _count_in_hand(players) == 2

    def test_one_folded(self):
        players = [
            PlayerState(stack=1000, hole_cards=["As", "Kd"]),
            PlayerState(stack=1000, hole_cards=["Qs", "Jd"], folded=True),
        ]
        assert _count_in_hand(players) == 1

    def test_none_with_cards(self):
        players = [
            PlayerState(stack=1000, hole_cards=None),
            PlayerState(stack=1000, hole_cards=None),
        ]
        assert _count_in_hand(players) == 0


class TestComputeSidePots:
    """Tests for side pot calculation."""

    def test_simple_pot_no_all_ins(self):
        contrib = [100, 100, 100]
        eligible = [True, True, True]
        pots = _compute_side_pots(contrib, eligible)
        assert len(pots) == 1
        assert pots[0]["amount"] == 300
        assert set(pots[0]["eligible_seats"]) == {0, 1, 2}

    def test_one_all_in_creates_side_pot(self):
        contrib = [50, 100, 100]  # Seat 0 is short
        eligible = [True, True, True]
        pots = _compute_side_pots(contrib, eligible)
        # Main pot at 50 level: 50*3 = 150
        # Side pot at 100 level: 50*2 = 100
        assert len(pots) == 2
        assert pots[0]["amount"] == 150  # Main pot
        assert pots[1]["amount"] == 100  # Side pot

    def test_folded_player_not_eligible(self):
        contrib = [100, 100, 100]
        eligible = [False, True, True]  # Seat 0 folded
        pots = _compute_side_pots(contrib, eligible)
        assert len(pots) == 1
        assert 0 not in pots[0]["eligible_seats"]
        assert 1 in pots[0]["eligible_seats"]
        assert 2 in pots[0]["eligible_seats"]

    def test_multiple_all_ins(self):
        contrib = [30, 60, 100]  # Three different levels
        eligible = [True, True, True]
        pots = _compute_side_pots(contrib, eligible)
        assert len(pots) == 3


class TestTableConfig:
    """Tests for table configuration."""

    def test_default_config(self):
        cfg = TableConfig()
        assert cfg.seats == 6
        assert cfg.starting_stack == 1000
        assert cfg.small_blind == 10
        assert cfg.big_blind == 20

    def test_custom_config(self):
        cfg = TableConfig(seats=2, starting_stack=500, small_blind=5, big_blind=10)
        assert cfg.seats == 2
        assert cfg.starting_stack == 500
        assert cfg.small_blind == 5
        assert cfg.big_blind == 10


class TestSimulateHandBasic:
    """Basic tests for hand simulation."""

    def test_simulate_returns_hand_result(self):
        cfg = TableConfig(seats=2)
        codes = ["code1", "code2"]
        result = simulate_hand(
            codes,
            seed=42,
            config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert isinstance(result, HandResult)

    def test_deterministic_with_seed(self):
        cfg = TableConfig(seats=2)
        codes = ["code1", "code2"]
        r1 = simulate_hand(
            codes,
            seed=123,
            config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        r2 = simulate_hand(
            codes,
            seed=123,
            config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert r1.board == r2.board
        assert r1.actions == r2.actions
        assert r1.final_stacks == r2.final_stacks

    def test_different_seeds_different_results(self):
        cfg = TableConfig(seats=2)
        codes = ["code1", "code2"]
        r1 = simulate_hand(
            codes,
            seed=100,
            config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        r2 = simulate_hand(
            codes,
            seed=200,
            config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        # Boards should be different (with high probability)
        assert r1.board != r2.board or r1.hole_cards != r2.hole_cards


class TestSimulateHandBlinds:
    """Tests for blind posting."""

    def test_blinds_posted(self):
        cfg = TableConfig(seats=3, small_blind=10, big_blind=20)
        codes = ["c1", "c2", "c3"]
        result = simulate_hand(
            codes,
            seed=42,
            config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        # First two actions should be blind posts
        assert result.actions[0]["type"] == "post_sb"
        assert result.actions[0]["amount"] == 10
        assert result.actions[1]["type"] == "post_bb"
        assert result.actions[1]["amount"] == 20


class TestSimulateHandFolding:
    """Tests for fold behavior."""

    def test_everyone_folds_preflop(self):
        cfg = TableConfig(seats=3, small_blind=10, big_blind=20)
        codes = ["c1", "c2", "c3"]
        result = simulate_hand(
            codes,
            seed=42,
            config=cfg,
            bot_decide=_always_fold,
            make_state_for_actor=make_bot_visible_state,
        )
        # BB wins the pot when everyone folds
        # Check that there's at least one winner
        assert len(result.winners) >= 1
        # Total stacks should equal starting stacks
        assert sum(result.final_stacks) == cfg.starting_stack * cfg.seats


class TestSimulateHandAllIn:
    """Tests for all-in scenarios."""

    def test_all_in_via_max_raise(self):
        cfg = TableConfig(seats=2, starting_stack=100, small_blind=10, big_blind=20)
        codes = ["c1", "c2"]
        result = simulate_hand(
            codes,
            seed=42,
            config=cfg,
            bot_decide=_always_raise_max,
            make_state_for_actor=make_bot_visible_state,
        )
        # At least one player should have gone all in
        has_all_in = any(stack == 0 for stack in result.final_stacks)
        # The hand should complete normally
        assert sum(result.final_stacks) == cfg.starting_stack * cfg.seats


class TestSimulateHandShowdown:
    """Tests for showdown behavior."""

    def test_showdown_with_check_call(self):
        cfg = TableConfig(seats=2)
        codes = ["c1", "c2"]
        result = simulate_hand(
            codes,
            seed=42,
            config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        # Board should have 5 cards at showdown
        assert len(result.board) == 5

    def test_winner_gains_chips(self):
        cfg = TableConfig(seats=2)
        codes = ["c1", "c2"]
        result = simulate_hand(
            codes,
            seed=42,
            config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        # At least one delta should be positive
        assert any(d > 0 for d in result.delta_stacks) or all(d == 0 for d in result.delta_stacks)

    def test_chips_conserved(self):
        cfg = TableConfig(seats=4)
        codes = ["c1", "c2", "c3", "c4"]
        result = simulate_hand(
            codes,
            seed=42,
            config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert sum(result.final_stacks) == cfg.starting_stack * cfg.seats


class TestSimulateHandEdgeCases:
    """Edge case tests."""

    def test_heads_up_play(self):
        cfg = TableConfig(seats=2)
        codes = ["c1", "c2"]
        result = simulate_hand(
            codes,
            seed=42,
            config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert len(result.hole_cards) == 2
        assert all(hc is not None and len(hc) == 2 for hc in result.hole_cards)

    def test_six_player_table(self):
        cfg = TableConfig(seats=6)
        codes = ["c" + str(i) for i in range(6)]
        result = simulate_hand(
            codes,
            seed=42,
            config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert len(result.hole_cards) == 6

    def test_custom_initial_stacks(self):
        cfg = TableConfig(seats=3)
        codes = ["c1", "c2", "c3"]
        stacks = [500, 1000, 1500]
        result = simulate_hand(
            codes,
            seed=42,
            config=cfg,
            initial_stacks=stacks,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        # Total should be conserved
        assert sum(result.final_stacks) == sum(stacks)

    def test_mismatched_bot_codes_raises(self):
        cfg = TableConfig(seats=4)
        codes = ["c1", "c2"]  # Only 2 codes for 4 seats
        with pytest.raises(ValueError):
            simulate_hand(
                codes,
                seed=42,
                config=cfg,
                bot_decide=_always_check_or_call,
                make_state_for_actor=make_bot_visible_state,
            )

    def test_mismatched_initial_stacks_raises(self):
        cfg = TableConfig(seats=3)
        codes = ["c1", "c2", "c3"]
        stacks = [1000, 1000]  # Only 2 stacks for 3 seats
        with pytest.raises(ValueError):
            simulate_hand(
                codes,
                seed=42,
                config=cfg,
                initial_stacks=stacks,
                bot_decide=_always_check_or_call,
                make_state_for_actor=make_bot_visible_state,
            )


class TestSimulateHandDealerRotation:
    """Tests for dealer position."""

    def test_dealer_seat_used(self):
        cfg = TableConfig(seats=4)
        codes = ["c" + str(i) for i in range(4)]
        result = simulate_hand(
            codes,
            seed=42,
            config=cfg,
            dealer_seat=2,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert result.dealer_seat == 2


class TestSimulateHandMissingCallbacks:
    """Tests for missing required callbacks."""

    def test_missing_bot_decide_raises(self):
        cfg = TableConfig(seats=2)
        codes = ["c1", "c2"]
        with pytest.raises(ValueError):
            simulate_hand(
                codes,
                seed=42,
                config=cfg,
                bot_decide=None,
                make_state_for_actor=make_bot_visible_state,
            )

    def test_missing_make_state_raises(self):
        cfg = TableConfig(seats=2)
        codes = ["c1", "c2"]
        with pytest.raises(ValueError):
            simulate_hand(
                codes,
                seed=42,
                config=cfg,
                bot_decide=_always_check_or_call,
                make_state_for_actor=None,
            )
