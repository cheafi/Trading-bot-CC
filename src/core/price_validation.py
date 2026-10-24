"""
src/core/price_validation.py — Fail-closed validation for financial inputs
==========================================================================

Financial state must never be mutated from an unvalidated number. A single
``NaN`` price entering ``Position.update_price`` propagates into
``unrealized_pnl``, then into ``current_equity`` on exit — and because every
comparison against ``NaN`` is ``False``, ``peak_equity`` silently stops
updating and drawdown reporting is permanently corrupted with no error raised.

This module provides explicit, machine-readable validation instead of silent
substitution. We deliberately do **not** "repair" a bad price by falling back
to the last known value: inventing a price is worse than refusing to act.

Usage
-----
    ok, code = validate_price(px)
    if not ok:
        ...  # reject the update, log ``code``

    require_price(px, field="exit_price")  # raises InvalidPriceError
"""

from __future__ import annotations

import math
from typing import Any, Tuple

__all__ = [
    "InvalidPriceError",
    "InvalidStopError",
    "PriceRejectionCode",
    "require_price",
    "validate_price",
    "validate_stop_placement",
]


class PriceRejectionCode:
    """Machine-readable reason codes for a rejected price."""

    MISSING = "PRICE_MISSING"
    NOT_NUMERIC = "PRICE_NOT_NUMERIC"
    NAN = "PRICE_NAN"
    INFINITE = "PRICE_INFINITE"
    NEGATIVE = "PRICE_NEGATIVE"
    ZERO = "PRICE_ZERO"
    OK = "OK"


class InvalidPriceError(ValueError):
    """Raised when a price cannot be used for a financial calculation."""

    def __init__(self, code: str, field: str, value: Any) -> None:
        self.code = code
        self.field = field
        self.value = value
        super().__init__(f"{field}: {code} (received {value!r})")


class InvalidStopError(ValueError):
    """Raised when a stop-loss is on the wrong side of the reference price."""

    def __init__(self, message: str, code: str = "STOP_WRONG_SIDE") -> None:
        self.code = code
        super().__init__(message)


def validate_price(
    value: Any,
    *,
    allow_zero: bool = False,
) -> Tuple[bool, str]:
    """Return ``(is_valid, reason_code)`` for a candidate price.

    ``allow_zero`` exists for fields where 0 is a legitimate sentinel meaning
    "unset" (e.g. ``take_profit_price``), not a tradeable price.
    """
    if value is None:
        return False, PriceRejectionCode.MISSING
    if isinstance(value, bool):  # bool is an int subclass; never a price
        return False, PriceRejectionCode.NOT_NUMERIC
    try:
        px = float(value)
    except (TypeError, ValueError):
        return False, PriceRejectionCode.NOT_NUMERIC
    if math.isnan(px):
        return False, PriceRejectionCode.NAN
    if math.isinf(px):
        return False, PriceRejectionCode.INFINITE
    if px < 0:
        return False, PriceRejectionCode.NEGATIVE
    if px == 0 and not allow_zero:
        return False, PriceRejectionCode.ZERO
    return True, PriceRejectionCode.OK


def require_price(
    value: Any,
    *,
    field: str = "price",
    allow_zero: bool = False,
) -> float:
    """Validate and coerce, or raise :class:`InvalidPriceError`."""
    ok, code = validate_price(value, allow_zero=allow_zero)
    if not ok:
        raise InvalidPriceError(code, field, value)
    return float(value)


def validate_stop_placement(
    *,
    entry_price: float,
    stop_price: float,
    direction: str = "long",
) -> Tuple[bool, str]:
    """Check the stop sits on the risk-reducing side of the entry.

    A long stop above entry (or a short stop below it) is not a stop at all —
    it guarantees a loss on the next tick and usually indicates a sign error
    upstream. Returns ``(is_valid, reason_code)``.

    A ``stop_price`` of 0 means "no stop configured" and is reported as
    ``STOP_MISSING`` so the caller can decide its own policy rather than
    having one silently imposed here.
    """
    ok, code = validate_price(entry_price, allow_zero=False)
    if not ok:
        return False, f"ENTRY_{code}"

    ok, code = validate_price(stop_price, allow_zero=True)
    if not ok:
        return False, f"STOP_{code}"

    if float(stop_price) == 0:
        return False, "STOP_MISSING"

    if direction == "short":
        if float(stop_price) <= float(entry_price):
            return False, "STOP_WRONG_SIDE_SHORT"
    elif float(stop_price) >= float(entry_price):
        return False, "STOP_WRONG_SIDE_LONG"

    return True, "OK"
