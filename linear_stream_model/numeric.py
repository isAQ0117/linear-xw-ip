"""Integer-exact B3-B arithmetic, plus an independent *unrounded* rational baseline.

The B3-B numerical rules here are transcribed from the user's:
 qwen3_gate_b3b/model/gate_b3b_functional_oracle.py
 and the locked original Level-A hw_numeric/{linear,accumulator,bfp,integer,e4m3fn}.py.
No numpy, torch or float arithmetic is used in the arithmetic paths.
"""
from fractions import Fraction

class NumericFault(ValueError):
    def __init__(self, stage, message):
        self.stage = stage
        super().__init__(f"{stage}: {message}")

def check_signed(value, bits, stage):
    value = int(value)
    if value < -(1 << (bits-1)) or value >= (1 << (bits-1)):
        raise NumericFault(stage, f"signed{bits} overflow: {value}")
    return value

def required_signed_bits(x):
    x = int(x)
    return (x.bit_length() if x >= 0 else (~x).bit_length()) + 1

def fits_signed(x, bits):
    return -(1 << (bits-1)) <= x < (1 << (bits-1))

def rne_shift(n, shift):
    """Signed round-to-nearest, ties-to-even on division by 2**shift."""
    n, shift = int(n), int(shift)
    if shift <= 0:
        return n << -shift
    sign = -1 if n < 0 else 1
    q, r = divmod(abs(n), 1 << shift)
    half = 1 << (shift - 1)
    if r > half or (r == half and (q & 1)):
        q += 1
    return sign * q

def fp8_e4m3fn_q9(code):
    code = int(code)
    if not 0 <= code <= 255:
        raise NumericFault("FP8", f"invalid byte: {code}")
    exp = (code >> 3) & 15
    frac = code & 7
    if exp == 15 and frac == 7:
        raise NumericFault("FP8", f"E4M3FN NaN: 0x{code:02x}")
    mag = frac if exp == 0 else ((8 + frac) << (exp - 1))
    return -mag if code & 128 else mag

def fp32_positive_scale(code):
    """Decode finite, strictly positive FP32 bits into (integer significand, power-of-two).

    A normal IEEE-754 float has 24 bits of precision; a subnormal has
    no hidden leading 1 and uses exponent -149. The returned integer
    times 2**exponent is EXACTLY the stored FP32 value.
    """
    code = int(code)
    if not 0 <= code <= 0xffffffff:
        raise NumericFault("FP32_SCALE", f"invalid raw32: {code}")
    sign = code >> 31
    exponent = (code >> 23) & 0xff
    fraction = code & 0x7fffff
    if sign or exponent == 255 or (exponent == 0 and fraction == 0):
        raise NumericFault("FP32_SCALE",
                           f"expected positive finite nonzero: 0x{code:08x}")
    if exponent == 0:
        return fraction, -149
    return (1 << 23) + fraction, exponent - 150


def fp32_exact_scale(code):
    """Reference FP32 decoding as an exact rational, no Python float rounding."""
    c = int(code)
    if not 0 <= c <= 0xffffffff:
        raise NumericFault("REF_FP32_SCALE", f"invalid raw32: {c}")
    exp = (c >> 23) & 0xff
    frac = c & 0x7fffff
    if c >> 31 or exp == 255 or (exp == 0 and frac == 0):
        raise NumericFault("REF_FP32_SCALE", f"invalid FP32 scale: 0x{c:08x}")
    if exp == 0:
        return Fraction(frac, 1 << 149)
    mant = Fraction((1 << 23) + frac)
    return mant * pow2(exp - 150)


def bf16_positive_scale(code):
    code = int(code)
    if not 0 <= code <= 0xffff:
        raise NumericFault("BF16_SCALE", f"invalid raw16: {code}")
    exp, frac = (code >> 7) & 255, code & 127
    if (code & 0x8000) or exp == 255 or (exp == 0 and frac == 0):
        raise NumericFault("BF16_SCALE", f"expected positive finite nonzero: 0x{code:04x}")
    return (frac, -133) if exp == 0 else (128 + frac, exp - 134)

def accumulate_48(state, term, term_bits=56):
    """48-bit RNE ordered A2 state update.

    Legacy BF16 B2 terms occupy signed56. The FP32-scale profile generates
    a mathematically exact signed72 term; no pre-A2 reduction to 56 bits is
    permitted. A2 state remains signed48 + signed16.
    """
    if term_bits not in (56, 72):
        raise ValueError("unsupported B2 term width")
    sn, se = map(int, state)
    tn, te = map(int, term)
    check_signed(tn, term_bits, "TERM")
    check_signed(te, 12, "TERM_EXP")
    if not tn:
        return sn, se
    target = te if sn == 0 else min(se, te)
    exact = tn if sn == 0 else ((sn << (se - target)) + (tn << (te - target)))
    shift = max(0, required_signed_bits(exact) - 48)
    rounded = rne_shift(exact, shift)
    while not fits_signed(rounded, 48):
        shift += 1
        rounded = rne_shift(exact, shift)
    return check_signed(rounded, 48, "ACC48"), check_signed(target + shift, 16, "ACC_EXP")

def requant_bfp18(pairs):
    """B3-B / locked A2 quantizer for a 1..128 element output group."""
    pairs = list(pairs)
    if not 1 <= len(pairs) <= 128:
        raise NumericFault("A2", "group length must be 1..128")
    pairs = [(check_signed(n, 48, "A2_IN"), check_signed(e, 16, "A2_IN_EXP")) for n, e in pairs]
    nonzero = [(n, e) for n, e in pairs if n]
    exponent = max(e + abs(n).bit_length() - 1 for n, e in nonzero) - 17 if nonzero else 0
    while any(abs(rne_shift(n, exponent-e)) > 131071 for n, e in pairs):
        exponent += 1
    check_signed(exponent, 8, "A2_GROUP_EXP")
    result = [check_signed(rne_shift(n, exponent-e), 18, "A2_MANT") for n, e in pairs]
    return result, exponent

# The reference path below intentionally derives exact values from FP8/BF16
# *mathematical* definitions, without using fp8_e4m3fn_q9 or bf16_positive_scale.
def pow2(exponent):
    exponent = int(exponent)
    return Fraction(1 << exponent, 1) if exponent >= 0 else Fraction(1, 1 << -exponent)

def fp8_exact(code):
    c = int(code)
    if not 0 <= c <= 255:
        raise NumericFault("REF_FP8", f"invalid byte {c}")
    sign = -1 if c & 0x80 else 1
    e, f = (c >> 3) & 15, c & 7
    if e == 15 and f == 7:
        raise NumericFault("REF_FP8", "E4M3FN NaN")
    if e == 0:
        return sign * Fraction(f, 512)
    return sign * Fraction(8+f, 8) * pow2(e - 7)

# Exact textbook-derived Q9 units, cached for fast large-shape reference runs.
# This table does NOT call the B3-B fp8_e4m3fn_q9 production-style decoder.
REF_FP8_Q9_TABLE = tuple(
    None if b in (0x7f, 0xff) else int(fp8_exact(b) * 512)
    for b in range(256)
)

def bf16_exact_scale(code):
    c = int(code)
    if not 0 <= c <= 65535 or c & 0x8000:
        raise NumericFault("REF_SCALE", f"negative/invalid BF16 0x{c:04x}")
    e, f = (c >> 7) & 255, c & 127
    if e == 255 or (e == 0 and f == 0):
        raise NumericFault("REF_SCALE", f"nonfinite/zero BF16 0x{c:04x}")
    if e == 0:
        return Fraction(f, 1 << 133)
    return Fraction(128+f) * pow2(e-134)

def ideal_block_reference(mantissa, exponent, fp8_codes, bf16_code, scalar_fractions=False):
    """No intermediate rounding. Exact dyadic result from quantized source data.

    scalar_fractions=True independently multiplies Fraction values per input.
    Fast mode accumulates exact FP8 weights in Q9-derived integer units; because
    all E4M3FN finite values are exactly integer/512, this is *mathematically*
    identical and uses no floating-point approximations.
    """
    if len(mantissa) != len(fp8_codes):
        raise ValueError("reference K-block shape mismatch")
    factor = pow2(exponent) * bf16_exact_scale(bf16_code)
    if scalar_fractions:
        inner = sum((Fraction(int(a)) * fp8_exact(w) for a, w in zip(mantissa, fp8_codes)), Fraction(0))
    else:
        # Independent textbook FP8 rational conversion, exact integer Q9 units.
        total = sum(int(a) * int(fp8_exact(w) * 512) for a, w in zip(mantissa, fp8_codes))
        inner = Fraction(total, 512)
    return inner * factor

def hardware_value(mantissa, exponent):
    return Fraction(int(mantissa)) * pow2(exponent)

def as_decimal(fraction, precision=40):
    from decimal import Decimal, localcontext
    f = Fraction(fraction)
    with localcontext() as ctx:
        ctx.prec = precision
        return str(Decimal(f.numerator) / Decimal(f.denominator))

def signed_error(hardware, exact):
    return Fraction(hardware) - Fraction(exact)

def fraction_payload(fraction):
    f = Fraction(fraction)
    return {"numerator": str(f.numerator), "denominator": str(f.denominator)}
