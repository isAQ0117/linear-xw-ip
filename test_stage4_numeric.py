import random
import unittest
from fractions import Fraction
from linear_stream_model.numeric import fp8_e4m3fn_q9, fp32_positive_scale, accumulate_48, NumericFault
from stage4_golden import q9, scale, power, accum, term, dot
from stage4_a2_math import fast, special, update


def vectors(count=12000):
    rng = random.Random(0xA2482026)
    # The remote old-state bit is outside the 128bit window but breaks an
    # exact half-way tie in the HIGH 72bit term. Sticky must come from the
    # fully propagated exact sum (including borrow), not truncated inputs.
    for sn,tn in [(1,1),(-1,-1),(-1,1),(1,-1)]:
        yield (sn,-286),(tn*((1<<70)+(1<<23)),0)
    # Asymmetric boundaries, +/- ties, exact cancellation, retry normalization.
    for sn in [0,1,-1,2,-2,(1<<47)-1,-(1<<47),(1<<46),-(1<<46)]:
        for tn in [0,1,-1,2,-2,(1<<47)-1,1<<47,-(1<<47),(1<<71)-1,-(1<<71)]:
            for diff in [-537,-286,-73,-72,-65,-64,-49,-48,-47,-1,0,1,47,48,49,64,65,72,73,286,537]:
                yield (sn,0),(tn,diff)
    for i in range(count):
        se = rng.randrange(-600,601)
        te = rng.randrange(-600,601)
        sn = rng.randrange(-(1<<47),1<<47)
        tn = rng.randrange(-(1<<71),1<<71)
        # Frequently target exact powers, cancellation, and near half-way cuts.
        if i%5==0:sn = rng.choice([-1,1])*(1<<rng.randrange(47))
        if i%7==0:tn = rng.choice([-1,1])*((1<<rng.randrange(71))+rng.choice([-1,0,1]))
        yield (sn,se),(tn,te)


class Stage4NumericTests(unittest.TestCase):
    def test_fp8_all(self):
        for c in range(256):
            if c in [127,255]:
                with self.assertRaises(ValueError):q9(c)
                with self.assertRaises(NumericFault):fp8_e4m3fn_q9(c)
            else:self.assertEqual(q9(c),fp8_e4m3fn_q9(c))

    def test_fp32(self):
        rng=random.Random(32)
        bits=[0,0x80000000,0xbf800000,0x7f800000,0xff800000,0x7fc00001,1,0x7fffff,0x800000,0x7f7fffff]
        bits += [rng.randrange(1<<32) for _ in range(5000)]
        for b in bits:
            if 0 < b < 0x7f800000:
                m,e=fp32_positive_scale(b)
                self.assertEqual(scale(b),m*power(e))
            else:
                with self.assertRaises(ValueError):scale(b)
                with self.assertRaises(NumericFault):fp32_positive_scale(b)

    def test_a2_proof_vectors(self):
        for st,tm in vectors():
            existing=accumulate_48(st,tm,term_bits=72)
            self.assertEqual(accum(st,tm),existing,(st,tm))
            self.assertEqual(update(st,tm),existing,(st,tm))
            if st[0] and tm[0] and abs(st[1]-tm[1])<=48:
                self.assertEqual(fast(st,tm),special(st,tm),(st,tm))

    def test_counterexample_and_full_exponent_fields(self):
        self.assertEqual(update((1,0),(1,-286)),(70368744177664,-46))
        for st,tm in [((1,32767),(1,-2048)),((-1,-32768),(1,2047)),((1,0),(-1,-2048))]:
            self.assertEqual(update(st,tm),accumulate_48(st,tm,term_bits=72))
        with self.assertRaises(OverflowError):update((-(1<<47),32767),(-1,2047))

    def test_ordered_nonassociative(self):
        seq=[(1<<70,0),(1,0),(-(1<<70),0)]
        st=(0,0)
        for t in seq:
            a=accum(st,t)
            self.assertEqual(a,update(st,t));st=a
        exact=sum((m*power(e) for m,e in seq),Fraction())
        self.assertNotEqual(st[0]*power(st[1]),exact)

if __name__=='__main__':unittest.main()
