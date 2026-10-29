"""Independent scoreboards, directed protocols, and exact-cycle HDL vectors."""
import json,random
from pathlib import Path
from stage5_model import GroupBuffer,Requant,ResultBuffer,Stage5,signed
from stage5_golden import requant,power
from test_stage5_numeric import cases
from linear_stream_model.numeric import requant_bfp18
from tools.gen_stage5_tb import ports

class Trace:
    def __init__(self,name,model):
        self.name,self.model=name,model;self.rows=[];self.events=[];self.counts={};self.previous_visible=self.previous_error=0
        ps=ports(name);self.ins=[(n,w) for d,n,w in ps if d=='input' and n!='clk'];self.outs=[(n,w) for d,n,w in ps if d=='output']
        self.step(rst_n=0);self.step(rst_n=0);self.step()
    @staticmethod
    def pack(fields,values):
        v=0
        for n,w in fields:v=(v<<w)|(int(values[n])&((1<<w)-1))
        return v
    def step(self,**kw):
        i={n:kw.get(n,1 if n in ['rst_n','clean_boundary'] else 0) for n,w in self.ins}
        if not i['rst_n']:self.model.reset()
        pre=self.model.snapshot(**i);cycle=len(self.rows);events=[]
        c=self.model if isinstance(self.model,Stage5) else getattr(self.model,'s5',None)
        def add(name,**v):events.append(dict(cycle=cycle,event=name,job_id=c.active_job,group=c.current_group,**v))
        if c is not None:
            ci=i if isinstance(self.model,Stage5) else self.model.signals(**i)[2]
            _,cs,d=c.signals(**ci);gi,qi,ri=cs;qo=c.q.snapshot(**qi);ro,rd=c.rb.signals(**ri)
            if i['rst_n']:
                if d['accept']:events.append(dict(cycle=cycle,event='JOB_ACCEPT',job_id=ci['job_id'],group=0,n=ci['job_n']))
                if ci.get('result_valid') and c.snapshot(**ci)['result_ready']:
                    events.append(dict(cycle=cycle,event='RESULT_ACCEPT',job_id=ci['result_job'],group=ci['result_channel']>>7,channel=ci['result_channel'],mant=signed(ci['result_mant'],48),exp=signed(ci['result_exp'],16)))
                if qo['attempt_begin']:add('ATTEMPT_BEGIN',retry=int(not qi['start']))
                if qo['rd_req']:add('GROUP_RAM_READ',index=qo['rd_index'])
                if qo['q_valid']:add('QUANT_ACCEPT',index=qo['q_index'],mant=qo['q_mant'],last=qo['q_last'],retry=qo['retried'])
                if rd['write']:add('RESULT_WORD_WRITE',index=rd['wi'],data_hex=f"{rd['assembled']:036x}")
                if rd['commit']:add('GROUP_COMMIT',exp=qo['shared_exp'])
        self.model.trace_cycle=cycle;self.model.step(**i);post=self.model.snapshot(**i)
        if c is not None:
            ci=i if isinstance(self.model,Stage5) else self.model.signals(**i)[2]
            co=c.snapshot(**ci)
            if i['rst_n']:
                _,postcs,_=c.signals(**ci)
                pq=c.q.snapshot(**postcs[1])
                if pq['q_valid']:add('QUANT_VALID',index=pq['q_index'],mant=pq['q_mant'],retry=pq['retried'])
                if pq['done']:add('REQUANT_DONE',exp=pq['shared_exp'])
                if co['rd_valid']:events.append(dict(cycle=cycle,event='RESULT_READ',job_id=c.active_job,group=co['rd_index']>>4,index=co['rd_index'],data_hex=f"{co['rd_data']:036x}",exp=co['rd_exp'],mask=co['rd_mask']))
                if co['group_done']:events.append(dict(cycle=cycle,event='GROUP_REQUANT',job_id=co['group_job'],group=co['group_id'],length=co['group_len'],exp=co['group_exp']))
                if co['job_results_ready'] and not self.previous_visible:add('JOB_RESULTS_READY')
                if co['error_valid'] and not self.previous_error:add('ERROR',code=co['error_code'],lock=co['fault_lock'])
            self.previous_visible=co['job_results_ready'];self.previous_error=co['error_valid']
        self.events.extend(events);self.rows.append((self.pack(self.ins,i),self.pack(self.outs,pre),self.pack(self.outs,post)))
        return pre,post
    def reset(self):self.step(rst_n=0);self.step()
    def save(self,path):
        with Path(path).open('w') as f:
            for a,b,c in self.rows:f.write(f'{a:x} {b:x} {c:x}\n')

def group_suite():
    t=Trace('xw_output_group_buffer',GroupBuffer());rng=random.Random(0x5181);groups=0
    for length in [1,7,8,9,28,29,127,128]*4:
        pairs=[(rng.randrange(-(1<<47),1<<47),rng.randrange(-32768,32768)) for _ in range(length)]
        pairs[0]=(-(1<<47),32767) if groups%2 else (0,-32768)
        base=128*(groups%4);job=31+groups
        t.step(begin_group=1,group_job=job,group_base=base,group_len=length)
        seen=[]
        for j,(m,e) in enumerate(pairs):
            if j%5==0:t.step(result_mant=-1,result_exp=32767,result_job=999,result_channel=999)
            pre,post=t.step(result_valid=1,result_mant=m,result_exp=e,result_job=job,result_channel=base+j)
            assert pre['result_ready'] and not post['fault'];seen.append((m,e))
            hs=[ee+abs(mm).bit_length()-1 for mm,ee in seen if mm]
            assert post['nonzero']==bool(hs) and post['hmax']==(max(hs) if hs else 0)
        assert post['loaded']
        assert not t.step(result_valid=1,result_job=999)[0]['result_ready']
        for j,p in enumerate(pairs):
            pre,post=t.step(rd_req=1,rd_index=j)
            assert post['rd_valid'] and (post['rd_mant'],post['rd_exp'])==p and not post['fault']
        t.step();groups+=1
    for kind in ['job','duplicate','skip','reverse','read_early','length','begin_busy']:
        t.reset();t.step(begin_group=1,group_job=3,group_len=2)
        if kind=='read_early':t.step(rd_req=1)
        elif kind in ['length','begin_busy']:t.step(begin_group=1,group_len=0 if kind=='length' else 1)
        else:
            t.step(result_valid=1,result_job=3,result_channel=0)
            t.step(result_valid=1,result_job=4 if kind=='job' else 3,result_channel={'duplicate':0,'skip':2,'reverse':65535,'job':1}[kind])
        assert t.model.fault and not t.model.snapshot()['loaded']
        t.step();assert t.model.fault
    t.reset();t.step(begin_group=1,group_job=5,group_len=1)
    t.step(result_valid=1,result_job=5,result_mant=1,cancel=1)
    assert not t.model.snapshot()['loaded'];t.step()
    t.counts=dict(groups=groups,lengths=[1,7,8,9,28,29,127,128],fault_cases=7,seed='0x5181')
    return t

def requant_suite():
    t=Trace('xw_bfp18_requant',Requant());groups=retry=fault=0
    for pairs in cases(700):
        g=requant(pairs);nz=[(m,e) for m,e in pairs if m];h=max(e+abs(m).bit_length()-1 for m,e in nz) if nz else 0
        t.step(start=1,group_len=len(pairs),nonzero=int(bool(nz)),hmax=h)
        response={};attempts=[];observed=[]
        for tick in range(2*len(pairs)+20):
            pre,post=t.step(**response)
            if pre['attempt_begin']:attempts.append(len(observed))
            if pre['q_valid']:
                idx=pre['q_index'];ex=g['candidate']+pre['retried'] if nz else 0
                expected=round(pairs[idx][0]*power(pairs[idx][1]-ex))
                assert (pre['q_mant'],pre['q_last'])==(expected,int(idx+1==len(pairs)))
                if pre['retried'] or not g['retry']:assert pre['q_mant']==g['mant'][idx]
                observed.append((pre['retried'],idx,pre['q_mant']))
            response={}
            if pre['rd_req']:
                m,e=pairs[pre['rd_index']];response=dict(rd_valid=1,rd_mant=m,rd_exp=e)
            if post['done'] or post['fault']:
                assert post['error_code']==g['error'],(pairs,g,post)
                assert post['retried']==g['retry']
                if not g['error']:assert post['shared_exp']==g['exp']
                assert len(observed)==len(pairs)*(1+g['retry'])
                break
        else:raise AssertionError('requant timeout')
        groups+=1;retry+=g['retry'];fault+=bool(g['error'])
        t.step(cancel=1);t.step()
    # Missing/stray synchronous response and invalid start.
    t.reset();assert t.step(rd_valid=1)[1]['error_code']==0x40
    t.reset();t.step(start=1,group_len=2,nonzero=1,hmax=0);t.step()
    assert t.step()[1]['error_code']==0x40
    t.reset();assert t.step(start=1,group_len=0)[1]['error_code']==0x40
    t.reset();t.step(start=1,group_len=128);t.step(cancel=1)
    for _ in range(4):assert not t.step()[1]['done']
    t.counts=dict(groups=groups,retries=retry,range_errors=fault,response_errors=2,cycles=len(t.rows))
    return t

def words_from(mants):
    return [sum((v&0x3ffff)<<(18*j) for j,v in enumerate(mants[lo:lo+8])) for lo in range(0,len(mants),8)]

def result_suite(max_n=12288):
    t=Trace('xw_result_buffer',ResultBuffer(max_n));rng=random.Random(0x5183);jobs=0
    for n in [x for x in [1,7,8,9,28,29,127,128,129,255,256,257,max_n,1] if x<=max_n]:
        t.step(cancel=1);t.step(job_begin=1,job_n=n)
        expected=[];exps=[]
        for group,lo in enumerate(range(0,n,128)):
            length=min(128,n-lo);exp=(group*19)%256-128;qs=[rng.randrange(-131071,131072) for _ in range(length)]
            # Initial speculative attempt deliberately differs; retry overwrites every actual lane.
            for attempt in range(2):
                t.step(attempt_begin=1,group_index=group,group_len=length)
                for j,q in enumerate(qs):
                    _,p=t.step(q_valid=1,q_index=j,q_mant=q if attempt else 131071,q_last=int(j+1==length))
                    assert not p['fault'] and not p['job_results_ready']
            p=t.step(commit=1,commit_exp=exp)[1]
            assert p['group_committed'] and not p['job_results_ready'] and not p['fault']
            expected.extend(words_from(qs));exps.append(exp)
        p=t.step(publish=1)[1];assert p['job_results_ready']
        for j,w in enumerate(expected):
            p=t.step(rd_req=1,rd_word_index=j)[1]
            assert p['rd_valid'] and (p['rd_data'],p['rd_exp'],p['rd_index'])==(w,exps[j//16],j)
            assert p['rd_mask']==((1<<(n%8))-1 if j+1==len(expected) and n%8 else 255)
        t.step();jobs+=1
    for kind in ['early_publish','early_commit','bad_index','bad_last','bad_group','read_range','job_busy','symmetric_range']:
        t.reset();t.step(job_begin=1,job_n=1)
        if kind=='early_publish':t.step(publish=1)
        elif kind=='job_busy':t.step(job_begin=1,job_n=1)
        elif kind=='bad_group':t.step(attempt_begin=1,group_index=1,group_len=1)
        else:
            t.step(attempt_begin=1,group_len=1)
            if kind=='symmetric_range':
                t.step(q_valid=1,q_mant=-131072,q_last=1);t.step(commit=1)
            elif kind=='early_commit':t.step(commit=1)
            elif kind=='bad_index':t.step(q_valid=1,q_index=1,q_last=1)
            elif kind=='bad_last':t.step(q_valid=1)
            else:
                t.step(q_valid=1,q_mant=1,q_last=1);t.step(commit=1);t.step(publish=1);t.step(rd_req=1,rd_word_index=1)
        assert t.model.fault and not t.model.snapshot()['job_results_ready'],kind
    t.reset();t.step(job_begin=1,job_n=1);t.step(attempt_begin=1,group_len=1)
    t.step(q_valid=1,q_last=1,q_mant=2,cancel=1)
    assert not t.model.snapshot()['job_results_ready']
    t.counts=dict(jobs=jobs,max_n=max_n,fault_cases=8,retry_overwrite=True,cycles=len(t.rows))
    return t

def check_job(t,pairs,job,gaps=False,early_read=False):
    n=len(pairs);gold=[requant(pairs[lo:lo+128]) for lo in range(0,n,128)]
    for group,g in enumerate(gold):assert not g['error'] and requant_bfp18(pairs[group*128:group*128+128])==(g['mant'],g['exp'])
    assert t.step(job_start=1,job_n=n,job_id=job)[0]['job_ready']
    ch=0;done=[];start=len(t.rows);offered=False
    for tick in range(5*n+1000):
        kw=dict(rd_req=int(early_read),rd_word_index=0)
        if not offered and ch<n and not(gaps and tick%7 in (1,2)):offered=True
        if offered:
            m,e=pairs[ch];kw.update(result_valid=1,result_job=job,result_channel=ch,result_mant=m,result_exp=e)
        pre,post=t.step(**kw)
        if kw.get('result_valid') and pre['result_ready']:ch+=1;offered=False
        if post['group_done']:
            group=post['group_id'];done.append(group)
            assert (post['group_job'],post['group_len'],post['group_exp'])==(job,len(gold[group]['mant']),gold[group]['exp'])
        assert not post['error_valid'],(n,ch,post,t.model.q.error_code)
        if post['job_results_ready']:break
    else:raise AssertionError(('Stage5 timeout',n,ch,t.model.state))
    assert ch==n and done==list(range(len(gold)))
    expected=[]
    for g in gold:expected.extend(words_from(g['mant']))
    for j,w in enumerate(expected):
        pre,p=t.step(rd_req=1,rd_word_index=j)
        assert pre['rd_ready'] and p['rd_valid']
        assert (p['rd_data'],p['rd_exp'],p['rd_index'])==(w,gold[j//16]['exp'],j)
        assert p['rd_mask']==((1<<(n%8))-1 if j+1==len(expected) and n%8 else 255)
    t.step();assert t.model.snapshot()['job_results_ready']
    t.step(retire=1);assert not t.model.snapshot()['job_results_ready']
    t.step();return len(t.rows)-start

def controller_suite(max_n=12288):
    t=Trace('xw_stage5_ctrl',Stage5(max_n));rng=random.Random(0x5184);jobs=0
    lengths=[1,7,8,9,28,29,127,128,129,255,256,257,max_n,1]
    for n in [n for n in lengths if n<=max_n]:
        for mode in ([0,1,2] if n in [1,128,129] else [1]):
            pairs=[(0,32767 if j%2 else -32768) if mode==0 else
                   ((262143 if j%2 else -262143),-130) if mode==2 else
                   (rng.randrange(-(1<<47),1<<47),rng.randrange(-30,-15)) for j in range(n)]
            check_job(t,pairs,100+jobs,gaps=jobs%2==0,early_read=True);jobs+=1
    for kind in ['job','duplicate','skip','reverse','range','late_range','upstream30','upstream31','upstream32','abort','unclean33','upstream_vs_abort']:
        t.reset();n=129 if kind=='late_range' else 2
        t.step(job_start=1,job_n=n,job_id=77)
        if kind=='late_range':
            ch=0
            while ch<128:
                pre,_=t.step(result_valid=1,result_mant=1,result_exp=0,result_job=77,result_channel=ch)
                ch+=pre['result_ready']
            for _ in range(160):
                _,p=t.step()
                if p['group_done']:break
            assert p['group_done'];channel=128
        else:
            t.step(result_valid=1,result_job=77,result_mant=1);channel=1
        if kind in ['upstream30','upstream31','upstream32','upstream_vs_abort']:
            code={'upstream30':0x30,'upstream31':0x31,'upstream32':0x32,'upstream_vs_abort':0x31}[kind]
            t.step(upstream_fault=1,upstream_code=code,abort=int(kind=='upstream_vs_abort'))
        elif kind=='abort':t.step(abort=1);code=0x40
        else:
            code=0x33 if kind in ['range','late_range','unclean33'] else 0x40
            clean=kind!='unclean33'
            for _ in range(5):
                before,_=t.step(result_valid=1,result_job=78 if kind=='job' else 77,
                       result_channel={'duplicate':0,'skip':2,'reverse':65535}.get(kind,channel),
                       result_mant=1,result_exp=32767 if code==0x33 else 0,clean_boundary=int(clean))
                if before['result_ready']:break
            else:raise AssertionError('fault stimulus was not accepted')
            for _ in range(170):
                _,p=t.step(clean_boundary=int(clean))
                if p['error_valid']:break
        p=t.model.snapshot();assert p['error_valid'] and p['error_code']==code and not p['job_results_ready'],(kind,p)
        if kind in ['range','late_range','upstream30','upstream31','upstream32','upstream_vs_abort']:
            assert not p['fault_lock'];t.step(retire=1);assert t.model.snapshot()['job_ready']
            check_job(t,[(262143,-130)],900+jobs);jobs+=1
        else:
            assert p['fault_lock'];t.step(retire=1);assert not t.model.snapshot()['job_ready']
    # First error retained, late actual system error escalates lock.
    t.reset();t.step(job_start=1,job_n=1,job_id=70);t.step(upstream_fault=1,upstream_code=0x32)
    p=t.step(upstream_fault=1,upstream_code=0x21,upstream_lock=1)[1]
    assert p['error_code']==0x32 and p['fault_lock'];t.step(retire=1);assert not t.model.snapshot()['job_ready']
    # Reset and abort at final RAM write, metadata commit, and group event edges.
    priorities=0
    for phase in ['word','commit','event','publish']:
        for op in ['abort','reset','upstream']:
            t.reset();t.step(job_start=1,job_n=1,job_id=80);t.step(result_valid=1,result_job=80,result_mant=65536)
            for _ in range(20):
                c=t.model
                ready=(phase=='word' and c.q.q_pending and c.q.q_last) or (phase=='commit' and c.state==c.COMMIT) or (phase=='event' and c.state==c.PUBLISH) or (phase=='publish' and c.state==c.FINAL)
                if ready:break
                t.step()
            else:raise AssertionError('priority phase timeout')
            p=t.step(**({'abort':1} if op=='abort' else {'rst_n':0} if op=='reset' else {'upstream_fault':1,'upstream_code':0x30}))[1]
            assert not p['group_done'] and not p['job_results_ready'] and not p['rd_valid'],(phase,op,p)
            for _ in range(5):
                p=t.step()[1];assert not p['group_done'] and not p['job_results_ready']
            priorities+=1
    t.counts=dict(jobs=jobs,max_n=max_n,n_matrix=lengths,fault_cases=12,collision_cases=priorities,seed='0x5184',cycles=len(t.rows))
    return t
