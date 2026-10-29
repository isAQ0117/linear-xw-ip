"""Real Stage234/Stage5 composition; independent A2 and final buffer checks."""
from stage4_integration import Harness as ComputeHarness,DDR
from stage4_golden import checkpoints
from stage23_golden import axis_tensor
from stage5_model import Stage5
from stage5_golden import requant
from linear_stream_model.numeric import requant_bfp18
from test_stage5 import Trace,words_from

class Harness:
    def __init__(self):self.s4=ComputeHarness();self.s5=Stage5(129)
    def reset(self):self.s4.reset();self.s5.reset()
    def signals(self,**i):
        raw,_,_=self.s4.signals(**dict(i,result_ready=0))
        ci=dict(rst_n=(self.s4.storage.release>>1)&1,abort=i.get('abort',0),
                job_start=int(i.get('job_valid',0) and raw['job_ready']),job_id=i.get('job_id',0),job_n=i.get('job_n',0),
                retire=i.get('retire',0),clean_boundary=1,upstream_fault=raw['error_valid'],upstream_code=raw['error_code'],upstream_lock=raw['fault_lock'],
                result_valid=raw['result_valid'],result_mant=raw['result_mant'],result_exp=raw['result_exp'],result_job=raw['result_job'],result_channel=raw['result_channel'],
                rd_req=i.get('rd_req',0),rd_word_index=i.get('rd_word_index',0))
        so=self.s5.snapshot(**ci);si=dict(i,result_ready=so['result_ready'])
        raw=self.s4.snapshot(**si)
        out={n:v for n,v in raw.items() if n not in ('error_valid','error_code','fault_lock')}
        out.update(stage4_error_valid=raw['error_valid'],stage4_error_code=raw['error_code'],stage4_fault_lock=raw['fault_lock'])
        out.update({n:so[n] for n in ('result_ready','group_done','group_job','group_id','group_len','group_exp','job_results_ready','error_valid','error_code','fault_lock','rd_ready','rd_valid','rd_data','rd_exp','rd_mask','rd_index')})
        return out,si,ci
    def snapshot(self,**i):return self.signals(**i)[0]
    def step(self,**i):
        if not i.get('rst_n',1):self.reset();return
        _,si,ci=self.signals(**i)
        self.s4.trace_cycle=getattr(self,'trace_cycle',0)
        self.s4.step(**si);self.s5.step(**ci)


def harness_suite():
    t=Trace('xw_stage45_harness',Harness());d=DDR(t);metrics=[];stalls=0;channels=0
    for job,n,k in [(5001,2,129),(5002,129,129),(5003,129,1)]:
        t.reset();d.queue=[]
        for _ in range(4):d.tick()
        x=[(j*13)%61-30 for j in range(k)];nb=(k+127)//128;ex=[0]*nb
        if k==1:x=[7]
        weights=[[0xb8 if ch%2 else 0x38]*k for ch in range(n)]
        groups=(n+127)//128
        scales=[[0x3f800000 if g==0 else 0x37800000]*nb for g in range(groups)]
        wb=0x100;rw=(k+63)//64;sb=wb+n*rw*8;sw=(nb+15)//16
        d.image={}
        for g,sc in enumerate(scales):
            raw=b''.join(s.to_bytes(4,'little') for s in sc)+bytes(sw*64-nb*4)
            d.image.update({sb+(g*sw+q)*8:int.from_bytes(raw[q*64:(q+1)*64],'little') for q in range(sw)})
        for ch,w in enumerate(weights):
            raw=bytes(w)+bytes([255])*((-k)%64)
            d.image.update({wb+(ch*rw+q)*8:int.from_bytes(raw[q*64:(q+1)*64],'little') for q in range(rw)})
        assert d.tick(job_valid=1,job_id=job,job_m=1,job_n=n,job_k=k,job_m_tile=1,job_weight_base=wb,job_scale_base=sb)[0]['job_ready']
        for beat in axis_tensor(x,ex,job):
            for _ in range(1000):
                if d.tick(s_axis_tvalid=1,**beat)[0]['s_axis_tready']:break
            else:raise AssertionError('input timeout')
        d.until(lambda o:o['object_ready']);pairs=[];old_result=None
        start=len(t.rows)
        for ch,w in enumerate(weights):
            if ch%128==0:
                d.tick(object_valid=1,object_kind=0,object_index=ch//128)
                d.until(lambda o:o['object_done'])
            d.tick(object_valid=1,object_kind=1,object_index=ch);d.until(lambda o:o['object_done'])
            gold=checkpoints(x,ex,w,scales[ch//128]);pair=gold[-1]['acc_mant'],gold[-1]['acc_exp'];pairs.append(pair)
            assert d.tick(compute_valid=1,compute_job=job,compute_channel=ch,compute_k=k)[0]['compute_ready']
            for tick in range(nb*100+1000):
                pre,p=d.tick()
                assert not p['stage4_error_valid'] and not p['error_valid'],p
                if pre['result_valid']:
                    payload=(pre['result_mant'],pre['result_exp'],pre['result_job'],pre['result_channel'])
                    assert payload==(*pair,job,ch),(pair,pre)
                    if not pre['result_ready']:
                        if old_result is not None:assert payload==old_result
                        old_result=payload;stalls+=1
                    else:old_result=None;break
            else:raise AssertionError('compute/result timeout')
            channels+=1
        p=d.until(lambda o:o['job_results_ready'])
        gg=[requant(pairs[lo:lo+128]) for lo in range(0,n,128)]
        for g,a in enumerate(gg):assert requant_bfp18(pairs[g*128:g*128+128])==(a['mant'],a['exp'])
        if n==129:assert gg[0]['exp']!=gg[1]['exp']
        expected=[]
        for a in gg:expected.extend(words_from(a['mant']))
        for j,w in enumerate(expected):
            pre,p=d.tick(rd_req=1,rd_word_index=j)
            assert pre['rd_ready'] and p['rd_valid']
            mask=(1<<(n%8))-1 if j+1==len(expected) and n%8 else 255
            assert (p['rd_data'],p['rd_exp'],p['rd_mask'],p['rd_index'])==(w,gg[j//16]['exp'],mask,j)
        ev=[e for e in t.events if e['job_id']==job and e['event']=='GROUP_REQUANT']
        assert [(e['group'],e['length'],e['exp']) for e in ev]==[(g,len(a['mant']),a['exp']) for g,a in enumerate(gg)]
        accepts=[e for e in t.events if e['job_id']==job and e['event']=='RESULT_ACCEPT']
        assert [(a['channel'],a['mant'],a['exp']) for a in accepts]==[(ch,*pair) for ch,pair in enumerate(pairs)]
        metrics.append(dict(job=job,n=n,k=k,cycles_with_loading_compute_requant=len(t.rows)-start,groups=[dict(exp=a['exp'],mant=a['mant']) for a in gg]))
    t.counts=dict(channels=channels,real_n2_k129=True,real_n129_k129=True,real_n129_k1=True,stage4_result_stall_edges=stalls,ddr_requests=d.requests,ddr_beats=d.beats,cycles=len(t.rows))
    from pathlib import Path
    import json
    Path('docs/stage5/INTEGRATION_MEASUREMENTS.json').write_text(json.dumps(metrics,indent=2)+'\n')
    return t
