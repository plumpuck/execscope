from execscope.algos.vwap import interval_vwap


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def test_two_bars():
    # (110 + 360) / 400
    assert close(interval_vwap([(1.10, 100), (1.20, 300)]), 1.175)


def test_equal_volume_is_simple_average():
    assert close(interval_vwap([(1.0, 10), (2.0, 10), (3.0, 10)]), 2.0)


def test_zero_volume_bar_has_no_weight():
    assert close(interval_vwap([(1.0, 0), (2.0, 10)]), 2.0)


def test_empty_raises():
    try:
        interval_vwap([])
    except ValueError:
        return
    raise AssertionError("expected ValueError for empty input")


def test_all_zero_volume_raises():
    try:
        interval_vwap([(1.0, 0), (2.0, 0)])
    except ValueError:
        return
    raise AssertionError("expected ValueError when total volume is 0")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
