from core import constants as C


def test_ways_sum_to_total_comb():
    assert sum(C.WAYS.values()) == C.TOTAL_COMB


def test_known_ways():
    assert C.WAYS[5] == 1
    assert C.WAYS[4] == 170
    assert C.WAYS[3] == 5610
    assert C.WAYS[2] == 59840


def test_probabilities_sum_to_one():
    assert abs(sum(C.prob(k) for k in C.PRIZE) - 1.0) < 1e-12


def test_expected_return_is_about_minus_44_percent():
    assert -0.45 < C.EXPECTED_RETURN < -0.44
