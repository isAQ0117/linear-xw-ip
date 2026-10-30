"""Production scheduler and real end-to-end stimuli, independent oracle checks."""
import random,collections,json
from pathlib import Path
from stage7_model import Scheduler,LinearIP
from stage67_golden import linear_job,image
from stage23_golden import axis_tensor
from tools.run_stage67 import Trace

class FullTrace(Trace):
    def __init__(self,model):
        super().__init__('linear_xw_ip',model)
        self.ins += [('inject_valid',1),('inject_source',3),('inject_code',8)]
        self.outs += [('debug_control',44),('debug_pipeline',48)]
    def tick(self,**kw):
        self.model.cycle=len(self.rows)
        pre,post=super().tick(**kw)
        self.events+=self.model.edge_events
        return pre,post

class Driver:
    def __init__(self,t,seed=0x6707):
        self.t=t;self.rng=random.Random(seed);self.mem={};self.queue=[];self.beats=0;self.requests=[];self.same_edge=True;self.gaps=True;self.fast=False
    def tick(self,**kw):
        i=dict(ddr_rd_rdy=1 if self.fast else int(self.rng.randrange(4)!=0),
               m_axis_tready=1 if self.fast else int(self.rng.randrange(3)!=0),status_ready=0)
        i.update(kw);o=self.t.model.snapshot(**i)
        if o['ddr_rd_req']:
            assert not self.queue,'second outstanding'
            self.queue=list(range(o['ddr_rd_addra'],o['ddr_rd_addrb']+1,8));self.requests.append((len(self.t.rows),o['ddr_rd_addra'],o['ddr_rd_addrb']))
        if self.queue and (self.fast or not self.gaps or self.rng.randrange(3)!=0) and (not o['ddr_rd_req'] or self.same_edge):
            addr=self.queue.pop(0);assert addr in self.mem,('outside manifest',addr)
            i.update(ddr_rd_vld=1,ddr_rd_data=self.mem[addr]);self.beats+=1
        return self.t.tick(**i)
    def until(self,predicate,limit=100000,**kw):
        for _ in range(limit):
            pre,post=self.tick(**kw)
            if predicate(post):return post
        raise AssertionError(('watchdog',self.t.model.sch.state,self.t.model.sch.first_error,self.t.model.sch.fault_lock))
    def ready(self):return self.until(lambda p:p['job_ready'],limit=100)
    def reset(self):
        # Platform clears external transaction domain before local reset.
        self.queue=[];self.t.reset();self.ready()
    def submit(self,job,n,k,m=1,tile=1,wb=0x100,sb=None,physical=None):
        self.ready();sb=wb+8*n*((k+63)//64) if sb is None else sb
        self.tick(job_valid=1,job_id=job,job_m=m,job_m_tile=tile,job_n=n if physical is None else physical[0],job_k=k if physical is None else physical[1],job_weight_base=wb,job_scale_base=sb)
        return wb,sb
    def feed(self,x,ex,job,mutate=None):
        beats=axis_tensor(x,ex,job)
        if mutate:mutate(beats)
        for b in beats:
            if not self.fast:
                for _ in range(self.rng.randrange(4)):self.tick()
            for _ in range(1000):
                pre,post=self.tick(s_axis_tvalid=1,**b)
                if pre['s_axis_tready']:break
            else:raise AssertionError('input watchdog')
    def finish(self,job,code=0,wait=25):
        self.until(lambda p:p['status_valid'])
        for _ in range(wait):
            p=self.tick()[1]
            assert p['status_valid'] and p['busy'] and not p['job_ready']
            assert (p['status_job_id'],p['status_ok'],p['status_error_code'])==(job,int(code==0),code),(job,code,p)
        pre,post=self.tick(status_ready=1,job_valid=1,job_id=0xdead)
        assert pre['status_valid'] and pre['busy'] and not pre['job_ready'] and not post['busy']
        for _ in range(2):assert not self.tick()[1]['status_valid']

def integration_suite(static=0,burst=3,extended=False):
    t=FullTrace(LinearIP(burst,static));d=Driver(t);d.reset();rng=random.Random(0x6717);measure=[]
    cases=[(2,129),(129,1),(1,127),(2,128),(3,129),(1,2048),(2,2049),(2,4096),(2,12288),(257,7)]
    if static:cases=[(2,129),(2,129)]
    if extended:cases=[(12288,1)]
    for case,(n,k) in enumerate(cases):
        job=100+case;nb=(k+127)//128;ng=(n+127)//128
        x=[rng.randrange(-131072,131072) for _ in range(k)];ex=[rng.randrange(-4,5) for _ in range(nb)]
        w=[[rng.choice([0,0x38,0xb8,0x7e,0xfe,1,0x81]) for _ in range(k)] for _ in range(n)]
        scales=[[0x3f800001+b+(g%4)*0x0a000000 for b in range(nb)] for g in range(ng)]
        
        if (n,k)==(129,1):w[-1]=[0x38]
        gold=linear_job(x,ex,w,scales,job);wb=0x100;sb=wb+8*n*((k+63)//64)
        d.mem=image(w,scales,wb,sb);d.same_edge=case%2==0;d.gaps=case%3!=0;d.fast=extended or case%2==0
        start=len(t.rows);br=d.beats;rr=len(d.requests);evstart=len(t.events)
        d.submit(job,n,k,wb=wb,sb=sb,physical=(0,65535) if static else None)
        d.feed(x,ex,job)
        d.until(lambda p:p['status_valid'],limit=n*(nb*120+200)+k*3+5000)
        ev=t.events[evstart:];out=[e for e in ev if e['event']=='AXIS_OUT_ACCEPT']
        actual=[dict(s_axis_tdata=int(e['data_hex'],16),s_axis_tkeep=int(e['keep_hex'],16),s_axis_tlast=e['last'],s_axis_tuser=int(e['user_hex'],16)) for e in out]
        assert actual==gold['axis'],(n,k,actual,gold['axis'])
        for e in ev:
            if e['event'] in ('B1_VALID','B2_VALID','A2_UPDATE'):
                cp=gold['checkpoints'][e['channel']][e['block']]
                if e['event']=='B1_VALID':assert e['raw']==cp['raw']
                elif e['event']=='B2_VALID':assert (int(e['term_hex'],16)-(1<<72) if int(e['term_hex'],16)>>71 else int(e['term_hex'],16),e['exp'])==(cp['term_mant'],cp['term_exp'])
                else:assert (e['mant'],e['exp'])==(cp['acc_mant'],cp['acc_exp'])
        assert len([e for e in ev if e['event']=='A2_UPDATE'])==n*nb
        loads=[(e['kind'],e['index']) for e in ev if e['event']=='LOAD_ACCEPT']
        expected=[]
        for g in range(ng):expected.append((0,g));expected += [(1,ch) for ch in range(g*128,min(n,g*128+128))]
        assert loads==expected
        assert d.beats-br==ng*((k+2047)//2048)+n*((k+63)//64)
        if (n,k)==(2,129):assert len(axis_tensor(x,ex,job))==6 and d.beats-br==7 and len(out)==1
        if (n,k)==(129,1):assert len(out)==6 and len(gold['exp'])==2 and gold['exp'][0]!=gold['exp'][1]
        last=out[-1]['cycle'];status_first=len(t.rows)-1;assert status_first>last
        d.finish(job,wait=37);status_events=[e for e in t.events[evstart:] if e['event']=='STATUS_ACCEPT']
        assert len(status_events)==1
        measure.append(dict(job_id=job,n=n,k=k,job_accept=start,last_output=last,status_first=status_first,
                            status_accept=status_events[0]['cycle'],end_to_end_cycles=status_events[0]['cycle']-start+1,
                            ddr_beats=d.beats-br,ddr_requests=len(d.requests)-rr,output_beats=len(out),exponents=gold['exp']))
    t.counts=dict(static=static,burst=burst,jobs=len(cases),measurements=measure,seed='0x6717')
    return t

def scheduler_suite():
    t=Trace('xw_linear_scheduler',Scheduler());t.reset();rng=random.Random(0x6757);jobs=0
    default=dict(datapath_online=1,stage5_ready=1,compute_ready=1,output_ready=1,finish_ready=1,clean_boundary=1)
    t.defaults.update(default)
    for n,k in [(1,1),(129,129),(257,2049),(12288,12288)]:
        assert t.tick(job_valid=1,job_id=jobs+50,job_m=1,job_m_tile=1,job_n=n,job_k=k)[0]['job_ready']
        loads=[];results=0;hold=0;laststate=-1
        for tick in range(n*18+300):
            s=t.model;kw={}
            if s.state!=laststate:hold=0;laststate=s.state
            hold+=1
            if s.state==s.CHECK:kw['cfg_done']=1
            if s.state==s.START and hold<15:kw['stage5_ready']=0
            if s.state==s.X:kw.update(x_loaded=1,input_done=1)
            if s.state in (s.SCALE_REQ,s.WEIGHT_REQ):kw['load_ready']=int(hold>1)
            if s.state in (s.SCALE_WAIT,s.WEIGHT_WAIT):kw['load_done']=int(hold>2)
            if s.state==s.RESULT:kw.update(result_valid=1,result_ready=int(hold>3))
            if s.state==s.GROUP:kw.update(group_done=int(hold>7),committed_group=s.group_index)
            if s.state==s.PUBLISH:kw['job_results_ready']=int(hold>3)
            if s.state==s.OUTPUT_WAIT:kw['output_done']=int(hold>5)
            if s.state==s.STATUS:kw['status_accept']=int(hold>70)
            pre,post=t.tick(**kw)
            if pre['load_valid'] and kw.get('load_ready'):loads.append((pre['load_kind'],pre['load_index']))
            if kw.get('result_valid') and kw.get('result_ready'):results+=1
            if post['job_ready']:
                assert not post['busy'] and results==n;break
        else:raise AssertionError(('scheduler stub timeout',n,t.model.state))
        expected=[]
        for g in range((n+127)//128):expected.append((0,g));expected += [(1,ch) for ch in range(g*128,min(n,g*128+128))]
        assert loads==expected;jobs+=1
    # Every root code, clean/unclean numeric boundary, first-wins and late lock.
    faults=[(c,clean,late) for c in [0x10,0x11,0x12,0x13,0x20,0x21,0x23,0x30,0x31,0x32,0x33,0x40] for clean,late in ([(1,0),(0,0),(1,1)] if c in range(0x30,0x34) else [(1,0)])]
    for code,clean,late in faults:
        t.reset();t.tick(job_valid=1,job_id=99,job_m=1,job_m_tile=1,job_n=1,job_k=1)
        for _ in range(10):
            if t.model.state==t.model.X:break
            t.tick(cfg_done=1)
        t.tick(fault_valid=1,fault_code=code,fault_system=int(code<0x30 or code==0x40),clean_boundary=clean)
        assert t.model.first_error==code
        if late:t.tick(fault_valid=1,fault_code=0x21,fault_system=1);assert t.model.first_error==code and t.model.fault_lock
        for _ in range(3):t.tick()
        for _ in range(50):
            pre,p=t.tick();assert p['first_error']==code and p['busy'] and not p['job_ready']
        t.tick(status_accept=1)
        for _ in range(5):t.tick()
        locked=code<0x30 or code==0x40 or not clean or late
        assert bool(t.model.fault_lock)==bool(locked)
        assert bool(t.model.snapshot(**t.defaults)['job_ready'])==(not bool(locked))
    # IDLE unowned fault: busy remains0, never finish_valid.
    t.reset();p=t.tick(fault_valid=1,fault_code=0x21,fault_system=1)[1]
    assert p['fault_lock'] and not p['busy'] and not p['finish_valid']
    t.counts=dict(traversal_jobs=jobs,max_n=12288,max_k=12288,faults=len(faults),stage5_ready_stall=14,result_stall=3,group_stall=7,status_stall=70)
    return t

def fault_suite():
    t=FullTrace(LinearIP());d=Driver(t,0x67f7);d.reset();job=1000;cases=[]
    prechecks=[('n_zero',0,1,1,1,0,8,1),('k_zero',1,0,1,1,0,8,1),
               ('n_capacity',12289,1,1,1,0,200000,1),('k_capacity',1,12289,1,1,0,200000,1),
               ('m_zero',1,1,0,1,0,8,2),('m_two',1,1,2,1,0,8,2),
               ('tile_zero',1,1,1,0,0,8,2),('tile_two',1,1,1,2,0,8,2),
               ('unaligned_w',1,1,1,1,1,16,3),('unaligned_s',1,1,1,1,0,9,3),
               ('overlap',1,129,1,1,0,8,3),('overflow',2,64,1,1,(1<<29)-8,0,3)]
    for label,n,k,m,tile,wb,sb,code in prechecks:
        start=len(t.events);d.submit(job,n,k,m,tile,wb,sb);d.finish(job,code)
        assert not any(e['event'] in ('AXIS_IN_ACCEPT','DDR_REQ_ACCEPT','AXIS_OUT_ACCEPT') for e in t.events[start:])
        d.ready();cases.append(dict(label=label,code=code,recoverable=True));job+=1
    # Real parser violations, reset is coordinated with the empty mock DDR domain.
    for code in [0x10,0x11,0x12,0x13]:
        d.submit(job,1,1,wb=0,sb=8);d.until(lambda p:p['s_axis_tready'])
        b=axis_tensor([1],[0],job)[0]
        if code==0x10:b['s_axis_tuser']|=1<<127
        elif code==0x11:b['s_axis_tuser']|=1<<80
        elif code==0x12:b['s_axis_tkeep']=0
        else:b['s_axis_tlast']=0
        d.tick(s_axis_tvalid=1,**b);d.finish(job,code)
        assert t.model.sch.fault_lock and not d.tick(job_valid=1)[1]['job_ready']
        cases.append(dict(label='real_parser',code=code,recoverable=False));job+=1;d.reset()
    # Same-edge AXIS10 vs DDR21 selects table order10.
    d.submit(job,1,1,wb=0,sb=8);d.until(lambda p:p['s_axis_tready'])
    d.tick(s_axis_tvalid=1,ddr_rd_vld=1);d.finish(job,0x10);cases.append(dict(label='same_edge_axis_ddr_priority',code=0x10));job+=1;d.reset()
    for label,scale,weight,ex,code in [('scale_zero',0,0x38,0,0x30),('scale_negative',0xbf800000,0x38,0,0x30),
            ('fp8_nan',0x3f800000,0x7f,0,0x31),('both',0,0x7f,0,0x30),('bfp_exp',0x7f7fffff,0x7e,127,0x33)]:
        start=len(t.events);d.mem=image([[weight]],[[scale]],0,8);d.submit(job,1,1,wb=0,sb=8);d.feed([131071],[ex],job)
        d.finish(job,code);assert not t.model.sch.fault_lock
        assert not any(e['event']=='AXIS_OUT_ACCEPT' for e in t.events[start:])
        d.ready();cases.append(dict(label=label,code=code,recoverable=True));job+=1
    # Prove a clean recoverable numeric fault can be followed by real successful data.
    d.mem=image([[0x38]],[[0x3f800000]],0,8);d.submit(job,1,1,wb=0,sb=8);d.feed([-7],[0],job);d.finish(job)
    d.ready();job+=1
    for source,code in [(0,0x32),(0,0x40),(3,0x23),(4,0x20)]:
        d.mem=image([[0x38]],[[0x3f800000]],0,8);d.submit(job,1,1,wb=0,sb=8);d.feed([1],[0],job)
        d.until(lambda p:t.model.sch.state==t.model.sch.COMPUTE_REQ)
        d.tick(inject_valid=1,inject_source=source,inject_code=code)
        d.finish(job,code)
        if code==0x32:d.ready()
        else:assert t.model.sch.fault_lock;d.reset()
        cases.append(dict(label='diagnostic_injection',source=source,code=code));job+=1
    # First numeric error retained while a later real unsolicited DDR beat upgrades lock.
    d.mem=image([[0x38]],[[0]],0,8);d.submit(job,1,1,wb=0,sb=8);d.feed([1],[0],job)
    d.until(lambda p:t.model.sch.first_error==0x30)
    d.tick(ddr_rd_vld=1);d.finish(job,0x30);assert t.model.sch.fault_lock
    cases.append(dict(label='first30_late21',code=0x30,lock=True));job+=1;d.reset()
    # Published Status is immutable even if a later platform fault locks allocation.
    d.mem=image([[0x38]],[[0x3f800000]],0,8);d.submit(job,1,1,wb=0,sb=8);d.feed([1],[0],job)
    d.until(lambda p:p['status_valid'])
    d.tick(ddr_rd_vld=1);d.finish(job,0)
    assert t.model.sch.fault_lock
    cases.append(dict(label='published_success_immutable_late_platform_fault',code=0,lock=True));job+=1;d.reset()
    # IDLE unsolicited response must never invent a status or Job ID.
    d.tick(ddr_rd_vld=1)
    for _ in range(20):
        p=d.tick(status_ready=1)[1];assert not p['status_valid'] and not p['busy'] and not p['job_ready']
    cases.append(dict(label='idle_unowned',code=0x21));d.reset()
    # Missing DDR response: no hardware timeout; independent finite TB observation.
    d.submit(job,1,129,wb=0,sb=24);d.feed([1]*129,[0,0],job)
    for _ in range(1000):
        p=t.tick(ddr_rd_rdy=1)[1]
        assert p['busy'] and not p['status_valid'] and not t.model.sch.first_error
    assert t.model.r.busy
    cases.append(dict(label='missing_response_environment_incomplete',watchdog_cycles=1000,rtl_timeout=False));job+=1;d.reset()
    # Numeric diagnostic during an unfinished physical range must lock, not soft-recover.
    d.submit(job,1,129,wb=0,sb=24);d.feed([1]*129,[0,0],job)
    for _ in range(30):
        t.tick(ddr_rd_rdy=1)
        if t.model.r.busy:break
    assert t.model.r.busy
    t.tick(inject_valid=1,inject_source=0,inject_code=0x30)
    for _ in range(6):t.tick()
    assert t.model.sch.first_error==0x30 and t.model.sch.fault_lock and t.model.r.busy
    for _ in range(30):
        p=t.tick()[1];assert p['status_valid'] and p['status_error_code']==0x30 and not p['ddr_rd_req']
    t.tick(status_ready=1)
    assert t.model.r.busy and not t.model.sch.busy and t.model.sch.fault_lock
    cases.append(dict(label='numeric_during_outstanding',code=0x30,lock=True,receiver_still_busy=True));job+=1;d.reset()
    # Held output beat, post-output error, and last-EOT/error race.
    for label,n in [('held_output',29),('after_first_output',129),('last_eot_error',1),('reset_last_eot',1)]:
        d.mem=image([[0x38]]*n,[[0x3f800000]]*((n+127)//128),0,8*n)
        start=len(t.events);d.submit(job,n,1,wb=0,sb=8*n);d.feed([1],[0],job)
        d.until(lambda p:p['m_axis_tvalid'],m_axis_tready=0)
        if label=='after_first_output':
            d.tick(m_axis_tready=1)
            d.until(lambda p:p['m_axis_tvalid'],m_axis_tready=0)
        held=tuple(t.model.snapshot()[k] for k in ['m_axis_tdata','m_axis_tkeep','m_axis_tlast','m_axis_tuser'])
        if label=='reset_last_eot':
            t.tick(rst_n=0,m_axis_tready=1)
            assert not t.model.snapshot()['m_axis_tvalid'] and not t.model.snapshot()['status_valid'];d.reset()
        else:
            d.tick(ddr_rd_vld=1,m_axis_tready=int(label=='last_eot_error'))
            d.until(lambda p:p['status_valid'],m_axis_tready=0)
            for _ in range(80):
                p=d.tick(m_axis_tready=0)[1]
                assert p['status_error_code']==0x21 and not p['status_ok'] and p['busy']
                if label!='last_eot_error':
                    assert p['m_axis_tvalid'] and tuple(p[k] for k in ['m_axis_tdata','m_axis_tkeep','m_axis_tlast','m_axis_tuser'])==held
            d.tick(status_ready=1,m_axis_tready=0)
            assert t.model.sch.fault_lock and not t.model.sch.busy
            d.reset()
        cases.append(dict(label=label,code=0x21 if label!='reset_last_eot' else 0));job+=1
    t.counts=dict(cases=cases,jobs=job-1000,cycle_definition='pre-edge handshakes, registered producer events after edge',diagnostic_injection='TB-only force of internal diagnostic nets; no production ports')
    return t

def retry_suite():
    """First full Group rounds to131072 before retry; tail has its own exponent."""
    t=FullTrace(LinearIP());d=Driver(t);d.fast=True;d.gaps=False;d.reset()
    n=129;k=1;job=900;wb=0x100;sb=wb+8*n
    x=[131071];ex=[0];weights=[[0x38] for _ in range(n)];scales=[[0x3f800030],[0x3f800000]]
    gold=linear_job(x,ex,weights,scales,job)
    assert gold['exp']==[1,0] and gold['mant']==[65536]*128+[131071]
    d.mem=image(weights,scales,wb,sb);d.submit(job,n,k,wb=wb,sb=sb);d.feed(x,ex,job)
    d.until(lambda p:t.model.q.group_pending and t.model.q.group_id==0)
    assert t.model.q.q.retried
    d.until(lambda p:p['status_valid'])
    out=[e for e in t.events if e['event']=='AXIS_OUT_ACCEPT']
    assert [dict(s_axis_tdata=int(e['data_hex'],16),s_axis_tkeep=int(e['keep_hex'],16),s_axis_tlast=e['last'],s_axis_tuser=int(e['user_hex'],16)) for e in out]==gold['axis']
    for e in t.events:
        if e['event'] in ('B1_VALID','B2_VALID','A2_UPDATE'):
            g=gold['checkpoints'][e['channel']][e['block']]
            if e['event']=='B1_VALID':assert e['raw']==g['raw']
            elif e['event']=='B2_VALID':assert int(e['term_hex'],16)==g['term_mant'] and e['exp']==g['term_exp']
            else:assert (e['mant'],e['exp'])==(g['acc_mant'],g['acc_exp'])
    d.finish(job,wait=17)
    t.counts=dict(static=0,burst=3,jobs=1,group0_retry=True,tail_independent_exp=True,measurements=[dict(job_id=job,n=n,k=k)])
    return t
