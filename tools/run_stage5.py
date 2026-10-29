#!/usr/bin/env python3
"""Execute real HDL, fail closed, retain exact vectors/events/commands/hashes."""
import argparse,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from test_stage5 import group_suite,requant_suite,result_suite,controller_suite

LOG=ROOT/'docs/stage5/logs';BUILD=ROOT/'sim_build/stage5'
def run(cmd,log,timeout=300,pass_marker=None):
    log.write('COMMAND '+ ' '.join(map(str,cmd))+'\n');log.flush()
    p=subprocess.run(list(map(str,cmd)),cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    log.write(p.stdout);log.write('EXIT_CODE '+str(p.returncode)+'\n');log.flush()
    if p.returncode or 'FAIL' in p.stdout:raise RuntimeError('command failed: '+str(cmd)+'\n'+p.stdout[-4000:])
    if pass_marker is not None and p.stdout.count(pass_marker)!=1:raise RuntimeError('missing/duplicate PASS: '+str(cmd))
    return p.stdout

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--only',nargs='*');args=ap.parse_args()
    for name in ['iverilog','vvp']:
        if not shutil.which(name):raise SystemExit(name+' missing: HDL PENDING')
    LOG.mkdir(parents=True,exist_ok=True);BUILD.mkdir(parents=True,exist_ok=True)
    jobs=[('group',group_suite),('requant',requant_suite),('result',result_suite),('controller',controller_suite)]
    if (ROOT/'stage5_integration.py').exists():
        from stage5_integration import harness_suite
        jobs.append(('integration',harness_suite))
    report=dict(status='IN_PROGRESS',iverilog=subprocess.run(['iverilog','-V'],text=True,capture_output=True).stdout.splitlines()[0],tests=[])
    for label,f in jobs:
        if args.only and label not in args.only:continue
        stamp=time.monotonic();t=f();vec=BUILD/(label+'.vec');t.save(vec);binary=BUILD/(label+'.vvp')
        with (LOG/(label+'_hdl.log')).open('w') as log:
            cmd=['iverilog','-g2001','-Wall','-s','tb_'+t.name+'_cycle','-o',binary]+sorted((ROOT/'rtl').glob('*.v'))
            if label=='integration':cmd+=sorted((ROOT/'tb/support').glob('*.v'))
            cmd += [ROOT/'tb'/('tb_'+t.name+'_cycle.v')]
            run(cmd,log)
            cmd=['vvp','-N',binary,'+VECTORS='+str(vec)]
            trace=LOG/(label+'_rtl_events.jsonl')
            if label in ['controller','integration']:cmd+=['+TRACE='+str(trace)]
            run(cmd,log,pass_marker='PASS tb_'+t.name+'_cycle ')
            event_count=0
            if label in ['controller','integration']:
                actual=[json.loads(s) for s in trace.read_text().splitlines()]
                assert actual==t.events,next(((a,b) for a,b in zip(actual,t.events) if a!=b),(len(actual),len(t.events)))
                event_count=len(actual)
                (BUILD/(label+'_expected_events.jsonl')).write_text(''.join(json.dumps(e)+'\n' for e in t.events))
                log.write('PASS actual RTL events == cycle events '+str(event_count)+'\n')
        report['tests'].append(dict(label=label,result='PASS',cycles=len(t.rows),coverage=t.counts,events=event_count,
            vector_sha256=hashlib.sha256(vec.read_bytes()).hexdigest(),seconds=round(time.monotonic()-stamp,3)))
        print('PASS',label,len(t.rows),'cycles',t.counts,flush=True)
    report['status']='PASS';dest='RESULTS_'+('_'.join(args.only))+'.json' if args.only else 'VERIFICATION_RESULTS.json'
    (ROOT/'docs/stage5'/dest).write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
