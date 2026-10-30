"""Independent Stage6 functional packing, cross-checked with frozen AXIS oracle.
There is no RAM/FIFO or timing dependency in this implementation.
"""
def output_beats(mantissas,exponents,job_id):
    assert 1<=len(mantissas)<=65535 and len(exponents)==(len(mantissas)+127)//128
    result=[]
    for group,start in enumerate(range(0,len(mantissas),128)):
        vals=mantissas[start:start+128]
        for offset in range(0,len(vals),28):
            payload=vals[offset:offset+28];last=offset+len(payload)==len(vals)
            assert all(-(1<<17)<=v<(1<<17) for v in payload)
            data=sum((v&0x3ffff)<<(18*j) for j,v in enumerate(payload))
            user=(job_id|group<<48|(exponents[group]&255)<<64|len(vals)<<72|offset<<80|
                  int(last and start+len(vals)==len(mantissas))<<88|0xb2<<96)
            result.append(dict(s_axis_tdata=data,s_axis_tkeep=(1<<((18*len(payload)+7)//8))-1,
                               s_axis_tlast=int(last),s_axis_tuser=user))
    from stage23_golden import axis_tensor
    assert result==axis_tensor(mantissas,exponents,job_id)
    return result
