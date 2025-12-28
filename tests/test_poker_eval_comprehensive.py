"""Comprehensive tests for poker_eval module - hand ranking and comparison."""
from __future__ import annotations

import pytest

from holdem_together.poker_eval import (
    HandStrength,
    best_of_7,
    compare_best_of_7,
    parse_card,
    rank_5,
    RANKS,
    SUITS,
)


class TestParseCard:
    """Tests for card parsing."""

    def test_parse_valid_cards(self):
        """Test parsing all valid cards."""
        for r in RANKS:
            for s in SUITS:
                card = r + s
                rank_val, suit = parse_card(card)
                assert suit == s
                assert 2 <= rank_val <= 14

    def test_ace_is_14(self):
        rank_val, _ = parse_card("As")
        assert rank_val == 14

    def test_two_is_2(self):
        rank_val, _ = parse_card("2c")
        assert rank_val == 2

    def test_king_is_13(self):
        rank_val, _ = parse_card("Kh")
        assert rank_val == 13

    def test_invalid_card_raises(self):
        with pytest.raises((ValueError, KeyError)):
            parse_card("Xx")


class TestRank5HighCard:
    """Tests for 5-card high card hands."""

    def test_basic_high_card(self):
        hand = rank_5(["Ac", "Kd", "7h", "4s", "2c"])
        assert hand.category == "high_card"
        assert hand.rank[0] == 14  # Ace high

    def test_high_card_with_jack_high(self):
        hand = rank_5(["Jc", "9d", "7h", "4s", "2c"])
        assert hand.category == "high_card"
        assert hand.rank[0] == 11  # Jack high

    def test_high_card_kickers_matter(self):
        hand1 = rank_5(["Ac", "Kd", "7h", "4s", "2c"])
        hand2 = rank_5(["Ac", "Qd", "7h", "4s", "2c"])
        assert hand1.rank > hand2.rank


class TestRank5Pair:
    """Tests for pair hands."""

    def test_pair_of_aces(self):
        hand = rank_5(["Ac", "Ad", "Kh", "7s", "2c"])
        assert hand.category == "pair"
        assert hand.rank[0] == 14  # Aces

    def test_pair_of_twos(self):
        hand = rank_5(["2c", "2d", "Ah", "Ks", "Qc"])
        assert hand.category == "pair"
        assert hand.rank[0] == 2

    def test_pair_kickers_ordered(self):
        hand = rank_5(["Ac", "Ad", "Kh", "Qs", "Jc"])
        assert hand.category == "pair"
        assert hand.rank == (14, 13, 12, 11)  # AA with K, Q, J kickers


class TestRank5TwoPair:
    """Tests for two pair hands."""

    def test_aces_and_kings(self):
        hand = rank_5(["Ac", "Ad", "Kh", "Ks", "7c"])
        assert hand.category == "two_pair"
        assert hand.rank[0] == 14  # Higher pair
        assert hand.rank[1] == 13  # Lower pair
        assert hand.rank[2] == 7   # Kicker

    def test_twos_and_threes(self):
        hand = rank_5(["2c", "2d", "3h", "3s", "Ac"])
        assert hand.category == "two_pair"
        assert hand.rank[0] == 3  # Higher pair (threes)
        assert hand.rank[1] == 2  # Lower pair (twos)
        assert hand.rank[2] == 14  # Kicker (Ace)


class TestRank5ThreeOfAKind:
    """Tests for three of a kind hands."""

    def test_trip_aces(self):
        hand = rank_5(["Ac", "Ad", "Ah", "Ks", "7c"])
        assert hand.category == "three_of_a_kind"
        assert hand.rank[0] == 14

    def test_trip_twos(self):
        hand = rank_5(["2c", "2d", "2h", "As", "Kc"])
        assert hand.category == "three_of_a_kind"
        assert hand.rank[0] == 2
        assert hand.rank[1] == 14  # First kicker
        assert hand.rank[2] == 13  # Second kicker


class TestRank5Straight:
    """Tests for straight hands."""

    def test_ace_high_straight(self):
        hand = rank_5(["Ac", "Kd", "Qh", "Js", "Tc"])
        assert hand.category == "straight"
        assert hand.rank == (14,)

    def test_wheel_straight(self):
        # A-2-3-4-5 (wheel)
        hand = rank_5(["Ac", "2d", "3h", "4s", "5c"])
        assert hand.category == "straight"
        assert hand.rank == (5,)  # 5-high straight

    def test_six_high_straight(self):
        hand = rank_5(["2c", "3d", "4h", "5s", "6c"])
        assert hand.category == "straight"
        assert hand.rank == (6,)

    def test_middle_straight(self):
        hand = rank_5(["7c", "8d", "9h", "Ts", "Jc"])
        assert hand.category == "straight"
        assert hand.rank == (11,)


class TestRank5Flush:
    """Tests for flush hands."""

    def test_ace_high_flush(self):
        hand = rank_5(["As", "Ks", "7s", "4s", "2s"])
        assert hand.category == "flush"
        assert hand.rank[0] == 14

    def test_flush_all_ranks_matter(self):
        hand1 = rank_5(["As", "Ks", "7s", "4s", "2s"])
        hand2 = rank_5(["As", "Ks", "7s", "4s", "3s"])
        assert hand2.rank > hand1.rank  # 3 > 2

    def test_low_flush(self):
        hand = rank_5(["2c", "4c", "6c", "8c", "9c"])
        assert hand.category == "flush"


class TestRank5FullHouse:
    """Tests for full house hands."""

    def test_aces_full_of_kings(self):
        hand = rank_5(["Ac", "Ad", "Ah", "Ks", "Kc"])
        assert hand.category == "full_house"
        assert hand.rank == (14, 13)

    def test_twos_full_of_threes(self):
        hand = rank_5(["2c", "2d", "2h", "3s", "3c"])
        assert hand.category == "full_house"
        assert hand.rank == (2, 3)


class TestRank5FourOfAKind:
    """Tests for four of a kind hands."""

    def test_quad_aces(self):
        hand = rank_5(["Ac", "Ad", "Ah", "As", "Kc"])
        assert hand.category == "four_of_a_kind"
        assert hand.rank == (14, 13)  # Quads + kicker

    def test_quad_twos(self):
        hand = rank_5(["2c", "2d", "2h", "2s", "Ac"])
        assert hand.category == "four_of_a_kind"
        assert hand.rank == (2, 14)


class TestRank5StraightFlush:
    """Tests for straight flush hands."""

    def test_royal_flush(self):
        hand = rank_5(["As", "Ks", "Qs", "Js", "Ts"])
        assert hand.category == "straight_flush"
        assert hand.rank == (14,)

    def test_steel_wheel(self):
        # A-2-3-4-5 of same suit
        hand = rank_5(["Ac", "2c", "3c", "4c", "5c"])
        assert hand.category == "straight_flush"
        assert hand.rank == (5,)

    def test_mid_straight_flush(self):
        hand = rank_5(["7h", "8h", "9h", "Th", "Jh"])
        assert hand.category == "straight_flush"
        assert hand.rank == (11,)


class TestBestOf7:
    """Tests for 7-card hand evaluation."""

    def test_finds_best_5_from_7(self):
        # Cards contain a flush (5 spades) plus two other cards
        cards = ["As", "Ks", "Qs", "7s", "2s", "3d", "4c"]
        hand = best_of_7(cards)
        assert hand.category == "flush"

    def test_royal_flush_in_7_cards(self):
        cards = ["As", "Ks", "Qs", "Js", "Ts", "2d", "3c"]
        hand = best_of_7(cards)
        assert hand.category == "straight_flush"
        assert hand.rank == (14,)

    def test_full_house_from_7(self):
        # AAA + KK + random
        cards = ["Ac", "Ad", "Ah", "Ks", "Kc", "7d", "2h"]
        hand = best_of_7(cards)
        assert hand.category == "full_house"
        assert hand.rank == (14, 13)

    def test_chooses_best_two_pair(self):
        # Three pairs available, picks the best two
        cards = ["Ac", "Ad", "Kh", "Ks", "Qc", "Qd", "2h"]
        hand = best_of_7(cards)
        assert hand.category == "two_pair"
        assert hand.rank[0] == 14  # Aces
        assert hand.rank[1] == 13  # Kings

    def test_accepts_list(self):
        cards = ["As", "Ks", "Qs", "Js", "Ts", "2d", "3c"]
        hand = best_of_7(cards)
        assert hand.category == "straight_flush"

    def test_accepts_tuple(self):
        cards = ("As", "Ks", "Qs", "Js", "Ts", "2d", "3c")
        hand = best_of_7(cards)
        assert hand.category == "straight_flush"

    def test_raises_on_wrong_count(self):
        with pytest.raises(ValueError):
            best_of_7(["As", "Ks", "Qs"])


class TestCompareHands:
    """Tests for comparing hands."""

    def test_straight_flush_beats_quads(self):
        sf = ["As", "Ks", "Qs", "Js", "Ts", "2d", "3c"]
        quads = ["Ac", "Ad", "Ah", "Ah", "Ks", "Qd", "Jc"]  # Invalid but for testing
        # Actually use valid quads
        quads = ["Kc", "Kd", "Kh", "Ks", "2c", "3d", "4h"]
        assert compare_best_of_7(sf, quads) > 0

    def test_quads_beats_full_house(self):
        quads = ["Ac", "Ad", "Ah", "As", "Kc", "2d", "3h"]
        full = ["Kc", "Kd", "Kh", "Qs", "Qc", "2d", "3h"]
        assert compare_best_of_7(quads, full) > 0

    def test_full_house_beats_flush(self):
        full = ["Ac", "Ad", "Ah", "Ks", "Kc", "2d", "3h"]
        flush = ["As", "Ks", "Qs", "7s", "2s", "3d", "4c"]
        assert compare_best_of_7(full, flush) > 0

    def test_flush_beats_straight(self):
        flush = ["As", "Ks", "Qs", "7s", "2s", "3d", "4c"]
        straight = ["Ac", "Kd", "Qh", "Js", "Tc", "2d", "3h"]
        assert compare_best_of_7(flush, straight) > 0

    def test_straight_beats_trips(self):
        straight = ["Ac", "Kd", "Qh", "Js", "Tc", "2d", "3h"]
        trips = ["Ac", "Ad", "Ah", "7s", "2c", "3d", "4h"]
        assert compare_best_of_7(straight, trips) > 0

    def test_trips_beats_two_pair(self):
        trips = ["Ac", "Ad", "Ah", "7s", "2c", "3d", "4h"]
        two_pair = ["Ac", "Ad", "Kh", "Ks", "2c", "3d", "4h"]
        assert compare_best_of_7(trips, two_pair) > 0

    def test_two_pair_beats_pair(self):
        two_pair = ["Ac", "Ad", "Kh", "Ks", "2c", "3d", "4h"]
        pair = ["Qc", "Qd", "7h", "5s", "9c", "Ts", "Jh"]
        assert compare_best_of_7(two_pair, pair) > 0

    def test_pair_beats_high_card(self):
        pair = ["Qc", "Qd", "7h", "5s", "9c", "Ts", "Jh"]
        high = ["Ac", "Kd", "8h", "6s", "2c", "3d", "9h"]  # No straight possible
        assert compare_best_of_7(pair, high) > 0

    def test_equal_hands_return_zero(self):
        hand = ["Ac", "Ad", "Kh", "Ks", "Qc", "3d", "2h"]
        assert compare_best_of_7(hand, hand) == 0

    def test_same_category_higher_rank_wins(self):
        aa = ["Ac", "Ad", "Kh", "7s", "2c", "3d", "4h"]
        kk = ["Kc", "Kd", "Ah", "7s", "2c", "3d", "4h"]
        assert compare_best_of_7(aa, kk) > 0

    def test_same_pair_kicker_decides(self):
        aa_king = ["Ac", "Ad", "Kh", "7s", "2c", "3d", "4h"]
        aa_queen = ["Ac", "Ad", "Qh", "7s", "2c", "3d", "4h"]
        assert compare_best_of_7(aa_king, aa_queen) > 0


class TestCategoryOrder:
    """Test that all categories are ordered correctly."""

    def test_all_categories_ranking(self):
        # Create one hand from each category and verify ordering
        # Each hand uses distinct cards to avoid overlap
        hands = {
            "high_card": ["Ac", "Kd", "Jh", "9s", "7c", "5d", "3h"],
            "pair": ["Qc", "Qd", "Th", "8s", "6c", "4d", "2h"],
            "two_pair": ["Jc", "Jd", "9h", "9s", "7c", "5d", "3h"],
            "three_of_a_kind": ["Tc", "Td", "Th", "8s", "6c", "4d", "2h"],
            "straight": ["5c", "6d", "7h", "8s", "9c", "2d", "3h"],
            "flush": ["2s", "4s", "6s", "8s", "Ts", "3d", "5h"],
            "full_house": ["Ac", "Ad", "Ah", "Ks", "Kc", "2d", "3h"],
            "four_of_a_kind": ["Ac", "Ad", "Ah", "As", "Kc", "2d", "3h"],
            "straight_flush": ["5s", "6s", "7s", "8s", "9s", "2d", "3h"],
        }

        categories = list(hands.keys())
        for i, cat1 in enumerate(categories):
            for j, cat2 in enumerate(categories):
                cmp = compare_best_of_7(hands[cat1], hands[cat2])
                if i > j:
                    assert cmp > 0, f"{cat1} should beat {cat2}"
                elif i < j:
                    assert cmp < 0, f"{cat2} should beat {cat1}"
                else:
                    assert cmp == 0, f"{cat1} should tie {cat1}"
