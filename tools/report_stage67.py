#!/usr/bin/env python3
"""Reconstruct phase occupancy from RTL-checked PRE states, actual RTL events.
Independently verify every Layout-V3 command and per-job status uniqueness.
"""
import json,collections,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from stage23_golden import ranges
PHASE={5:'AXIS_Input',6:'DDR_Scale',7:'DDR_Scale',8:'DDR_Weight',9:'DDR_Weight',
       10:'Computing',11:'Computing',12:'Group_Requant',14:'AXIS_Output',15:'AXIS_Output',17:'Status_Wait'}

def analyze(label,meta):
    ev=[json.loads(s) for s in (ROOT/'docs/stage67/logs'/(label+'_rtl_events.jsonl')).read_text().splitlines()]
    byjob=collections.defaultdict(list);bycycle=collections.defaultdict(list)
    for e in ev:byjob[e['job_id']].append(e);bycycle[e['cycle']].append(e)
    metrics=[];owner=None;counts=collections.Counter();accepted=0
    with (ROOT/'sim_build/stage67'/(label+'.vec')).open() as f:
        for cycle,line in enumerate(f):
            _,pre,_=line.split();value=int(pre,16);control=(value>>48)&((1<<44)-1);state=(control>>35)&31
            pipeline=value&((1<<48)-1);core=(pipeline>>41)&7
            assert not (((pipeline>>44)&1) and core in (1,2,3)),'DDR/compute overlap'
            events=bycycle[cycle]
            for e in events:
                if e['event']=='JOB_ACCEPT':
                    assert owner is None;owner=e['job_id'];counts=collections.Counter();accepted=cycle
            if owner is not None:counts[PHASE.get(state,'Scheduler_Overhead')]+=1
            if any(e['event']=='STATUS_ACCEPT' for e in events):
                records=byjob[owner];info=next(m for m in meta if m['job_id']==owner);n,k=info['n'],info['k'];burst=info['burst']
                commands=[(e['start'],e['end'],e['beats']) for e in records if e['event']=='DDR_REQ_ACCEPT']
                wb=0x100;rw=(k+63)//64;sb=wb+8*n*rw;rs=(k+2047)//2048
                expected=[]
                for grp in range((n+127)//128):
                    expected += [r[:3] for r in ranges(sb+8*grp*rs,rs,burst)]
                    for ch in range(grp*128,min(n,(grp+1)*128)):
                        expected += [r[:3] for r in ranges(wb+8*ch*rw,rw,burst)]
                assert commands==expected,(label,owner,commands[:8],expected[:8])
                status=[e for e in records if e['event']=='STATUS_ACCEPT'];outputs=[e for e in records if e['event']=='AXIS_OUT_ACCEPT']
                assert len(status)==1 and status[0]['ok']==1 and status[0]['code']==0
                assert int(outputs[-1]['user_hex'],16)>>88&1 and outputs[-1]['cycle']<status[0]['cycle']
                assert sum(counts.values())==cycle-accepted+1
                ca=[e for e in records if e['event']=='COMPUTE_ACCEPT'];ra=[e for e in records if e['event']=='RESULT_ACCEPT']
                assert len(ca)==len(ra)==n
                compute=sum(b['cycle']-a['cycle']+1 for a,b in zip(ca,ra))
                assert compute==counts['Computing']
                metrics.append(dict(label=label,job_id=owner,n=n,k=k,burst=burst,job_accept=accepted,last_output=outputs[-1]['cycle'],
                                    status_accept=cycle,end_to_end_cycles=cycle-accepted+1,phase_cycles=dict(counts),
                                    pure_compute_request_to_result_cycles=compute,ddr_requests=len(commands),
                                    ddr_beats=sum(e['event']=='DDR_BEAT' for e in records),output_beats=len(outputs)))
                owner=None
    return metrics

def main():
    results=json.load(open(ROOT/'docs/stage67/STAGE7_RESULTS.json'))
    for name in ['extended','retry']:
        ep=ROOT/'docs/stage67'/('STAGE'+name+'_RESULTS.json')
        if ep.exists():results+=json.load(open(ep))
    metrics=[]
    for r in results:
        if not r['label'].startswith('integration'):continue
        meta=[dict(m,burst=r['coverage']['burst']) for m in r['coverage']['measurements']]
        metrics+=analyze(r['label'],meta)
    paths=re.findall(r'Longest topological path.*?length=(\d+)',(ROOT/'docs/stage67/logs/xc7_mapping.log').read_text())
    out=dict(status='PASS',evidence='Actual RTL JSONL events; phase counts from every PRE state bit-checked against actual RTL (including scheduler state)',
             cycle_definition='inclusive Job accept through Status accept; cleanup after Status excluded; no DDR/compute overlap',
             jobs=metrics,topological_cells=int(paths[-1]) if paths else None,
             timing_note='Topological graph length can traverse RAM vendor models; it is not a timed register path, ns, Fmax, or Vivado sign-off')
    (ROOT/'docs/stage67/PERFORMANCE.json').write_text(json.dumps(out,indent=2)+'\n')
    text=['# 实测周期分解','',out['evidence'],'',out['cycle_definition'],'',
          '|Profile|Job|N|K|输入|Scale|Weight|计算|Requant|输出|Status等待|调度额外|端到端|',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for m in metrics:
        c=m['phase_cycles'];vals=[c.get(n,0) for n in ['AXIS_Input','DDR_Scale','DDR_Weight','Computing','Group_Requant','AXIS_Output','Status_Wait','Scheduler_Overhead']]
        text.append('|'+ '|'.join(map(str,[m['label'],m['job_id'],m['n'],m['k'],*vals,m['end_to_end_cycles']]))+'|')
    text+=['','计算列独立核对每个真实 COMPUTE_ACCEPT→RESULT_ACCEPT 包含两端的间隔；输入包含Parser解包及X RAM提交，DDR列包含合法Gap与逻辑提交，输出包含下游反压，Status等待取真实终态状态驻留。',
           'Scheduler额外包括Job接受、预检查、子模块启动、整Job发布观察及终态提交；没有将DDR/输入或Requant计为纯计算。',
           'Stage6完整128组无stall从start到最后握手含起止沿22 cycles。末EOT握手到status_valid相差2沿，最早Status接受再下一沿。',
           'Status后的受控清理/重开门控不计入端到端Job周期；其释放链和Ready仍逐拍比对。','',out['timing_note']]
    (ROOT/'docs/stage67/PERFORMANCE.md').write_text('\n'.join(text)+'\n')
    print('PASS performance and independent DDR command audit',len(metrics),'jobs')
if __name__=='__main__':main()
