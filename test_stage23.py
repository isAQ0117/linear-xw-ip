"""Data-level assertions + exact cycle stimuli, independent of HDL execution.

build_suites returns traces which the real HDL runner consumes. All traffic is
seeded; failures raise, and neither software nor static checks imply HDL PASS.
"""
import random
import unittest
from pathlib import Path
from stage23_model import Parser, Buffer, AddrGen, Harness
from stage23_golden import axis_tensor, activation_words, layout, ranges
from stage1_contract_model import DdrRangeReceiver, ScaleGroupCache
from tools.gen_stage23_tb import ports


class Trace:
    def __init__(self, name, model, seed=0):
        self.name, self.model, self.rows = name, model, []
        self.ins = [(p,w) for d,p,w in ports(name) if d=='input' and p!='clk']
        self.outs = [(p,w) for d,p,w in ports(name) if d=='output']
        self.rng = random.Random(seed)
        self.counts = {}
        self.step(rst_n=0)
        self.step(rst_n=0)
        self.step()

    def snapshot(self, **i):
        # Stage-1 model port spelling adapter, not an oracle.
        if self.name == 'xw_ddr_range_rx':
            r=self.model
            c=self.rx_args(i)
            return r.outputs(**{k:v for k,v in c.items() if k in ('rst_n','cmd_valid','start','end','beats','ddr_rd_rdy')}) | r.snapshot()
        if self.name == 'xw_scale_group_cache':
            return self.model.snapshot()
        return self.model.snapshot(**i)

    @staticmethod
    def rx_args(i):
        return {({'cmd_addr_start':'start','cmd_addr_end':'end','cmd_beats':'beats','cmd_kind':'kind'}.get(k,k)):v for k,v in i.items()}

    def step(self, **i):
        i = {p:i.get(p, 1 if p=='rst_n' else 0) for p,w in self.ins}
        if not i['rst_n']:
            if hasattr(self.model,'reset_all'):
                self.model.reset_all()
            else:
                self.model.reset()
        pre = self.snapshot(**i)
        if self.name == 'xw_ddr_range_rx':
            self.model.step(**self.rx_args(i))
        else:
            self.model.step(**i)
        post = self.snapshot(**i)
        self.rows.append((self.packed(self.ins,i),self.packed(self.outs,pre),self.packed(self.outs,post)))
        return pre,post

    @staticmethod
    def packed(fields, values):
        x=0
        for n,w in fields:
            v=int(values[n])
            assert 0 <= v < (1<<w), (n,v,w)
            x=(x<<w)|v
        return x

    def save(self, path):
        with Path(path).open('w') as f:
            for i,pre,post in self.rows:
                f.write(f'{i:x} {pre:x} {post:x}\n')


def parser_suite():
    t=Trace('xw_axis_bfp18_input',Parser(65535),0x1828)
    good=[1,7,8,27,28,29,63,64,65,127,128,129,2048,2049,4096,12288,65535]
    good += [t.rng.randrange(1,700) for _ in range(12)]
    for job,k in enumerate(good,17):
        values=[t.rng.randrange(-131072,131072) for _ in range(k)]
        values[:min(k,4)] = [-131072,131071,-1,0][:min(k,4)]
        exps=[t.rng.randrange(-128,128) for _ in range((k+127)//128)]
        beats=axis_tensor(values,exps,job)
        expected=activation_words(values,exps)
        t.step(job_begin=1,job_id=job,job_k=k)
        index=0; words=[]; pending=None; done=False
        for tick in range(k*5+1000):
            if pending is None and index<len(beats) and t.rng.randrange(4):
                pending=beats[index]
            i=dict(wr_ready=int(t.rng.randrange(5)!=0))
            if pending:
                i.update(pending,s_axis_tvalid=1)
            pre,post=t.step(**i)
            if pending and pre['s_axis_tready']:
                index+=1; pending=None
            if pre['wr_valid'] and i['wr_ready']:
                assert pre['wr_word_index']==len(words)
                assert pre['wr_last']==(len(words)+1==len(expected))
                words.append((pre['wr_data'],pre['wr_mask'],pre['wr_exp']))
            if post['done']:
                done=True;break
            assert not post['fault']
        assert done and index==len(beats) and words==expected,(k,index,len(words))
        t.step()
    # Every frozen header/sequence/payload/terminator field, error priority,
    # stalled output preservation, reset mid-pack, sticky new-job rejection.
    mutations=[('job',0,0x10),('tag',96,0x10),('r0',57,0x10),('r1',89,0x10),('r2',104,0x10),
               ('row',32,0x11),('group',48,0x11),('len',72,0x11),('offset',80,0x11),
               ('eot',88,0x13),('last',None,0x13),('keep',None,0x12),('pad',None,0x12)]
    for name,bit,code in mutations:
        t.step(rst_n=0);t.step(job_begin=1,job_id=9,job_k=129)
        b=axis_tensor(list(range(129)),[-128,127],9)[0].copy()
        if bit is not None:b['s_axis_tuser']^=1<<bit
        elif name=='last':b['s_axis_tlast']^=1
        elif name=='keep':b['s_axis_tkeep']^=1
        else:b['s_axis_tdata']|=1<<511
        _,o=t.step(**b,s_axis_tvalid=1,wr_ready=1)
        assert o['fault'] and o['error_code']==code,(name,o)
        for _ in range(3):
            _,o=t.step(job_begin=1,job_k=1,wr_ready=1)
            assert not o['s_axis_tready'] and not o['wr_valid'] and o['error_code']==code
    for data_bit in (18,19,23,24,503,504,511):
        t.step(rst_n=0);t.step(job_begin=1,job_id=9,job_k=1)
        b=axis_tensor([-131072],[-128],9)[0]
        b['s_axis_tdata']|=1<<data_bit
        assert t.step(**b,s_axis_tvalid=1)[1]['error_code']==0x12
    for keep_bit in (0,2,3,63):
        t.step(rst_n=0);t.step(job_begin=1,job_id=9,job_k=1)
        b=axis_tensor([1],[0],9)[0];b['s_axis_tkeep']^=1<<keep_bit
        assert t.step(**b,s_axis_tvalid=1)[1]['error_code']==0x12
    # Inconsistent exponent in a non-first beat.
    t.step(rst_n=0);t.step(job_begin=1,job_id=9,job_k=128)
    bs=axis_tensor(list(range(128)),[4],9)
    t.step(**bs[0],s_axis_tvalid=1,wr_ready=1)
    while not t.model.ready():t.step(wr_ready=1)
    b=bs[1].copy();b['s_axis_tuser']^=1<<64
    assert t.step(**b,s_axis_tvalid=1)[1]['error_code']==0x11
    # Error precedence with multiple bad fields.
    t.step(rst_n=0);t.step(job_begin=1,job_id=1,job_k=1)
    assert t.step(s_axis_tvalid=1,s_axis_tdata=2**511)[1]['error_code']==0x10
    # Reset while residue/output pending; abort prevents any reuse.
    t.step(rst_n=0);t.step(job_begin=1,job_id=9,job_k=128)
    t.step(**bs[0],s_axis_tvalid=1)
    for _ in range(10):t.step(wr_ready=0)
    held=t.model.snapshot()
    for _ in range(5):
        post=t.step(wr_ready=0)[1]
        for f in ('wr_valid','wr_data','wr_mask','wr_exp','wr_word_index','wr_last'):assert post[f]==held[f]
    t.step(abort=1)
    assert t.step(job_begin=1,job_k=1)[1]['fault']
    t.step(rst_n=0);assert not t.step()[1]['wr_valid']
    t.step(rst_n=0);t.step(job_begin=1,job_id=9,job_k=1)
    beat=axis_tensor([7],[0],9)[0]
    pre,post=t.step(job_begin=1,job_id=9,job_k=1,s_axis_tvalid=1,**beat)
    assert not pre['s_axis_tready'] and post['error_code']==0x40 and not post['wr_valid']
    t.counts=dict(legal_jobs=len(good),malformed_fields=len(mutations)+13,boundary_k=good[:17])
    return t


def buffer_suite(kind):
    t=Trace('xw_activation_buffer' if kind=='x' else 'xw_weight_row_buffer',Buffer(kind,65535),0x88)
    for k in [1,7,8,28,127,128,129,2048,2049,12288,65535]+[t.rng.randrange(1,2000) for _ in range(8)]:
        t.step(load_begin=1,load_k=k)
        if kind=='x':
            src=[t.rng.randrange(-131072,131072) for _ in range(k)]
            exp=[t.rng.randrange(-128,128) for _ in range((k+127)//128)]
            expected=activation_words(src,exp)
            for idx,(data,mask,e) in enumerate(expected):
                if t.rng.randrange(2):t.step()
                _,o=t.step(wr_valid=1,wr_word_index=idx,wr_data=data,wr_mask=mask,wr_exp=e,wr_last=int(idx+1==len(expected)))
                assert o['loaded']==(idx+1==len(expected))
        else:
            # Nonzero DDR padding proves masked lanes do not leak into B1.
            src=bytes(t.rng.randrange(256) for _ in range(k))
            payload=src+bytes([0xa5])*((-k)%64)
            expected=[(int.from_bytes(src[idx:idx+8],'little'),(1<<len(src[idx:idx+8]))-1) for idx in range(0,k,8)]
            for idx in range(len(payload)//64):
                _,o=t.step(wr_valid=1,wr_word_index=idx,wr_data=int.from_bytes(payload[idx*64:(idx+1)*64],'little'))
                assert o['loaded']==(idx+1==len(payload)//64)
        for idx in list(range(len(expected)))+[t.rng.randrange(len(expected)) for _ in range(4)]:
            _,o=t.step(rd_req=1,rd_word_index=idx)
            want=expected[idx]
            assert o['rd_valid'] and o['rd_data']==want[0] and o['rd_mask']==want[1]
            if kind=='x':assert o['rd_exp']==want[2]
        assert not t.step()[1]['rd_valid']
    # Buffer misuse tests; each must invalidate and lock until reset.
    cases=[dict(rd_req=1),dict(load_begin=1,load_k=0),dict(load_begin=1,load_k=1,wr_valid=1),
           dict(wr_valid=1),dict(abort=1)]
    for i in cases:
        t.step(rst_n=0)
        _,o=t.step(**i)
        assert o['fault'] and o['error_code']==(0x23 if kind=='w' and i==dict(wr_valid=1) else 0x40)
        assert not o['loaded']
        assert not t.step(load_begin=1,load_k=1,rd_req=1)[1]['rd_valid']
    for index in [1,65535]:
        t.step(rst_n=0);t.step(load_begin=1,load_k=129)
        assert t.step(wr_valid=1,wr_word_index=index)[1]['error_code']==(0x40 if kind=='x' else 0x23)
    t.step(rst_n=0);t.step(load_begin=1,load_k=129)
    assert t.step(load_begin=1,load_k=1)[1]['error_code']==0x40
    t.step(rst_n=0);t.step(load_begin=1,load_k=1)
    if kind=='x':
        assert t.step(wr_valid=1,wr_data=2**18,wr_mask=1,wr_last=1)[1]['error_code']==(0x40 if kind=='x' else 0x23)
        for kw in [dict(wr_mask=255,wr_last=1),dict(wr_mask=1,wr_last=0)]:
            t.step(rst_n=0);t.step(load_begin=1,load_k=1)
            assert t.step(wr_valid=1,**kw)[1]['error_code']==(0x40 if kind=='x' else 0x23)
        t.step(rst_n=0);t.step(load_begin=1,load_k=16)
        t.step(wr_valid=1,wr_word_index=0,wr_mask=255,wr_exp=4)
        assert t.step(wr_valid=1,wr_word_index=1,wr_mask=255,wr_exp=5,wr_last=1)[1]['error_code']==(0x40 if kind=='x' else 0x23)
    t.step(rst_n=0);t.step(load_begin=1,load_k=1)
    good=dict(wr_mask=1,wr_last=1) if kind=='x' else {}
    t.step(wr_valid=1,**good)
    assert t.step(rd_req=1,rd_word_index=1)[1]['error_code']==0x40
    t.step(rst_n=0);t.step(load_begin=1,load_k=1)
    assert t.step(wr_valid=1,rd_req=1,**good)[1]['error_code']==0x40
    t.step(rst_n=0);t.step(load_begin=1,load_k=1)
    t.step(wr_valid=1,**good)
    assert t.step(wr_valid=1,**good)[1]['error_code']==(0x40 if kind=='x' else 0x23)
    t.step(rst_n=0);t.step(load_begin=1,load_k=1)
    pre,post=t.step(abort=1,wr_valid=1,**good)
    assert not post['loaded'] and post['error_code']==0x40
    t.step(rst_n=0,wr_valid=1,**good)
    assert not t.step()[1]['loaded']
    t.counts=dict(legal_loads=19,random_seed=0x88,misuse_cases=12 if kind=='w' else 16)
    return t


def addr_suite(burst):
    t=Trace('xw_ddr_addr_gen',AddrGen(burst,65535,65535),0xadd2+burst)
    for n in [127,128,129]:
        for k in [127,128,129,2048,2049,12288,65535]:
            wb=8*t.rng.randrange(0,100)
            sb=wb+8*n*((k+63)//64)
            assert t.step(cfg_begin=1,cfg_n=n,cfg_k=k,cfg_weight_base=wb,cfg_scale_base=sb)[1]['cfg_error']==0
            err,objects=layout(n,k,wb,sb);assert err==0
            # Tail groups and first/middle/final rows, not 129 redundant copies.
            selected=[o for o in objects if o[0]==0 or o[1] in (0,n//2,n-1)]
            for kind,index,base,words in selected:
                pre,post=t.step(load_valid=1,load_kind=kind,load_index=index)
                assert pre['load_ready']
                requests=[];inits=0
                for tick in range(words*20+200):
                    pre0=t.model.snapshot()
                    init=pre0['scale_load_begin'] or pre0['weight_load_begin']
                    inits+=int(init)
                    # Isolated receiver stub: response completion after accepted
                    # request, with random latency; buffer_loaded delayed again.
                    if pre0['cmd_valid']:
                        ready=int(t.rng.randrange(4)!=0)
                    else:ready=0
                    if t.model.state==AddrGen.RECEIVE:
                        done=int(t.rng.randrange(3)==0)
                    else:done=0
                    pre,post=t.step(cmd_ready=ready,range_done=done,buffer_loaded=int(t.model.state==AddrGen.LOADED))
                    if pre['cmd_valid'] and ready:
                        requests.append((pre['cmd_addr_start'],pre['cmd_addr_end'],pre['cmd_beats'],pre['segment_offset']))
                    if post['load_done']:break
                    assert not post['fault']
                else:raise AssertionError('address completion')
                assert requests==ranges(base,words,burst),(n,k,kind,index,requests)
                assert inits==1
                t.step()
    # Boundary exactly 2^29 allowed; overflow, overlap, unaligned rejected.
    for n,k,wb,sb,code in [(1,1,2**29-8,0,0),(1,1,0,2**29-8,0),
                          (2,64,2**29-8,0,3),(1,65,0,8,3),(1,1,1,16,3),
                          (1,1,0,9,3),(0,1,0,16,1),(1,0,0,16,1),
                          (65535,65535,0,2**29-8,3)]:
        _,o=t.step(cfg_begin=1,cfg_n=n,cfg_k=k,cfg_weight_base=wb,cfg_scale_base=sb)
        assert o['cfg_done'] and o['cfg_error_code']==code
        assert not o['fault']
    for kind,wb,sb in [(1,2**29-8,0),(0,0,2**29-8)]:
        t.step(cfg_begin=1,cfg_n=1,cfg_k=1,cfg_weight_base=wb,cfg_scale_base=sb)
        t.step(load_valid=1,load_kind=kind)
        t.step()
        pre,post=t.step(cmd_ready=1)
        assert (pre['cmd_addr_start'],pre['cmd_addr_end'],pre['cmd_beats'])==(2**29-8,2**29-8,1)
        t.step(range_done=1);t.step();t.step(buffer_loaded=1);t.step()
    t.step(cfg_begin=1,cfg_n=1,cfg_k=1,cfg_weight_base=0,cfg_scale_base=8)
    t.step(load_valid=1,load_kind=1,load_index=1)
    assert t.model.error_code==0x40
    t.step(rst_n=0)
    t.step(range_error=1,range_error_code=0x21)
    assert t.step(cfg_begin=1)[1]['error_code']==0x21
    t.step(rst_n=0)
    assert t.step(buffer_error=1,buffer_error_code=0x23)[1]['error_code']==0x23
    t.step(rst_n=0)
    t.step(cfg_begin=1,cfg_n=1,cfg_k=2049,cfg_scale_base=8*33)
    t.step(load_valid=1,load_kind=1)
    assert t.step(cfg_begin=1)[1]['error_code']==0x40
    for priority in ('range_error','buffer_error','abort','reset'):
        t.step(rst_n=0)
        t.step(cfg_begin=1,cfg_n=1,cfg_k=1,cfg_scale_base=8)
        t.step(load_valid=1,load_kind=1);t.step();t.step(cmd_ready=1)
        t.step(range_done=1);t.step()
        assert t.model.state==AddrGen.LOADED
        inputs={'buffer_loaded':1}
        if priority=='reset':inputs['rst_n']=0
        elif priority=='range_error':inputs.update(range_error=1,range_error_code=0x21)
        elif priority=='buffer_error':inputs.update(buffer_error=1,buffer_error_code=0x23)
        else:inputs['abort']=1
        pre,post=t.step(**inputs)
        assert not pre['load_done'] and not post['load_done']
    t.counts=dict(burst=burst,config_matrix=21,config_negative_cases=7)
    return t


class DDRDriver:
    def __init__(self, trace):
        self.t=trace;self.image={};self.queue=[];self.requests=[];self.beats=[];self.events=[]
        self.cycle=0;self.job=0;self.gaps=True;self.same_edge=True

    def tick(self, **i):
        # Build a legal physical response schedule solely from accepted ranges.
        i.setdefault('ddr_rd_rdy',int(self.t.rng.randrange(4)!=0))
        i.setdefault('ddr_rd_vld',0)
        i.setdefault('ddr_rd_data',0)
        before=self.t.model.snapshot(**i)
        if before['ddr_rd_req']:
            assert not self.queue,'second outstanding physical range'
            a,b=before['ddr_rd_addra'],before['ddr_rd_addrb']
            self.queue=list(range(a,b+1,8))
            self.requests.append((a,b,(b-a)//8+1))
        ready_response=(not self.gaps or self.t.rng.randrange(3)!=0)
        if self.queue and ready_response and (not before['ddr_rd_req'] or self.same_edge):
            addr=self.queue.pop(0)
            assert addr in self.image,('read outside image',addr)
            i['ddr_rd_vld'],i['ddr_rd_data']=1,self.image[addr]
            self.beats.append(addr)
        old_word=(self.t.model.r.word_valid,self.t.model.r.word_kind,
                  self.t.model.a.offset+self.t.model.r.word_index,self.t.model.a.total_words)
        pre,post=self.t.step(**i)
        # Independent timing assertions: physical final beat is not a RAM commit.
        if not post['fault_lock']:
            if i['ddr_rd_vld'] and self.t.model.r.range_done:
                loaded=self.t.model.w.loaded_reg if self.t.model.r.word_kind else self.t.model.s.loaded
                assert not loaded,'Loaded before final receiver register was committed'
            if old_word[0]:
                loaded=self.t.model.w.loaded_reg if old_word[1] else self.t.model.s.loaded
                assert loaded==(old_word[2]+1==old_word[3]),'logical final write / Loaded mismatch'
            if post['object_done']:
                assert self.t.model.w.loaded_reg if self.t.model.a.kind else self.t.model.s.loaded
        for event,yes,fields in [
            ('JOB_ACCEPT',i.get('job_valid',0) and pre['job_ready'],{}),
            ('AXIS_IN_ACCEPT',i.get('s_axis_tvalid',0) and pre['s_axis_tready'],
             {'group':(i.get('s_axis_tuser',0)>>48)&511,'offset':(i.get('s_axis_tuser',0)>>80)&255}),
            ('DDR_REQ_ACCEPT',pre['ddr_rd_req'],{'start':pre['ddr_rd_addra'],'end':pre['ddr_rd_addrb']}),
            ('DDR_BEAT',i['ddr_rd_vld'],{}),
            ('RANGE_DONE',self.t.model.r.range_done,{}),
            ('CACHE_OBJECT_DONE',post['object_done'],{}),
            ('CACHE_TEST_RESULT_ACCEPT',pre['result_valid'] and i.get('result_ready',0),{'code':pre['result_code']})]:
            if yes:self.events.append(dict(cycle=self.cycle,event=event,job_id=self.job,**fields))
        self.cycle+=1
        return pre,post

    def until(self, predicate, limit=200000, **i):
        for _ in range(limit):
            pre,post=self.tick(**i)
            if predicate(post):return post
            assert not post['fault_lock'],('unexpected harness fault',post,self.t.model.state)
        raise AssertionError('simulation-time timeout in driver')


def harness_suite(burst, static=0):
    t=Trace('xw_stage23_harness',Harness(burst,static=static),0x2330+burst+static)
    d=DDRDriver(t)
    d.tick();d.tick();d.tick()
    cases=[(2,129)] if static else [(1,1),(127,127),(128,128),(129,129),(2,2048),(129,2049),(2,12288)]
    for case_index,(n,k) in enumerate(cases):
        job=0xa530+case_index;d.job=job
        x=[t.rng.randrange(-131072,131072) for _ in range(k)]
        exps=[t.rng.randrange(-128,128) for _ in range((k+127)//128)]
        beats=axis_tensor(x,exps,job);goldx=activation_words(x,exps)
        wb,sb=0x100,0x100+8*n*((k+63)//64)
        err,objects=layout(n,k,wb,sb);assert err==0
        weights={};scales={};d.image={};startreq=len(d.requests);startbeat=len(d.beats)
        for kind,index,base,words in objects:
            if kind:
                source=bytes(t.rng.randrange(256) for _ in range(k))
                weights[index]=source
                payload=source+bytes([0xa5])*((-k)%64)
            else:
                # Include FP32 raw extrema and non-BF16-exact values. The buffer
                # transports bits; arithmetic validation belongs to Stage4.
                edges=[0x00000001,0x007fffff,0x00800000,0x3f800001,0x3f80624e,0x7f7fffff]
                source=[edges[(j+index)%len(edges)] for j in range((k+127)//128)]
                scales[index]=source
                payload=b''.join(v.to_bytes(4,'little') for v in source)
                payload+=bytes([0x5a])*(words*64-len(payload))
            for q in range(words):d.image[base+q*8]=int.from_bytes(payload[q*64:(q+1)*64],'little')
        # Static mode ignores arbitrary invalid physical N/K.
        kwargs=dict(job_valid=1,job_id=job,job_m=1,job_m_tile=1,job_n=0 if static else n,
                    job_k=65535 if static else k,job_weight_base=wb,job_scale_base=sb)
        pre,post=d.tick(**kwargs,**beats[0],s_axis_tvalid=1)
        assert pre['job_ready'] and not pre['s_axis_tready'] and not pre['ddr_rd_req']
        # Keep first beat stable during preflight and until it is actually accepted.
        for b in beats:
            for wait in range(1000):
                pre,post=d.tick(**b,s_axis_tvalid=1)
                assert not post['fault_lock']
                if pre['s_axis_tready']:break
            else:raise AssertionError('AXIS wait')
            for _ in range(t.rng.randrange(3)):d.tick()
        d.until(lambda o:o['object_ready'])
        assert not d.requests[startreq:],'DDR started before explicit test object'
        for index,want in enumerate(goldx):
            _,o=d.tick(x_rd_req=1,x_rd_index=index)
            assert (o['x_rd_valid'],o['x_rd_data'],o['x_rd_mask'],o['x_rd_exp'])==(1,*want)
        expected_requests=[]
        # Frozen logical traversal: Group scale once, then each associated row.
        visit=[]
        for g in range((n+127)//128):
            visit.append(next(obj for obj in objects if obj[:2]==(0,g)))
            visit += [obj for obj in objects if obj[0]==1 and g*128 <= obj[1] < min(n,(g+1)*128)]
        for kind,index,base,words in visit:
            d.same_edge=(index%2==0)
            d.gaps=(index%3!=0)
            pre,post=d.tick(object_valid=1,object_kind=kind,object_index=index)
            assert pre['object_ready']
            d.until(lambda o:o['object_done'],limit=words*20+500)
            assert not d.queue
            expected_requests += [r[:3] for r in ranges(base,words,burst)]
            if not kind:
                for j,bits in enumerate(scales[index]):
                    _,o=d.tick(scale_rd_req=1,scale_rd_index=j)
                    assert o['scale_loaded'] and o['scale_rd_valid'] and o['scale_rd_bits']==bits
            else:
                source=weights[index]
                for j in range((k+7)//8):
                    _,o=d.tick(weight_rd_req=1,weight_rd_index=j)
                    part=source[j*8:(j+1)*8]
                    assert o['weight_loaded'] and o['weight_rd_valid']
                    assert (o['weight_rd_data'],o['weight_rd_mask'])==(int.from_bytes(part,'little'),(1<<len(part))-1)
                # Activation and scale survive every weight segment/row reload.
                j=t.rng.randrange(len(goldx));want=goldx[j]
                _,o=d.tick(x_rd_req=1,x_rd_index=j,scale_rd_req=1,scale_rd_index=0)
                assert (o['x_rd_data'],o['x_rd_mask'],o['x_rd_exp'])==want
                assert o['scale_rd_bits']==scales[index//128][0]
        assert d.requests[startreq:]==expected_requests,(burst,n,k)
        assert len(d.beats)-startbeat==sum(o[3] for o in objects)
        assert d.tick(finish_test=1)[1]['result_valid']
        for _ in range(4):
            pre,o=d.tick()
            assert o['result_valid'] and o['result_code']==0 and not o['job_ready']
        d.tick(result_ready=1);d.tick()
        assert t.model.snapshot()['job_ready']
    if not static:
        # System preflight must reject BEFORE ANY AXIS handshake, not merely document it.
        rejected=[(1,129,0,8,3),(1,1,1,16,3),(2,64,2**29-8,0,3),(0,129,0,4096,1)]
        for n,k,wb,sb,code in rejected:
            b=axis_tensor([1]*max(1,k),[0]*((max(1,k)+127)//128),42)[0]
            pre,o=d.tick(job_valid=1,job_id=42,job_m=1,job_m_tile=1,job_n=n,job_k=k,
                         job_weight_base=wb,job_scale_base=sb,**b,s_axis_tvalid=1)
            assert pre['job_ready'] and not pre['s_axis_tready']
            for _ in range(20):
                pre,o=d.tick(**b,s_axis_tvalid=1)
                assert not pre['s_axis_tready'] and not pre['ddr_rd_req']
                if o['result_valid']:break
            assert o['result_valid'] and o['result_code']==code and not o['fault_lock']
            for _ in range(3):
                assert d.tick(**b,s_axis_tvalid=1)[1]['result_code']==code
            d.tick(result_ready=1);d.tick()
        for m,tile in [(0,1),(2,1),(1,0),(1,2)]:
            d.tick(job_valid=1,job_id=42,job_m=m,job_m_tile=tile,job_n=1,job_k=1,job_scale_base=8)
            o=d.until(lambda o:o['result_valid'],limit=30)
            assert o['result_code']==2
            d.tick(result_ready=1);d.tick()
        # Malformed accepted AXIS locks and invalidates all public buffers.
        d.tick(job_valid=1,job_id=42,job_m=1,job_m_tile=1,job_n=1,job_k=1,job_scale_base=8)
        d.until(lambda o:o['s_axis_tready'])
        d.tick(s_axis_tvalid=1,ddr_rd_vld=1)  # simultaneous AXIS10 / DDR21: table priority10
        for _ in range(4):pre,o=d.tick()
        assert o['fault_lock'] and o['result_valid'] and o['result_code']==0x10
        d.tick(result_ready=1)
        for _ in range(4):
            _,o=d.tick(job_valid=1,x_rd_req=1,weight_rd_req=1,scale_rd_req=1)
            assert not any(o[f] for f in ('job_ready','x_loaded','scale_loaded','weight_loaded','x_rd_valid','weight_rd_valid','scale_rd_valid'))
        # Controlled external cleanup + reset; an idle unsolicited response has no fictitious job result.
        d.queue=[];t.step(rst_n=0);d.tick();d.tick();d.tick()
        t.step(ddr_rd_vld=1)
        for _ in range(4):_,o=d.tick()
        assert o['fault_lock'] and not o['result_valid'] and not o['job_ready']
        # A complete row followed by an EXTRA physical beat must invalidate
        # an already-loaded row immediately and preserve 21 through aborts.
        t.step(rst_n=0);d.queue=[]
        d.tick();d.tick();d.tick()
        d.image={0:0x1234,8:0x3f800001}
        d.tick(job_valid=1,job_id=90,job_m=1,job_m_tile=1,job_n=1,job_k=1,job_scale_base=8)
        b=axis_tensor([7],[-1],90)[0]
        for _ in range(100):
            pre,o=d.tick(**b,s_axis_tvalid=1)
            if pre['s_axis_tready']:break
        d.until(lambda o:o['object_ready'])
        d.tick(object_valid=1,object_kind=1)
        o=d.until(lambda o:o['object_done'])
        assert o['weight_loaded']
        _,o=d.tick(ddr_rd_vld=1)
        assert o['fault_lock'] and not o['weight_loaded'] and not o['x_loaded']
        for _ in range(4):_,o=d.tick()
        assert o['result_valid'] and o['result_code']==0x21
        d.tick(result_ready=1)
        assert not d.tick(job_valid=1)[1]['job_ready']
        # Internal early-read error propagates and prevents stale X/Scale reads.
        t.step(rst_n=0);d.queue=[]
        d.tick();d.tick();d.tick()
        d.tick(job_valid=1,job_id=90,job_m=1,job_m_tile=1,job_n=1,job_k=1,job_scale_base=8)
        for _ in range(100):
            pre,o=d.tick(**b,s_axis_tvalid=1)
            if pre['s_axis_tready']:break
        d.until(lambda o:o['object_ready'])
        d.tick(weight_rd_req=1)
        for _ in range(4):_,o=d.tick(x_rd_req=1,scale_rd_req=1)
        assert o['result_code']==0x40 and o['fault_lock'] and not o['x_rd_valid']
        # Reset during an accepted range, external domain flushed first.
        t.step(rst_n=0);d.tick();d.tick();d.tick()
        d.tick(job_valid=1,job_id=88,job_m=1,job_m_tile=1,job_n=1,job_k=129,job_scale_base=24)
        for b in axis_tensor([1]*129,[0,0],88):
            for _ in range(300):
                pre,o=d.tick(**b,s_axis_tvalid=1)
                if pre['s_axis_tready']:break
        d.until(lambda o:o['object_ready'])
        d.tick(object_valid=1,object_kind=1,object_index=0)
        # No responses for 40 clocks must wait, never invent a timeout.
        for _ in range(40):
            t.step(ddr_rd_rdy=1)
            assert not t.model.snapshot()['fault_lock'] and not t.model.snapshot()['object_done']
        t.step(rst_n=0);d.queue=[]
        for _ in range(4):d.tick()
        # Unflushed old response is detected if it arrives outside a new range.
        t.step(ddr_rd_vld=1)
        for _ in range(4):_,o=d.tick()
        assert o['fault_lock'] and not o['result_valid']
    t.counts=dict(burst=burst,static=static,legal_jobs=len(cases),requests=len(d.requests),beats=len(d.beats),
                  valid_axis_jobs=[{'n':n,'k':k} for n,k in cases])
    t.events=d.events
    return t


def stage1_cycle_suites():
    rx=Trace('xw_ddr_range_rx',DdrRangeReceiver(),20)
    rng=rx.rng
    for count in [1,2,3,64,192]+[rng.randrange(1,15) for _ in range(20)]:
        start=8*rng.randrange(5000)
        cmd=dict(cmd_valid=1,cmd_addr_start=start,cmd_addr_end=start+8*(count-1),cmd_beats=count,cmd_kind=count%2)
        for _ in range(3):rx.step(**cmd,ddr_rd_rdy=0)
        same=bool(rng.randrange(2));rx.step(**cmd,ddr_rd_rdy=1,ddr_rd_vld=int(same),ddr_rd_data=999)
        for idx in range(int(same),count):
            for _ in range(rng.randrange(4)):rx.step()
            pre,post=rx.step(ddr_rd_vld=1,ddr_rd_data=idx)
            assert post['word_valid'] and post['word_index']==idx
        assert rx.model.range_done
        rx.step();rx.step()
    rx.step(ddr_rd_vld=1)
    for _ in range(3):assert rx.step(cmd_valid=1,cmd_beats=1,ddr_rd_rdy=1)[1]['range_error_code']==0x21
    rx.step(rst_n=0)
    assert rx.step(cmd_valid=1,cmd_addr_start=1,cmd_beats=1)[1]['range_error_code']==0x20
    sc=Trace('xw_scale_group_cache',ScaleGroupCache(max_k=65535),23)
    for count in [1,2,16,17,96,511,512]:
        words=(count+15)//16
        sc.step(load_begin=1,load_words=words,load_scales=count)
        values=[sc.rng.randrange(2**32) for _ in range(count)]
        payload=b''.join(v.to_bytes(4,'little') for v in values)+bytes(words*64-count*4)
        for idx in range(words):
            sc.step(wr_valid=1,wr_word_index=idx,wr_data=int.from_bytes(payload[idx*64:(idx+1)*64],'little'))
        for idx,v in enumerate(values):
            assert sc.step(rd_req=1,rd_scale_index=idx)[1]['rd_scale_bits']==v
        sc.step()
    sc.step(wr_valid=1,wr_word_index=32)
    assert sc.step(rd_req=1)[1]['cache_error_code']==0x23
    sc.step(rst_n=0)
    assert sc.step(rd_req=1)[1]['cache_error_code']==0x40
    return rx,sc


class Stage23SoftwareTests(unittest.TestCase):
    def test_parser(self):parser_suite()
    def test_activation(self):buffer_suite('x')
    def test_weight(self):buffer_suite('w')
    def test_address_matrix(self):
        for b in (1,2,3,64,192):addr_suite(b)
    def test_harness_matrix(self):
        for b in (1,2,3,64,192):harness_suite(b)
    def test_harness_static(self):harness_suite(3,1)
    def test_stage1_actual_cycle_vectors(self):stage1_cycle_suites()
    def test_independent_oracle_fixed_patterns(self):
        b=axis_tensor([-131072,131071,-1],[ -128 ],0x12345678)[0]
        assert b['s_axis_tdata']==0x20000 | (0x1ffff<<18) | (0x3ffff<<36)
        assert b['s_axis_tkeep']==127 and b['s_axis_tlast']==1
        assert b['s_axis_tuser'].to_bytes(16,'little').hex()=='785634120000000080030001b2000000'
        assert layout(1,1,2**29-8,0)[0]==0
        assert layout(2,1,2**29-8,0)[0]==3


if __name__=='__main__':unittest.main()
