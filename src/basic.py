def tolerance(current_price: float, target_price: float, tolerance: float = 0.5) -> bool:
    """
    Returns True if current_price is within ±tolerance of target_price.

    Example:
        target = 125
        current = 124.9  → True
        current = 125.45 → True
        current = 124.3  → False
    """
    return abs(current_price - target_price) <= tolerance


def round4(value: float) -> float:
    """
    Rounds a float to exactly 4 decimal places and returns a float.
    Example:
        12.345678 → 12.3457
        0.123454  → 0.1235
        1.2       → 1.2
    """
    return float(f"{value:.4f}")
