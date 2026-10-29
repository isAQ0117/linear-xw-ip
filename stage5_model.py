"""Stage5 register/RAM cycle models. Old snapshots compose every rising edge.

No arbitrary latency knobs, no production numeric or Fraction oracle calls.
Memories deliberately survive reset/cancel; valid/ownership registers do not.
"""
def signed(v,bits):
    v &= (1<<bits)-1
    return v-(1<<bits) if v>>(bits-1) else v

class GroupBuffer:
    def __init__(self):
        self.mem={};self.read_data=(0,0);self.reset()
    def reset(self):
        for n in 'read_pending read_seen active complete active_job base length count nonzero hmax fault'.split():setattr(self,n,0)
    def signals(self,**i):
        g=lambda n:i.get(n,0)
        en=i.get('rst_n',1) and not(g('cancel') or self.fault)
        ready=int(en and self.active and not self.complete and not(g('begin_group') or g('rd_req')))
        take=g('result_valid') and ready
        bad=(g('begin_group') and (g('rd_req') or (self.active and not self.complete) or not 1<=g('group_len')<=128 or g('group_base')%128 or g('group_base')+g('group_len')>65535)) or (take and (g('result_job')!=self.active_job or g('result_channel')!=self.base+self.count)) or (g('rd_req') and (not self.complete or g('rd_index')>=self.length or take))
        o=dict(result_ready=ready,loaded=int(en and self.complete),nonzero=self.nonzero,hmax=self.hmax,
               rd_valid=int(en and self.read_pending),rd_mant=self.read_data[0] if self.read_seen else 0,
               rd_exp=self.read_data[1] if self.read_seen else 0,fault=self.fault)
        return o,dict(take=take,bad=bad,write=take and not bad,read=en and not g('begin_group') and g('rd_req') and not bad)
    def snapshot(self,**i):return self.signals(**i)[0]
    def step(self,**i):
        if not i.get('rst_n',1):self.reset();return
        o,d=self.signals(**i);g=lambda n:i.get(n,0)
        if d['write']:self.mem[self.count]=(signed(g('result_mant'),48),signed(g('result_exp'),16))
        if d['read']:self.read_data=self.mem[g('rd_index')]
        if g('cancel'):
            self.active=self.complete=self.count=self.nonzero=self.hmax=self.read_pending=self.read_seen=self.fault=0
        elif self.fault or d['bad']:
            self.fault=1;self.active=self.complete=self.read_pending=0
        else:
            self.read_pending=int(d['read'])
            if d['read']:self.read_seen=1
            if g('begin_group'):
                self.active=1;self.complete=0;self.active_job=g('group_job');self.base=g('group_base');self.length=g('group_len')
                self.count=self.nonzero=self.hmax=self.read_seen=0
            elif d['take']:
                m,e=signed(g('result_mant'),48),signed(g('result_exp'),16)
                if m:
                    h=e+abs(m).bit_length()-1
                    if not self.nonzero or h>self.hmax:self.hmax=h
                    self.nonzero=1
                self.count+=1
                if self.count==self.length:self.complete=1

class Requant:
    IDLE,READ,DRAIN,CHECK,RESTART=range(5)
    def __init__(self):self.reset()
    def reset(self):
        for n in 'state length issued pending pending_index q_pending done_pending overflow_seen exponent shared_exp retried fault error_code q_index q_mant q_last'.split():setattr(self,n,0)
    @staticmethod
    def quant(m,e,target):
        a=abs(m);delta=target-e
        q=0
        if a:
            if delta<=0:
                q=(a&((1<<18)-1))<<((-delta)&31)
                q&=(1<<18)-1
            elif delta<48:
                q=(a>>delta)&((1<<18)-1)
                guard=(a>>(delta-1))&1
                sticky=bool((a<< (49-delta))&((1<<48)-1))
                q+=int(guard and (sticky or q&1))
        return -q if m<0 else q
    def signals(self,**i):
        g=lambda n:i.get(n,0)
        en=i.get('rst_n',1) and not(g('cancel') or self.fault)
        req=int(en and self.state==self.READ and self.issued<self.length)
        bad=(g('start') and (self.state!=self.IDLE or not 1<=g('group_len')<=128)) or g('rd_valid')!=self.pending or (self.pending and self.state not in (self.READ,self.DRAIN)) or self.state>self.RESTART
        o=dict(rd_req=req,rd_index=self.issued&127,attempt_begin=int(en and ((g('start') and self.state==self.IDLE) or self.state==self.RESTART)),
               q_valid=int(en and self.q_pending),q_index=self.q_index,q_mant=self.q_mant,q_last=self.q_last,
               done=int(en and self.done_pending),shared_exp=self.shared_exp,retried=self.retried,fault=self.fault,error_code=self.error_code)
        return o,bad
    def snapshot(self,**i):return self.signals(**i)[0]
    def step(self,**i):
        if not i.get('rst_n',1):self.reset();return
        o,bad=self.signals(**i);g=lambda n:i.get(n,0)
        if g('cancel'):
            self.state=self.pending=self.q_pending=self.done_pending=self.fault=self.error_code=0;return
        if self.fault or bad:
            if not self.fault:self.fault,self.error_code=1,0x40
            self.state=self.pending=self.q_pending=self.done_pending=0;return
        oldstate=self.state;oldindex=self.pending_index
        self.pending=o['rd_req'];self.q_pending=g('rd_valid');self.done_pending=0
        if o['rd_req']:
            self.pending_index=self.issued&127;self.issued+=1
            if self.issued==self.length:self.state=self.DRAIN
        if g('rd_valid'):
            self.q_mant=self.quant(signed(g('rd_mant'),48),signed(g('rd_exp'),16),self.exponent)
            self.q_index=oldindex;self.q_last=int(oldindex+1==self.length)
            self.overflow_seen|=abs(self.q_mant)>131071
            if self.q_last:self.state=self.CHECK
        if oldstate==self.IDLE and g('start'):
            self.length=g('group_len');self.issued=self.overflow_seen=self.retried=0
            self.exponent=signed(g('hmax'),18)-16 if g('nonzero') else 0;self.state=self.READ
        elif oldstate==self.CHECK:
            if self.overflow_seen:
                if self.retried:self.fault,self.error_code,self.state=1,0x40,self.IDLE
                else:
                    self.retried=1;self.exponent+=1;self.issued=self.overflow_seen=0;self.state=self.RESTART
            elif not -128<=self.exponent<=127:self.fault,self.error_code,self.state=1,0x33,self.IDLE
            else:self.shared_exp=self.exponent;self.done_pending=1;self.state=self.IDLE
        elif oldstate==self.RESTART:self.state=self.READ

class ResultBuffer:
    def __init__(self,max_n=12288):
        assert 1<=max_n<=65535
        self.max_n=max_n;self.mem={};self.exps={};self.ram_data=self.ram_exp=0;self.reset()
    def reset(self):
        for n in 'read_pending read_seen active visible active_n total_words total_groups committed_count attempt_active current_group length received attempt_range_bad pack_data group_committed rd_mask rd_index fault'.split():setattr(self,n,0)
    def signals(self,**i):
        g=lambda n:i.get(n,0)
        en=i.get('rst_n',1) and not(g('cancel') or self.fault)
        remaining=(self.active_n-g('group_index')*128)&0x1ffff
        length=min(128,remaining)&255
        wi=self.current_group*16+(g('q_index')>>3)
        flush=g('q_index')%8==7 or g('q_last')
        bad=(g('job_begin') and (self.active or any(g(n) for n in ('attempt_begin','q_valid','commit','publish')) or not 1<=g('job_n')<=self.max_n)) or (g('attempt_begin') and (not self.active or self.visible or any(g(n) for n in ('q_valid','commit','publish')) or g('group_index')!=self.committed_count or self.committed_count>=self.total_groups or g('group_len')!=length or not 1<=g('group_len')<=128 or (self.attempt_active and self.received!=self.length))) or (g('q_valid') and (not self.attempt_active or self.visible or g('commit') or g('publish') or self.received>=self.length or g('q_index')!=self.received or g('q_last')!=(self.received+1==self.length) or wi >= (self.max_n+7)//8)) or (g('commit') and (not self.attempt_active or self.visible or self.received!=self.length or g('q_valid') or self.pack_data!=0 or self.attempt_range_bad or g('publish') or self.current_group!=self.committed_count)) or (g('publish') and (not self.active or self.visible or self.attempt_active or self.committed_count!=self.total_groups)) or (self.visible and g('rd_req') and g('rd_word_index')>=self.total_words)
        visible=en and self.visible
        ready=visible and g('rd_word_index')<self.total_words
        data=0 if g('q_index')%8==0 else self.pack_data
        lane=g('q_index')%8;data &= ~(((1<<18)-1)<<(lane*18));data |= (g('q_mant')&((1<<18)-1))<<(lane*18)
        o=dict(group_committed=self.group_committed,job_results_ready=int(visible),rd_ready=int(ready),
               rd_valid=int(visible and self.read_pending),rd_data=self.ram_data if visible and self.read_seen else 0,
               rd_exp=self.ram_exp if visible and self.read_seen else 0,rd_mask=self.rd_mask,rd_index=self.rd_index,fault=self.fault)
        d=dict(bad=bad,write=en and not bad and not g('job_begin') and g('q_valid') and flush,
               commit=en and not bad and not g('job_begin') and g('commit'),
               read=g('rd_req') and ready and not bad and not g('job_begin'),flush=flush,assembled=data,wi=wi)
        return o,d
    def snapshot(self,**i):return self.signals(**i)[0]
    def step(self,**i):
        if not i.get('rst_n',1):self.reset();return
        o,d=self.signals(**i);g=lambda n:i.get(n,0)
        if d['write']:self.mem[d['wi']]=d['assembled']
        if d['commit']:self.exps[self.current_group]=signed(g('commit_exp'),8)
        if d['read']:self.ram_data=self.mem[g('rd_word_index')];self.ram_exp=self.exps[g('rd_word_index')>>4]
        if g('cancel'):
            self.active=self.visible=self.committed_count=self.attempt_active=self.received=self.attempt_range_bad=self.pack_data=self.group_committed=self.read_pending=self.read_seen=self.rd_mask=self.fault=0;return
        if self.fault or d['bad']:
            self.fault=1;self.visible=self.active=self.attempt_active=self.group_committed=self.read_pending=0;return
        self.group_committed=0;self.read_pending=int(d['read'])
        if d['read']:
            self.read_seen=1;self.rd_index=g('rd_word_index');r=self.active_n%8
            self.rd_mask=(1<<r)-1 if g('rd_word_index')+1==self.total_words and r else 255
        if g('job_begin'):
            self.active=1;self.visible=0;self.active_n=g('job_n');self.total_words=(self.active_n+7)//8;self.total_groups=(self.active_n+127)//128
            self.committed_count=self.attempt_active=self.pack_data=self.read_seen=0
        elif g('attempt_begin'):
            self.attempt_active=1;self.current_group=g('group_index');self.length=g('group_len');self.received=self.attempt_range_bad=self.pack_data=0
        elif g('q_valid'):
            self.received+=1;self.attempt_range_bad|=signed(g('q_mant'),18)==-131072
            self.pack_data=0 if d['flush'] else d['assembled']
        elif g('commit'):self.committed_count+=1;self.attempt_active=0;self.group_committed=1
        elif g('publish'):self.visible=1

class Stage5:
    IDLE,COLLECT,WAIT,COMMIT,PUBLISH,NEXT,FINAL,COMPLETE,FAILED=range(9)
    def __init__(self,max_n=12288):
        self.max_n=max_n;self.gb=GroupBuffer();self.q=Requant();self.rb=ResultBuffer(max_n);self.reset_control()
    def reset_control(self):
        for n in 'state active_job active_n current_group error_pending error_code fault_lock group_pending group_job group_id group_len group_exp'.split():setattr(self,n,0)
    def reset(self):
        self.reset_control()
        for m in (self.gb,self.q,self.rb):m.reset()
    def signals(self,**i):
        g=lambda n:i.get(n,0)
        rst=i.get('rst_n',1)
        ready=int(rst and not(g('abort') or g('upstream_fault') or self.error_pending or self.fault_lock) and self.state==self.IDLE)
        accept=g('job_start') and ready
        remaining=(self.active_n-self.current_group*128)&0x1ffff
        length=min(128,remaining)&255
        bad=(g('job_start') and (not ready or not 1<=g('job_n')<=self.max_n)) or (g('retire') and (self.state not in (self.COMPLETE,self.FAILED) or not g('clean_boundary') or self.fault_lock)) or (self.state==self.PUBLISH and not self.rb.group_committed) or self.state>self.FAILED
        if g('upstream_fault') and (g('upstream_lock') or g('upstream_code')<0x30 or g('upstream_code')==0x40):err=g('upstream_code') or 0x40
        elif bad or self.gb.fault or self.rb.fault or (self.q.fault and self.q.error_code==0x40) or (g('abort') and not g('upstream_fault')):err=0x40
        elif g('upstream_fault'):err=g('upstream_code')
        elif self.q.fault:err=self.q.error_code
        else:err=0
        stop=bool(g('abort') or g('upstream_fault') or self.error_pending or err)
        common=dict(rst_n=rst,cancel=int(stop or g('retire')))
        # Memory outputs depend only on pre-edge ownership/registers.
        go=self.gb.snapshot(**common)
        qi=dict(common,start=int(self.state==self.COLLECT and go['loaded'] and not stop),group_len=length,
                nonzero=go['nonzero'],hmax=go['hmax'],rd_valid=go['rd_valid'],rd_mant=go['rd_mant'],rd_exp=go['rd_exp'])
        qo=self.q.snapshot(**qi)
        gi=dict(common,begin_group=int((accept or self.state==self.NEXT) and not stop),group_job=g('job_id') if accept else self.active_job,
                group_base=0 if accept else self.current_group*128,group_len=min(128,g('job_n')) if accept else length,
                result_valid=int(g('result_valid') and self.state==self.COLLECT),result_mant=g('result_mant'),result_exp=g('result_exp'),result_job=g('result_job'),result_channel=g('result_channel'),rd_req=qo['rd_req'],rd_index=qo['rd_index'])
        go=self.gb.snapshot(**gi)
        ri=dict(common,job_begin=int(accept and not stop),job_n=g('job_n'),attempt_begin=qo['attempt_begin'],group_index=self.current_group,group_len=length,
                q_valid=qo['q_valid'],q_index=qo['q_index'],q_mant=qo['q_mant']&((1<<18)-1),q_last=qo['q_last'],
                commit=int(self.state==self.COMMIT and not stop),commit_exp=qo['shared_exp'],publish=int(self.state==self.FINAL and not stop),rd_req=g('rd_req'),rd_word_index=g('rd_word_index'))
        ro=self.rb.snapshot(**ri)
        o=dict(job_ready=ready,result_ready=int(not stop and self.state==self.COLLECT and go['result_ready']),group_done=int(rst and not stop and self.group_pending),
               group_job=self.group_job,group_id=self.group_id,group_len=self.group_len,group_exp=self.group_exp,
               job_results_ready=int(rst and not stop and ro['job_results_ready']),error_valid=int(rst and self.error_pending),error_code=self.error_code,fault_lock=self.fault_lock)
        o.update({n:ro[n] for n in ('rd_ready','rd_valid','rd_data','rd_exp','rd_mask','rd_index')})
        return o,(gi,qi,ri),dict(err=err,accept=accept,bad=bad,length=length,remaining=remaining,qo=qo,stop=stop)
    def snapshot(self,**i):return self.signals(**i)[0]
    def step(self,**i):
        if not i.get('rst_n',1):self.reset();return
        pre,controls,d=self.signals(**i);g=lambda n:i.get(n,0);s=self.state
        self.group_pending=0
        if self.error_pending:
            self.state=self.FAILED
            if g('upstream_fault') and (g('upstream_lock') or g('upstream_code')<0x30 or g('upstream_code')==0x40):self.fault_lock=1
            if g('retire') and g('clean_boundary') and not self.fault_lock and not g('upstream_fault') and not g('abort'):
                self.error_pending=self.error_code=0;self.state=self.IDLE
        elif d['err']:
            self.error_pending=1;self.error_code=d['err'];self.fault_lock=int(d['err']<0x30 or d['err']==0x40 or g('upstream_lock') or not g('clean_boundary'));self.state=self.FAILED
        elif g('retire'):self.state=self.IDLE
        elif s==self.IDLE and d['accept']:
            self.active_job=g('job_id');self.active_n=g('job_n');self.current_group=0;self.state=self.COLLECT
        elif s==self.COLLECT and controls[1]['start']:self.state=self.WAIT
        elif s==self.WAIT and d['qo']['done']:self.state=self.COMMIT
        elif s==self.COMMIT:self.state=self.PUBLISH
        elif s==self.PUBLISH:
            self.group_pending=1;self.group_job=self.active_job;self.group_id=self.current_group;self.group_len=d['length'];self.group_exp=d['qo']['shared_exp']
            if d['remaining']<=128:self.state=self.FINAL
            else:self.current_group+=1;self.state=self.NEXT
        elif s==self.NEXT:self.state=self.COLLECT
        elif s==self.FINAL:self.state=self.COMPLETE
        for m,c in zip((self.gb,self.q,self.rb),controls):m.step(**c)
