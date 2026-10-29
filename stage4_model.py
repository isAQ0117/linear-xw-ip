"""Level 2: Stage4 pre-edge/NBA register models, no selectable fake latencies.

Every step shifts the actual B1 stages, B2 elastic registers, or executes one
A2 state/chunk. Inter-module composition must use OLD snapshots throughout.
Numeric values here use integer hardware-oriented math, not the Fraction oracle.
"""
from stage4_a2_math import segment, rne_window


def signed(v, n):
    v &= (1 << n)-1
    return v-(1 << n) if v >> (n-1) else v


def decode(c):
    e, f = (c >> 3) & 15, c & 7
    v = f if not e else (8+f) << (e-1)
    return -v if c & 128 else v


class B1:
    def __init__(self): self.reset()
    def reset(self):
        self.pipe=[None]*4
        self.acc=self.expected=self.block=self.exp=self.closed=self.pending=0
        self.out_raw=self.out_exp=self.out_block=self.fault=self.error_code=0
    def snapshot(self, **i):
        enable=i.get('rst_n',1) and not i.get('abort',0) and not self.fault
        return dict(in_ready=int(enable and not self.closed and not self.pending),
                    out_valid=int(enable and self.pending),out_raw=self.out_raw,
                    out_exp=self.out_exp,out_block=self.out_block,fault=self.fault,error_code=self.error_code)
    def step(self, **i):
        if not i.get('rst_n',1): self.reset(); return
        o=self.snapshot(**i); accept=i.get('in_valid',0) and o['in_ready']
        sl=i.get('in_slice',0); block=i.get('in_block',0); ex=signed(i.get('in_exp',0),8)
        err=0
        if accept:
            if sl!=self.expected or (sl and (block!=self.block or ex!=self.exp)) or (sl==15 and not i.get('in_last',0)):err=0x40
            elif any((i.get('in_mask',0)>>l)&1 and ((i.get('in_w',0)>>(l*8))&127)==127 for l in range(8)):err=0x31
        if self.fault or i.get('abort',0) or err:
            self.pipe=[None]*4; self.pending=0; self.closed=1
            if not self.fault:self.fault,self.error_code=1,0x40 if i.get('abort',0) else err
            return
        old=self.pipe[-1]
        payload=None
        if accept:
            value=sum(signed(i.get('in_x',0)>>(l*18),18)*decode((i.get('in_w',0)>>(l*8))&255)
                      for l in range(8) if (i.get('in_mask',0)>>l)&1)
            payload=(value,sl==0,i.get('in_last',0),block,ex)
            self.expected=(sl+1)&15
            if not sl:self.block,self.exp=block,ex
            if i.get('in_last',0):self.closed=1
        self.pipe=[payload]+self.pipe[:-1]
        if old:
            value,first,last,block,ex=old
            self.acc=value if first else self.acc+value
            if last:self.pending,self.out_raw,self.out_exp,self.out_block=1,self.acc,ex,block
        if o['out_valid'] and i.get('out_ready',0):self.pending=self.expected=self.closed=0


class B2:
    def __init__(self): self.reset()
    def reset(self):
        self.p0=None; self.v1=0
        self.out_mant=self.out_exp=self.out_block=self.out_error=0
    def snapshot(self, **i):
        enable=i.get('rst_n',1) and not i.get('abort',0)
        return dict(in_ready=int(enable and (self.p0 is None or not self.v1 or i.get('out_ready',0))),
                    out_valid=int(enable and self.v1),out_mant=self.out_mant,out_exp=self.out_exp,
                    out_block=self.out_block,out_error=self.out_error)
    def step(self, **i):
        if not i.get('rst_n',1):self.reset();return
        if i.get('abort',0):self.p0=None;self.v1=0;return
        o=self.snapshot(**i)
        if not self.v1 or i.get('out_ready',0):
            self.v1=int(self.p0 is not None)
            if self.p0 is not None:
                raw,ex,sc,bl=self.p0
                self.out_block=bl
                if 0 < sc < 0x7f800000:
                    e,f=divmod(sc,1<<23);sig=f+(1<<23) if e else f
                    self.out_mant=raw*sig;self.out_exp=ex-9+(e-150 if e else -149);self.out_error=0
                else:self.out_mant=self.out_exp=0;self.out_error=0x30
        if o['in_ready']:
            self.p0=(signed(i.get('in_raw',0),48),signed(i.get('in_exp',0),8),i.get('in_scale',0),i.get('in_block',0)) if i.get('in_valid',0) else None


class A2:
    IDLE,ALIGN,SUM,ABS,LEAD,ROUND,CHECK,COMMIT,SETUP,CHUNK,ZERO=range(11)
    def __init__(self): self.reset()
    def reset(self):
        self.state=self.state_mant=self.state_exp=self.out_block=self.special_path=self.fault=self.error_code=self.update_pending=0
        self.old_mant=self.term_mant=self.target_exp=self.old_shift=self.term_shift=0
        self.aligned_old=self.aligned_term=self.exact_sum=self.window=self.window_base=0
        self.magnitude_length=self.negative=self.is_power_two=self.sticky=self.norm_shift=self.round_shift=self.rounded=self.retried=0
        self.high_mag=self.low_mag=self.high_negative=self.low_negative=self.gap=self.high_offset=0
        self.subtract_mode=self.high_larger=self.carry_borrow=self.chunk_index=self.chunk_count=self.previous_chunk=self.low_sticky=0
    def snapshot(self, **i):
        enable=i.get('rst_n',1) and not i.get('abort',0) and not self.fault
        return dict(in_ready=int(enable and not i.get('clear',0) and self.state==self.IDLE),
                    busy=int(self.state!=self.IDLE),update_valid=int(enable and self.update_pending),
                    state_mant=self.state_mant,state_exp=self.state_exp,out_block=self.out_block,
                    special_path=self.special_path,fault=self.fault,error_code=self.error_code)
    def fail(self, code):self.fault,self.error_code,self.state=1,code,self.IDLE
    def step(self, **i):
        if not i.get('rst_n',1):self.reset();return
        pre=self.snapshot(**i);self.update_pending=0
        if self.fault or i.get('abort',0) or (i.get('clear',0) and self.state!=self.IDLE):
            if not self.fault:self.fail(0x40)
            self.state=self.IDLE;return
        if i.get('clear',0):self.state_mant=self.state_exp=0;return
        s=self.state
        if s==self.IDLE and i.get('in_valid',0) and pre['in_ready']:
            tn,te=signed(i.get('in_mant',0),72),signed(i.get('in_exp',0),12)
            sn,se=self.state_mant,self.state_exp;d=se-te
            self.old_mant,self.term_mant,self.out_block=sn,tn,i.get('in_block',0)
            self.retried=self.window=self.window_base=self.sticky=self.magnitude_length=self.is_power_two=0
            self.target_exp=te if not sn else min(se,te)
            self.old_shift=0 if not sn or d<0 else abs(d)
            self.term_shift=0 if not sn or d>=0 else abs(d)
            self.special_path=int(sn!=0 and tn!=0 and abs(d)>48)
            if not tn:self.state=self.ZERO
            elif not self.special_path:self.state=self.ALIGN
            else:
                self.gap=abs(d)
                h,l=(sn,tn) if d>=0 else (tn,sn)
                self.high_mag,self.low_mag=abs(h),abs(l)
                self.high_negative,self.low_negative=h<0,l<0
                self.state=self.SETUP
        elif s==self.ALIGN:
            self.aligned_old=self.old_mant<<self.old_shift
            self.aligned_term=self.term_mant<<self.term_shift
            self.state=self.SUM
        elif s==self.SUM:self.exact_sum=self.aligned_old+self.aligned_term;self.state=self.ABS
        elif s==self.ABS:self.negative=self.exact_sum<0;self.window=abs(self.exact_sum);self.state=self.LEAD
        elif s==self.SETUP:
            self.high_offset=-self.gap
            hl,ll=self.high_mag.bit_length()+self.gap,self.low_mag.bit_length()
            self.high_larger=hl>ll or (hl==ll and self.high_mag<<self.gap >= self.low_mag)
            self.negative=self.high_negative if self.high_larger else self.low_negative
            self.subtract_mode=self.high_negative!=self.low_negative
            self.chunk_count=(self.gap+136)//64
            self.chunk_index=self.previous_chunk=self.low_sticky=self.carry_borrow=0
            self.state=self.CHUNK
        elif s==self.CHUNK:
            pos=self.chunk_index*64
            h,l=segment(self.high_mag,self.high_offset),segment(self.low_mag,pos)
            self.high_offset+=64
            if self.subtract_mode:
                a,b=(h,l) if self.high_larger else (l,h)
                v=a-b-self.carry_borrow;self.carry_borrow=int(v<0)
            else:
                v=h+l+self.carry_borrow;self.carry_borrow=v>>64
            word=v&((1<<64)-1)
            if word:
                self.window=(word<<64)|self.previous_chunk;self.window_base=pos-64
                self.magnitude_length=pos+word.bit_length();self.sticky=self.low_sticky
                self.is_power_two=not(word&(word-1) or self.previous_chunk or self.low_sticky)
            self.low_sticky|=self.previous_chunk!=0;self.previous_chunk=word;self.chunk_index+=1
            if self.chunk_index==self.chunk_count:
                if self.carry_borrow:self.fail(0x40)
                else:self.state=self.LEAD
        elif s==self.LEAD:
            length=self.magnitude_length if self.special_path else self.window.bit_length()
            pt=self.is_power_two if self.special_path else self.window!=0 and self.window&(self.window-1)==0
            self.norm_shift=max(0,length-(48 if self.negative and pt else 47))
            rs=self.norm_shift-self.window_base
            if not 0<=rs<=127:self.fail(0x40)
            else:self.round_shift=rs;self.state=self.ROUND
        elif s==self.ROUND:self.rounded=rne_window(self.window,self.round_shift,self.sticky);self.state=self.CHECK
        elif s==self.CHECK:
            if self.rounded>((1<<47) if self.negative else (1<<47)-1):
                if self.retried:self.fail(0x40)
                else:self.norm_shift+=1;self.round_shift+=1;self.retried=1;self.state=self.ROUND
            else:self.state=self.COMMIT
        elif s==self.COMMIT:
            e=self.target_exp+self.norm_shift
            if not -32768<=e<=32767:self.fail(0x32)
            else:self.state_mant=(-self.rounded if self.negative else self.rounded);self.state_exp=e;self.update_pending=1
            self.state=self.IDLE
        elif s==self.ZERO:self.update_pending=1;self.state=self.IDLE
        elif s!=self.IDLE:self.fail(0x40)


class Controller:
    IDLE,SETUP,RUN,WAIT,RESULT,FAIL=range(6)
    def __init__(self,max_k=12288):
        self.max_k=max_k;self.b1=B1();self.b2=B2();self.a2=A2();self.reset_control()
    def reset_control(self):
        for n in ('state active_job active_channel active_k total_blocks block_index issued pending pending_slice pending_mask pending_last '
                  'scale_pending scale_have scale_bits write_ptr read_ptr fifo_count error_pending result_pending result_mant result_exp result_job '
                  'result_channel error_code fault_lock').split():setattr(self,n,0)
        self.responses={}
    def reset(self):
        self.reset_control();self.b1.reset();self.b2.reset();self.a2.reset()
    def signals(self,**i):
        g=lambda n:i.get(n,0)
        rst=i.get('rst_n',1);active=self.state in (self.SETUP,self.RUN,self.WAIT)
        base=bool(g('abort') or self.error_pending or g('upstream_fault'))
        b1=self.b1.snapshot(rst_n=rst,abort=base);b2=self.b2.snapshot(rst_n=rst,abort=base)
        req_ready=int(rst and not g('abort') and not self.error_pending and not g('upstream_fault') and self.state==self.IDLE)
        accept=g('req_valid') and req_ready
        early=(accept and (not all(g(n) for n in ('x_loaded','w_loaded','s_loaded')) or not 1<=g('req_k')<=self.max_k)) or (active and (
            not all(g(n) for n in ('x_loaded','w_loaded','s_loaded')) or self.fifo_count>4 or
            (self.pending and self.fifo_count==4) or g('x_rd_valid')!=self.pending or g('w_rd_valid')!=self.pending or
            g('s_rd_valid')!=self.scale_pending or (self.pending and (g('x_rd_mask')!=self.pending_mask or g('w_rd_mask')!=self.pending_mask)) or
            (b1['out_valid'] and (b1['out_block']!=self.block_index or self.fifo_count!=0 or self.pending)) or
            (b2['out_valid'] and b2['out_block']!=self.block_index)))
        scale_bad=active and self.scale_pending and g('s_rd_valid') and not 0<g('s_rd_bits')<0x7f800000
        aa=bool(base or early or scale_bad or self.b1.fault or self.a2.fault or (b2['out_valid'] and b2['out_error']))
        a2=self.a2.snapshot(rst_n=rst,abort=aa,clear=accept)
        bad=early or (active and a2['update_valid'] and (self.state!=self.WAIT or a2['out_block']!=self.block_index))
        if g('upstream_fault') and g('upstream_code')==0:err=0x40
        elif g('upstream_fault') and g('upstream_code')<0x30:err=g('upstream_code')
        elif g('abort') or bad or (self.b1.fault and self.b1.error_code==0x40) or (self.a2.fault and self.a2.error_code==0x40):err=0x40
        elif g('upstream_fault'):err=g('upstream_code')
        elif scale_bad or (b2['out_valid'] and b2['out_error']):err=0x30
        elif self.b1.fault:err=self.b1.error_code
        elif self.a2.fault:err=self.a2.error_code
        else:err=0
        stop=base or err!=0
        remaining=(self.active_k-self.block_index*128)&0x1ffff
        slices=16 if remaining>=128 else (remaining+7)//8
        mask=(1<<(self.active_k%8))-1 if self.issued+1==slices and remaining<128 and self.active_k%8 else 255
        issue=int(rst and not stop and self.state in (self.SETUP,self.RUN) and self.issued<slices and self.fifo_count+self.pending<4)
        sr=int(rst and not stop and self.state==self.SETUP)
        index=(self.block_index*16+self.issued)&65535
        h=self.responses.get(self.read_ptr,(0,0,0,0,0,0,0,0))
        hx,hw,he,hxm,hwm,hs,hb,hl=h
        bi=int(rst and not stop and self.state==self.RUN and self.fifo_count!=0 and g('slice_enable'))
        pop=int(bi and b1['in_ready']);push=int(self.pending and g('x_rd_valid') and g('w_rd_valid') and not stop)
        bc=dict(rst_n=rst,abort=base,in_valid=bi,in_x=hx,in_w=hw,in_mask=hxm&hwm,in_exp=he,
                in_block=hb,in_slice=hs,in_last=hl,out_ready=int(not stop and self.scale_have and self.state==self.RUN and b2['in_ready']))
        sc=dict(rst_n=rst,abort=base,in_valid=int(b1['out_valid'] and self.scale_have and self.state==self.RUN and not stop),
                in_raw=b1['out_raw'],in_exp=b1['out_exp'],in_scale=self.scale_bits,in_block=b1['out_block'],
                out_ready=int(a2['in_ready'] and self.state==self.RUN and not stop))
        ac=dict(rst_n=rst,abort=aa,clear=accept,in_valid=int(b2['out_valid'] and b2['out_error']==0 and self.state==self.RUN and not stop),
                in_mant=b2['out_mant'],in_exp=b2['out_exp'],in_block=b2['out_block'])
        o=dict(req_ready=req_ready,x_rd_req=issue,x_rd_index=index,w_rd_req=issue,w_rd_index=index,s_rd_req=sr,s_rd_index=self.block_index,
               result_valid=int(rst and not g('abort') and self.result_pending),result_mant=self.result_mant,result_exp=self.result_exp,
               result_job=self.result_job,result_channel=self.result_channel,error_valid=int(rst and self.error_pending),error_code=self.error_code,fault_lock=self.fault_lock)
        detail=dict(accept=accept,err=err,issue=issue,sr=sr,push=push,pop=pop,mask=mask,slices=slices,b1=b1,b2=b2,a2=a2)
        return o,(bc,sc,ac),detail
    def snapshot(self,**i):return self.signals(**i)[0]
    def step(self,**i):
        if not i.get('rst_n',1):self.reset();return
        pre,cs,d=self.signals(**i);err=d['err'];old_state=self.state
        if not self.error_pending and err:
            self.error_pending,self.error_code,self.fault_lock=1,err,int(err<0x30 or err==0x40)
            self.pending=self.scale_pending=self.fifo_count=0
            self.state=self.RESULT if self.result_pending and not i.get('abort',0) else self.FAIL
            if i.get('abort',0):self.result_pending=0
        elif i.get('abort',0):
            self.result_pending=self.pending=self.scale_pending=self.fifo_count=0;self.fault_lock=1;self.state=self.FAIL
        elif self.error_pending and self.state!=self.RESULT:
            if i.get('upstream_fault',0) and (i.get('upstream_code',0)<0x30 or i.get('upstream_code',0)==0x40):self.fault_lock=1
            self.state=self.FAIL;self.pending=self.scale_pending=self.fifo_count=0
        else:
            if self.error_pending and i.get('upstream_fault',0) and (i.get('upstream_code',0)<0x30 or i.get('upstream_code',0)==0x40):self.fault_lock=1
            old_pending=self.pending;old_sp=self.scale_pending
            if d['push']:
                self.responses[self.write_ptr]=(i.get('x_rd_data',0),i.get('w_rd_data',0),i.get('x_rd_exp',0),i.get('x_rd_mask',0),
                    i.get('w_rd_mask',0),self.pending_slice,self.block_index,self.pending_last)
                self.write_ptr=(self.write_ptr+1)&3
            if d['pop']:self.read_ptr=(self.read_ptr+1)&3
            self.fifo_count+=d['push']-d['pop']
            self.pending=d['issue'];self.scale_pending=d['sr']
            if d['issue']:
                self.pending_slice=self.issued&15;self.pending_mask=d['mask'];self.pending_last=int(self.issued+1==d['slices']);self.issued+=1
            if old_sp and i.get('s_rd_valid',0):self.scale_bits=i.get('s_rd_bits',0);self.scale_have=1
            if old_state==self.IDLE and d['accept']:
                self.active_job,self.active_channel,self.active_k=(i.get(n,0) for n in ('req_job','req_channel','req_k'))
                self.total_blocks=(self.active_k+127)//128
                self.block_index=self.issued=self.scale_have=self.write_ptr=self.read_ptr=self.fifo_count=0
                self.state=self.SETUP
            elif old_state==self.SETUP:self.state=self.RUN
            elif old_state==self.RUN and d['b2']['out_valid'] and d['a2']['in_ready'] and d['b2']['out_error']==0:self.state=self.WAIT
            elif old_state==self.WAIT and d['a2']['update_valid']:
                if self.block_index+1==self.total_blocks:
                    self.result_pending=1;self.result_mant=d['a2']['state_mant'];self.result_exp=d['a2']['state_exp']
                    self.result_job=self.active_job;self.result_channel=self.active_channel;self.state=self.RESULT
                else:self.block_index+=1;self.issued=self.scale_have=0;self.state=self.SETUP
            elif old_state==self.RESULT and self.result_pending and i.get('result_ready',0):self.result_pending=0;self.state=self.FAIL if self.error_pending else self.IDLE
            elif old_state not in (self.IDLE,self.RUN,self.WAIT,self.RESULT,self.FAIL):self.error_pending,self.error_code,self.fault_lock,self.state=1,0x40,1,self.FAIL
        for model,c in zip((self.b1,self.b2,self.a2),cs):model.step(**c)
