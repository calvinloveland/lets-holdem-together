from holdem_together.poker_eval import best_of_7, compare_best_of_7


def test_best_of_7_categories():
    # royal-ish straight flush
    hs = best_of_7(["As", "Ks", "Qs", "Js", "Ts", "2d", "3c"])
    assert hs.category == "straight_flush"


def test_compare():
    # AA should beat KK on empty board
    a = ["As", "Ad", "2c", "3d", "7h", "9s", "Tc"]
    b = ["Ks", "Kd", "2c", "3d", "7h", "9s", "Tc"]
    assert compare_best_of_7(a, b) > 0
