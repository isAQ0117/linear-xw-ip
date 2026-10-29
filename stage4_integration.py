"""Real Stage23 + Stage4 composition, independent checkpoint and cycle checks."""
import json,random
from pathlib import Path
from stage4_model import Controller,signed
from stage23_model import Harness as Storage
from stage4_golden import checkpoints
from stage23_golden import axis_tensor,activation_words
from test_stage4 import Trace,pack_w,pack_x


class Harness:
    def __init__(self):self.storage=Storage(3);self.core=Controller();self.edge_events=[];self.prev=(0,0,0)
    def reset(self):self.storage.reset_all();self.core.reset();self.edge_events=[];self.prev=(0,0,0)
    def signals(self,**i):
        g=lambda n:i.get(n,0)
        si={n:i[n] for n in i if n in [n for n,w in self.storage_ports()]}
        so,_,fatal,code=self.storage.signals(**si)
        ci=dict(rst_n=(self.storage.release>>1)&1,abort=g('abort'),req_valid=g('compute_valid'),
                req_job=g('compute_job'),req_channel=g('compute_channel'),req_k=g('compute_k'),
                x_loaded=so['x_loaded'],w_loaded=so['weight_loaded'],s_loaded=so['scale_loaded'],upstream_fault=fatal,upstream_code=code,
                slice_enable=g('slice_enable'),result_ready=g('result_ready'),x_rd_valid=so['x_rd_valid'],x_rd_data=so['x_rd_data'],
                x_rd_exp=so['x_rd_exp'],x_rd_mask=so['x_rd_mask'],w_rd_valid=so['weight_rd_valid'],w_rd_data=so['weight_rd_data'],
                w_rd_mask=so['weight_rd_mask'],s_rd_valid=so['scale_rd_valid'],s_rd_bits=so['scale_rd_bits'])
        co=self.core.snapshot(**ci)
        si.update(x_rd_req=co['x_rd_req'],x_rd_index=co['x_rd_index'],weight_rd_req=co['w_rd_req'],weight_rd_index=co['w_rd_index'],
                  scale_rd_req=co['s_rd_req'],scale_rd_index=co['s_rd_index'])
        out={n:so[n] for n in ['job_ready','s_axis_tready','ddr_rd_req','ddr_rd_addra','ddr_rd_addrb','object_ready','object_done','x_loaded']}
        out.update(w_loaded=so['weight_loaded'],s_loaded=so['scale_loaded'],compute_ready=co['req_ready'])
        out.update({n:co[n] for n in ['result_valid','result_mant','result_exp','result_job','result_channel','error_valid','error_code','fault_lock']})
        return out,si,ci
    @staticmethod
    def storage_ports():
        # Only exogenous controls; read-port controls come exclusively from core.
        return [(n,1) for n in ('rst_n job_valid job_id job_m job_n job_k job_m_tile job_weight_base job_scale_base '
            's_axis_tdata s_axis_tvalid s_axis_tkeep s_axis_tlast s_axis_tuser ddr_rd_rdy ddr_rd_data ddr_rd_vld '
            'object_valid object_kind object_index').split()]
    def snapshot(self,**i):return self.signals(**i)[0]
    def step(self,**i):
        if not i.get('rst_n',1):self.reset();return
        out,si,ci=self.signals(**i)
        co,cs,detail=self.core.signals(**ci)
        cycle=getattr(self,'trace_cycle',0);ev=[];c=self.core
        def add(name,**kw):ev.append(dict(cycle=cycle,event=name,job_id=c.active_job,channel=c.active_channel,row=0,group=c.active_channel>>7,**kw))
        if (self.storage.release>>1)&1:
            if i.get('compute_valid',0) and out['compute_ready']:
                ev.append(dict(cycle=cycle,event='COMPUTE_ACCEPT',job_id=i['compute_job'],channel=i['compute_channel'],row=0,group=i['compute_channel']>>7,k=i['compute_k']))
            if co['x_rd_req']:add('RAM_READ',block=c.block_index,slice=c.issued,index=co['x_rd_index'])
            if detail['pop']:
                h=c.responses[c.read_ptr];add('B1_ACCEPT',block=h[6],slice=h[5])
            if detail['b1']['out_valid'] and cs[0]['out_ready']:add('B2_ACCEPT',block=detail['b1']['out_block'])
            if cs[2]['in_valid'] and detail['a2']['in_ready']:add('A2_ACCEPT',block=detail['b2']['out_block'])
            if out['result_valid'] and i.get('result_ready',0):
                ev.append(dict(cycle=cycle,event='RESULT_ACCEPT',job_id=out['result_job'],channel=out['result_channel'],row=0,group=out['result_channel']>>7))
        self.storage.step(**si);self.core.step(**ci)
        po,_,pci=self.signals(**i);_,_,pd=self.core.signals(**pci)
        b1,b2,a2=pd['b1'],pd['b2'],pd['a2']
        if b1['out_valid'] and not self.prev[0]:add('B1_VALID',block=b1['out_block'],raw=b1['out_raw'])
        if b2['out_valid'] and not self.prev[1]:add('B2_VALID',block=b2['out_block'],term_mant=b2['out_mant'],term_exp=b2['out_exp'])
        if a2['update_valid']:add('A2_UPDATE',block=a2['out_block'],mant=a2['state_mant'],exp=a2['state_exp'],special=a2['special_path'])
        if po['result_valid'] and not self.prev[2]:
            ev.append(dict(cycle=cycle,event='RESULT_VALID',job_id=po['result_job'],channel=po['result_channel'],row=0,group=po['result_channel']>>7,mant=po['result_mant'],exp=po['result_exp']))
        if c.state in (c.SETUP,c.RUN,c.WAIT):add('FIFO_LEVEL',block=c.block_index,count=c.fifo_count,pending=c.pending)
        self.prev=(b1['out_valid'],b2['out_valid'],po['result_valid']);self.edge_events=ev


class Reader:
    """Fixed one-edge registered RAM response stub for standalone controller TB."""
    def __init__(self,t,x,w,exps,scales):
        self.t=t;self.x=x;self.w=w;self.exps=exps;self.scales=scales;self.response={};self.peak=0;self.requests=[]
    def tick(self,**kw):
        i=dict(x_loaded=1,w_loaded=1,s_loaded=1,slice_enable=1,**self.response);i.update(kw)
        pre,post=self.t.step(**i)
        r={}
        if pre['x_rd_req']:
            idx=pre['x_rd_index'];part=self.x[idx*8:idx*8+8];mask=(1<<len(part))-1
            r.update(x_rd_valid=1,x_rd_data=pack_x(part),x_rd_mask=mask,x_rd_exp=self.exps[idx//16]&255)
            self.requests.append((len(self.t.rows)-1,idx))
        if pre['w_rd_req']:
            idx=pre['w_rd_index'];part=self.w[idx*8:idx*8+8]
            r.update(w_rd_valid=1,w_rd_data=pack_w(part+[255]*(8-len(part))),w_rd_mask=(1<<len(part))-1)
        if pre['s_rd_req']:r.update(s_rd_valid=1,s_rd_bits=self.scales[pre['s_rd_index']])
        self.response=r
        core=self.t.model
        assert core.fifo_count+core.pending<=4
        self.peak=max(self.peak,core.fifo_count)
        return pre,post


def observed(core,cycle,previous):
    """Same event definition as HDL: first producing NBA, not consumer edge."""
    events=[]
    if core.b1.snapshot()['out_valid'] and not previous[0]:events.append(dict(cycle=cycle,event='B1_VALID',job_id=core.active_job,channel=core.active_channel,block=core.b1.out_block,raw=core.b1.out_raw))
    if core.b2.snapshot()['out_valid'] and not previous[1]:events.append(dict(cycle=cycle,event='B2_VALID',job_id=core.active_job,channel=core.active_channel,block=core.b2.out_block,term_mant=core.b2.out_mant,term_exp=core.b2.out_exp))
    if core.a2.snapshot()['update_valid']:events.append(dict(cycle=cycle,event='A2_UPDATE',job_id=core.active_job,channel=core.active_channel,block=core.a2.out_block,mant=core.a2.state_mant,exp=core.a2.state_exp,special=int(core.a2.special_path)))
    return events,(core.b1.snapshot()['out_valid'],core.b2.snapshot()['out_valid'])


def verify_event(e,gold):
    b=gold[e['block']]
    if e['event']=='B1_VALID':assert e['raw']==b['raw']
    elif e['event']=='B2_VALID':assert (e['term_mant'],e['term_exp'])==(b['term_mant'],b['term_exp'])
    else:assert (e['mant'],e['exp'])==(b['acc_mant'],b['acc_exp'])


def controller_suite():
    t=Trace('xw_b3b_compute_ctrl',Controller());rng=random.Random(0x2344);results=[];peak=0
    ks=[1,7,8,9,127,128,129,2048,2049,4096,12288]
    for mode in ['normal','special','stall']:
        for k in ks:
            t.reset();x=[rng.randrange(-131072,131072) for _ in range(k)]
            w=[rng.choice([0x38,0xb8,0x7e,0xfe,1,0x80]) for _ in range(k)];nb=(k+127)//128
            ex=[(-128 if b%2 else 127) if mode=='special' else rng.randrange(-5,6) for b in range(nb)]
            sc=[(1 if b%2 else 0x7f7fffff) if mode=='special' else 0x3f800001+b for b in range(nb)]
            gold=checkpoints(x,ex,w,sc);d=Reader(t,x,w,ex,sc);start=len(t.rows)
            assert d.tick(req_valid=1,req_job=k,req_channel=7,req_k=k)[0]['req_ready']
            previous=(0,0);events=[]
            for tick in range(nb*90+100):
                enable=int(not(mode=='stall' and (tick<20 or tick%19 in range(8))))
                pre,p=d.tick(slice_enable=enable,req_job=9999,req_k=65535,req_channel=99)
                ev,previous=observed(t.model,len(t.rows)-1,previous)
                for e in ev:verify_event(e,gold)
                events.extend(ev)
                assert not p['error_valid'],(mode,k,t.model.error_code,t.model.state)
                if p['result_valid']:break
            else:raise AssertionError('controller timeout')
            assert len(events)==nb*3
            assert (p['result_mant'],p['result_exp'],p['result_job'],p['result_channel'])==(gold[-1]['acc_mant'],gold[-1]['acc_exp'],k,7)
            cycles=len(t.rows)-start;peak=max(peak,d.peak)
            held={n:p[n] for n in ['result_valid','result_mant','result_exp','result_job','result_channel']}
            for _ in range(13):assert all(d.tick()[1][n]==v for n,v in held.items())
            d.tick(result_ready=1)
            results.append(dict(k=k,mode=mode,channel_cycles=cycles,blocks=nb,events=events,requests=d.requests,peak_fifo=d.peak))
    # Same deterministic source stub, deliberate faults without changing the DUT.
    fault_cases=[('missing_loaded',0x40),('scale',0x30),('fp8',0x31),('mask',0x40),('missing_x',0x40),('stray_scale',0x40),('abort',0x40),('system_vs_nan',0x21),('upstream_zero',0x40),('bad_k',0x40),('scale_mask',0x40)]
    for name,code in fault_cases:
        t.reset();d=Reader(t,[1]*128,[127 if name in ['fp8','system_vs_nan'] else 0x38]*128,[0],[0 if name in ['scale','scale_mask'] else 0x3f800000])
        kw={'x_loaded':0} if name=='missing_loaded' else {}
        d.tick(req_valid=1,req_job=88,req_k=0 if name=='bad_k' else 128,**kw)
        for tick in range(50):
            kw={}
            if tick==1 and name=='scale_mask':kw['x_rd_mask']=0
            if tick==2:
                if name=='upstream_zero':kw.update(upstream_fault=1,upstream_code=0)
                elif name=='mask':kw['x_rd_mask']=0
                elif name=='missing_x':kw['x_rd_valid']=0
                elif name=='stray_scale':kw['s_rd_valid']=1
                elif name=='abort':kw['abort']=1
                elif name=='system_vs_nan':kw.update(upstream_fault=1,upstream_code=0x21)
            _,p=d.tick(**kw)
            if p['error_valid']:break
        assert p['error_valid'] and p['error_code']==code and not p['result_valid'],(name,p)
        for _ in range(5):
            p=d.tick(req_valid=1,req_k=1,upstream_fault=1,upstream_code=0x40)[1]
            assert p['error_code']==code and not p['result_valid'] and not p['req_ready']
    # reset mid-flight discards pending RAM reservations and all old pipeline data.
    t.reset();d=Reader(t,[1]*128,[0x38]*128,[0],[0x3f800000]);d.tick(req_valid=1,req_k=128)
    for _ in range(5):d.tick()
    t.reset()
    for _ in range(12):assert not t.step()[1]['result_valid']
    t.counts=dict(channels=len(results),peak_fifo=peak,fault_cases=fault_cases,cycles=len(t.rows))
    Path('docs/stage4/CONTROLLER_MEASUREMENTS.json').write_text(json.dumps(results,indent=2)+'\n')
    return t


class DDR:
    def __init__(self,t):self.t=t;self.image={};self.queue=[];self.rng=random.Random(0xDD234);self.requests=0;self.beats=0
    def tick(self,**kw):
        i=dict(ddr_rd_rdy=int(self.rng.randrange(4)!=0),slice_enable=1);i.update(kw)
        pre=self.t.model.snapshot(**i)
        if pre['ddr_rd_req']:
            assert not self.queue
            self.queue=list(range(pre['ddr_rd_addra'],pre['ddr_rd_addrb']+1,8));self.requests+=1
        if self.queue and self.rng.randrange(3):
            a=self.queue.pop(0);i.update(ddr_rd_vld=1,ddr_rd_data=self.image[a]);self.beats+=1
        return self.t.step(**i)
    def until(self,predicate,limit=100000,**i):
        for _ in range(limit):
            pre,post=self.tick(**i)
            if predicate(post):return post
            assert not post['error_valid'],post
        raise AssertionError('DDR harness timeout')


def harness_suite():
    t=Trace('xw_stage234_harness',Harness());d=DDR(t);rng=random.Random(0x234);metrics=[];all_events=[]
    cases=[(2,129,'normal'),(1,1,'normal'),(1,7,'normal'),(1,8,'normal'),(1,9,'normal'),(1,127,'normal'),(1,128,'normal'),
           (1,2048,'normal'),(1,2049,'normal'),(1,4096,'normal'),(1,12288,'normal'),(1,4096,'special'),(1,12288,'special'),(1,129,'stall')]
    for case,(n,k,mode) in enumerate(cases):
        t.reset();d.queue=[]
        for _ in range(4):d.tick()
        x=[rng.randrange(-131072,131072) for _ in range(k)];nb=(k+127)//128
        ex=[(-128 if b%2 else 127) if mode=='special' else rng.randrange(-3,4) for b in range(nb)]
        sc=[(1 if b%2 else 0x7f7fffff) if mode=='special' else 0x3f800001+b for b in range(nb)]
        weights=[[rng.choice([0x7e,0xfe,0x38,0xb8,0,1,0x81]) for _ in range(k)] for _ in range(n)]
        wb=0x100;rw=(k+63)//64;sb=wb+8*n*rw;sw=(nb+15)//16;job=1000+case
        payload=b''.join(s.to_bytes(4,'little') for s in sc)+bytes(sw*64-nb*4)
        d.image={sb+q*8:int.from_bytes(payload[q*64:(q+1)*64],'little') for q in range(sw)}
        for ch,w in enumerate(weights):
            raw=bytes(w)+bytes([255])*((-k)%64)
            d.image.update({wb+(ch*rw+q)*8:int.from_bytes(raw[q*64:(q+1)*64],'little') for q in range(rw)})
        load_start=len(t.rows);startreq=d.requests;startbeat=d.beats
        assert d.tick(job_valid=1,job_id=job,job_m=1,job_n=n,job_k=k,job_m_tile=1,job_weight_base=wb,job_scale_base=sb)[0]['job_ready']
        for beat in axis_tensor(x,ex,job):
            for _ in range(1000):
                if d.tick(s_axis_tvalid=1,**beat)[0]['s_axis_tready']:break
            else:raise AssertionError('AXIS timeout')
        d.until(lambda o:o['object_ready'])
        d.tick(object_valid=1,object_kind=0,object_index=0)
        d.until(lambda o:o['object_done'])
        for ch,w in enumerate(weights):
            d.tick(object_valid=1,object_kind=1,object_index=ch)
            d.until(lambda o:o['object_done'])
            loading=len(t.rows)-load_start
            gold=checkpoints(x,ex,w,sc);start=len(t.rows)
            assert d.tick(compute_valid=1,compute_job=job,compute_channel=ch,compute_k=k)[0]['compute_ready']
            events=[];previous=(0,0);peak=0;reserved=0;reads=[];b1_accepts=[]
            for tick in range(nb*100+200):
                enable=int(not(mode=='stall' and (tick<24 or tick%29<12)))
                # Record sampled actual-model request/handshake edges independently of traces.
                _,_,ci=t.model.signals(slice_enable=enable)
                outs,cs,detail=t.model.core.signals(**ci)
                if outs['x_rd_req']:reads.append((len(t.rows),outs['x_rd_index']))
                if detail['pop']:b1_accepts.append((len(t.rows),t.model.core.block_index,t.model.core.responses[t.model.core.read_ptr][5]))
                pre,p=d.tick(slice_enable=enable)
                ev,previous=observed(t.model.core,len(t.rows)-1,previous)
                for e in ev:verify_event(e,gold)
                events.extend(ev);all_events.extend(ev)
                peak=max(peak,t.model.core.fifo_count);reserved=max(reserved,t.model.core.fifo_count+t.model.core.pending)
                assert reserved<=4 and not p['error_valid'],(k,mode,p)
                if p['result_valid']:break
            else:raise AssertionError('compute timeout')
            assert len(events)==nb*3 and [e['block'] for e in events if e['event']=='A2_UPDATE']==list(range(nb))
            assert (p['result_mant'],p['result_exp'],p['result_job'],p['result_channel'])==(gold[-1]['acc_mant'],gold[-1]['acc_exp'],job,ch)
            cycles=len(t.rows)-start
            result_payload=tuple(p[n] for n in ['result_valid','result_mant','result_exp','result_job','result_channel'])
            for _ in range(17):
                p=d.tick()[1];assert tuple(p[n] for n in ['result_valid','result_mant','result_exp','result_job','result_channel'])==result_payload
            d.tick(result_ready=1)
            metrics.append(dict(job=job,channel=ch,k=k,mode=mode,compute_start=start,result_cycle=start+cycles-1,
                channel_cycles=cycles,load_cycles_before_compute=loading,result_stall_cycles=17,peak_fifo=peak,peak_reserved=reserved,
                events=events,reads=reads,b1_accepts=b1_accepts,ddr_requests=d.requests-startreq,ddr_beats=d.beats-startbeat))
            load_start=len(t.rows)
    # Numeric error integration: real DDR transport + real loaded buffers, no oracle bypass.
    for bad,code in [('fp8',0x31),('scale',0x30),('both',0x30)]:
        t.reset();d.queue=[]
        for _ in range(4):d.tick()
        d.image={0:127 if bad in ('fp8','both') else 0x38,8:0 if bad in ('scale','both') else 0x3f800000}
        d.tick(job_valid=1,job_id=9000,job_m=1,job_n=1,job_k=1,job_m_tile=1,job_scale_base=8)
        beat=axis_tensor([1],[0],9000)[0]
        for _ in range(100):
            if d.tick(s_axis_tvalid=1,**beat)[0]['s_axis_tready']:break
        d.until(lambda o:o['object_ready'])
        for kind in [0,1]:
            d.tick(object_valid=1,object_kind=kind);d.until(lambda o:o['object_done'])
        d.tick(compute_valid=1,compute_job=9000,compute_k=1)
        for _ in range(40):
            _,p=d.tick()
            if p['error_valid']:break
        assert p['error_code']==code and not p['result_valid']
        # Subsequent reset suppresses every stale checkpoint.
        t.reset();d.queue=[]
        for _ in range(12):d.tick()
    # Reset/abort with real outstanding RAM responses, and same-edge
    # unsolicited DDR21 versus FP8 NaN31 at the first B1 acceptance.
    for scenario in ['reset_inflight','abort_inflight','system_vs_nan']:
        t.reset();d.queue=[]
        for _ in range(4):d.tick()
        wcode=127 if scenario=='system_vs_nan' else 0xb8
        full=int.from_bytes(bytes([wcode])*64,'little')
        d.image={0:full,8:full,16:0x3f800000}
        d.tick(job_valid=1,job_id=8000,job_m=1,job_n=1,job_k=128,job_m_tile=1,job_scale_base=16)
        for beat in axis_tensor([1]*128,[0],8000):
            for _ in range(200):
                if d.tick(s_axis_tvalid=1,**beat)[0]['s_axis_tready']:break
        d.until(lambda o:o['object_ready'])
        for kind in [0,1]:
            d.tick(object_valid=1,object_kind=kind);d.until(lambda o:o['object_done'])
        d.tick(compute_valid=1,compute_job=8000,compute_k=128)
        d.tick();d.tick()
        if scenario=='reset_inflight':
            assert t.model.core.pending
            t.reset();d.queue=[]
            for _ in range(15):
                p=d.tick()[1]
                assert not any(p[n] for n in ['x_loaded','w_loaded','s_loaded','result_valid','error_valid'])
        else:
            kw={'abort':1} if scenario=='abort_inflight' else {'ddr_rd_vld':1,'ddr_rd_data':0}
            d.tick(**kw)
            for _ in range(15):
                p=d.tick()[1]
                if p['error_valid']:break
            assert p['error_code']==(0x40 if scenario=='abort_inflight' else 0x21) and not p['result_valid']
            for _ in range(10):assert not d.tick()[1]['result_valid']
    t.checkpoint_events=all_events
    t.counts=dict(legal_channels=len(metrics),joint_n2k129_updates=4,cycles=len(t.rows),ddr_requests=d.requests,ddr_beats=d.beats,
                  numeric_error_cases=3,inflight_fault_cases=3,max_fifo=max(r['peak_fifo'] for r in metrics))
    Path('docs/stage4/HARNESS_MEASUREMENTS.json').write_text(json.dumps(metrics,indent=2)+'\n')
    return t


def check_events(t,path):
    actual=[json.loads(s) for s in Path(path).read_text().splitlines()]
    # Errors can produce a B1 partial attempt before a fault. Compare only legal
    # jobs, defined independently from test case job ownership, not value filters.
    actual=[e for e in actual if 1000<=e['job_id']<2000]
    for e in actual:
        if 'term_mant_hex' in e:e['term_mant']=signed(int(e.pop('term_mant_hex'),16),72)
    expected=[e for e in t.events if 1000<=e['job_id']<2000]
    assert actual==expected, next(((a,b) for a,b in zip(actual,expected) if a!=b),(len(actual),len(expected)))
    return dict(result='PASS',records=len(actual),source='actual HDL $fdisplay vs cycle model + independent per-block Golden')
