"""TWAP slicing: split a parent order into near-equal child quantities. Pure Python."""


def twap_schedule(total_qty, n_slices):
    """Return n_slices integer quantities that sum to total_qty and differ by at most 1.

    The remainder is spread over the first slices, e.g. 10 into 3 -> [4, 3, 3].
    """
    if not isinstance(total_qty, int) or not isinstance(n_slices, int):
        raise TypeError("total_qty and n_slices must be int")
    if n_slices < 1:
        raise ValueError("n_slices must be >= 1")
    if total_qty < n_slices:
        raise ValueError("total_qty must be >= n_slices (each slice needs at least 1)")
    base, rem = divmod(total_qty, n_slices)
    return [base + 1 if i < rem else base for i in range(n_slices)]
