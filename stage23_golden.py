"""Independent data-level oracles. No imports from any cycle/RTL model.

AXIS stimulus is constructed bit-by-bit and headers via little-endian bytes;
DDR regions are constructed in byte coordinates before converting to address
units. This intentionally differs from the RTL shifts/range arithmetic.
"""
import struct


def axis_tensor(values, exponents, job_id):
    assert 1 <= len(values) <= 65535
    assert len(exponents) == (len(values) + 127) // 128
    records = []
    for g, begin in enumerate(range(0, len(values), 128)):
        group = values[begin:begin + 128]
        for offset in range(0, len(group), 28):
            part = group[offset:offset + 28]
            bits = [0] * 512
            for i, value in enumerate(part):
                assert -131072 <= value <= 131071
                raw = value % 262144
                for b in range(18):
                    bits[i * 18 + b] = raw // (2 ** b) % 2
            payload = int(''.join(map(str, reversed(bits))), 2)
            last = offset + len(part) == len(group)
            header = bytearray(16)
            header[0:4] = struct.pack('<I', job_id)
            header[6:8] = struct.pack('<H', g)
            header[8] = exponents[g] % 256
            header[9] = len(group)
            header[10] = offset
            header[11] = int(last and begin + len(group) == len(values))
            header[12] = 0xb2
            used = (len(part) * 18 + 7) // 8
            keep = int('0' * (64-used) + '1' * used, 2)
            records.append(dict(s_axis_tdata=payload, s_axis_tkeep=keep,
                                s_axis_tlast=int(last),
                                s_axis_tuser=int.from_bytes(header, 'little')))
    return records


def activation_words(values, exponents):
    result = []
    for i in range(0, len(values), 8):
        lanes = values[i:i+8]
        # String concatenation gives an independent two's-complement packing.
        s = ''.join(f'{v % 262144:018b}' for v in reversed(lanes))
        result.append((int(s, 2), (2 ** len(lanes))-1, exponents[i//128] % 256))
    return result


def layout(n, k, wb, sb):
    if not (1 <= n <= 65535 and 1 <= k <= 65535):
        return 1, []
    # Convert address units to byte positions first; regions are half-open.
    row_bytes = ((k + 63) // 64) * 64
    scale_bytes = ((((k+127)//128)*4 + 63)//64)*64
    wr = (wb*8, wb*8+n*row_bytes)
    sr = (sb*8, sb*8+((n+127)//128)*scale_bytes)
    if wb % 8 or sb % 8 or min(wb, sb) < 0 or max(wr[1],sr[1]) > 2**32:
        return 3, []
    if max(wr[0],sr[0]) < min(wr[1],sr[1]):
        return 3, []
    objects = [(0, g, (sr[0]+g*scale_bytes)//8, scale_bytes//64)
               for g in range((n+127)//128)]
    objects += [(1, r, (wr[0]+r*row_bytes)//8, row_bytes//64) for r in range(n)]
    return 0, objects


def ranges(base, words, burst):
    # Enumerate all beat addresses then partition, independently of gen FSM.
    addresses = list(range(base, base+words*8, 8))
    return [(a[0], a[-1], len(a), p)
            for p in range(0, len(addresses), burst)
            for a in [addresses[p:p+burst]]]
