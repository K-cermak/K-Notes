"""Fractional index keys, ported from the fractional-indexing npm package (v4) that the client uses.

The server only creates keys for conflict copies and the REST API, but every key it creates must be
one the client's library accepts and can keep generating keys around.
"""

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
INT_DIGITS = DIGITS[10:]
_ZERO = DIGITS[0]
_SMALLEST_INTEGER = INT_DIGITS[0] + _ZERO * (len(INT_DIGITS) // 2)


class InvalidKeyError(ValueError):
    pass


def _midpoint(a: str, b: str | None) -> str:
    if b is not None and a >= b:
        raise InvalidKeyError(f"{a} >= {b}")
    if a[-1:] == _ZERO or (b and b[-1:] == _ZERO):
        raise InvalidKeyError("trailing zero")
    if b:
        n = 0
        while (a[n] if n < len(a) else _ZERO) == b[n]:
            n += 1
        if n > 0:
            return b[:n] + _midpoint(a[n:], b[n:])
    digit_a = DIGITS.index(a[0]) if a else 0
    digit_b = DIGITS.index(b[0]) if b is not None else len(DIGITS)
    if digit_b - digit_a > 1:
        # JavaScript's Math.round, which rounds halves up, unlike Python's round().
        return DIGITS[int(0.5 * (digit_a + digit_b) + 0.5)]
    if b and len(b) > 1:
        return b[:1]
    return DIGITS[digit_a] + _midpoint(a[1:], None)


def _integer_length(head: str) -> int:
    i = INT_DIGITS.find(head)
    if i < 0 or len(head) != 1:
        raise InvalidKeyError(f"invalid order key head: {head}")
    half = len(INT_DIGITS) // 2
    return half - i + 1 if i < half else i - half + 2


def _integer_part(key: str) -> str:
    length = _integer_length(key[:1])
    if length > len(key):
        raise InvalidKeyError(f"invalid order key: {key}")
    return key[:length]


def _validate_integer(value: str) -> None:
    if len(value) != _integer_length(value[0]):
        raise InvalidKeyError(f"invalid integer part of order key: {value}")


def validate_key(key: str) -> None:
    if not key or any(c not in DIGITS for c in key) or key == _SMALLEST_INTEGER:
        raise InvalidKeyError(f"invalid order key: {key}")
    integer = _integer_part(key)
    if key[len(integer) :][-1:] == _ZERO:
        raise InvalidKeyError(f"invalid order key: {key}")


def _increment_integer(x: str) -> str | None:
    _validate_integer(x)
    head = x[0]
    trailing = ""
    for i in range(len(x) - 1, 0, -1):
        d = DIGITS.index(x[i]) + 1
        if d == len(DIGITS):
            trailing = _ZERO + trailing
        else:
            return head + x[1:i] + DIGITS[d] + trailing
    head_index = INT_DIGITS.index(head)
    if head_index == len(INT_DIGITS) - 1:
        return None
    h = INT_DIGITS[head_index + 1]
    delta = _integer_length(h) - _integer_length(head)
    return h + (trailing + _ZERO if delta > 0 else trailing[1:] if delta < 0 else trailing)


def _decrement_integer(x: str) -> str | None:
    _validate_integer(x)
    head = x[0]
    last = DIGITS[-1]
    trailing = ""
    for i in range(len(x) - 1, 0, -1):
        d = DIGITS.index(x[i]) - 1
        if d == -1:
            trailing = last + trailing
        else:
            return head + x[1:i] + DIGITS[d] + trailing
    head_index = INT_DIGITS.index(head)
    if head_index == 0:
        return None
    h = INT_DIGITS[head_index - 1]
    delta = _integer_length(h) - _integer_length(head)
    return h + (trailing + last if delta > 0 else trailing[1:] if delta < 0 else trailing)


def key_between(a: str | None, b: str | None) -> str:
    """A key that sorts after a and before b; None means the start or end of the list."""
    if a is not None:
        validate_key(a)
    if b is not None:
        validate_key(b)
    if a is not None and b is not None and a > b:
        a, b = b, a
    if a is None:
        if b is None:
            return INT_DIGITS[len(INT_DIGITS) // 2] + _ZERO
        ib = _integer_part(b)
        fb = b[len(ib) :]
        if ib == _SMALLEST_INTEGER:
            return ib + _midpoint("", fb)
        if ib < b:
            return ib
        result = _decrement_integer(ib)
        if result is None:
            raise InvalidKeyError("cannot decrement any more")
        return result
    if b is None:
        ia = _integer_part(a)
        fa = a[len(ia) :]
        i = _increment_integer(ia)
        return ia + _midpoint(fa, None) if i is None else i
    ia = _integer_part(a)
    fa = a[len(ia) :]
    ib = _integer_part(b)
    fb = b[len(ib) :]
    if ia == ib:
        return ia + _midpoint(fa, fb)
    i = _increment_integer(ia)
    if i is None:
        raise InvalidKeyError("cannot increment any more")
    if i < b:
        return i
    return ia + _midpoint(fa, None)
