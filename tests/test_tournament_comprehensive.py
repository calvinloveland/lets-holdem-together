"""Comprehensive tests for tournament module."""
from __future__ import annotations

import pytest

from holdem_together.tournament import MatchConfig, MatchResult, run_match
from holdem_together.game_state import make_bot_visible_state


# Helper decide functions for testing
def _always_check_or_call(code: str, game_state: dict) -> dict:
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    if "check" in legal:
        return {"type": "check"}
    if "call" in legal:
        return {"type": "call"}
    return {"type": "fold"}


def _always_fold(code: str, game_state: dict) -> dict:
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


class TestMatchConfig:
    """Tests for match configuration."""

    def test_default_config(self):
        cfg = MatchConfig()
        assert cfg.hands == 50
        assert cfg.seats == 6
        assert cfg.starting_stack == 1000
        assert cfg.small_blind == 10
        assert cfg.big_blind == 20

    def test_custom_config(self):
        cfg = MatchConfig(hands=100, seats=4, starting_stack=2000, small_blind=5, big_blind=10)
        assert cfg.hands == 100
        assert cfg.seats == 4
        assert cfg.starting_stack == 2000
        assert cfg.small_blind == 5
        assert cfg.big_blind == 10

    def test_config_is_frozen(self):
        cfg = MatchConfig()
        with pytest.raises(Exception):  # FrozenInstanceError
            cfg.hands = 100


class TestMatchResultDataclass:
    """Tests for MatchResult structure."""

    def test_result_attributes(self):
        result = MatchResult(
            seed=42,
            hands=10,
            seats=2,
            final_stacks=[1100, 900],
            chips_won=[100, -100],
            hand_results=[],
        )
        assert result.seed == 42
        assert result.hands == 10
        assert result.seats == 2
        assert result.final_stacks == [1100, 900]
        assert result.chips_won == [100, -100]
        assert result.hand_results == []


class TestRunMatchBasic:
    """Basic tests for running matches."""

    def test_returns_match_result(self):
        cfg = MatchConfig(hands=5, seats=2)
        codes = ["code1", "code2"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert isinstance(result, MatchResult)

    def test_correct_hand_count(self):
        cfg = MatchConfig(hands=10, seats=2)
        codes = ["code1", "code2"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert len(result.hand_results) == 10
        assert result.hands == 10

    def test_deterministic_with_seed(self):
        cfg = MatchConfig(hands=5, seats=2)
        codes = ["code1", "code2"]
        r1 = run_match(
            bot_codes=codes,
            seed=123,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        r2 = run_match(
            bot_codes=codes,
            seed=123,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert r1.final_stacks == r2.final_stacks
        assert r1.chips_won == r2.chips_won

    def test_different_seeds_different_results(self):
        cfg = MatchConfig(hands=10, seats=2)
        codes = ["code1", "code2"]
        r1 = run_match(
            bot_codes=codes,
            seed=100,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        r2 = run_match(
            bot_codes=codes,
            seed=200,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        # Very likely to have different results
        assert r1.chips_won != r2.chips_won or r1.hand_results[0].board != r2.hand_results[0].board


class TestRunMatchChipConservation:
    """Tests for chip conservation."""

    def test_total_chips_conserved(self):
        cfg = MatchConfig(hands=20, seats=4)
        codes = ["c" + str(i) for i in range(4)]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        total_start = cfg.starting_stack * cfg.seats
        total_end = sum(result.final_stacks)
        assert total_end == total_start

    def test_chips_won_sums_to_zero(self):
        cfg = MatchConfig(hands=10, seats=3)
        codes = ["c1", "c2", "c3"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert sum(result.chips_won) == 0

    def test_chips_won_matches_stacks(self):
        cfg = MatchConfig(hands=10, seats=2)
        codes = ["c1", "c2"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        for i in range(cfg.seats):
            assert result.chips_won[i] == result.final_stacks[i] - cfg.starting_stack


class TestRunMatchDealerRotation:
    """Tests for dealer rotation."""

    def test_dealer_rotates(self):
        cfg = MatchConfig(hands=6, seats=3)
        codes = ["c1", "c2", "c3"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        dealers = [hr.dealer_seat for hr in result.hand_results]
        # Should see 0, 1, 2, 0, 1, 2
        expected = [0, 1, 2, 0, 1, 2]
        assert dealers == expected


class TestRunMatchSeedProgression:
    """Tests for seed handling across hands."""

    def test_each_hand_different_seed(self):
        cfg = MatchConfig(hands=5, seats=2)
        codes = ["c1", "c2"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        seeds = [hr.seed for hr in result.hand_results]
        # All seeds should be unique
        assert len(set(seeds)) == len(seeds)


class TestRunMatchTableSizes:
    """Tests for different table sizes."""

    def test_heads_up(self):
        cfg = MatchConfig(hands=10, seats=2)
        codes = ["c1", "c2"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert result.seats == 2
        assert len(result.final_stacks) == 2

    def test_three_handed(self):
        cfg = MatchConfig(hands=10, seats=3)
        codes = ["c1", "c2", "c3"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert result.seats == 3

    def test_six_handed(self):
        cfg = MatchConfig(hands=10, seats=6)
        codes = ["c" + str(i) for i in range(6)]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        assert result.seats == 6
        assert len(result.final_stacks) == 6


class TestRunMatchValidation:
    """Tests for input validation."""

    def test_mismatched_codes_raises(self):
        cfg = MatchConfig(hands=5, seats=4)
        codes = ["c1", "c2"]  # Only 2 codes for 4 seats
        with pytest.raises(ValueError):
            run_match(
                bot_codes=codes,
                seed=42,
                match_config=cfg,
                bot_decide=_always_check_or_call,
                make_state_for_actor=make_bot_visible_state,
            )


class TestRunMatchStackProgression:
    """Tests for stack changes across hands."""

    def test_stacks_carry_over(self):
        cfg = MatchConfig(hands=5, seats=2)
        codes = ["c1", "c2"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        # Each hand's final stacks should be next hand's starting stacks
        for i in range(len(result.hand_results) - 1):
            current = result.hand_results[i].final_stacks
            # The engine uses these as initial stacks for next hand
            # We can't directly verify, but ensure continuity through final result
        
        # Final match stacks should equal last hand's final stacks
        assert result.final_stacks == result.hand_results[-1].final_stacks


class TestRunMatchFoldingBehavior:
    """Tests for folding patterns."""

    def test_folder_loses_blinds(self):
        cfg = MatchConfig(hands=20, seats=2, small_blind=10, big_blind=20)
        codes = ["c1", "c2"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_fold,
            make_state_for_actor=make_bot_visible_state,
        )
        # With everyone folding, BB wins preflop
        # Net effect is blinds moving around
        # Total should still be conserved
        assert sum(result.final_stacks) == cfg.starting_stack * cfg.seats


class TestRunMatchRaisingBehavior:
    """Tests for aggressive play."""

    def test_raising_works(self):
        cfg = MatchConfig(hands=10, seats=2)
        codes = ["c1", "c2"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_raise_min,
            make_state_for_actor=make_bot_visible_state,
        )
        # Should complete without errors
        # Note: match may end early if one player wins all chips
        assert len(result.hand_results) >= 1
        assert len(result.hand_results) <= 10
        # Chips conserved
        assert sum(result.final_stacks) == cfg.starting_stack * cfg.seats


class TestRunMatchHandResults:
    """Tests for individual hand results."""

    def test_hand_results_have_boards(self):
        cfg = MatchConfig(hands=5, seats=2)
        codes = ["c1", "c2"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        for hr in result.hand_results:
            # Each hand that went to showdown should have 5 board cards
            # (unless someone folded early)
            assert isinstance(hr.board, list)
            assert len(hr.board) <= 5

    def test_hand_results_have_actions(self):
        cfg = MatchConfig(hands=5, seats=2)
        codes = ["c1", "c2"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        for hr in result.hand_results:
            # At minimum, should have blind posts
            assert len(hr.actions) >= 2

    def test_hand_results_have_hole_cards(self):
        cfg = MatchConfig(hands=5, seats=2)
        codes = ["c1", "c2"]
        result = run_match(
            bot_codes=codes,
            seed=42,
            match_config=cfg,
            bot_decide=_always_check_or_call,
            make_state_for_actor=make_bot_visible_state,
        )
        for hr in result.hand_results:
            assert len(hr.hole_cards) == 2
            for hc in hr.hole_cards:
                assert hc is None or len(hc) == 2
