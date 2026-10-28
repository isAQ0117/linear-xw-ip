
"""Cycle-stepped, deterministic B3-B Linear architecture model (NOT RTL simulation).

I/O: JSON case with BFP18 mantissas+exponents, quantized FP8 bits, FP32 scale bits.
The exact same JSON may later be generated from safetensors by a separate loader.
Cycle semantics: one clock tick per step; single outstanding DDR request; return
valid can have bubbles; no DDR response ready; AXIS stalls hold payload.
Latency of B1/B2/A2 can be chosen, not inferred from unfinished RTL.
"""
import argparse,csv,json,math
from pathlib import Path
from fractions import Fraction
from linear_stream_model.numeric import (check_signed,fp8_e4m3fn_q9,
    fp32_positive_scale,accumulate_48,requant_bfp18,fp8_exact,
    fp32_exact_scale,hardware_value,pow2,NumericFault)

def ceildiv(a,b): return (a+b-1)//b
def bits_integer(x):
    return int(x,0) if isinstance(x,str) and x.startswith(("0x","0X","0b","0B")) else int(x)

def pack_user(job,row,group,exp,group_len,offset,eot):
    return (job | (row<<32) | (group<<48) | ((exp&255)<<64) |
            (group_len<<72) | (offset<<80) | (int(eot)<<88) | (0xB2<<96))
def unpack_user(u):
    if u>>104 or ((u>>96)&255)!=0xB2 or ((u>>57)&127) or ((u>>89)&127):
        raise ValueError("bad TUSER V2 format/reserved bits")
    ex=(u>>64)&255
    return dict(job_id=u&0xffffffff,row=(u>>32)&65535,
       group=(u>>48)&511,exp=ex-256 if ex>=128 else ex,
       group_len=(u>>72)&255,offset=(u>>80)&255,eot=(u>>88)&1)

def emit_axis(mants,exps,job_id,width=512):
    if width not in (128,256,512,1024): raise ValueError("unsupported AXIS_DATA_W")
    if not 0<=job_id<(1<<32): raise ValueError("job id width")
    M=len(mants); K=len(mants[0]); lanes=width//18
    result=[]
    for m in range(M):
        if len(mants[m])!=K or len(exps[m])!=ceildiv(K,128): raise ValueError("activation shape")
        for g in range(ceildiv(K,128)):
            group=mants[m][128*g:min(K,128*g+128)]
            e=check_signed(exps[m][g],8,"AXIS_EXP")
            for off in range(0,len(group),lanes):
                vals=group[off:off+lanes]
                data=sum((check_signed(v,18,"AXIS_MANT")&((1<<18)-1))<<(i*18) for i,v in enumerate(vals))
                vb=ceildiv(18*len(vals),8)
                end=(off+len(vals)==len(group))
                eot=end and m==M-1 and g==ceildiv(K,128)-1
                result.append(dict(tdata=data,tkeep=(1<<vb)-1,tlast=int(end),
                    tuser=pack_user(job_id,m,g,e,len(group),off,eot)))
    return result

def parse_axis(accepted,M,K,job_id,width):
    lanes=width//18; a=[[] for _ in range(M)]; ex=[[] for _ in range(M)]
    exp_order=[(m,g) for m in range(M) for g in range(ceildiv(K,128))]
    cursor=0; offset=0
    for beat in accepted:
        if cursor>=len(exp_order): raise ValueError("extra AXIS input")
        m,g=exp_order[cursor]
        u=unpack_user(beat["tuser"])
        length=min(128,K-g*128)
        if (u["job_id"],u["row"],u["group"],u["group_len"],u["offset"])!=(job_id,m,g,length,offset):
            raise ValueError("AXIS user identity, order or offset mismatch")
        count=min(lanes,length-offset)
        valid_bytes=ceildiv(count*18,8)
        if beat["tkeep"]!=(1<<valid_bytes)-1 or beat["tdata"]>>(18*count):
            raise ValueError("AXIS TKEEP/padding invalid")
        if beat["tlast"]!=int(offset+count==length):
            raise ValueError("AXIS TLAST invalid")
        final=int(m==M-1 and g==ceildiv(K,128)-1 and offset+count==length)
        if u["eot"]!=final: raise ValueError("AXIS EOT invalid")
        if offset==0: ex[m].append(u["exp"])
        elif ex[m][g]!=u["exp"]: raise ValueError("inconsistent exponent")
        for i in range(count):
            raw=(beat["tdata"]>>(18*i))&((1<<18)-1)
            a[m].append(raw-(1<<18) if raw&(1<<17) else raw)
        offset+=count
        if offset==length: cursor+=1;offset=0
    if cursor!=len(exp_order): raise ValueError("truncated AXIS")
    return a,ex

def prepare(case):
    job=case["job"]; M=int(job["m"]);N=int(job["n"]);K=int(job["k"])
    if not (1<=M<=65535 and 1<=N<=65535 and 1<=K<=65535):
        raise ValueError("illegal dimension")
    if ceildiv(max(N,K),128)>512: raise ValueError("TUSER group_id exceeds 9 bits")
    mode=int(job.get("static_dim_mode",1))
    if mode not in (0,1): raise ValueError("static_dim_mode must be 0 or 1")
    if mode and (N!=int(job.get("n_dim",N)) or K!=int(job.get("k_dim",K))):
        raise ValueError("STATIC N_DIM/K_DIM disagree with case")
    if not mode and (N>int(job.get("max_n",N)) or K>int(job.get("max_k",K))):
        raise ValueError("dynamic max dimensions exceeded")
    A=case["activation"]["mantissa"]; E=case["activation"]["exponents"]
    W=case["weight"]["fp8_bits"]; S=case["weight"]["scale_fp32_bits"]
    J=ceildiv(K,128); B=ceildiv(N,128)
    if len(A)!=M or any(len(a)!=K for a in A) or len(E)!=M or any(len(e)!=J for e in E):
        raise ValueError("activation shape")
    if len(W)!=N or any(len(w)!=K for w in W) or len(S)!=B or any(len(s)!=J for s in S):
        raise ValueError("weight/scale shape")
    if any(not 0<=int(v)<256 for row in W for v in row):
        raise ValueError("invalid FP8 bit")
    for row in W:
        for v in row: fp8_e4m3fn_q9(v)
    for row in S:
        for v in row: fp32_positive_scale(bits_integer(v))
    wbase=int(job.get("weight_base_addr",0))
    wr=ceildiv(K,64);stride=wr*8
    sbase=int(job.get("scale_base_addr",wbase+stride*N))
    scale_group_words=ceildiv(J,16)
    scale_stride=scale_group_words*8
    for b in (wbase,sbase):
        if b<0 or b%8 or b>=(1<<29): raise ValueError("base must be 29-bit multiple of 8")
    wend=wbase+stride*N;send=sbase+scale_stride*B
    if max(wend,send)>(1<<29) or not (wend<=sbase or send<=wbase):
        raise ValueError("DDR ranges overflow/overlap")
    image_bytes=max(wend,send)//8*64
    if image_bytes > 512*1024*1024:
        raise ValueError("in-memory DDR mirror exceeds 512 MiB; use chunked loader later")
    image=bytearray(image_bytes)
    for n in range(N):
        pos=(wbase+n*stride)//8*64
        image[pos:pos+K]=bytes(W[n])
    for b in range(B):
        pos=(sbase+b*scale_stride)//8*64
        for j in range(J): image[pos+j*4:pos+j*4+4]=bits_integer(S[b][j]).to_bytes(4,'little')
    manifest=dict(format="DDR_RANGE_512_ADDR_STEP8_V1",
        weight_layout="FP8_OUTPUT_MAJOR_K_CONTIGUOUS_PAD64_V1",
        scale_layout="FP32_LE_NBLOCK128_GROUP_PAD64_V3",
        weight_base=wbase,scale_base=sbase,weight_words_per_row=wr,
        scale_words_per_group=scale_group_words,scale_format="FP32_RAW32",
        scale_bytes_per_value=4,n=N,k=K)
    return bytes(image),manifest

class Simulator:
    """Registered-state cycle model. Logs one record per tick."""
    def __init__(self,case,ddr_image,manifest,*,ddr_latency=2,ddr_gap=0,ddr_ready_period=0,
                 input_gap=0,output_stall_period=0,b1_latency=1,b2_latency=1,a2_latency=1,
                 max_cycles=3000000, trace_detail=True):
        self.case=case;self.j=case["job"];self.M=int(self.j["m"]);self.N=int(self.j["n"]);self.K=int(self.j["k"])
        self.J=ceildiv(self.K,128);self.B=ceildiv(self.N,128)
        self.job_id=int(self.j.get("job_id",42));self.axis_width=int(self.j.get("axis_width_bits",512))
        self.a_input=emit_axis(case["activation"]["mantissa"],case["activation"]["exponents"],self.job_id,self.axis_width)
        self.ddr=ddr_image;self.man=manifest;self.ddr_latency=ddr_latency;self.ddr_gap=ddr_gap
        self.ddr_ready_period=ddr_ready_period
        self.input_gap=input_gap;self.output_stall_period=output_stall_period
        self.latencies=[b1_latency,b2_latency,a2_latency]
        if min(*self.latencies,ddr_latency,ddr_gap,ddr_ready_period,input_gap,output_stall_period)<0: raise ValueError("negative delay")
        self.max_cycles=max_cycles;self.trace_detail=trace_detail
        self.cycle=0;self.state="JOB_ACCEPT";self.trace=[];self.event_counts={}
        self.in_idx=0;self.in_accepted=[];self.act=None;self.exp=None
        self.out=[];self.out_idx=0
        self.ddr_tx=None;self.pending=None;self.ddr_words=[];self.scale=[]
        self.b=0;self.n=0;self.row=0;self.kblock=0;self.compute_stage=0;self.stage_remaining=0
        self.raw=0;self.term=0;self.term_exp=0;self.acc=(0,0)
        self.states=[[(0,0) for _ in range(self.N)] for _ in range(self.M)]
        self.exact=[[Fraction(0) for _ in range(self.N)] for _ in range(self.M)]
        self.mants=[[0]*self.N for _ in range(self.M)]
        self.expout=[[0]*self.B for _ in range(self.M)]
        self.ddr_requests=0;self.ddr_beats=0
    def log(self,event,**kw):
        self.event_counts[event]=self.event_counts.get(event,0)+1
        if self.trace_detail or event not in ("DDR_BEAT","AXIS_IN_BEAT","AXIS_OUT_BEAT","B1","B2","A2"):
            self.trace.append(dict(cycle=self.cycle,state=self.state,event=event,**kw))
    def start_read(self,base,words,kind):
        if self.ddr_tx is not None: raise AssertionError("multiple outstanding DDR")
        end=base+8*(words-1)
        if base%8 or words<1 or (end//8+1)*64>len(self.ddr): raise ValueError("bad DDR request")
        self.ddr_tx=dict(base=base,words=words,kind=kind,next=0,
                         next_cycle=self.cycle+self.ddr_latency)
        self.ddr_words=[];self.ddr_requests+=1
        self.log("DDR_REQUEST",kind=kind,ddr_rd_req=1,ddr_rd_rdy=1,
                 ddr_rd_addra=base,ddr_rd_addrb=end,expected_beats=words)
        # Old FFN permits the very first return word on the ACCEPT cycle.
        if self.ddr_latency == 0:
            self.tick_ddr()
    def ddr_request_ready(self):
        return not (self.ddr_ready_period and
                    self.cycle % self.ddr_ready_period == 0)
    def tick_ddr(self):
        t=self.ddr_tx
        if t is None or self.cycle<t["next_cycle"]: return
        i=t["next"]; address=t["base"]+8*i
        word=self.ddr[(address//8)*64:(address//8+1)*64]
        self.ddr_words.append(word);self.ddr_beats+=1
        self.log("DDR_BEAT",kind=t["kind"],ddr_rd_vld=1,beat_index=i,beat_addr=address,
                 ddr_rd_data="0x"+word[::-1].hex())
        t["next"]+=1;t["next_cycle"]=self.cycle+1+self.ddr_gap
        if t["next"]==t["words"]:
            kind=t["kind"];payload=b''.join(self.ddr_words)
            self.ddr_tx=None;self.pending=(kind,payload)
            self.log("DDR_RANGE_COMPLETE",kind=kind,total_beats=t["words"])
    def tick(self):
        if self.cycle>=self.max_cycles: raise TimeoutError("max_cycles exceeded")
        self.tick_ddr()
        s=self.state
        if s=="JOB_ACCEPT":
            self.log("JOB_ACCEPT",job_id=self.job_id,m=self.M,n=self.N,k=self.K)
            self.state="LOAD_X"
        elif s=="LOAD_X":
            if self.in_idx<len(self.a_input) and self.cycle%(self.input_gap+1)==0:
                item=self.a_input[self.in_idx]
                self.in_accepted.append(item);self.in_idx+=1
                self.log("AXIS_IN_BEAT",index=self.in_idx-1,tlast=item["tlast"])
            if self.in_idx==len(self.a_input):
                self.act,self.exp=parse_axis(self.in_accepted,self.M,self.K,self.job_id,self.axis_width)
                self.log("AXIS_INPUT_COMPLETE",beats=self.in_idx)
                self.state="SCALE_REQUEST"
        elif s=="SCALE_REQUEST":
            if self.ddr_request_ready():
                base=self.man["scale_base"]+8*self.man["scale_words_per_group"]*self.b
                self.start_read(base,self.man["scale_words_per_group"],"SCALE")
                self.state="SCALE_WAIT"
            else:
                self.log("DDR_READY_STALL",kind="SCALE",ddr_rd_req=0,ddr_rd_rdy=0)
        elif s=="SCALE_WAIT":
            if self.pending is not None:
                kind,data=self.pending;self.pending=None
                if kind!="SCALE": raise AssertionError(kind)
                self.scale=[int.from_bytes(data[4*j:4*j+4],"little") for j in range(self.J)]
                if any(data[4*self.J:]): raise ValueError("scale group padding != 0")
                self.n=self.b*128
                self.log("SCALE_CACHE_READY",group=self.b,scale_count=self.J)
                self.state="WEIGHT_REQUEST"
        elif s=="WEIGHT_REQUEST":
            if self.ddr_request_ready():
                addr=self.man["weight_base"]+8*self.man["weight_words_per_row"]*self.n
                self.start_read(addr,self.man["weight_words_per_row"],"WEIGHT")
                self.state="WEIGHT_WAIT"
            else:
                self.log("DDR_READY_STALL",kind="WEIGHT",ddr_rd_req=0,ddr_rd_rdy=0)
        elif s=="WEIGHT_WAIT":
            if self.pending is not None:
                kind,data=self.pending;self.pending=None
                if kind!="WEIGHT": raise AssertionError(kind)
                if any(data[self.K:]): raise ValueError("weight row padding != 0")
                self.weight=data[:self.K];self.row=0;self.kblock=0;self.acc=(0,0)
                self.log("WEIGHT_ROW_READY",channel=self.n,bytes=self.K)
                self.state="COMPUTE_SETUP"
        elif s=="COMPUTE_SETUP":
            self.compute_stage=0;self.stage_remaining=self.latencies[0]
            self.state="COMPUTE"
        elif s=="COMPUTE":
            if self.stage_remaining>0: self.stage_remaining-=1
            else:
                lo=self.kblock*128;hi=min(lo+128,self.K)
                if self.compute_stage==0:
                    self.raw=check_signed(sum(self.act[self.row][k]*fp8_e4m3fn_q9(self.weight[k])
                                               for k in range(lo,hi)),48,"B1_RAW")
                    self.log("B1",row=self.row,n=self.n,k_block=self.kblock,raw=self.raw)
                elif self.compute_stage==1:
                    sig,se=fp32_positive_scale(self.scale[self.kblock])
                    self.term=check_signed(self.raw*sig,72,"B2_TERM_FP32")
                    self.term_exp=check_signed(self.exp[self.row][self.kblock]-9+se,12,"B2_TERM_EXP")
                    self.log("B2",row=self.row,n=self.n,k_block=self.kblock,
                             term_mant=self.term,term_exp=self.term_exp)
                else:
                    self.acc=accumulate_48(self.acc,(self.term,self.term_exp),term_bits=72)
                    reference_inner=sum(self.act[self.row][k]*fp8_exact(self.weight[k]) for k in range(lo,hi))
                    self.exact[self.row][self.n]+=reference_inner*pow2(self.exp[self.row][self.kblock])*fp32_exact_scale(self.scale[self.kblock])
                    self.log("A2",row=self.row,n=self.n,k_block=self.kblock,
                             acc_mant=self.acc[0],acc_exp=self.acc[1])
                self.compute_stage+=1
                if self.compute_stage<3: self.stage_remaining=self.latencies[self.compute_stage]
                else:
                    self.kblock+=1
                    if self.kblock<self.J: self.state="COMPUTE_SETUP"
                    else:
                        self.states[self.row][self.n]=self.acc
                        self.row+=1
                        if self.row<self.M:
                            self.acc=(0,0);self.kblock=0;self.state="COMPUTE_SETUP"
                        else: self.state="NEXT_CHANNEL"
        elif s=="NEXT_CHANNEL":
            self.n+=1
            if self.n<min((self.b+1)*128,self.N): self.state="WEIGHT_REQUEST"
            else:
                for row in range(self.M):
                    a=self.states[row][self.b*128:min(self.N,(self.b+1)*128)]
                    q,e=requant_bfp18(a)
                    self.mants[row][self.b*128:self.b*128+len(q)]=q
                    self.expout[row][self.b]=e
                self.log("OUTPUT_GROUP_REQUANT",group=self.b)
                self.b+=1
                if self.b<self.B: self.state="SCALE_REQUEST"
                else:
                    self.out=emit_axis(self.mants,self.expout,self.job_id,self.axis_width)
                    self.state="OUTPUT"
        elif s=="OUTPUT":
            ready=not (self.output_stall_period and self.cycle%self.output_stall_period==0)
            if self.out_idx<len(self.out) and ready:
                beat=self.out[self.out_idx];self.log("AXIS_OUT_BEAT",index=self.out_idx,
                         tlast=beat["tlast"],eot=unpack_user(beat["tuser"])["eot"])
                self.out_idx+=1
            if self.out_idx==len(self.out):
                self.log("STATUS_SUCCESS",job_id=self.job_id)
                self.state="DONE"
        elif s=="DONE": return False
        else: raise AssertionError(s)
        self.cycle+=1
        return True
    def run(self):
        while self.state!="DONE": self.tick()
        return self


def independent_golden(case):
    """Independent loop order, numerical reference (no DDR, scheduler, AXIS)."""
    job=case["job"];M=int(job["m"]);N=int(job["n"]);K=int(job["k"])
    A=case["activation"]["mantissa"];E=case["activation"]["exponents"]
    W=case["weight"]["fp8_bits"];S=case["weight"]["scale_fp32_bits"]
    states=[[(0,0) for n in range(N)] for m in range(M)]
    for m in range(M):
        for n in range(N):
            state=(0,0)
            for j in range(ceildiv(K,128)):
                lo=j*128;hi=min(K,lo+128)
                raw=check_signed(sum(int(A[m][k])*fp8_e4m3fn_q9(W[n][k])
                                     for k in range(lo,hi)),48,"B1_RAW")
                sig,se=fp32_positive_scale(bits_integer(S[n//128][j]))
                term=check_signed(raw*sig,72,"B2_TERM_FP32")
                te=check_signed(int(E[m][j])-9+se,12,"B2_TERM_EXP")
                state=accumulate_48(state,(term,te),term_bits=72)
            states[m][n]=state
    mants=[[0]*N for m in range(M)]
    exps=[[0]*ceildiv(N,128) for m in range(M)]
    for m in range(M):
        for b in range(ceildiv(N,128)):
            q,e=requant_bfp18(states[m][b*128:min(N,(b+1)*128)])
            mants[m][b*128:b*128+len(q)]=q
            exps[m][b]=e
    return mants,exps

def report(sim,case,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    job=case["job"]
    with (out/"cycle_trace.jsonl").open("w",encoding="utf-8") as f:
        for x in sim.trace:f.write(json.dumps(x,ensure_ascii=False)+"\n")
    with (out/"input_axis_v2.jsonl").open("w") as f:
        for x in sim.a_input:f.write(json.dumps(x)+"\n")
    with (out/"output_axis_v2.jsonl").open("w") as f:
        for x in sim.out:f.write(json.dumps(x)+"\n")
    (out/"ddr_manifest.json").write_text(json.dumps(sim.man,indent=2))
    golden_m,golden_e=independent_golden(case)
    if sim.mants!=golden_m or sim.expout!=golden_e:
        raise AssertionError("cycle model differs from independent ordered B3-B golden")
    decode_out,decode_exps=parse_axis(sim.out,sim.M,sim.N,sim.job_id,sim.axis_width)
    if decode_out!=sim.mants or decode_exps!=sim.expout: raise AssertionError("output AXIS roundtrip")
    errs=[];absolute=[];relative=[];sq=0.;exact_values=[]
    float_source=case.get("reference",{}).get("float_xw")
    if float_source is not None and (len(float_source)!=sim.M or any(len(r)!=sim.N for r in float_source)):
        raise ValueError("reference.float_xw shape mismatch")
    for m in range(sim.M):
        for n in range(sim.N):
            pred=hardware_value(sim.mants[m][n],sim.expout[m][n//128])
            ref=sim.exact[m][n]
            err=float(pred-ref); aerr=abs(err)
            re=aerr/abs(float(ref)) if ref else (0. if not aerr else None)
            absolute.append(aerr);sq+=err*err;exact_values.append(float(ref))
            if re is not None:relative.append(re)
            record=dict(row=m,n=n,mantissa=sim.mants[m][n],shared_exp=sim.expout[m][n//128],
                b3b_value=float(pred),quantized_input_ideal=float(ref),error=err,
                abs_error=aerr,rel_error=re)
            if float_source is not None:
                v=float(float_source[m][n]);record["original_float_xw"]=v
                record["total_float_error"]=float(pred)-v
            errs.append(record)
    with (out/"element_errors.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(errs[0].keys()));w.writeheader();w.writerows(errs)
    count=len(errs);mae=sum(absolute)/count
    metrics=dict(status="SOFTWARE_CYCLE_MODEL_SUCCESS_NOT_RTL_SIGNOFF",
        cycles=sim.cycle,m=sim.M,n=sim.N,k=sim.K,
        b3b_golden_bit_exact=True,scale_format="IEEE754_FP32_RAW32",
        b2_term_width_bits=72,a2_state_mantissa_bits=48,a2_state_exponent_bits=16,
        ddr_requests=sim.ddr_requests,ddr_return_beats=sim.ddr_beats,
        axis_input_beats=sim.in_idx,axis_output_beats=len(sim.out),
        reference_definition="exact unrounded xW from BFP18, FP8, FP32-scale decoded data",
        max_abs_error=max(absolute),mean_abs_error=mae,rmse=math.sqrt(sq/count),
        max_rel_error=max(relative) if relative else None,
        event_counts=sim.event_counts,scale_layout=sim.man["scale_layout"])
    if float_source is not None:
        te=[r["total_float_error"] for r in errs]
        metrics["original_float_xw_comparison"]=dict(
            mae=sum(abs(v) for v in te)/count,max_abs_error=max(abs(v) for v in te),
            rmse=math.sqrt(sum(v*v for v in te)/count))
    (out/"metrics.json").write_text(json.dumps(metrics,indent=2))
    (out/"output_numeric.json").write_text(json.dumps(dict(mantissa=sim.mants,exponents=sim.expout)))
    return metrics

def demo():
    M,N,K=2,5,129
    return dict(job=dict(job_id=42,m=M,n=N,k=K,static_dim_mode=1,n_dim=N,k_dim=K,
                         weight_base_addr=0,axis_width_bits=512),
        activation=dict(mantissa=[[(m*7+k*3)%255-127 for k in range(K)] for m in range(M)],
                        exponents=[[j-20 for j in range(ceildiv(K,128))] for m in range(M)]),
        weight=dict(fp8_bits=[[(n*3+k*5)%127+(((n+k)%2)*128) for k in range(K)] for n in range(N)],
                    scale_fp32_bits=[[0x3f800000+1024*j for j in range(ceildiv(K,128))]
                                     for b in range(ceildiv(N,128))]))
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--case",help="JSON case with already-quantized tensors; safetensors loader added later")
    ap.add_argument("--out",default="results")
    ap.add_argument("--ddr-latency",type=int,default=2)
    ap.add_argument("--ddr-gap",type=int,default=0)
    ap.add_argument("--ddr-ready-period",type=int,default=0,
                    help="0: always ready; otherwise every Nth cycle stalls range requests")
    ap.add_argument("--input-gap",type=int,default=0)
    ap.add_argument("--output-stall-period",type=int,default=0)
    ap.add_argument("--b1-latency",type=int,default=1)
    ap.add_argument("--b2-latency",type=int,default=1)
    ap.add_argument("--a2-latency",type=int,default=1)
    ap.add_argument("--max-cycles",type=int,default=3000000)
    ap.add_argument("--summary-trace",action="store_true")
    args=ap.parse_args()
    case=json.loads(Path(args.case).read_text()) if args.case else demo()
    image,manifest=prepare(case)
    sim=Simulator(case,image,manifest,ddr_latency=args.ddr_latency,ddr_gap=args.ddr_gap,
                  ddr_ready_period=args.ddr_ready_period,input_gap=args.input_gap,output_stall_period=args.output_stall_period,
                  b1_latency=args.b1_latency,b2_latency=args.b2_latency,a2_latency=args.a2_latency,
                  max_cycles=args.max_cycles,trace_detail=not args.summary_trace).run()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    (out/"ddr_image.bin").write_bytes(image)
    result=report(sim,case,out)
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
