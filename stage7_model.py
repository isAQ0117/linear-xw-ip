"""Stage7 actual FSM and complete Stage0--6 register-level composition.
There are no architecture-delay knobs. All consumers step from OLD snapshots.
"""
from stage1_contract_model import DimensionConfig,DdrRangeReceiver,ScaleGroupCache
from stage23_model import Parser,Buffer,AddrGen
from stage4_model import Controller
from stage5_model import Stage5
from stage6_model import AxisOutput,JobStatus

class Scheduler:
    (IDLE,DIMS,CFG,CHECK,START,X,SCALE_REQ,SCALE_WAIT,WEIGHT_REQ,WEIGHT_WAIT,COMPUTE_REQ,
     RESULT,GROUP,PUBLISH,OUTPUT_START,OUTPUT_WAIT,FINISH,STATUS,CLEAN,REARM,LOCK)=range(21)
    def __init__(self,static=0,n_dim=2,k_dim=129,max_n=12288,max_k=12288):
        self.d=DimensionConfig(static,n_dim,k_dim,max_n,max_k);self.reset_control()
    def reset_control(self):
        for n in ('state busy active_id active_n active_k active_m active_tile weight_base scale_base channel '
                  'group_index first_error fault_lock started x_complete').split():setattr(self,n,0)
    def reset(self):self.reset_control();self.d.reset()
    def signals(self,**i):
        g=lambda n:i.get(n,0);rst=i.get('rst_n',1)
        ready=int(rst and g('datapath_online') and self.state==self.IDLE and not(self.fault_lock or g('fault_valid')))
        local=self.state>self.LOCK or (self.state==self.GROUP and g('group_done') and g('committed_group')!=self.group_index)
        fault=g('fault_valid') or local
        code=(g('fault_code') or 0x40) if g('fault_valid') and (g('fault_system') or not local) else 0x40
        lock=local or g('fault_system') or not g('clean_boundary') or code==0x40
        en=rst and not(self.first_error or self.fault_lock or fault)
        all_ready=all(g(n) for n in ('datapath_online','stage5_ready','compute_ready','output_ready'))
        o={n:getattr(self,n) for n in ('busy active_id active_n active_k weight_base scale_base channel group_index x_complete first_error fault_lock').split()}
        o.update(job_ready=ready,cfg_begin=int(en and self.state==self.CFG),job_start=int(en and self.state==self.START and all_ready),
                 load_valid=int(en and self.state in (self.SCALE_REQ,self.WEIGHT_REQ)),load_kind=int(self.state==self.WEIGHT_REQ),
                 load_index=self.channel if self.state==self.WEIGHT_REQ else self.group_index,
                 compute_valid=int(en and self.state==self.COMPUTE_REQ),output_start=int(en and self.state==self.OUTPUT_START),
                 finish_valid=int(rst and self.state==self.FINISH and (self.first_error!=0 or not fault)),
                 finish_ok=int(self.first_error==0),finish_code=self.first_error,
                 cancel_datapath=int(self.busy and self.started and self.first_error!=0),clear_datapath=int(self.state==self.CLEAN))
        return o,dict(fault=fault,code=code,lock=lock,all_ready=all_ready,accept=g('job_valid') and ready)
    def snapshot(self,**i):return self.signals(**i)[0]
    def step(self,**i):
        if not i.get('rst_n',1):self.reset();return
        o,d=self.signals(**i);g=lambda n:i.get(n,0);s=self.state;old_busy=self.busy;old_error=self.first_error
        dc=dict(rst_n=1,job_accept=d['accept'],job_n=g('job_n'),job_k=g('job_k'))
        if d['fault'] and d['lock']:self.fault_lock=1
        if d['fault'] and not old_busy:self.state=self.LOCK;self.fault_lock=1
        elif d['fault'] and not old_error and s!=self.STATUS:self.first_error=d['code'];self.state=self.FINISH
        elif s==self.IDLE and d['accept']:
            self.busy=1;self.active_id=g('job_id');self.active_m=g('job_m');self.active_tile=g('job_m_tile')
            self.weight_base=g('job_weight_base');self.scale_base=g('job_scale_base')
            self.channel=self.group_index=self.first_error=self.x_complete=self.started=0;self.state=self.DIMS
        elif s==self.DIMS and self.d.cfg_valid:
            self.active_n,self.active_k=self.d.active_n,self.d.active_k
            if self.d.cfg_error:self.first_error=1;self.state=self.FINISH
            elif self.active_m!=1 or self.active_tile!=1:self.first_error=2;self.state=self.FINISH
            else:self.state=self.CFG
        elif s==self.CFG:self.state=self.CHECK
        elif s==self.CHECK and g('cfg_done'):
            if g('cfg_error'):self.first_error=g('cfg_error_code');self.state=self.FINISH
            else:self.state=self.START
        elif s==self.START and o['job_start']:self.started=1;self.state=self.X
        elif s==self.X and g('x_loaded') and g('input_done'):self.x_complete=1;self.state=self.SCALE_REQ
        elif s==self.SCALE_REQ and o['load_valid'] and g('load_ready'):self.state=self.SCALE_WAIT
        elif s==self.SCALE_WAIT and g('load_done'):self.state=self.WEIGHT_REQ
        elif s==self.WEIGHT_REQ and o['load_valid'] and g('load_ready'):self.state=self.WEIGHT_WAIT
        elif s==self.WEIGHT_WAIT and g('load_done'):self.state=self.COMPUTE_REQ
        elif s==self.COMPUTE_REQ and o['compute_valid'] and g('compute_ready'):self.state=self.RESULT
        elif s==self.RESULT and g('result_valid') and g('result_ready'):
            if self.channel%128==127 or self.channel+1==self.active_n:self.state=self.GROUP
            else:self.channel+=1;self.state=self.WEIGHT_REQ
        elif s==self.GROUP and g('group_done'):
            if self.channel+1==self.active_n:self.state=self.PUBLISH
            else:self.channel+=1;self.group_index+=1;self.state=self.SCALE_REQ
        elif s==self.PUBLISH and g('job_results_ready'):self.state=self.OUTPUT_START
        elif s==self.OUTPUT_START and o['output_start'] and g('output_ready'):self.state=self.OUTPUT_WAIT
        elif s==self.OUTPUT_WAIT and g('output_done'):self.state=self.FINISH
        elif s==self.FINISH and o['finish_valid'] and g('finish_ready'):self.state=self.STATUS
        elif s==self.STATUS and g('status_accept'):self.busy=0;self.state=self.LOCK if self.fault_lock else self.CLEAN
        elif s==self.CLEAN:self.started=self.x_complete=0;self.state=self.REARM
        elif s==self.REARM and d['all_ready']:self.first_error=0;self.state=self.IDLE
        self.d.step(**dc)

class LinearIP:
    def __init__(self,burst=3,static=0,n_dim=2,k_dim=129,max_n=12288,max_k=12288):
        self.sch=Scheduler(static,n_dim,k_dim,max_n,max_k)
        self.p=Parser(max_k);self.x=Buffer('x',max_k);self.w=Buffer('w',max_k)
        self.a=AddrGen(burst,max_n,max_k);self.r=DdrRangeReceiver();self.s=ScaleGroupCache(max_k)
        self.c=Controller(max_k);self.q=Stage5(max_n);self.out=AxisOutput(max_n);self.st=JobStatus()
        self.system_release=self.data_release=0;self.edge_events=[];self.cycle=0;self.prev_valid=(0,0)
    def reset(self):
        self.system_release=self.data_release=0
        for m in (self.sch,self.r,self.st,self.p,self.x,self.w,self.a,self.s,self.c,self.q,self.out):m.reset()
        self.edge_events=[];self.prev_valid=(0,0)
    def raw(self,i):
        codes=[self.p.error_code if self.p.fault else 0,self.x.error_code if self.x.fault else 0,
               self.w.error_code if self.w.fault else 0,self.s.cache_error_code if self.s.cache_error else 0,
               self.a.error_code if self.a.fault else 0,self.c.error_code if self.c.error_pending else 0,
               self.q.error_code if self.q.error_pending else 0,0x40 if self.out.fault else 0]
        # Test-only diagnostic injection; RTL bench forces the selected internal source.
        injected=i.get('inject_code',0) if i.get('inject_valid',0) else 0
        rx=self.r.range_error_code if self.r.range_error else 0
        src=i.get('inject_source',0)
        if injected:
            if src==0:codes[5]=injected
            elif src==1:codes[6]=injected
            elif src==2:rx=injected
            elif src==3:codes[2]=injected
            elif src==4:codes[4]=injected
        selected=[rx] if self.sch.first_error else [rx]+codes
        return min((v for v in selected if v),key=lambda v:(0 if v<0x30 or v==0x40 else 1,v),default=0)
    def signals(self,**i):
        g=lambda n:i.get(n,0);sr=(self.system_release>>1)&1;dr=(self.data_release>>1)&1
        raw=self.raw(i);cancel=int(self.sch.busy and self.sch.started and self.sch.first_error!=0);stop=bool(raw or cancel)
        common=dict(rst_n=dr,abort=cancel)
        xo=self.x.snapshot(**common);wo=self.w.snapshot(**common);so=self.s.snapshot()
        rx_fault=self.r.range_error;rx_code=self.r.range_error_code
        if g('inject_valid') and g('inject_source')==2:rx_fault=1;rx_code=g('inject_code')
        wf=self.w.fault;wc=self.w.error_code
        if g('inject_valid') and g('inject_source')==3:wf=1;wc=g('inject_code')
        ac=dict(common,cfg_n=self.sch.active_n,cfg_k=self.sch.active_k,cfg_weight_base=self.sch.weight_base,cfg_scale_base=self.sch.scale_base,
                range_done=self.r.range_done,range_error=rx_fault,range_error_code=rx_code,
                buffer_loaded=wo['loaded'] if self.a.kind else self.s.loaded,buffer_error=wf or self.s.cache_error,
                buffer_error_code=wc if wf else self.s.cache_error_code)
        ao=self.a.snapshot(**ac)
        clean=int(self.sch.x_complete and not(self.r.busy or self.r.word_valid or ao['cmd_valid']))
        oi=dict(rst_n=dr,halt=int(stop),job_id=self.sch.active_id,job_n=self.sch.active_n,m_axis_tready=g('m_axis_tready'))
        oo=self.out.snapshot(**oi)
        qi=dict(rst_n=dr,abort=0,job_id=self.sch.active_id,job_n=self.sch.active_n,retire=0,clean_boundary=clean,
                upstream_fault=cancel,upstream_code=self.sch.first_error,upstream_lock=self.sch.fault_lock,
                rd_req=oo['rd_req'],rd_word_index=oo['rd_word_index'])
        qo=self.q.snapshot(**qi)
        ci=dict(common,req_job=self.sch.active_id,req_channel=self.sch.channel,req_k=self.sch.active_k,
                x_loaded=xo['loaded'],w_loaded=wo['loaded'],s_loaded=self.s.loaded,upstream_fault=0,upstream_code=0,slice_enable=1,
                result_ready=int(qo['result_ready'] and not stop),x_rd_valid=xo['rd_valid'],x_rd_data=xo['rd_data'],x_rd_exp=xo['rd_exp'],x_rd_mask=xo['rd_mask'],
                w_rd_valid=wo['rd_valid'],w_rd_data=wo['rd_data'],w_rd_mask=wo['rd_mask'],s_rd_valid=self.s.rd_valid,s_rd_bits=self.s.rd_scale_bits)
        co=self.c.snapshot(**ci)
        sto=self.st.snapshot(rst_n=sr)
        schi=dict(rst_n=sr,**{n:g(n) for n in 'job_valid job_id job_m job_n job_k job_m_tile job_weight_base job_scale_base'.split()},
                  cfg_done=ao['cfg_done'],cfg_error=ao['cfg_error'],cfg_error_code=ao['cfg_error_code'],datapath_online=dr,
                  stage5_ready=qo['job_ready'],x_loaded=xo['loaded'],input_done=self.p.done,load_ready=ao['load_ready'],load_done=ao['load_done'],
                  compute_ready=co['req_ready'],result_valid=int(co['result_valid'] and not stop),result_ready=int(qo['result_ready'] and not stop),
                  group_done=qo['group_done'],committed_group=qo['group_id'],job_results_ready=qo['job_results_ready'],output_ready=oo['start_ready'],output_done=oo['output_done'],
                  finish_ready=sto['finish_ready'],status_accept=self.st.status_valid and g('status_ready'),fault_valid=int(bool(raw)),fault_code=raw,
                  fault_system=int(raw<0x30 or raw==0x40),clean_boundary=clean)
        scho=self.sch.snapshot(**schi)
        ac.update(cfg_begin=scho['cfg_begin'],load_valid=scho['load_valid'],load_kind=scho['load_kind'],load_index=scho['load_index'])
        ao=self.a.snapshot(**ac)
        rc=dict(rst_n=sr,cmd_valid=int(ao['cmd_valid'] and not stop),start=ao['cmd_addr_start'],end=ao['cmd_addr_end'],beats=ao['cmd_beats'],kind=ao['cmd_kind'],
                ddr_rd_rdy=g('ddr_rd_rdy'),ddr_rd_vld=g('ddr_rd_vld'),ddr_rd_data=g('ddr_rd_data'))
        ro=self.r.outputs(**{n:v for n,v in rc.items() if n not in ('kind','ddr_rd_vld','ddr_rd_data')})
        ac['cmd_ready']=int(ro['cmd_ready'])
        ci['req_valid']=scho['compute_valid'];co=self.c.snapshot(**ci)
        qi.update(job_start=scho['job_start'],result_valid=int(co['result_valid'] and not stop),
                  **{n:co[n] for n in ('result_mant','result_exp','result_job','result_channel')})
        qo=self.q.snapshot(**qi)
        oi.update(start=scho['output_start'],rd_ready=qo['rd_ready'],rd_valid=qo['rd_valid'],rd_data=qo['rd_data'],
                  rd_exp=qo['rd_exp']&255,rd_mask=qo['rd_mask'],rd_index=qo['rd_index'])
        oo=self.out.snapshot(**oi)
        xc=dict(common,load_begin=scho['job_start'],load_k=self.sch.active_k,wr_valid=int(self.p.wr_valid and not stop),
                wr_data=self.p.wr_data,wr_mask=self.p.wr_mask,wr_exp=self.p.wr_exp,wr_word_index=self.p.wr_word_index,wr_last=self.p.wr_last,
                rd_req=co['x_rd_req'],rd_word_index=co['x_rd_index'])
        xo=self.x.snapshot(**xc)
        pc=dict(common,job_begin=scho['job_start'],job_id=self.sch.active_id,job_k=self.sch.active_k,
                s_axis_tvalid=int(g('s_axis_tvalid') and not stop),**{n:g(n) for n in 's_axis_tdata s_axis_tkeep s_axis_tlast s_axis_tuser'.split()},wr_ready=xo['wr_ready'])
        po=self.p.snapshot(**pc)
        index=(self.a.offset+self.r.word_index)&65535
        wci=dict(common,load_begin=ao['weight_load_begin'],load_k=ao['load_k'],wr_valid=int(self.r.word_valid and self.r.word_kind and not stop),
                 wr_data=self.r.word_data,wr_word_index=index,rd_req=co['w_rd_req'],rd_word_index=co['w_rd_index'])
        sci=dict(rst_n=dr,load_begin=ao['scale_load_begin'],load_words=ao['load_words'],load_scales=ao['load_scales'],
                 wr_valid=int(self.r.word_valid and not self.r.word_kind and not stop),wr_data=self.r.word_data,wr_word_index=index,rd_req=co['s_rd_req'],rd_scale_index=co['s_rd_index'])
        sti=dict(rst_n=sr,finish_valid=scho['finish_valid'],finish_job_id=self.sch.active_id,finish_ok=scho['finish_ok'],finish_error_code=scho['finish_code'],status_ready=g('status_ready'))
        o={n:ro[n] for n in ('ddr_rd_req','ddr_rd_addra','ddr_rd_addrb')}
        o.update(job_ready=scho['job_ready'],busy=scho['busy'],s_axis_tready=int(po['s_axis_tready'] and not stop and dr),
                 **{n:sto[n] for n in ('status_valid','status_job_id','status_ok','status_error_code')})
        o.update({n:oo[n] for n in ('m_axis_tvalid','m_axis_tdata','m_axis_tkeep','m_axis_tlast','m_axis_tuser')})
        # Internal state comparison belongs only to the testbench, never the ABI.
        o['debug_control']=(self.system_release<<42)|(self.data_release<<40)|(self.sch.state<<35)|(self.sch.first_error<<27)|(self.sch.fault_lock<<26)|(self.sch.channel<<10)|self.sch.group_index
        o['debug_pipeline']=(self.a.state<<45)|(int(self.r.busy)<<44)|(self.c.state<<41)|(self.c.block_index<<25)|(self.q.state<<21)|(self.out.count<<18)|(self.out.pending<<17)|self.out.issued
        return o,dict(schi=schi,pc=pc,xc=xc,wci=wci,ac=ac,rc=rc,sci=sci,ci=ci,qi=qi,oi=oi,sti=sti),dict(sch=scho,co=co,qo=qo,ao=ao,raw=raw,clean=clean)
    def snapshot(self,**i):return self.signals(**i)[0]
    def step(self,**i):
        if not i.get('rst_n',1):self.reset();return
        pre,cs,d=self.signals(**i);old_sr=(self.system_release>>1)&1
        olddr=(self.data_release>>1)&1;clear=d['sch']['clear_datapath']
        previous=(*self.prev_valid,self.sch.first_error,self.sch.fault_lock)
        ev=[];cy=self.cycle;owner=self.sch.active_id;ch=self.sch.channel;grp=self.sch.group_index
        def add(event,**kw):ev.append(dict(cycle=cy,event=event,job_id=owner,row=0,**kw))
        if old_sr:
            if i.get('job_valid',0) and pre['job_ready']:add('JOB_ACCEPT',job_id_override=i.get('job_id',0))
            if i.get('s_axis_tvalid',0) and pre['s_axis_tready']:
                add('AXIS_IN_ACCEPT',group=(i.get('s_axis_tuser',0)>>48)&511,index=(i.get('s_axis_tuser',0)>>80)&255)
            if pre['ddr_rd_req']:add('DDR_REQ_ACCEPT',group=grp,channel=ch,kind=self.a.kind,start=pre['ddr_rd_addra'],end=pre['ddr_rd_addrb'],beats=d['ao']['cmd_beats'])
            if i.get('ddr_rd_vld',0):add('DDR_BEAT',group=grp,channel=ch,index=0 if pre['ddr_rd_req'] else self.r.received_count,data_hex=f"{i.get('ddr_rd_data',0):0128x}")
            if d['sch']['load_valid'] and cs['schi']['load_ready']:add('LOAD_ACCEPT',kind=d['sch']['load_kind'],index=d['sch']['load_index'])
            if d['sch']['compute_valid'] and cs['schi']['compute_ready']:add('COMPUTE_ACCEPT',channel=ch)
            if cs['schi']['result_valid'] and cs['schi']['result_ready']:add('RESULT_ACCEPT',channel=ch,mant=d['co']['result_mant'],exp=d['co']['result_exp'])
            if d['sch']['output_start'] and cs['schi']['output_ready']:add('OUTPUT_START')
            if pre['m_axis_tvalid'] and i.get('m_axis_tready',0):add('AXIS_OUT_ACCEPT',group=(pre['m_axis_tuser']>>48)&511,index=(pre['m_axis_tuser']>>80)&255,data_hex=f"{pre['m_axis_tdata']:0128x}",keep_hex=f"{pre['m_axis_tkeep']:016x}",last=pre['m_axis_tlast'],user_hex=f"{pre['m_axis_tuser']:032x}")
            if pre['status_valid'] and i.get('status_ready',0):add('STATUS_ACCEPT',status_id=pre['status_job_id'],ok=pre['status_ok'],code=pre['status_error_code'])
        for name,key in [('sch','schi'),('p','pc'),('x','xc'),('w','wci'),('a','ac'),('r','rc'),('s','sci'),('c','ci'),('q','qi'),('out','oi'),('st','sti')]:getattr(self,name).step(**cs[key])
        self.system_release=((self.system_release<<1)|1)&3
        self.data_release=0 if not old_sr or clear else ((self.data_release<<1)|1)&3
        if not (self.data_release>>1)&1:
            for m in (self.p,self.x,self.w,self.a,self.s,self.c,self.q,self.out):m.reset()
        post_o,post_cs,post_d=self.signals(**i)
        cd=self.c.signals(**post_cs['ci'])[2]
        if old_sr:
            if self.r.range_done:add('RANGE_DONE',group=grp,channel=ch,index=self.r.word_index)
            if cd['b1']['out_valid'] and not previous[0]:add('B1_VALID',channel=self.c.active_channel,block=self.c.b1.out_block,raw=self.c.b1.out_raw)
            if cd['b2']['out_valid'] and not previous[1]:add('B2_VALID',channel=self.c.active_channel,block=self.c.b2.out_block,term_hex=f'{self.c.b2.out_mant% (1<<72):018x}',exp=self.c.b2.out_exp)
            if cd['a2']['update_valid']:add('A2_UPDATE',channel=self.c.active_channel,block=self.c.a2.out_block,mant=self.c.a2.state_mant,exp=self.c.a2.state_exp)
            if post_d['qo']['group_done']:add('GROUP_REQUANT',group=self.q.group_id,length=self.q.group_len,exp=self.q.group_exp)
            if (self.sch.first_error and not previous[2]) or self.sch.fault_lock!=previous[3]:add('FAULT',code=self.sch.first_error or self.raw(i),lock=self.sch.fault_lock,owned=int(self.sch.busy))
        for e in ev:
            if 'job_id_override' in e:e['job_id']=e.pop('job_id_override')
        self.prev_valid=(cd['b1']['out_valid'],cd['b2']['out_valid'])
        self.edge_events=ev
