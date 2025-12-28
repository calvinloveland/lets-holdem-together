"""Comprehensive tests for game_state module."""
from __future__ import annotations

import pytest

from holdem_together.game_state import (
    make_bot_visible_state,
    normalize_action,
    estimate_equity,
    _current_made_hand,
    _make_deck_excluding,
)


class TestMakeDeckExcluding:
    """Tests for deck creation with exclusions."""

    def test_full_deck_size(self):
        deck = _make_deck_excluding(set())
        assert len(deck) == 52

    def test_excluding_one_card(self):
        deck = _make_deck_excluding({"As"})
        assert len(deck) == 51
        assert "As" not in deck

    def test_excluding_multiple_cards(self):
        excluded = {"As", "Kd", "7h", "2c"}
        deck = _make_deck_excluding(excluded)
        assert len(deck) == 48
        for card in excluded:
            assert card not in deck

    def test_excluding_all_aces(self):
        aces = {"Ac", "Ad", "Ah", "As"}
        deck = _make_deck_excluding(aces)
        assert len(deck) == 48
        for ace in aces:
            assert ace not in deck


class TestCurrentMadeHand:
    """Tests for current hand evaluation."""

    def test_preflop_high_card(self):
        hand = _current_made_hand(["As", "Kd"], [])
        assert hand.category == "high_card"
        assert 14 in hand.rank  # Ace

    def test_flop_pair(self):
        hand = _current_made_hand(["As", "Kd"], ["Ac", "7h", "2s"])
        assert hand.category == "pair"
        assert hand.rank[0] == 14  # Pair of Aces

    def test_turn_two_pair(self):
        hand = _current_made_hand(["As", "Kd"], ["Ac", "Kh", "2s", "7c"])
        assert hand.category == "two_pair"

    def test_river_full_evaluation(self):
        hand = _current_made_hand(["As", "Ad"], ["Ac", "Kh", "Ks", "2c", "3d"])
        assert hand.category == "full_house"


class TestEstimateEquity:
    """Tests for equity estimation."""

    def test_pocket_aces_vs_one_opponent(self):
        equity = estimate_equity(["As", "Ad"], [], 1, seed=42, samples=100)
        # Pocket aces should have high equity
        assert 0.7 < equity < 1.0

    def test_no_opponents_full_equity(self):
        equity = estimate_equity(["As", "Ad"], [], 0, seed=42, samples=100)
        assert equity == 1.0

    def test_equity_is_deterministic_with_seed(self):
        eq1 = estimate_equity(["As", "Ad"], [], 1, seed=123, samples=50)
        eq2 = estimate_equity(["As", "Ad"], [], 1, seed=123, samples=50)
        assert eq1 == eq2

    def test_equity_decreases_with_opponents(self):
        eq_1 = estimate_equity(["As", "Ad"], [], 1, seed=42, samples=100)
        eq_3 = estimate_equity(["As", "Ad"], [], 3, seed=42, samples=100)
        assert eq_3 < eq_1

    def test_equity_on_flop(self):
        # AA on A-K-Q flop (set of aces) should be very high
        equity = estimate_equity(["As", "Ad"], ["Ac", "Kh", "Qs"], 1, seed=42, samples=100)
        assert equity > 0.9

    def test_invalid_hole_cards(self):
        equity = estimate_equity(["As"], [], 1, seed=42, samples=100)
        assert equity == 0.0

    def test_empty_hole_cards(self):
        equity = estimate_equity([], [], 1, seed=42, samples=100)
        assert equity == 0.0


class TestNormalizeAction:
    """Tests for action normalization."""

    def test_fold_action(self):
        ok, err, norm = normalize_action({"type": "fold"})
        assert ok
        assert err is None
        assert norm == {"type": "fold"}

    def test_check_action(self):
        ok, err, norm = normalize_action({"type": "check"})
        assert ok
        assert err is None
        assert norm == {"type": "check"}

    def test_call_action(self):
        ok, err, norm = normalize_action({"type": "call"})
        assert ok
        assert err is None
        assert norm == {"type": "call"}

    def test_raise_with_amount(self):
        ok, err, norm = normalize_action({"type": "raise", "amount": 100})
        assert ok
        assert err is None
        assert norm == {"type": "raise", "amount": 100}

    def test_raise_without_amount_fails(self):
        ok, err, norm = normalize_action({"type": "raise"})
        assert not ok
        assert "amount" in err.lower()
        assert norm is None

    def test_raise_with_zero_amount_fails(self):
        ok, err, norm = normalize_action({"type": "raise", "amount": 0})
        assert not ok
        assert norm is None

    def test_raise_with_negative_amount_fails(self):
        ok, err, norm = normalize_action({"type": "raise", "amount": -50})
        assert not ok
        assert norm is None

    def test_raise_with_float_amount_converts(self):
        ok, err, norm = normalize_action({"type": "raise", "amount": 100.5})
        # Should fail because not an integer
        assert not ok

    def test_unknown_action_type(self):
        ok, err, norm = normalize_action({"type": "all_in"})
        assert not ok
        assert "unknown" in err.lower()
        assert norm is None

    def test_missing_type_fails(self):
        ok, err, norm = normalize_action({"amount": 100})
        assert not ok
        assert norm is None

    def test_non_dict_fails(self):
        ok, err, norm = normalize_action("fold")
        assert not ok
        assert norm is None

    def test_none_fails(self):
        ok, err, norm = normalize_action(None)
        assert not ok
        assert norm is None


class TestMakeBotVisibleState:
    """Tests for creating bot-visible game state."""

    def test_basic_state_creation(self):
        state = make_bot_visible_state(
            seed=1,
            street="preflop",
            dealer_seat=0,
            actor_seat=1,
            hole_cards=["As", "Kd"],
            board_cards=[],
            stacks=[1000, 1000, 1000],
            contributed_this_street=[10, 20, 0],
            contributed_total=[10, 20, 0],
            action_history=[],
            legal_actions=[{"type": "fold"}, {"type": "call"}, {"type": "raise", "min": 40, "max": 1000}],
            active_seats=[0, 1, 2],
        )

        assert state["street"] == "preflop"
        assert state["actor_seat"] == 1
        assert state["dealer_seat"] == 0
        assert state["hole_cards"] == ["As", "Kd"]
        assert state["board_cards"] == []
        assert state["stacks"] == [1000, 1000, 1000]
        assert state["pot"] == 30
        assert "hand_strength" in state
        assert "legal_actions" in state

    def test_pot_calculation(self):
        state = make_bot_visible_state(
            seed=1,
            street="flop",
            dealer_seat=0,
            actor_seat=1,
            hole_cards=["As", "Kd"],
            board_cards=["Ac", "7h", "2s"],
            stacks=[900, 900, 900],
            contributed_this_street=[0, 0, 0],
            contributed_total=[100, 100, 100],
            action_history=[],
            legal_actions=[{"type": "check"}],
            active_seats=[0, 1, 2],
        )

        assert state["pot"] == 300

    def test_hand_strength_included(self):
        state = make_bot_visible_state(
            seed=1,
            street="flop",
            dealer_seat=0,
            actor_seat=0,
            hole_cards=["As", "Ad"],
            board_cards=["Ac", "Kh", "2s"],
            stacks=[1000, 1000],
            contributed_this_street=[0, 0],
            contributed_total=[30, 30],
            action_history=[],
            legal_actions=[{"type": "check"}],
            active_seats=[0, 1],
        )

        hs = state["hand_strength"]
        assert hs["category"] == "three_of_a_kind"
        assert "equity_estimate" in hs
        assert 0 <= hs["equity_estimate"] <= 1

    def test_hand_id_format(self):
        state = make_bot_visible_state(
            seed=12345,
            street="preflop",
            dealer_seat=0,
            actor_seat=0,
            hole_cards=["As", "Kd"],
            board_cards=[],
            stacks=[1000, 1000],
            contributed_this_street=[10, 20],
            contributed_total=[10, 20],
            action_history=[],
            legal_actions=[{"type": "call"}],
            active_seats=[0, 1],
        )

        assert state["hand_id"] == "hand-12345"

    def test_action_history_preserved(self):
        history = [
            {"street": "preflop", "seat": 0, "type": "post_sb", "amount": 10},
            {"street": "preflop", "seat": 1, "type": "post_bb", "amount": 20},
            {"street": "preflop", "seat": 2, "type": "call", "amount": 20},
        ]
        state = make_bot_visible_state(
            seed=1,
            street="preflop",
            dealer_seat=0,
            actor_seat=0,
            hole_cards=["As", "Kd"],
            board_cards=[],
            stacks=[990, 980, 980],
            contributed_this_street=[10, 20, 20],
            contributed_total=[10, 20, 20],
            action_history=history,
            legal_actions=[{"type": "fold"}, {"type": "call"}],
            active_seats=[0, 1, 2],
        )

        assert state["action_history"] == history

    def test_equity_with_no_opponents(self):
        state = make_bot_visible_state(
            seed=1,
            street="river",
            dealer_seat=0,
            actor_seat=0,
            hole_cards=["As", "Kd"],
            board_cards=["Ac", "Kh", "2s", "7c", "9d"],
            stacks=[1500],
            contributed_this_street=[0],
            contributed_total=[500],
            action_history=[],
            legal_actions=[{"type": "check"}],
            active_seats=[0],  # Only actor is active
            equity_samples=50,
        )

        # With no opponents, equity should be 1.0
        assert state["hand_strength"]["equity_estimate"] == 1.0

    def test_side_pots_empty_by_default(self):
        state = make_bot_visible_state(
            seed=1,
            street="preflop",
            dealer_seat=0,
            actor_seat=0,
            hole_cards=["As", "Kd"],
            board_cards=[],
            stacks=[1000, 1000],
            contributed_this_street=[10, 20],
            contributed_total=[10, 20],
            action_history=[],
            legal_actions=[{"type": "call"}],
            active_seats=[0, 1],
        )

        assert state["side_pots"] == []
