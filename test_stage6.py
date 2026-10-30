"""Independent AXIS golden plus register-level and hostile backpressure checks."""
import random
from stage6_model import AxisOutput,JobStatus
from stage23_golden import activation_words
from stage6_golden import output_beats as axis_tensor
from tools.run_stage67 import Trace

def output_suite():
    t=Trace('xw_axis_bfp18_output',AxisOutput());t.reset();rng=random.Random(0x6706)
    jobs=0;peak=0;timings=[]
    lengths=list(range(1,129))+[129,255,256,257,12288,1,2,7,8,9,28,29,127,128,129]
    for n in lengths:
        for mode in (['fast','stall'] if n in [1,28,128,129,12288] else ['random']):
            job=jobs+0x67000000
            vals=[rng.choice([0,-131072,131071,-1,1,rng.randrange(-131072,131072)]) for _ in range(n)]
            exps=[rng.randrange(256) for _ in range((n+127)//128)]
            gold=axis_tensor(vals,exps,job);words=activation_words(vals,exps)
            response={};observed=[];held=None;last=-1;stall_count=0
            start=len(t.rows);assert t.tick(start=1,job_id=job,job_n=n)[0]['start_ready']
            for tick in range(n*8+5000):
                ready=1 if mode=='fast' else int(tick>200 and tick%7 not in [0,1,2]) if mode=='stall' else int(rng.randrange(3)!=0)
                if len(observed)==len(gold)-1 and stall_count<60 and mode!='fast':ready=0;stall_count+=1
                i=dict(rd_ready=1,m_axis_tready=ready,**response)
                pre,post=t.tick(**i)
                assert not post['fault'],(n,mode,tick,vars(t.model))
                assert t.model.count+t.model.pending<=4
                peak=max(peak,t.model.count+t.model.pending)
                payload=tuple(pre[k] for k in ('m_axis_tdata','m_axis_tkeep','m_axis_tlast','m_axis_tuser'))
                if held is not None:assert pre['m_axis_tvalid'] and payload==held
                held=payload if pre['m_axis_tvalid'] and not ready else None
                if pre['m_axis_tvalid'] and ready:
                    observed.append(dict(zip(('s_axis_tdata','s_axis_tkeep','s_axis_tlast','s_axis_tuser'),payload)))
                    last=len(t.rows)-1
                if post['output_done']:
                    assert last==len(t.rows)-1 and observed==gold and len(observed)==len(gold),(n,mode,observed,gold)
                    break
                response={}
                if pre['rd_req']:
                    j=pre['rd_word_index'];data,mask,exp=words[j]
                    response=dict(rd_valid=1,rd_data=data,rd_exp=exp,rd_mask=mask,rd_index=j)
            else:raise AssertionError(('output watchdog',n,mode))
            for _ in range(4):
                p=t.tick(rd_ready=1,m_axis_tready=1)[1]
                assert not p['m_axis_tvalid'] and not p['output_done']
            timings.append(dict(n=n,mode=mode,cycles=last-start+1));jobs+=1
    # Reset coincident with pending response and with held final beat.
    for phase in ('pending','held'):
        t.reset();t.tick(start=1,job_n=1,job_id=99)
        t.tick(rd_ready=1)
        if phase=='held':t.tick(rd_valid=1,rd_data=1,rd_mask=1);t.tick()
        t.tick(rst_n=0,rd_valid=1,rd_data=1,rd_mask=1)
        for _ in range(5):assert not t.tick()[1]['m_axis_tvalid']
    # Fatal halt must keep an advertised stalled beat; no fabricated done.
    t.reset();t.tick(start=1,job_n=1);t.tick(rd_ready=1);t.tick(rd_valid=1,rd_mask=1,rd_data=7);t.tick()
    held=t.model.m_axis_tdata
    for _ in range(100):
        p=t.tick(halt=1)[1];assert p['m_axis_tvalid'] and p['m_axis_tdata']==held and not p['output_done']
    assert not t.tick(halt=1,m_axis_tready=1)[1]['output_done']
    t.counts=dict(jobs=jobs,lengths=lengths,peak_reserved=peak,timings=timings,reset_collisions=2,halt_stall=100)
    return t

def status_suite():
    t=Trace('xw_job_status',JobStatus());t.reset();accepted=0
    codes=[0,1,2,3,0x10,0x11,0x12,0x13,0x20,0x21,0x23,0x30,0x31,0x32,0x33,0x40]
    for j,code in enumerate(codes):
        assert t.tick(finish_valid=1,finish_job_id=j,finish_ok=int(code==0),finish_error_code=code,status_ready=1)[0]['finish_ready']
        for _ in range(150):
            pre,p=t.tick(finish_valid=1,finish_job_id=999,finish_ok=0,finish_error_code=0x40)
            assert p['status_valid'] and (p['status_job_id'],p['status_ok'],p['status_error_code'])==(j,int(code==0),code)
            assert not pre['finish_ready']
        pre,p=t.tick(status_ready=1,finish_valid=1,finish_job_id=999)
        assert pre['status_valid'] and not p['status_valid'];accepted+=1
        t.tick()
    t.tick(finish_valid=1,finish_job_id=42);t.tick(rst_n=0,status_ready=1)
    assert not t.model.status_valid
    t.counts=dict(codes=codes,statuses=accepted,stall_per_status=150)
    return t
