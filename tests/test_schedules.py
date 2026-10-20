import pytest
from hypothesis import given, strategies as st

from execscope.algos.schedules import build_volume_profile, pov_child_qty, volume_profile_schedule


def test_profile_schedule_hand_case():
    assert volume_profile_schedule(100, [1, 2, 1]) == [25, 50, 25]
    assert volume_profile_schedule(10, [1, 1, 1]) == [4, 3, 3]


def test_zero_weight_slot_gets_nothing():
    assert volume_profile_schedule(10, [1, 0, 1]) == [5, 0, 5]


@given(total=st.integers(0, 10**6), w=st.lists(st.floats(0, 100, allow_nan=False), min_size=1, max_size=40))
def test_profile_schedule_always_sums_and_nonnegative(total, w):
    if sum(w) <= 0:
        return
    s = volume_profile_schedule(total, w)
    assert sum(s) == total and all(x >= 0 for x in s)
    # a zero-weight slot never receives quantity
    assert all(x == 0 for x, wi in zip(s, w) if wi == 0)


def test_profile_rejects_bad_input():
    for bad in ([], [0, 0], [-1, 2]):
        with pytest.raises(ValueError):
            volume_profile_schedule(10, bad)


def test_build_profile_normalises_each_day():
    # day 2 is ten times busier but has the same shape: same profile
    p = build_volume_profile([[1, 3], [10, 30]])
    assert p == pytest.approx([0.25, 0.75])


def test_build_profile_rejects_ragged_or_empty():
    with pytest.raises(ValueError):
        build_volume_profile([])
    with pytest.raises(ValueError):
        build_volume_profile([[1, 2], [1]])


def test_pov_child_qty():
    assert pov_child_qty(1000, 200, 0.1) == 20
    assert pov_child_qty(5, 200, 0.1) == 5          # capped by what is left
    with pytest.raises(ValueError):
        pov_child_qty(10, 100, 0)
