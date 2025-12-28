"""Comprehensive tests for ratings module - Elo calculations."""
from __future__ import annotations

import math
import pytest

from holdem_together.ratings import (
    EloConfig,
    update_elo_pairwise,
    clamp_rating,
    _expected_score,
)


class TestExpectedScore:
    """Tests for expected score calculation."""

    def test_equal_ratings(self):
        score = _expected_score(1500.0, 1500.0)
        assert score == pytest.approx(0.5, rel=1e-6)

    def test_higher_rating_expects_win(self):
        score = _expected_score(1600.0, 1400.0)
        assert score > 0.5

    def test_lower_rating_expects_loss(self):
        score = _expected_score(1400.0, 1600.0)
        assert score < 0.5

    def test_symmetric_scores(self):
        score_a = _expected_score(1600.0, 1400.0)
        score_b = _expected_score(1400.0, 1600.0)
        assert score_a + score_b == pytest.approx(1.0, rel=1e-6)

    def test_400_point_difference(self):
        # With 400 point difference, expected score should be ~0.91
        score = _expected_score(1900.0, 1500.0)
        assert 0.90 < score < 0.92

    def test_large_difference(self):
        score = _expected_score(2500.0, 1500.0)
        assert score > 0.99


class TestEloConfig:
    """Tests for Elo configuration."""

    def test_default_k_factor(self):
        cfg = EloConfig()
        assert cfg.k_factor == 24.0

    def test_custom_k_factor(self):
        cfg = EloConfig(k_factor=32.0)
        assert cfg.k_factor == 32.0


class TestUpdateEloPairwiseBasic:
    """Basic tests for Elo updates."""

    def test_winner_gains_loser_loses(self):
        ratings = [1500.0, 1500.0]
        scores = [100, -100]  # Player 0 won chips
        new_ratings = update_elo_pairwise(ratings, scores)
        assert new_ratings[0] > 1500.0
        assert new_ratings[1] < 1500.0

    def test_zero_sum_rating_changes(self):
        ratings = [1500.0, 1500.0]
        scores = [100, -100]
        new_ratings = update_elo_pairwise(ratings, scores)
        # Total rating change should be zero (or very close)
        total_before = sum(ratings)
        total_after = sum(new_ratings)
        assert total_after == pytest.approx(total_before, rel=1e-6)

    def test_tie_no_change_equal_ratings(self):
        ratings = [1500.0, 1500.0]
        scores = [0, 0]  # Tie
        new_ratings = update_elo_pairwise(ratings, scores)
        # Equal ratings with tie should result in no change
        assert new_ratings[0] == pytest.approx(1500.0, rel=1e-6)
        assert new_ratings[1] == pytest.approx(1500.0, rel=1e-6)

    def test_upset_gives_more_points(self):
        # Lower rated player beats higher rated
        ratings = [1300.0, 1700.0]
        scores = [100, -100]  # Lower rated won
        new_ratings = update_elo_pairwise(ratings, scores)
        gain = new_ratings[0] - 1300.0
        # Gain should be substantial (upset bonus)
        assert gain > 12  # More than half K-factor

    def test_expected_win_gives_fewer_points(self):
        # Higher rated player beats lower rated
        ratings = [1700.0, 1300.0]
        scores = [100, -100]  # Higher rated won (expected)
        new_ratings = update_elo_pairwise(ratings, scores)
        gain = new_ratings[0] - 1700.0
        # Gain should be small (expected outcome)
        assert gain < 12  # Less than half K-factor


class TestUpdateEloPairwiseMultiplayer:
    """Tests for multiplayer Elo updates."""

    def test_three_players(self):
        ratings = [1500.0, 1500.0, 1500.0]
        scores = [100, 0, -100]
        new_ratings = update_elo_pairwise(ratings, scores)
        assert new_ratings[0] > 1500.0  # Winner
        assert new_ratings[2] < 1500.0  # Loser
        # Middle player should stay near 1500
        assert 1490.0 < new_ratings[1] < 1510.0

    def test_six_players(self):
        ratings = [1500.0] * 6
        scores = [500, 300, 100, -100, -300, -500]
        new_ratings = update_elo_pairwise(ratings, scores)
        # Verify ordering is preserved
        assert new_ratings[0] > new_ratings[1] > new_ratings[2]
        assert new_ratings[3] < new_ratings[2]
        assert new_ratings[5] < new_ratings[4] < new_ratings[3]

    def test_normalization_by_opponents(self):
        # With more opponents, individual changes should be similar magnitude
        two_player = update_elo_pairwise([1500.0, 1500.0], [100, -100])
        six_player = update_elo_pairwise([1500.0] * 6, [500, 300, 100, -100, -300, -500])
        
        # Winner's gain should be in similar ballpark regardless of player count
        two_gain = two_player[0] - 1500.0
        six_gain = six_player[0] - 1500.0
        # Both should be positive and reasonable
        assert two_gain > 0
        assert six_gain > 0


class TestUpdateEloPairwiseTies:
    """Tests for tie scenarios."""

    def test_two_way_tie(self):
        ratings = [1500.0, 1500.0]
        scores = [0, 0]
        new_ratings = update_elo_pairwise(ratings, scores)
        # No change with equal ratings and tie
        assert new_ratings == [pytest.approx(1500.0), pytest.approx(1500.0)]

    def test_partial_tie(self):
        ratings = [1500.0, 1500.0, 1500.0]
        scores = [100, 100, -200]  # Two winners, one loser
        new_ratings = update_elo_pairwise(ratings, scores)
        # Two winners should gain the same (since they tied)
        assert new_ratings[0] == pytest.approx(new_ratings[1], rel=1e-6)
        assert new_ratings[2] < 1500.0

    def test_tie_with_unequal_ratings(self):
        ratings = [1400.0, 1600.0]
        scores = [0, 0]  # Tie
        new_ratings = update_elo_pairwise(ratings, scores)
        # Lower rated player gains from tie (did better than expected)
        assert new_ratings[0] > 1400.0
        # Higher rated player loses from tie (did worse than expected)
        assert new_ratings[1] < 1600.0


class TestUpdateEloPairwiseEdgeCases:
    """Edge case tests."""

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            update_elo_pairwise([1500.0, 1500.0], [100])

    def test_empty_lists(self):
        new_ratings = update_elo_pairwise([], [])
        assert new_ratings == []

    def test_single_player(self):
        new_ratings = update_elo_pairwise([1500.0], [100])
        # No opponents means no change
        assert new_ratings == [1500.0]

    def test_custom_k_factor(self):
        cfg = EloConfig(k_factor=32.0)
        ratings = [1500.0, 1500.0]
        scores = [100, -100]
        new_ratings = update_elo_pairwise(ratings, scores, cfg=cfg)
        gain = new_ratings[0] - 1500.0
        # Higher K factor means larger changes
        assert gain > 12  # Should be about 16 for K=32

    def test_negative_scores(self):
        ratings = [1500.0, 1500.0, 1500.0]
        scores = [-10, -20, -30]  # All lost chips, but first lost least
        new_ratings = update_elo_pairwise(ratings, scores)
        # First player won relative to others
        assert new_ratings[0] > 1500.0
        assert new_ratings[2] < 1500.0


class TestUpdateEloPairwiseExtreme:
    """Tests for extreme rating differences."""

    def test_very_high_vs_very_low(self):
        ratings = [2500.0, 1000.0]
        scores = [100, -100]
        new_ratings = update_elo_pairwise(ratings, scores)
        # High rated player barely gains (expected win)
        gain_high = new_ratings[0] - 2500.0
        assert gain_high > 0
        assert gain_high < 5  # Very small gain

    def test_upset_extreme_ratings(self):
        ratings = [1000.0, 2500.0]
        scores = [100, -100]  # Low rated wins!
        new_ratings = update_elo_pairwise(ratings, scores)
        # Low rated player gains substantially
        gain_low = new_ratings[0] - 1000.0
        assert gain_low > 20  # Big upset bonus


class TestClampRating:
    """Tests for rating clamping."""

    def test_normal_rating_unchanged(self):
        assert clamp_rating(1500.0) == 1500.0

    def test_low_rating_clamped(self):
        assert clamp_rating(50.0) == 100.0

    def test_high_rating_clamped(self):
        assert clamp_rating(5000.0) == 4000.0

    def test_nan_becomes_default(self):
        assert clamp_rating(float('nan')) == 1500.0

    def test_inf_becomes_default(self):
        assert clamp_rating(float('inf')) == 1500.0

    def test_neg_inf_becomes_default(self):
        assert clamp_rating(float('-inf')) == 1500.0

    def test_boundary_low(self):
        assert clamp_rating(100.0) == 100.0

    def test_boundary_high(self):
        assert clamp_rating(4000.0) == 4000.0

    def test_just_below_min(self):
        assert clamp_rating(99.9) == 100.0

    def test_just_above_max(self):
        assert clamp_rating(4000.1) == 4000.0


class TestEloPairwiseConsistency:
    """Tests for mathematical consistency."""

    def test_ordering_preserved(self):
        # If A beat B beat C, final ratings should reflect that
        ratings = [1500.0, 1500.0, 1500.0]
        scores = [300, 100, -400]
        new_ratings = update_elo_pairwise(ratings, scores)
        assert new_ratings[0] > new_ratings[1] > new_ratings[2]

    def test_repeated_matches_convergence(self):
        # If same results keep happening, ratings should move
        ratings = [1500.0, 1500.0]
        for _ in range(10):
            ratings = update_elo_pairwise(ratings, [100, -100])
        # Winner should be significantly higher now
        assert ratings[0] > 1550.0  # Should move up after 10 wins
        assert ratings[1] < 1450.0  # Should move down after 10 losses

    def test_alternating_results_stable(self):
        # Alternating wins should keep ratings roughly stable
        ratings = [1500.0, 1500.0]
        for i in range(10):
            if i % 2 == 0:
                ratings = update_elo_pairwise(ratings, [100, -100])
            else:
                ratings = update_elo_pairwise(ratings, [-100, 100])
        # Ratings should be close to original
        assert 1450.0 < ratings[0] < 1550.0
        assert 1450.0 < ratings[1] < 1550.0
