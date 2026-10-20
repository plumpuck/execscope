from execscope.algos.twap import twap_schedule


def test_sum_equals_total():
    assert sum(twap_schedule(10_000, 9)) == 10_000


def test_even_split():
    assert twap_schedule(900, 9) == [100] * 9


def test_remainder_goes_to_first_slices():
    assert twap_schedule(10, 3) == [4, 3, 3]
    assert twap_schedule(10_000, 9) == [1112] + [1111] * 8


def test_slices_differ_by_at_most_one():
    s = twap_schedule(12_345, 7)
    assert max(s) - min(s) <= 1


def test_bad_inputs():
    for args in [(10, 0), (5, 9), (-1, 3)]:
        try:
            twap_schedule(*args)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {args}")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
