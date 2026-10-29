#!/usr/bin/env python3
"""Derive measurements from ACTUAL HDL events, not a guessed latency formula."""
import json,collections,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent


def main():
    events=[json.loads(s) for s in (ROOT/'docs/stage4/logs/compute_rtl_events.jsonl').read_text().splitlines()]
    events=[e for e in events if 1000<=e['job_id']<2000]
    measurements=json.loads((ROOT/'docs/stage4/HARNESS_MEASUREMENTS.json').read_text())
    cases=[];blocks=[]
    for m in measurements:
        row=[e for e in events if (e['job_id'],e['channel'])==(m['job'],m['channel'])]
        choose=lambda name:[e for e in row if e['event']==name]
        begin,end,ack=choose('COMPUTE_ACCEPT'),choose('RESULT_VALID'),choose('RESULT_ACCEPT')
        assert len(begin)==len(end)==len(ack)==1
        duration=end[0]['cycle']-begin[0]['cycle']+1
        assert duration==m['channel_cycles']
        cr=dict(job=m['job'],channel=m['channel'],k=m['k'],mode=m['mode'],cycles=duration,
                result_handshake_delay=ack[0]['cycle']-end[0]['cycle'],
                result_stall_edges=ack[0]['cycle']-end[0]['cycle']-1,
                load_cycles=m['load_cycles_before_compute'],first_edge=begin[0]['cycle'],result_edge=end[0]['cycle'])
        assert cr['result_stall_edges']==17
        cases.append(cr)
        previous_start=None
        nb=(m['k']+127)//128
        for b in range(nb):
            br=[e for e in row if e.get('block')==b];kind=lambda name:[e for e in br if e['event']==name]
            rd=kind('RAM_READ');ac=kind('B1_ACCEPT');r1=kind('B1_VALID')[0];ac2=kind('B2_ACCEPT')[0];r2=kind('B2_VALID')[0];aca=kind('A2_ACCEPT')[0];up=kind('A2_UPDATE')[0]
            assert [e['slice'] for e in rd]==[e['slice'] for e in ac]==list(range(len(rd)))
            assert [e['index'] for e in rd]==list(range(16*b,16*b+len(rd)))
            gaps=[v['cycle']-u['cycle'] for u,v in zip(ac,ac[1:])]
            if m['mode']!='stall':assert all(g==1 for g in gaps)
            info=dict(job=m['job'],channel=m['channel'],k=m['k'],mode=m['mode'],block=b,elements=min(128,m['k']-128*b),special=up['special'],
                first_read=rd[0]['cycle'],first_slice=ac[0]['cycle'],last_slice=ac[-1]['cycle'],
                b1_raw=r1['cycle'],b2_term=r2['cycle'],a2_accept=aca['cycle'],a2_update=up['cycle'],
                b1_cycles=r1['cycle']-ac[0]['cycle']+1,b2_cycles=r2['cycle']-ac2['cycle']+1,
                a2_cycles=up['cycle']-aca['cycle']+1,block_cycles=up['cycle']-rd[0]['cycle']+1,
                slice_intervals=gaps)
            assert info['b2_cycles']==2
            if previous_start is not None:blocks[-1]['next_block_start_interval']=rd[0]['cycle']-previous_start
            previous_start=rd[0]['cycle'];blocks.append(info)
    full=[b for b in blocks if b['elements']==128 and b['mode']!='stall']
    stat={}
    for name,path in [('normal',0),('special',1)]:
        a=[b for b in full if b['special']==path]
        stat[name]={key:{'min':min(x[key] for x in a),'max':max(x[key] for x in a),'mean':statistics.mean(x[key] for x in a)} for key in ['b1_cycles','b2_cycles','a2_cycles','block_cycles']}
        stat[name]['count']=len(a)
    fifo=[e for e in events if e['event']=='FIFO_LEVEL']
    assert max(e['count']+e['pending'] for e in fifo)<=4
    report=dict(source='actual Icarus HDL $fdisplay, all events lockstep-checked',
                convention='inclusive sampled-edge counts; output-producing events use NBA edge',
                channel_start='COMPUTE_ACCEPT',channel_end='first RESULT_VALID; excludes later result stalls and prior loading',
                block_start='first RAM_READ for block',block_end='A2_UPDATE',statistics=stat,
                fifo=dict(max_count=max(e['count'] for e in fifo),max_reserved=max(e['count']+e['pending'] for e in fifo)),
                channels=cases,blocks=blocks)
    (ROOT/'docs/stage4/PERFORMANCE.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS actual HDL performance extraction',len(cases),'channels',len(blocks),'blocks')

if __name__=='__main__':main()
