import random

from execscope.tca.shortfall import implementation_shortfall, vwap_slippage_bps

MULT = 125_000


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol


def test_hand_calculated_buy_with_all_four_parts():
    # BUY target 100 lots. Decision 1.1000, arrival 1.1002, filled 80 @ 1.1005, end price 1.1010.
    r = implementation_shortfall(
        fills=[(80, 1.1005)], side="BUY", target_qty=100,
        decision_price=1.1000, arrival_price=1.1002, end_price=1.1010,
        multiplier=MULT, fees=50.0,
    )
    assert close(r.delay, 0.0002 * 80 * MULT)            # 2000.0
    assert close(r.execution, 0.0003 * 80 * MULT)        # 3000.0
    assert close(r.opportunity, 0.0010 * 20 * MULT)      # 2500.0
    assert close(r.total, 2000 + 3000 + 2500 + 50)       # 7550.0
    assert close(r.total_bps, 7550 / (1.1 * 100 * MULT) * 10_000)


def test_sell_sign_flips_price_moves():
    # SELL: a lower price than decision is a cost.
    r = implementation_shortfall(
        fills=[(100, 1.0990)], side="SELL", target_qty=100,
        decision_price=1.1000, arrival_price=1.1000, end_price=1.1000, multiplier=1.0,
    )
    assert close(r.execution, 0.0010 * 100)
    assert r.unexecuted_qty == 0 and close(r.opportunity, 0.0)


def test_nothing_filled_is_pure_opportunity_cost():
    r = implementation_shortfall(
        fills=[], side="BUY", target_qty=10,
        decision_price=100.0, arrival_price=100.5, end_price=102.0,
    )
    assert r.avg_fill is None
    assert close(r.total, 20.0) and close(r.delay, 0.0) and close(r.execution, 0.0)


def test_parts_always_sum_to_perold_formula():
    # Identity check on random scenarios: the 4-way split must equal the one-line Perold formula.
    rng = random.Random(42)
    for _ in range(500):
        side = rng.choice(["BUY", "SELL"])
        s = 1 if side == "BUY" else -1
        target = rng.randint(1, 1000)
        q1 = rng.randint(0, target)
        fills = [(q1, rng.uniform(90, 110))] if q1 else []
        d, a, e = (rng.uniform(90, 110) for _ in range(3))
        r = implementation_shortfall(fills, side, target, d, a, e, multiplier=2.0, fees=1.5)
        avg = fills[0][1] if fills else 0.0
        perold = s * ((avg - d) * q1 + (e - d) * (target - q1)) * 2.0 + 1.5
        assert close(r.total, perold, 1e-6)


def test_rejects_bad_inputs():
    for kwargs in (
        dict(side="HOLD"),
        dict(target_qty=0),
        dict(fills=[(11, 100.0)]),   # overfill
        dict(fees=-1.0),
    ):
        base = dict(fills=[(5, 100.0)], side="BUY", target_qty=10,
                    decision_price=100.0, arrival_price=100.0, end_price=100.0)
        base.update(kwargs)
        try:
            implementation_shortfall(**base)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {kwargs}")


def test_vwap_slippage():
    assert close(vwap_slippage_bps(1.1002, 1.1000, "BUY"), 0.0002 / 1.1 * 10_000)
    assert vwap_slippage_bps(1.1002, 1.1000, "SELL") < 0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
