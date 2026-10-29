#!/usr/bin/env python3
"""Fail-closed real HDL runner, recorded commands/versions/vectors/hashes."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from test_stage4 import b1_suite,b2_suite,a2_suite


def run(cmd,log,timeout=180):
    log.write('COMMAND '+' '.join(cmd)+'\n');log.flush()
    p=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    log.write(p.stdout);log.flush()
    if p.returncode or 'FAIL' in p.stdout:raise RuntimeError(f'failed {cmd}\n{p.stdout[-4000:]}')
    return p.stdout


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--only',nargs='*');args=ap.parse_args()
    for tool in ['iverilog','vvp']:
        if not shutil.which(tool):raise SystemExit(f'{tool} unavailable; HDL PENDING')
    logs=ROOT/'docs/stage4/logs';logs.mkdir(exist_ok=True,parents=True)
    build=ROOT/'sim_build/stage4';build.mkdir(exist_ok=True,parents=True)
    jobs=[('b1',b1_suite),('b2',b2_suite),('a2',a2_suite)]
    if (ROOT/'stage4_integration.py').exists():
        from stage4_integration import controller_suite,harness_suite
        jobs += [('controller',controller_suite),('harness',harness_suite)]
    report=dict(hdl='IN_PROGRESS',tool=subprocess.run(['iverilog','-V'],text=True,capture_output=True).stdout.splitlines()[0],tests=[])
    for label,make in jobs:
        if args.only and label not in args.only:continue
        t=make();vec=build/(label+'.vec');t.save(vec)
        binary=build/(label+'.vvp');cmd=['iverilog','-g2001','-Wall','-s','tb_'+t.name+'_cycle','-o',str(binary)]
        cmd += [str(p) for p in sorted((ROOT/'rtl').glob('*.v'))]
        if label=='harness':cmd += ['tb/support/xw_stage234_harness.v','tb/support/xw_stage23_harness.v']
        cmd += ['tb/tb_'+t.name+'_cycle.v']
        with (logs/(label+'_hdl.log')).open('w') as f:
            run(cmd,f)
            args2=['vvp',str(binary),'+VECTORS='+str(vec)]
            if label=='harness':args2 += ['+TRACE='+str(logs/'compute_rtl_events.jsonl')]
            output=run(args2,f)
            if output.count('PASS tb_'+t.name+'_cycle ')!=1:raise RuntimeError('PASS missing/duplicate')
        report['tests'].append(dict(label=label,result='PASS',cycles=len(t.rows),coverage=t.counts,vector_sha256=hashlib.sha256(vec.read_bytes()).hexdigest()))
        print(label,'PASS',len(t.rows),'cycles',t.counts,flush=True)
        if label=='harness':
            from stage4_integration import check_events
            report['events']=check_events(t,logs/'compute_rtl_events.jsonl')
    report['hdl']='PASS'
    (ROOT/'docs/stage4'/('RESULTS_'+('_'.join(args.only))+'.json' if args.only else 'VERIFICATION_RESULTS.json')).write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
