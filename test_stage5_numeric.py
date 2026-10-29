"""Three-way numeric proof experiments; fixed seed and exact decisions."""
import random, unittest, gzip, json
from pathlib import Path
from stage5_golden import requant, decision, power
from linear_stream_model.numeric import requant_bfp18, rne_shift, NumericFault

def bounded_rne(m,e,out):
    a=abs(m); d=out-e
    if not a or d>=48: q=0
    elif d<=0:
        assert -d<=16
        q=a<<-d
    else:
        q=a>>d
        guard=(a>>(d-1))&1
        sticky=bool(a&((1<<(d-1))-1))
        q+=guard and (sticky or (q&1))
    return -q if m<0 else q

def optimized(pairs):
    nz=[(m,e) for m,e in pairs if m]
    ex=max(e+abs(m).bit_length()-1 for m,e in nz)-16 if nz else 0
    first=[bounded_rne(m,e,ex) for m,e in pairs]
    retry=any(abs(q)>131071 for q in first)
    if retry:ex+=1
    q=[bounded_rne(m,e,ex) for m,e in pairs]
    assert max(map(abs,q))<=131071
    return q,ex,retry

def cases(count=3000):
    yield [(262143,-130)]
    yield [(262143,0),(5,-1)]
    yield [(-262143,0),(-5,-1)]
    yield [(65536,0),(-(1<<47),-48)]
    yield [(65536,0),((1<<47)-1,-48),(-(1<<47),-49)]
    for l in [1,7,8,9,28,29,127,128]:
        yield [(0,32767 if i%2 else -32768) for i in range(l)]
        for m in [1,-1,(1<<47)-1,-(1<<47),131071,-131071,262143,-262143]:
            yield [(m,0)]*l
    for s in range(1,48):
        for q in [0,1,2,3,65534,65535,65536,131070,131071]:
            for r in [-1,0,1]:
                m=(q<<s)+(1<<(s-1))+r
                if m < 1<<47:
                    for sign in [-1,1]:
                        # Anchor forces exactly exponent 0, so directed rounding survives group selection.
                        yield [(65536,0),(sign*m,-s)]
    for e in [-32768,-176,-175,-145,-144,-130,-129,-128,-1,0,80,81,127,128,32767]:
        for m in [0,1,-1,(1<<47)-1,-(1<<47),262143,-262143]:yield [(m,e)]
    rng=random.Random(0x5182026)
    for j in range(count):
        l=rng.choice([1,7,8,9,28,29,127,128])
        yield [(rng.randrange(-(1<<47),1<<47),rng.randrange(-32768,32768) if j<100 else rng.randrange(-150,120)) for _ in range(l)]

class NumericTests(unittest.TestCase):
    def test_exact(self):
        total=retries=faults=0
        decisions=[]
        for pairs in cases():
            g=requant(pairs); q,e,retry=optimized(pairs)
            self.assertEqual((q,e,retry),(g['mant'],g['exp'],g['retry']))
            for (m,ie),v,dec in zip(pairs,q,g['decisions']):
                self.assertEqual(v,rne_shift(m,e-ie))
                self.assertEqual(dec['rounded'],v)
                shift=e-ie
                a=abs(m)
                floor=a>>shift if shift>0 else a<<-shift
                guard=(a>>(shift-1))&1 if shift>0 else 0
                sticky=bool(a&((1<<(shift-1))-1)) if shift>0 else False
                self.assertEqual(dec['floor'],floor)
                self.assertEqual(dec['increment'],bool(guard and (sticky or floor&1)))
                self.assertEqual(dec['tie'],bool(guard and not sticky))
            try:
                old=requant_bfp18(pairs)
                self.assertEqual(old,(q,e));self.assertEqual(g['error'],0)
            except NumericFault as err:
                self.assertEqual(err.stage,'A2_GROUP_EXP');self.assertEqual(g['error'],0x33);faults+=1
            if any(m for m,ie in pairs):self.assertGreaterEqual(max(map(abs,q)),65536)
            decisions.append(dict(pairs=pairs,exp=e,mant=q,retry=retry,error=g['error'],
                rne=[dict(floor=d['floor'],remainder_hex=hex(d['remainder']),
                          denominator_pow2=d['denominator'].bit_length()-1,
                          tie=d['tie'],increment=bool(d['increment']),rounded=d['rounded']) for d in g['decisions']]))
            total+=1;retries+=retry
        dest=Path(__file__).resolve().parent/'docs/stage5/NUMERIC_DECISIONS.jsonl.gz'
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('wb') as raw:
            with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as z:
                for row in decisions:z.write((json.dumps(row,separators=(',',':'))+'\n').encode())
        print('PASS independent/existing/bounded numeric',dict(groups=total,retries=retries,range_errors=faults,seed='0x5182026'))
    def test_small_exhaustive(self):
        for m in range(-(1<<17),(1<<17)):
            q,e,retry=optimized([(m,0)])
            self.assertEqual(requant_bfp18([(m,0)]),(q,e))
        print('PASS exhaustive signed18 mantissas at exponent0: 262144')
    def test_regression(self):
        self.assertEqual(requant([(262143,-130)])['mant'],[65536])
        self.assertEqual(requant([(262143,-130)])['exp'],-128)
        # Double-rounding counterexample: +5/8 rounds1; rounding 5/4 then /2 yields0.
        self.assertEqual(round(5*power(-3)),1)
        self.assertEqual(round(round(5*power(-2))*power(-1)),0)
        for sign in [-1,1]:
            g=requant([(sign*262143,0),(sign*5,-1)])
            self.assertTrue(g['retry']);self.assertEqual(g['mant'][1],sign)

if __name__=='__main__':unittest.main(verbosity=2)
