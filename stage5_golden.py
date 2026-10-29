"""Independent mathematical BFP18 oracle: exact Fraction, no production imports.

Search the smallest fitting power-of-two interval, starting strictly below it.
Python Fraction.__round__ supplies an independent exact signed ties-even rule.
"""
from fractions import Fraction

LIMIT = 131071

def power(e):
    return Fraction(1 << e) if e >= 0 else Fraction(1, 1 << -e)

def decision(value):
    a = abs(value)
    q, r = divmod(a.numerator, a.denominator)
    twice = 2*r
    return dict(floor=q, remainder=r, denominator=a.denominator,
                tie=twice == a.denominator,
                increment=twice > a.denominator or (twice == a.denominator and bool(q % 2)),
                rounded=round(value))

def requant(pairs):
    pairs = list(pairs)
    if not 1 <= len(pairs) <= 128:
        raise ValueError('group length')
    if any(not -(1<<47) <= m < (1<<47) or not -32768 <= e <= 32767 for m,e in pairs):
        raise ValueError('A2 range')
    values = [m * power(e) for m,e in pairs]
    peak = max(map(abs, values))
    if not peak:
        return dict(mant=[0]*len(pairs), exp=0, error=0, retry=False,
                    decisions=[decision(Fraction()) for _ in pairs], candidate=0)
    # Exact rational interval, independent of e+bit_length(abs(m)) reduction.
    h = peak.numerator.bit_length() - peak.denominator.bit_length()
    if peak < power(h):
        h -= 1
    assert power(h) <= peak < power(h+1)
    exponent = h - 18
    while True:
        scaled = [v / power(exponent) for v in values]
        result = [round(v) for v in scaled]
        if max(map(abs, result)) <= LIMIT:
            break
        exponent += 1
    candidate = h-16
    retry = max(abs(round(v/power(candidate))) for v in values) > LIMIT
    return dict(mant=result, exp=exponent, error=0 if -128 <= exponent <= 127 else 0x33,
                retry=retry, candidate=candidate, decisions=[decision(v) for v in scaled])
