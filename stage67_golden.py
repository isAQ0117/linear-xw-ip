"""Whole M=1 job functional oracle, cross-checked with frozen numeric.py.
AXIS packing uses the pre-existing independent bit/byte implementation.
"""
from stage4_golden import checkpoints
from stage5_golden import requant
from stage23_golden import axis_tensor
from linear_stream_model.numeric import fp8_e4m3fn_q9,fp32_positive_scale,accumulate_48,requant_bfp18

def linear_job(x,exponents,weights,scales,job_id):
    check=[];pairs=[]
    for ch,w in enumerate(weights):
        cp=checkpoints(x,exponents,w,scales[ch//128]);state=(0,0)
        for block,lo in enumerate(range(0,len(x),128)):
            raw=sum(a*fp8_e4m3fn_q9(b) for a,b in zip(x[lo:lo+128],w[lo:lo+128]))
            sig,power=fp32_positive_scale(scales[ch//128][block]);term=raw*sig;exp=exponents[block]-9+power
            state=accumulate_48(state,(term,exp),term_bits=72)
            assert (raw,term,exp,*state)==(cp[block]['raw'],cp[block]['term_mant'],cp[block]['term_exp'],cp[block]['acc_mant'],cp[block]['acc_exp'])
        check.append(cp);pairs.append(state)
    vals=[];exps=[]
    for lo in range(0,len(weights),128):
        group=requant(pairs[lo:lo+128]);assert group['error']==0
        assert requant_bfp18(pairs[lo:lo+128])==(group['mant'],group['exp'])
        vals+=group['mant'];exps.append(group['exp'])
    return dict(checkpoints=check,pairs=pairs,mant=vals,exp=exps,axis=axis_tensor(vals,exps,job_id))

def image(weights,scales,wb,sb):
    n=len(weights);k=len(weights[0]);rw=(k+63)//64;rs=(k+2047)//2048;mem={}
    for ch,w in enumerate(weights):
        payload=bytes(w)+bytes([255])*((-k)%64)
        for j in range(rw):mem[wb+8*(ch*rw+j)]=int.from_bytes(payload[64*j:64*(j+1)],'little')
    for grp,s in enumerate(scales):
        payload=b''.join(b.to_bytes(4,'little') for b in s)+bytes([0xa5])*(rs*64-4*len(s))
        for j in range(rs):mem[sb+8*(grp*rs+j)]=int.from_bytes(payload[64*j:64*(j+1)],'little')
    return mem
