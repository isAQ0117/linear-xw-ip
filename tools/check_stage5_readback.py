#!/usr/bin/env python3
"""Stage6 preflight using ACTUAL synchronous RAM read records, no AXIS RTL."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from stage5_golden import requant
from linear_stream_model.numeric import requant_bfp18

def signed18(x):return x-262144 if x&131072 else x

def main():
    jobs=[]
    for label in ['controller','integration']:
        ev=[json.loads(s) for s in (ROOT/f'docs/stage5/logs/{label}_rtl_events.jsonl').read_text().splitlines()]
        for k,ready in enumerate(ev):
            if ready['event']!='JOB_RESULTS_READY':continue
            starts=[(j,e) for j,e in enumerate(ev[:k]) if e['event']=='JOB_ACCEPT']
            si,start=starts[-1];job=ready['job_id'];assert start['job_id']==job
            end=next((j for j in range(k+1,len(ev)) if ev[j]['event']=='JOB_ACCEPT'),len(ev))
            n=start['n'];reads=[e for e in ev[k:end] if e['event']=='RESULT_READ' and e['job_id']==job]
            result={e['index']:e for e in reads};assert sorted(result)==list(range((n+7)//8))
            a2=[e for e in ev[si:k] if e['event']=='RESULT_ACCEPT' and e['job_id']==job]
            assert [e['channel'] for e in a2]==list(range(n))
            mants=[];exps=[]
            for word,e in sorted(result.items()):
                count=min(8,n-word*8);mask=(1<<count)-1;bits=int(e['data_hex'],16)
                assert e['mask']==mask and bits>>(count*18)==0
                mants.extend(signed18((bits>>(18*l))&0x3ffff) for l in range(count))
                if word%16==0:exps.append(e['exp'])
                else:assert e['exp']==exps[word//16]
            beats=0
            for g,lo in enumerate(range(0,n,128)):
                pairs=[(e['mant'],e['exp']) for e in a2[lo:lo+128]]
                gold=requant(pairs);actual=mants[lo:lo+128]
                assert (actual,exps[g])==(gold['mant'],gold['exp'])==requant_bfp18(pairs)
                # Test-only 28-lane regrouping. No TUSER/status/sender implementation.
                restored=[]
                for off in range(0,len(actual),28):
                    part=actual[off:off+28]
                    payload=sum((m&0x3ffff)<<(18*l) for l,m in enumerate(part))
                    assert payload < (1<<512) and payload>>(18*len(part))==0
                    restored.extend(signed18((payload>>(18*l))&0x3ffff) for l in range(len(part)))
                    beats+=1
                assert restored==actual
            jobs.append(dict(suite=label,job_id=job,n=n,read_words=len(result),groups=len(exps),test_only_512bit_beats=beats))
    assert jobs and any(j['n']==12288 for j in jobs) and any(j['n']==129 for j in jobs)
    (ROOT/'docs/stage5/READBACK_RESULTS.json').write_text(json.dumps(dict(status='PASS',source='actual RTL RESULT_READ events; independently checked against A2 Fraction Golden and original requant; software-only 28-lane roundtrip',jobs=jobs),indent=2)+'\n')
    print('PASS actual Result Buffer readback and Stage6 regrouping preflight',len(jobs),'jobs')
if __name__=='__main__':main()
