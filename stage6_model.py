"""Register-level Stage6 models. step consumes PRE-edge signals, snapshot is NBA.
No oracle imports; RAM response reservation and AXIS holding match actual slots.
"""
class JobStatus:
    def __init__(self): self.reset()
    def reset(self):
        self.status_valid=self.status_job_id=self.status_ok=self.status_error_code=0
    def snapshot(self,**i):
        return dict(finish_ready=int(i.get('rst_n',1) and not self.status_valid),
                    **{n:getattr(self,n) for n in ('status_valid','status_job_id','status_ok','status_error_code')})
    def step(self,**i):
        if not i.get('rst_n',1): self.reset();return
        if self.status_valid:
            if i.get('status_ready',0):self.status_valid=0
        elif i.get('finish_valid',0):
            self.status_valid=1
            self.status_job_id=i.get('finish_job_id',0);self.status_ok=i.get('finish_ok',0)
            self.status_error_code=i.get('finish_error_code',0)

class AxisOutput:
    def __init__(self,max_n=12288):self.max_n=max_n;self.fifo={};self.reset()
    def reset(self):
        for n in ('wp rp count pending issued received words active active_id active_n group_id offset packed '
                  'assembly half_word exponent response_exp output_done fault m_axis_tdata m_axis_tvalid '
                  'm_axis_tkeep m_axis_tlast m_axis_tuser').split():setattr(self,n,0)
    def signals(self,**i):
        g=lambda n:i.get(n,0);rst=i.get('rst_n',1)
        ready=int(rst and not(self.active or self.m_axis_tvalid or self.fault or g('halt')))
        req=int(rst and self.active and not(g('halt') or self.fault) and self.issued<self.words and self.count+self.pending<4)
        rem=(self.active_n-self.group_id*128)&0x1ffff
        length=min(128,rem)&255;bl=min(28,(length-self.offset)&255)
        left=(rem-self.offset-self.packed)&0x1ffff
        hl=(4 if self.half_word else 8) if left>=(4 if self.half_word else 8) else left
        take=min((bl-self.packed)&63,hl)&15
        consume=int(rst and self.active and not(g('halt') or self.fault) and self.count!=0 and (not self.m_axis_tvalid or g('m_axis_tready')))
        pop=consume and take==hl;push=g('rd_valid') and self.active and not(g('halt') or self.fault)
        head,he=self.fifo.get(self.rp,(0,0))
        mask=(1<<(self.active_n%8))-1 if self.received+1==self.words and self.active_n%8 else 255
        bad=(g('start') and (not ready or not 1<=g('job_n')<=self.max_n)) or (self.active and not g('halt') and (
            g('rd_valid')!=self.pending or self.count>4 or (self.pending and self.count==4) or
            (g('rd_valid') and (g('rd_index')!=self.received or g('rd_mask')!=mask or
             (self.received+1==self.words and self.active_n%8 and g('rd_data')>>(self.active_n%8*18)) or
             (self.received%16!=0 and g('rd_exp')!=self.response_exp))) or
            (consume and (take==0 or ((self.offset!=0 or self.packed!=0) and he!=self.exponent)))))
        o=dict(start_ready=ready,rd_req=req,rd_word_index=self.issued)
        o.update({n:getattr(self,n) for n in 'output_done fault m_axis_tdata m_axis_tvalid m_axis_tkeep m_axis_tlast m_axis_tuser'.split()})
        return o,dict(bad=bad,pop=int(pop),push=int(push),consume=consume,flush=consume and self.packed+take==bl,
                      head=head,exp=he,take=take,bl=bl,length=length,gl=self.offset+bl==length,
                      eot=self.offset+bl==length and rem<=128)
    def snapshot(self,**i):return self.signals(**i)[0]
    def step(self,**i):
        if not i.get('rst_n',1):self.reset();return
        o,d=self.signals(**i);g=lambda n:i.get(n,0);old_half=self.half_word;was_active=self.active;self.output_done=0
        if self.m_axis_tvalid and g('m_axis_tready'):
            self.m_axis_tvalid=0
            if self.m_axis_tuser>>88&1 and not(g('halt') or self.fault or d['bad']):self.output_done=1;self.active=0
        if d['push'] and not d['bad']:self.fifo[self.wp]=(g('rd_data'),g('rd_exp'))
        old_fault=self.fault
        if d['bad']:self.fault=1
        if g('halt') or old_fault or d['bad']:
            self.active=self.pending=self.count=0
        elif g('start') and o['start_ready']:
            self.active=1;self.active_id=g('job_id');self.active_n=g('job_n');self.words=(self.active_n+7)//8
            self.wp=self.rp=self.count=self.pending=self.issued=self.received=self.group_id=self.offset=self.packed=self.assembly=self.half_word=self.exponent=self.response_exp=0
        elif was_active:
            self.pending=int(o['rd_req'] and g('rd_ready'))
            self.issued+=self.pending
            if d['push']:
                self.wp=(self.wp+1)&3;self.received+=1;self.response_exp=g('rd_exp')
            if d['pop']:self.rp=(self.rp+1)&3;self.half_word=0
            elif d['consume']:self.half_word=1
            self.count+=d['push']-d['pop']
            if d['consume']:
                head=d['head'] >> (72 if old_half else 0)
                head &= (1<<(d['take']*18))-1
                assembled=self.assembly | (head<<(self.packed*18))
                self.exponent=d['exp']
                if d['flush']:
                    self.m_axis_tvalid=1;self.m_axis_tdata=assembled
                    self.m_axis_tkeep=(1<<((d['bl']*18+7)//8))-1;self.m_axis_tlast=int(d['gl'])
                    self.m_axis_tuser=(self.active_id|(self.group_id<<48)|(d['exp']<<64)|(d['length']<<72)|
                                       (self.offset<<80)|(int(d['eot'])<<88)|(0xb2<<96))
                    self.packed=self.assembly=0
                    if d['gl']:self.offset=0;self.group_id=(self.group_id+1)&511
                    else:self.offset+=d['bl']
                else:self.packed+=d['take'];self.assembly=assembled
