from tca import average_price, cost_usd, slippage_bps

ARRIVAL = 1.10780
MULT = 125_000  # EUR per contract (6E)


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol


def test_one_lot_has_no_slippage():
    fills = [(1, 1.10780)]
    assert close(slippage_bps(fills, ARRIVAL, "BUY"), 0.0)


def test_1000_lots_observed_in_run():
    fills = [(52, 1.10780), (948, 1.10785)]
    assert close(average_price(fills), 1.1078474)
    assert close(slippage_bps(fills, ARRIVAL, "BUY"), 0.42788, 1e-4)
    assert close(cost_usd(fills, ARRIVAL, "BUY", MULT), 5925.0, 1e-3)


def test_10000_lots_observed_in_run():
    fills = [(52, 1.10780), (9948, 1.10785)]
    assert close(slippage_bps(fills, ARRIVAL, "BUY"), 0.44903, 1e-4)
    assert close(cost_usd(fills, ARRIVAL, "BUY", MULT), 62175.0, 1e-2)


def test_sell_sign_is_flipped():
    fills = [(100, 1.10770)]  # sold lower than arrival = a cost
    assert slippage_bps(fills, ARRIVAL, "SELL") > 0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
