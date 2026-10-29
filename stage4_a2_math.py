"""Hardware-oriented exact algorithm prototype; separate from Fraction oracle.

Streaming radix-2**64 operations only; no full-width shifted integer sum is
formed on the special path. Supports the complete signed input exponent
fields (up to 34815 difference), without allocating a gap-sized register.
"""
MASK = (1 << 64) - 1


def rne_window(window, shift, sticky):
    assert 0 <= shift <= 127
    q = window >> shift
    if shift:
        guard = (window >> (shift-1)) & 1
        tail = bool(window & ((1 << (shift-1))-1)) or sticky
        q += guard and (tail or q & 1)
    else:
        assert not sticky
    return q


def finish(window, base, length, sticky, negative, target, power_two):
    shift = max(0, length - (48 if negative and power_two else 47))
    q = rne_window(window, shift-base, sticky)
    if q > ((1 << 47) if negative else (1 << 47)-1):
        shift += 1
        q = rne_window(window, shift-base, sticky)
    e = target + shift
    if not -32768 <= e <= 32767:
        raise OverflowError('ACC_RANGE')
    return (-q if negative else q), e


def fast(state, term):
    sn, se = state
    tn, te = term
    if not tn:
        return state
    target = te if not sn else min(se, te)
    exact = (sn << (se-target) if sn else 0) + (tn << (te-target))
    assert -(1 << 127) <= exact < 1 << 127
    mag = abs(exact)
    return finish(mag, 0, mag.bit_length(), False, exact < 0, target, mag != 0 and mag & (mag-1) == 0)


def segment(mag, pos):
    if pos >= 72 or pos <= -64:
        return 0
    return (mag >> pos if pos >= 0 else mag << -pos) & MASK


def special(state, term, details=False):
    sn, se = state
    tn, te = term
    if not tn:
        return state
    if not sn:
        return fast(state, term)
    if se >= te:
        h, l, d, target = sn, tn, se-te, te
    else:
        h, l, d, target = tn, sn, te-se, se
    hm, lm = abs(h), abs(l)
    # Compare without a shift wider than128. If d>=72, h is strictly larger.
    h_large = hm.bit_length()+d > lm.bit_length() or (hm.bit_length()+d == lm.bit_length() and (hm << d) >= lm)
    negative = (h < 0) if h_large else (l < 0)
    subtract = (h < 0) != (l < 0)
    carry = previous = low_sticky = window = length = base = 0
    sticky = power_two = False
    chunks = (d + 73 + 63) // 64  # extra bit for same-sign addition carry
    for i in range(chunks):
        a, b = segment(hm, i*64-d), segment(lm, i*64)
        if subtract:
            if not h_large:
                a, b = b, a
            v = a-b-carry
            carry = int(v < 0)
        else:
            v = a+b+carry
            carry = v >> 64
        word = v & MASK
        if word:
            window = (word << 64) | previous
            base = (i-1)*64
            length = i*64+word.bit_length()
            sticky = bool(low_sticky)
            power_two = not (word & (word-1) or previous or low_sticky)
        low_sticky |= previous != 0
        previous = word
    assert carry == 0
    result = finish(window, base, length, sticky, negative, target, power_two)
    return (result, chunks) if details else result


def update(state, term):
    sn, se = state
    tn, te = term
    return fast(state, term) if not sn or not tn or abs(se-te) <= 48 else special(state, term)
