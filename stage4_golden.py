"""Level 1B: independent mathematical oracle; imports no production arithmetic.

A2 deliberately uses an exact Fraction and searches from an analytic magnitude
bound in exponent units, then checks both sides of the signed48 interval.
It never uses numeric.py's required_signed_bits or its rounding helper.
"""
from fractions import Fraction


def power(e):
    return Fraction(2 ** e) if e >= 0 else Fraction(1, 2 ** -e)


def fp8(code):
    if not 0 <= code < 256 or code in (127, 255):
        raise ValueError('INVALID_FP8')
    sign = (-1) ** (code // 128)
    exponent, fraction = divmod(code % 128, 8)
    return sign * (Fraction(fraction, 8) if exponent == 0 else 1 + Fraction(fraction, 8)) * power(-6 if exponent == 0 else exponent - 7)


def q9(code):
    v = fp8(code) * 512
    assert v.denominator == 1
    return v.numerator


def scale(bits):
    if not 0 < bits < 0x7f800000:
        raise ValueError('INVALID_SCALE')
    e, f = divmod(bits, 1 << 23)
    return (Fraction(f, 1 << 23) if e == 0 else 1 + Fraction(f, 1 << 23)) * power(-126 if e == 0 else e - 127)


def dot(x, w):
    assert len(x) == len(w) <= 128
    total = sum((Fraction(a) * fp8(b) for a, b in zip(x, w)), Fraction()) * 512
    assert total.denominator == 1 and -(1 << 47) <= total < 1 << 47
    return total.numerator


def term(raw, act_exp, bits):
    v = raw * power(act_exp - 9) * scale(bits)
    e = -149 if bits < (1 << 23) else (bits // (1 << 23)) - 150
    te = act_exp - 9 + e
    m = v / power(te)
    assert m.denominator == 1
    return m.numerator, te


def nearest_even(value):
    # Fraction.__round__ is exact nearest-even and handles negative ties.
    return round(value)


def accum(state, new):
    sn, se = state
    tn, te = new
    assert -(1 << 71) <= tn < 1 << 71 and -2048 <= te <= 2047
    if tn == 0:
        return state
    base = min(se, te) if sn else te
    exact = sn * power(se) + tn * power(te) if sn else tn * power(te)
    # Start below any possible fitting signed48 scale, independent of RTL's
    # sign-width normalization; testing unrounded range is essential: just
    # searching the first *rounded* fitting pair changes the frozen algorithm.
    if not exact:
        return 0, base
    integer = exact / power(base)
    assert integer.denominator == 1
    # Doubling interval bounds avoids production bit_length / two's-complement.
    e = base
    scaled = integer
    lower, upper = -(1 << 47), (1 << 47) - 1
    while not lower <= scaled < (1 << 47):
        scaled /= 2
        e += 1
    m = nearest_even(scaled)
    while not lower <= m <= upper:
        e += 1
        scaled /= 2
        m = nearest_even(scaled)
    if not -32768 <= e <= 32767:
        raise OverflowError('ACC_RANGE')
    return m, e


def checkpoints(x, exps, w, scales):
    state = (0, 0)
    rows = []
    for b, lo in enumerate(range(0, len(x), 128)):
        raw = dot(x[lo:lo+128], w[lo:lo+128])
        tm, te = term(raw, exps[b], scales[b])
        state = accum(state, (tm, te))
        rows.append(dict(block=b, raw=raw, term_mant=tm, term_exp=te,
                         acc_mant=state[0], acc_exp=state[1]))
    return rows
