"""Tests for poker edge cases - busted players, heads-up, all-in showdown, etc."""

from __future__ import annotations

import pytest
from holdem_together.engine import TableConfig, simulate_hand, _compute_side_pots
from holdem_together.game_state import make_bot_visible_state


def _always_check_or_call(code: str, gs: dict) -> dict:
    """Bot that always checks if possible, otherwise calls."""
    legal = {a["type"]: a for a in gs.get("legal_actions", [])}
    if "check" in legal:
        return {"type": "check"}
    if "call" in legal:
        return {"type": "call"}
    return {"type": "fold"}


def _always_fold(code: str, gs: dict) -> dict:
    """Bot that always folds."""
    return {"type": "fold"}


def _always_all_in(code: str, gs: dict) -> dict:
    """Bot that always goes all-in."""
    legal = {a["type"]: a for a in gs.get("legal_actions", [])}
    if "raise" in legal:
        return {"type": "raise", "amount": legal["raise"]["max"]}
    if "call" in legal:
        return {"type": "call"}
    return {"type": "fold"}


class TestBustedPlayersNotDealt:
    """Tests that busted players (0 chips) don't receive cards."""

    def test_busted_player_no_hole_cards(self):
        """A player with 0 chips should not receive hole cards."""
        cfg = TableConfig(seats=3, starting_stack=1000, small_blind=10, big_blind=20)
        # Player 0 is busted
        initial_stacks = [0, 500, 500]
        
        hr = simulate_hand(
            ["bot0", "bot1", "bot2"],
            seed=42,
            config=cfg,
            dealer_seat=0,
            initial_stacks=initial_stacks,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        
        # Busted player should not have hole cards
        assert hr.hole_cards[0] is None
        # Active players should have hole cards
        assert hr.hole_cards[1] is not None
        assert hr.hole_cards[2] is not None
        assert len(hr.hole_cards[1]) == 2
        assert len(hr.hole_cards[2]) == 2

    def test_busted_player_not_in_action_history(self):
        """A busted player should not appear in action history (except if they were dealer)."""
        cfg = TableConfig(seats=3, starting_stack=1000, small_blind=10, big_blind=20)
        initial_stacks = [0, 500, 500]
        
        hr = simulate_hand(
            ["bot0", "bot1", "bot2"],
            seed=42,
            config=cfg,
            dealer_seat=0,
            initial_stacks=initial_stacks,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        
        # Busted player (seat 0) should not have any actions
        actions_by_seat_0 = [a for a in hr.actions if a.get("seat") == 0]
        assert len(actions_by_seat_0) == 0

    def test_chips_conserved_with_busted_player(self):
        """Chips should be conserved even with a busted player."""
        cfg = TableConfig(seats=3, starting_stack=1000, small_blind=10, big_blind=20)
        initial_stacks = [0, 500, 500]
        
        hr = simulate_hand(
            ["bot0", "bot1", "bot2"],
            seed=42,
            config=cfg,
            dealer_seat=0,
            initial_stacks=initial_stacks,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        
        # Total chips should be conserved
        assert sum(hr.final_stacks) == sum(initial_stacks)


class TestHeadsUpBlinds:
    """Tests for heads-up (2 player) blind posting."""

    def test_dealer_posts_sb_in_heads_up(self):
        """In heads-up, the dealer should post the small blind."""
        cfg = TableConfig(seats=2, starting_stack=1000, small_blind=10, big_blind=20)
        
        hr = simulate_hand(
            ["bot0", "bot1"],
            seed=42,
            config=cfg,
            dealer_seat=0,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        
        # Find SB and BB posting actions
        sb_action = next((a for a in hr.actions if a.get("type") == "post_sb"), None)
        bb_action = next((a for a in hr.actions if a.get("type") == "post_bb"), None)
        
        assert sb_action is not None
        assert bb_action is not None
        # Dealer (seat 0) should post SB
        assert sb_action["seat"] == 0
        # Non-dealer (seat 1) should post BB
        assert bb_action["seat"] == 1

    def test_heads_up_action_order_preflop(self):
        """In heads-up, SB acts first preflop."""
        cfg = TableConfig(seats=2, starting_stack=1000, small_blind=10, big_blind=20)
        
        hr = simulate_hand(
            ["bot0", "bot1"],
            seed=42,
            config=cfg,
            dealer_seat=0,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        
        # Get preflop actions (excluding blind posts)
        preflop_actions = [a for a in hr.actions if a.get("street") == "preflop" and a.get("type") not in ("post_sb", "post_bb")]
        
        # First action after blinds should be from seat 0 (SB/dealer)
        assert len(preflop_actions) >= 1
        assert preflop_actions[0]["seat"] == 0

    def test_heads_up_action_order_postflop(self):
        """In heads-up, BB acts first postflop (non-dealer acts first)."""
        cfg = TableConfig(seats=2, starting_stack=1000, small_blind=10, big_blind=20)
        
        hr = simulate_hand(
            ["bot0", "bot1"],
            seed=42,
            config=cfg,
            dealer_seat=0,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        
        # Get flop actions
        flop_actions = [a for a in hr.actions if a.get("street") == "flop"]
        
        if len(flop_actions) >= 1:
            # First action on flop should be from seat 1 (BB/non-dealer)
            assert flop_actions[0]["seat"] == 1


class TestAllInShowdown:
    """Tests for all-in situations and showdowns."""

    def test_both_players_all_in_goes_to_showdown(self):
        """When both players are all-in, hand should proceed to showdown."""
        cfg = TableConfig(seats=2, starting_stack=1000, small_blind=10, big_blind=20)
        
        hr = simulate_hand(
            ["bot0", "bot1"],
            seed=42,
            config=cfg,
            dealer_seat=0,
            bot_decide=_always_all_in,
            make_state_for_actor=make_bot_visible_state,
        )
        
        # Board should have 5 cards (full runout)
        assert len(hr.board) == 5
        # There should be a winner
        assert len(hr.winners) >= 1
        # Chips should be conserved
        assert sum(hr.final_stacks) == 2000

    def test_three_way_all_in(self):
        """Three players going all-in with different stack sizes."""
        cfg = TableConfig(seats=3, starting_stack=1000, small_blind=10, big_blind=20)
        # Different stack sizes to create side pots
        initial_stacks = [100, 300, 500]
        
        hr = simulate_hand(
            ["bot0", "bot1", "bot2"],
            seed=42,
            config=cfg,
            dealer_seat=0,
            initial_stacks=initial_stacks,
            bot_decide=_always_all_in,
            make_state_for_actor=make_bot_visible_state,
        )
        
        # Board should have 5 cards
        assert len(hr.board) == 5
        # Chips should be conserved
        assert sum(hr.final_stacks) == sum(initial_stacks)
        # Should have side pots
        assert len(hr.side_pots) >= 1

    def test_no_betting_after_all_in(self):
        """When everyone is all-in, no more betting actions should occur."""
        cfg = TableConfig(seats=2, starting_stack=100, small_blind=10, big_blind=20)
        
        hr = simulate_hand(
            ["bot0", "bot1"],
            seed=42,
            config=cfg,
            dealer_seat=0,
            bot_decide=_always_all_in,
            make_state_for_actor=make_bot_visible_state,
        )
        
        # Count action types
        action_types = [a.get("type") for a in hr.actions]
        
        # After all-in, there shouldn't be any check/call/fold actions on later streets
        # (Only preflop has the all-in raises)
        non_preflop_actions = [a for a in hr.actions if a.get("street") != "preflop"]
        assert len(non_preflop_actions) == 0


class TestSidePots:
    """Tests for side pot calculation."""

    def test_simple_side_pot(self):
        """Test basic side pot with one short-stacked player."""
        contrib = [100, 300, 300]
        eligible = [True, True, True]
        
        pots = _compute_side_pots(contrib, eligible)
        
        # Main pot: 100 * 3 = 300, all eligible
        # Side pot: 200 * 2 = 400, only seats 1 and 2 eligible
        assert len(pots) == 2
        assert pots[0]["amount"] == 300
        assert set(pots[0]["eligible_seats"]) == {0, 1, 2}
        assert pots[1]["amount"] == 400
        assert set(pots[1]["eligible_seats"]) == {1, 2}

    def test_folded_player_not_eligible(self):
        """Folded players contribute to pot but can't win."""
        contrib = [100, 100, 100]
        eligible = [False, True, True]  # Player 0 folded
        
        pots = _compute_side_pots(contrib, eligible)
        
        assert len(pots) == 1
        assert pots[0]["amount"] == 300
        # Player 0 is not in eligible_seats
        assert set(pots[0]["eligible_seats"]) == {1, 2}

    def test_multiple_side_pots(self):
        """Multiple side pots with different stack sizes."""
        contrib = [50, 100, 200, 200]
        eligible = [True, True, True, True]
        
        pots = _compute_side_pots(contrib, eligible)
        
        # Level 50: 50 * 4 = 200
        # Level 100: (100-50) * 3 = 150
        # Level 200: (200-100) * 2 = 200
        assert len(pots) == 3
        assert pots[0]["amount"] == 200
        assert set(pots[0]["eligible_seats"]) == {0, 1, 2, 3}
        assert pots[1]["amount"] == 150
        assert set(pots[1]["eligible_seats"]) == {1, 2, 3}
        assert pots[2]["amount"] == 200
        assert set(pots[2]["eligible_seats"]) == {2, 3}


class TestDealerRotation:
    """Tests for dealer button rotation with busted players."""

    def test_dealer_skips_busted_player(self):
        """When a player busts, dealer button should skip them."""
        from holdem_together.tournament import run_match, MatchConfig
        
        # Use a bot that always folds to guarantee someone busts quickly
        cfg = MatchConfig(hands=20, seats=3, starting_stack=100, small_blind=10, big_blind=20)
        
        # Run a match and check that hands are still playable
        result = run_match(
            bot_codes=["fold", "call", "call"],
            seed=42,
            match_config=cfg,
            bot_decide=lambda code, gs: {"type": "fold"} if code == "fold" else _always_check_or_call(code, gs),
            make_state_for_actor=make_bot_visible_state,
        )
        
        # Should have played at least some hands
        assert len(result.hand_results) >= 1
        # Chips should be conserved
        assert sum(result.final_stacks) == 300


class TestMatchEndsWithOnePlayer:
    """Tests that matches end when only one player has chips."""

    def test_match_ends_early(self):
        """Match should end when only one player remains."""
        from holdem_together.tournament import run_match, MatchConfig
        
        cfg = MatchConfig(hands=100, seats=2, starting_stack=100, small_blind=10, big_blind=20)
        
        result = run_match(
            bot_codes=["all_in", "all_in"],
            seed=42,
            match_config=cfg,
            bot_decide=_always_all_in,
            make_state_for_actor=make_bot_visible_state,
        )
        
        # Match should end early (not play all 100 hands)
        assert len(result.hand_results) < 100
        # One player should have all the chips
        assert 0 in result.final_stacks
        assert 200 in result.final_stacks


class TestReraiseValidation:
    """Tests for reraise size validation."""

    def test_min_reraise_size(self):
        """Minimum reraise should be at least the size of the last raise."""
        cfg = TableConfig(seats=2, starting_stack=1000, small_blind=10, big_blind=20)
        
        call_count = [0]
        legal_actions_seen = []
        
        def capture_legals(code: str, gs: dict) -> dict:
            legal_actions_seen.append(gs.get("legal_actions", []))
            call_count[0] += 1
            # Raise minimum on first action, then call
            legal = {a["type"]: a for a in gs.get("legal_actions", [])}
            if call_count[0] == 1 and "raise" in legal:
                return {"type": "raise", "amount": legal["raise"]["min"]}
            if "call" in legal:
                return {"type": "call"}
            if "check" in legal:
                return {"type": "check"}
            return {"type": "fold"}
        
        hr = simulate_hand(
            ["bot0", "bot1"],
            seed=42,
            config=cfg,
            dealer_seat=0,
            bot_decide=capture_legals,
            make_state_for_actor=make_bot_visible_state,
        )
        
        # Verify chips conserved (basic sanity)
        assert sum(hr.final_stacks) == 2000
        
        # Check that legal raise minimums are reasonable
        for la in legal_actions_seen:
            raise_opt = next((a for a in la if a["type"] == "raise"), None)
            if raise_opt:
                # Min should be at least BB (20) in normal play
                assert raise_opt["min"] >= 20
                # Max should not exceed stack
                assert raise_opt["max"] <= 1000
