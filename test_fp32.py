import json
import random
import struct
import tempfile
import unittest
from fractions import Fraction

from cycle_model import Simulator, prepare, report, demo, ceildiv
from linear_stream_model.numeric import (
    NumericFault, fp32_positive_scale, fp32_exact_scale,
    fp8_e4m3fn_q9, bf16_positive_scale, accumulate_48, requant_bfp18, pow2
)

def case_for(m, n, k, scales=None, seed=19, mode=0):
    rng = random.Random(seed)
    j = ceildiv(k, 128)
    b = ceildiv(n, 128)
    if scales is None:
        # values are genuinely non-BF16-exact FP32 scales near 1.0
        scales = [[0x3f800001 + bidx * 37 + ji * 101
                   for ji in range(j)] for bidx in range(b)]
    return {
        "job": {
            "job_id": 77, "m": m, "n": n, "k": k, "static_dim_mode": mode,
            "n_dim": n, "k_dim": k, "max_n": n, "max_k": k,
            "axis_width_bits": 512
        },
        "activation": {
            "mantissa": [[rng.randint(-16000,16000) for _ in range(k)] for _ in range(m)],
            "exponents": [[rng.randint(-13, -3) for _ in range(j)] for _ in range(m)]
        },
        "weight": {
            "fp8_bits": [[rng.randint(0,126) for _ in range(k)] for _ in range(n)],
            "scale_fp32_bits": scales
        }
    }

class FP32NumericalTests(unittest.TestCase):
    def test_fp32_known_bit_patterns(self):
        known = {
            0x3f800000: Fraction(1),
            0x3f800001: Fraction((1<<23)+1,1<<23),
            0x3f808000: Fraction(257,256),
            0x00800000: Fraction(1,1<<126),  # smallest positive normal
            0x007fffff: Fraction((1<<23)-1,1<<149),  # largest subnormal
            0x00000001: Fraction(1,1<<149),  # smallest positive subnormal
            0x7f7fffff: Fraction((1<<24)-1) * pow2(104)
        }
        for bits, expected in known.items():
            with self.subTest(bits=hex(bits)):
                sig, exponent = fp32_positive_scale(bits)
                self.assertEqual(Fraction(sig)*pow2(exponent),expected)
                self.assertEqual(fp32_exact_scale(bits),expected)

    def test_fp32_crosscheck_1024_bitpatterns(self):
        rng=random.Random(65531)
        for _ in range(1024):
            exponent=rng.randrange(0,255)
            fraction=rng.randrange(1, 1<<23) if exponent==0 else rng.randrange(1<<23)
            bits=(exponent<<23)|fraction
            value=struct.unpack("<f",bits.to_bytes(4,"little"))[0]
            exact=Fraction.from_float(value)
            self.assertEqual(fp32_exact_scale(bits),exact)
            sig,ex=fp32_positive_scale(bits)
            self.assertEqual(Fraction(sig)*pow2(ex), exact)

    def test_reject_bad_scales(self):
        for bits in [0,0x80000000,0x80000001,0xbf800000,0x7f800000,0x7fc00001,
                     0xff800000,0x7fffffff,0x100000000,-1]:
            with self.subTest(bits=bits):
                with self.assertRaises(NumericFault):
                    fp32_positive_scale(bits)

    def test_same_bf16_scale_value_preserves_acc(self):
        rng=random.Random(37)
        for _ in range(200):
            # choose regular BF16 scales with exact FP32 encoding
            bf16=0x3f00+rng.randrange(0x80)
            b_sig,b_exp=bf16_positive_scale(bf16)
            f_sig,f_exp=fp32_positive_scale(bf16 << 16)
            st=(0,0)
            sf=(0,0)
            for j in range(4):
                raw=rng.randint(-(1<<41),(1<<41))
                ex=rng.randint(-10,10)
                st=accumulate_48(st,(raw*b_sig, ex-9+b_exp), term_bits=56)
                sf=accumulate_48(sf,(raw*f_sig, ex-9+f_exp), term_bits=72)
            self.assertEqual(Fraction(st[0])*pow2(st[1]),
                             Fraction(sf[0])*pow2(sf[1]))


class FP32A2RoundoffTests(unittest.TestCase):
    @staticmethod
    def fraction_rne(x):
        sign=-1 if x<0 else 1
        q,r=divmod(abs(x.numerator),x.denominator)
        if 2*r>x.denominator or (2*r==x.denominator and q%2):
            q+=1
        return sign*q

    def test_accumulate_signed72_against_fraction(self):
        rng=random.Random(123456)
        for _ in range(100):
            # Mix widely separated exponents, positive and negative terms.
            sn=rng.randrange(-(1<<46),(1<<46))
            se=rng.randrange(-30,30)
            tn=rng.randrange(-(1<<69),(1<<69))
            te=rng.randrange(-100,100)
            if tn==0: continue
            actual=accumulate_48((sn,se),(tn,te),term_bits=72)
            value=(Fraction(sn)*pow2(se)+Fraction(tn)*pow2(te))
            target=min(se,te) if sn else te
            # Form an exact reference at the initial common power of two.
            # Increase the scale by one bit until rounded signed48 fits.
            for i in range(400):
                q=self.fraction_rne(value / pow2(target+i))
                if -(1<<47) <= q < (1<<47):
                    break
            else:
                self.fail("A2 precision search failed")
            self.assertEqual(actual,(q,target+i))

class FP32DDRSimulationTests(unittest.TestCase):
    def check_cycle(self,m,n,k,ready_period=0,gap=0,latency=2,stall=0,mode=0,seed=19,
                    trace_detail=False):
        case=case_for(m,n,k,seed=seed,mode=mode)
        image,man=prepare(case)
        J=ceildiv(k,128); B=ceildiv(n,128)
        self.assertEqual(man["scale_layout"],"FP32_LE_NBLOCK128_GROUP_PAD64_V3")
        self.assertEqual(man["scale_words_per_group"],ceildiv(J,16))
        for b in range(B):
            pos=(man["scale_base"]+8*man["scale_words_per_group"]*b)//8*64
            for j in range(J):
                bits=int.from_bytes(image[pos+4*j:pos+4*j+4],"little")
                self.assertEqual(bits,case["weight"]["scale_fp32_bits"][b][j])
            self.assertFalse(any(image[pos+4*J:pos+64*ceildiv(J,16)]))
        sim=Simulator(case,image,man,ddr_latency=latency,ddr_gap=gap,
            ddr_ready_period=ready_period,output_stall_period=stall,
            trace_detail=trace_detail,max_cycles=5_000_000).run()
        with tempfile.TemporaryDirectory() as folder:
            met=report(sim,case,folder)
            read=json.loads((__import__("pathlib").Path(folder)/"output_numeric.json").read_text())
            self.assertEqual(read["mantissa"],sim.mants)
        self.assertEqual(met["ddr_requests"],B+n)
        self.assertEqual(met["ddr_return_beats"],B*ceildiv(J,16)+n*ceildiv(k,64))
        self.assertTrue(met["b3b_golden_bit_exact"])
        self.assertEqual(met["scale_format"],"IEEE754_FP32_RAW32")
        self.assertEqual(met["b2_term_width_bits"],72)
        return sim,case

    def test_mixed_boundaries_and_stalls(self):
        for m,n,k in [(1,1,1),(1,1,127),(1,2,128),(1,7,129),
                       (2,5,257),(1,129,129),(2,4,513),(1,1,4096),(1,1,12288)]:
            with self.subTest(m=m,n=n,k=k):
                self.check_cycle(m,n,k,ready_period=3,gap=1,stall=4,mode=0)

    def test_multiple_batches_static(self):
        sim,_=self.check_cycle(3,5,129,ready_period=2,gap=2,latency=0,
                               stall=3,mode=1,trace_detail=True)
        self.assertTrue(any(e["event"]=="DDR_BEAT" and
                            e["cycle"]==next(r["cycle"] for r in sim.trace
                                if r["event"]=="DDR_REQUEST")
                            for e in sim.trace))
        self.assertEqual(sim.event_counts["B1"],3*5*2)

    def test_17_scale_values_need_two_beats(self):
        sim,_=self.check_cycle(1,2,2049)
        self.assertEqual(sim.man["scale_words_per_group"],2)

    def test_fp32_scale_not_truncated_to_bf16(self):
        one=case_for(1,1,128)
        one["activation"]["mantissa"]=[[10000]*128]
        one["activation"]["exponents"]=[[0]]
        one["weight"]["fp8_bits"]=[[0x38]*128]  # 1.0
        # Floating bits 0x3f80624e represent approximately 1.003.
        one["weight"]["scale_fp32_bits"]=[[0x3f80624e]]
        image,man=prepare(one)
        sim=Simulator(one,image,man).run()
        with tempfile.TemporaryDirectory() as t: report(sim,one,t)
        vfp=Fraction(sim.mants[0][0])*pow2(sim.expout[0][0])
        self.assertGreater(abs(float(vfp)-1280000),1000)

    def test_optional_full_float_reference(self):
        case=demo()
        image,man=prepare(case)
        sim=Simulator(case,image,man).run()
        case["reference"]={"float_xw":[[float(v) for v in row] for row in sim.exact]}
        with tempfile.TemporaryDirectory() as out:
            met=report(sim,case,out)
            self.assertIn("original_float_xw_comparison",met)
            table=(__import__("pathlib").Path(out)/"element_errors.csv").read_text()
            self.assertIn("original_float_xw",table)

if __name__=="__main__":
    unittest.main()
