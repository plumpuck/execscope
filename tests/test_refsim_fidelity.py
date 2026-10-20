import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from execscope.refsim.book import BookParams, level_sizes, simulate_schedule, walk


def test_walk_hand_calculation_buy():
    sizes = [10.0, 10.0, 10.0]
    fills, left = walk(sizes, best_price=100.0, tick=1.0, side="BUY", qty=15)
    assert fills == [(10.0, 100.0), (5.0, 101.0)] and left == [0.0, 5.0, 10.0]


def test_walk_sell_goes_down_and_does_not_mutate_input():
    sizes = [10.0, 10.0]
    fills, _ = walk(sizes, 100.0, 1.0, "SELL", 12)
    assert fills == [(10.0, 100.0), (2.0, 99.0)] and sizes == [10.0, 10.0]


def test_walk_beyond_book_leaves_unfilled():
    fills, left = walk([5.0, 5.0], 100.0, 1.0, "BUY", 20)
    assert sum(q for q, _ in fills) == 10.0 and left == [0.0, 0.0]


def test_level_sizes_grow():
    s = level_sizes(BookParams(tick=1, depth_at_best=10, level_growth=0.5, n_levels=3))
    assert s == [10.0, 15.0, 20.0]


def _avg(fills):
    return sum(q * p for q, p in fills) / sum(q for q, _ in fills)


def test_bigger_orders_pay_more_per_unit():
    p = BookParams(tick=0.01, depth_at_best=10)
    small, _ = simulate_schedule([5], [100.0], "BUY", p)
    big, _ = simulate_schedule([200], [100.0], "BUY", p)
    assert _avg(big) > _avg(small)


@settings(max_examples=60, deadline=None)
@given(q=st.integers(2, 300), n=st.integers(2, 10))
def test_splitting_with_full_resilience_never_costs_more(q, n):
    # with full refill and no permanent impact, spreading an order over time is weakly cheaper
    p = BookParams(tick=0.01, depth_at_best=10, resilience=1.0)
    base, k = divmod(q, n)
    sched = [base + (1 if i < k else 0) for i in range(n)]
    one, _ = simulate_schedule([q], [100.0] * n, "BUY", p)
    many, _ = simulate_schedule(sched, [100.0] * n, "BUY", p)
    assert _avg(many) <= _avg(one) + 1e-9


def test_no_resilience_removes_the_benefit_of_splitting():
    # if depth never comes back, slicing in time cannot help versus one big order
    p = BookParams(tick=0.01, depth_at_best=10, resilience=0.0)
    one, _ = simulate_schedule([100], [100.0] * 4, "BUY", p)
    many, _ = simulate_schedule([25] * 4, [100.0] * 4, "BUY", p)
    assert _avg(many) == pytest.approx(_avg(one))


def test_permanent_impact_pushes_later_prices_against_the_trader():
    p0 = BookParams(tick=0.01, depth_at_best=1000)
    p1 = BookParams(tick=0.01, depth_at_best=1000, permanent_impact_per_unit=0.001)
    a, _ = simulate_schedule([50, 50], [100.0, 100.0], "BUY", p0)
    b, _ = simulate_schedule([50, 50], [100.0, 100.0], "BUY", p1)
    assert _avg(b) > _avg(a)
