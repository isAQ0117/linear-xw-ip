"""Independent scoreboards plus exact registered-state stimuli for real HDL."""
import random
from pathlib import Path
from stage4_model import B1,B2,A2,signed
from stage4_golden import dot,term,accum
from test_stage4_numeric import vectors
from linear_stream_model.numeric import accumulate_48
from tools.gen_stage4_tb import ports


class Trace:
    def __init__(self,name,model):
        self.name,self.model,self.rows=name,model,[]
        self.ins=[(n,w) for d,n,w in ports(name) if d=='input' and n!='clk']
        self.outs=[(n,w) for d,n,w in ports(name) if d=='output']
        self.counts={};self.events=[]
        self.step(rst_n=0);self.step(rst_n=0);self.step()
    @staticmethod
    def pack(fields,values):
        v=0
        for n,w in fields:v=(v<<w)|(int(values[n])&((1<<w)-1))
        return v
    def step(self,**kwargs):
        i={n:kwargs.get(n,1 if n=='rst_n' else 0) for n,w in self.ins}
        if not i['rst_n']:self.model.reset()
        pre=self.model.snapshot(**i)
        self.model.trace_cycle=len(self.rows)
        self.model.step(**i)
        post=self.model.snapshot(**i)
        if hasattr(self.model,'edge_events'):self.events.extend(self.model.edge_events)
        self.rows.append((self.pack(self.ins,i),self.pack(self.outs,pre),self.pack(self.outs,post)))
        return pre,post
    def save(self,path):
        with Path(path).open('w') as f:
            for i,p,o in self.rows:f.write(f'{i:x} {p:x} {o:x}\n')
    def reset(self):self.step(rst_n=0);self.step()


def pack_x(x):return sum((a&0x3ffff)<<(18*l) for l,a in enumerate(x))
def pack_w(w):return sum(a<<(8*l) for l,a in enumerate(w))


def b1_suite():
    t=Trace('xw_b1_dot128',B1());rng=random.Random(0xB1128);blocks=0;intervals=[];latencies=[]
    legal=[c for c in range(256) if c not in [127,255]]
    def block(xs,ws,ex=0,gaps=False):
        nonlocal blocks
        gold=dot(xs,ws);start=len(t.rows);accepted=[]
        for s,lo in enumerate(range(0,len(xs),8)):
            if gaps and rng.randrange(3)==0:t.step()
            part=xs[lo:lo+8];ww=ws[lo:lo+8]+[255]*(8-len(part))
            i=dict(in_valid=1,in_x=pack_x(part),in_w=pack_w(ww),in_mask=(1<<len(part))-1,in_exp=ex&255,
                   in_block=blocks,in_slice=s,in_last=int(lo+8>=len(xs)),out_ready=0)
            assert t.step(**i)[0]['in_ready'];accepted.append(len(t.rows)-1)
        for _ in range(12):
            _,p=t.step()
            assert not p['fault']
            if p['out_valid']:break
        else:raise AssertionError('B1 timeout')
        assert (p['out_raw'],p['out_exp'],p['out_block'])==(gold,ex,blocks)
        latencies.append(len(t.rows)-1-accepted[0]+1)
        intervals.extend(b-a for a,b in zip(accepted,accepted[1:]))
        held=p.copy()
        for _ in range(3):
            p=t.step()[1];assert all(p[n]==held[n] for n in ['out_valid','out_raw','out_exp','out_block'])
        t.step(out_ready=1);t.step();blocks+=1
    ks=[1,7,8,9,127,128,129,2048,2049,4096,12288]
    for mode in range(4):
        for k in ks:
            xs=([0]*k if mode==0 else [131071]*k if mode==1 else [-131072]*k if mode==2 else [rng.randrange(-131072,131072) for _ in range(k)])
            ws=([0x7e]*k if mode==1 else [0xfe]*k if mode==2 else [rng.choice(legal) for _ in range(k)])
            for lo in range(0,k,128):block(xs[lo:lo+128],ws[lo:lo+128],rng.randrange(-128,128),mode==3)
    for c in range(256):
        if c in (127,255):
            t.reset();p=t.step(in_valid=1,in_mask=1,in_w=c,in_last=1)[1]
            assert p['fault'] and p['error_code']==0x31 and not p['out_valid']
            assert t.step(abort=1)[1]['error_code']==0x31
            t.reset()
        else:block([-131072,131071,-1,1,0,19,-7,100],[c]*8)
    # Masked illegal byte is neither decoded nor diagnosed.
    block([5],[0x38]);t.reset()
    t.step(in_valid=1,in_mask=255,in_x=1,in_last=0)
    assert t.step(abort=1)[1]['error_code']==0x40
    for _ in range(8):assert not t.step()[1]['out_valid']
    t.reset()
    assert t.step(in_valid=1,in_slice=1,in_w=127,in_mask=1)[1]['error_code']==0x40
    t.reset();t.step(in_valid=1,in_last=1,in_mask=255,in_x=1)
    t.step(rst_n=0)
    for _ in range(8):assert not t.step()[1]['out_valid']
    t.counts=dict(blocks=blocks,k_matrix=ks,all_fp8_codes=256,continuous_interval=1,
                  max_b1_cycles_no_gaps=20,cycles=len(t.rows))
    return t


def b2_suite():
    t=Trace('xw_b2_fp32_pipe',B2());rng=random.Random(0xB232);queue=[];sent=0;received=0
    scales=[1,2,0x7fffff,0x800000,0x800001,0x3f800000,0x3f800001,0x7f7fffff,0,0x80000000,0xbf800000,0x7f800000,0xff800000,0x7fc00001,0xffffffff]
    raws=[-(1<<47),(1<<47)-1,0,1,-1]
    cases=[(r,[-128,0,127][j%3],s) for j,s in enumerate(scales) for r in raws]
    cases += [(rng.randrange(-(1<<47),1<<47),rng.randrange(-128,128),rng.randrange(1<<32)) for _ in range(5000)]
    pending=None
    for tick in range(50000):
        if pending is None and sent<len(cases) and rng.randrange(4):pending=cases[sent]
        i=dict(out_ready=int(rng.randrange(4)!=0))
        if pending:
            r,e,s=pending;i.update(in_valid=1,in_raw=r,in_exp=e&255,in_scale=s,in_block=sent)
        pre,post=t.step(**i)
        if pre['out_valid'] and i['out_ready']:
            assert queue
            expected=queue.pop(0)
            assert (pre['out_mant'],pre['out_exp'],pre['out_error'],pre['out_block'])==expected
            received+=1
        if pending and pre['in_ready']:
            r,e,s=pending
            m,ex=term(r,e,s) if 0<s<0x7f800000 else (0,0)
            queue.append((m,ex,0 if 0<s<0x7f800000 else 0x30,sent))
            sent+=1;pending=None
        if received==len(cases):break
    else:raise AssertionError('B2 timeout')
    t.step(in_valid=1,in_raw=1,in_scale=0x3f800000)
    t.step(abort=1)
    for _ in range(5):assert not t.step(out_ready=1)[1]['out_valid']
    t.counts=dict(cases=sent,cycles=len(t.rows),backpressure='random, seed 0xB232',stages=2)
    return t


def a2_suite():
    t=Trace('xw_a2_accum48',A2());fast=[];special=[];retries=0;updates=0;vector_count=0
    def submit(tm,block):
        nonlocal retries,updates
        start=len(t.rows)
        assert t.step(in_valid=1,in_mant=tm[0],in_exp=tm[1]&4095,in_block=block)[0]['in_ready']
        for _ in range(600):
            _,p=t.step()
            if p['update_valid']:
                (special if p['special_path'] else fast).append(len(t.rows)-start)
                retries+=bool(t.model.retried);updates+=1
                return p['state_mant'],p['state_exp']
            assert not p['fault'],(tm,p)
        raise AssertionError('A2 timeout')
    for j,(st,tm) in enumerate(vectors(5000)):
        vector_count+=1
        t.step(clear=1)
        if st[0]:seed=submit(st,j)
        elif st[1]:
            submit((1,st[1]),j);seed=submit((-1,st[1]),j)
        else:seed=(0,0)
        assert seed==st,(seed,st)
        expected=accum(st,tm)
        assert expected==accumulate_48(st,tm,term_bits=72)
        assert submit(tm,j)==expected,(st,tm)
    # Every update consumes previous committed rounded pair, including lost tiny terms.
    t.step(clear=1);state=(0,0)
    for j,tm in enumerate([(1<<70,0),(1,0),(-(1<<70),0),(1,-286),(1,0),(-1,0),(0,127)]):
        state=accum(state,tm);assert submit(tm,j)==state
    t.step(clear=1);t.step(in_valid=1,in_mant=1)
    assert t.step(clear=1)[1]['error_code']==0x40
    t.reset();t.step(in_valid=1,in_mant=1)
    assert t.step(abort=1)[1]['error_code']==0x40
    t.reset();t.step(in_valid=1,in_mant=1)
    t.step(rst_n=0)
    for _ in range(20):assert not t.step()[1]['update_valid']
    t.counts=dict(vectors=vector_count,updates=updates,retries=retries,fast_count=len(fast),special_count=len(special),
                  fast_min=min(fast),fast_max=max(fast),special_min=min(special),special_max=max(special),cycles=len(t.rows))
    return t
