#!/usr/bin/env python3
"""Deterministic FP32 B2 bit-exact vectors from independent exact fractions.

Outputs 512 packed 173-bit records consumed by tb_xw_fp32_scale_b2.v.
A separate exact-rational identity cross-check is performed for all valid
vectors.  No binary floating-point arithmetic participates.
"""
import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from linear_stream_model.numeric import (fp32_positive_scale, fp32_exact_scale,
                                         NumericFault, pow2)

VECTORS = 512
SCALES_EDGE = (
    0x00000001, 0x00000002, 0x00000080, 0x007fffff,
    0x00800000, 0x00800001, 0x3f000000, 0x3f800000,
    0x3f800001, 0x3f80624e, 0x3fffffff, 0x40000000,
    0x7f7ffffe, 0x7f7fffff, 0x00000000, 0x80000000,
    0xbf800000, 0xff7fffff, 0x7f800000, 0xff800000,
    0x7fc00000, 0x7f800001, 0x7fffffff, 0xffffffff
)
RAWS = (-(1 << 47), -(1 << 47) + 1, -23456789, -1,
        0, 1, 23456789, (1 << 47) - 1)
EXPS = (-128, -127, -30, -1, 0, 1, 30, 126, 127)


def packed(raw, act_exp, scale):
    try:
        sig, power = fp32_positive_scale(scale)
        term = raw * sig
        term_exp = act_exp - 9 + power
        if not -(1<<71) <= term < (1<<71):
            raise AssertionError('term overflow signed72')
        if not -(1<<11) <= term_exp < (1<<11):
            raise AssertionError('term exponent overflow signed12')
        # Independent fraction representation: excludes production multiplier.
        true_result = raw * pow2(act_exp - 9) * fp32_exact_scale(scale)
        encoded_result = term * pow2(term_exp)
        if true_result != encoded_result:
            raise AssertionError('FP32 B2 exact rational cross-check failed')
        valid = 1
    except NumericFault:
        term, term_exp, valid = 0, 0, 0
    return ((((((raw & ((1<<48)-1)) << 8 | (act_exp & 255)) << 32 | scale)
              << 72 | (term & ((1<<72)-1))) << 12 | (term_exp & 4095)) << 1 | valid)


def make_vectors():
    rng = random.Random(0xB2F32026)
    records = []
    # Start with broad and signed extrema; distribute exponents.
    for si, scale in enumerate(SCALES_EDGE):
        for ri, raw in enumerate(RAWS):
            act = EXPS[(si + ri) % len(EXPS)]
            records.append(packed(raw, act, scale))
    while len(records) < VECTORS:
        raw = rng.randrange(-(1 << 47), 1 << 47)
        act = rng.randrange(-128, 128)
        bits = rng.randrange(1 << 32)
        records.append(packed(raw, act, bits))
    return ''.join(f'{record:044x}\n' for record in records)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    path = ROOT / 'tb' / 'vectors' / 'b2_fp32_vectors.mem'
    content = make_vectors()
    if args.check:
        if not path.exists() or path.read_text('ascii') != content:
            sys.exit('FAIL B2 vector file is not reproducible')
        print('PASS B2 deterministic vector reproducibility, count=512')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='ascii')
        print(f'Generated {VECTORS} vectors in {path.relative_to(ROOT)}')

if __name__ == '__main__':
    main()
