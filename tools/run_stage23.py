#!/usr/bin/env python3
"""Reproducible real Icarus regression; software-only is explicitly separate."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from test_stage23 import parser_suite,buffer_suite,addr_suite,harness_suite,stage1_cycle_suites
from tools.gen_stage23_tb import SOURCES


def execute(cmd, log, env=None):
    p=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,timeout=180)
    log.write(p.stdout);log.flush()
    if p.returncode or 'FAIL' in p.stdout:
        raise RuntimeError(f'command failed {cmd}:\n{p.stdout[-8000:]}')
    return p.stdout


def check_actual_events(trace, path):
    actual=[json.loads(line) for line in path.read_text().splitlines()]
    names={'JOB_ACCEPT','AXIS_IN_ACCEPT','DDR_REQ_ACCEPT','DDR_BEAT','CACHE_TEST_RESULT_ACCEPT','CACHE_OBJECT_ACCEPT'}
    def unpack(fields,value):
        decoded={}
        for name,width in reversed(fields):
            decoded[name]=value & ((1<<width)-1);value >>= width
        return decoded
    expected=[];owner=None;release=0
    for cycle,(inputs,outputs,post) in enumerate(trace.rows):
        i=unpack(trace.ins,inputs);o=unpack(trace.outs,outputs)
        if not i['rst_n']:release=0;owner=None
        enabled=bool(release & 2)
        if enabled:
            if i['job_valid'] and o['job_ready']:owner=i['job_id'];expected.append((cycle,'JOB_ACCEPT',owner))
            if i['s_axis_tvalid'] and o['s_axis_tready']:expected.append((cycle,'AXIS_IN_ACCEPT',owner))
            if i['object_valid'] and o['object_ready']:expected.append((cycle,'CACHE_OBJECT_ACCEPT',owner))
            if o['ddr_rd_req'] and i['ddr_rd_rdy']:expected.append((cycle,'DDR_REQ_ACCEPT',owner))
            if i['ddr_rd_vld']:expected.append((cycle,'DDR_BEAT',owner))
            if i['result_ready'] and o['result_valid']:
                expected.append((cycle,'CACHE_TEST_RESULT_ACCEPT',owner));owner=None
        if i['rst_n']:release=((release<<1)|1)&3
    observed=[(e['cycle'],e['event'],e['job_id']) for e in actual if e['event'] in names]
    assert observed==expected,'actual HDL event edges/ownership differ from vector edges'
    # Additional independent invariants over actual internal RTL events.
    pending=None;written=0;inits=0
    for e in actual:
        if e['event']=='CACHE_OBJECT_ACCEPT':pending=e;written=0;inits=0
        elif e['event']=='CACHE_INIT':
            assert pending is not None and inits==0
            inits+=1
        elif e['event']=='BUFFER_WRITE':
            assert pending is not None and inits==1
            assert e['kind']==pending['kind'] and e['logical_word_index']==written
            written+=1
        elif e['event']=='CACHE_OBJECT_DONE':
            assert inits==1 and pending is not None
            pending=None
        elif e['event']=='FAULT_LOCK':pending=None
    return dict(records=len(actual),external_event_edges=len(expected),result='PASS',source='actual HDL $fdisplay')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--software-only',action='store_true')
    args=ap.parse_args()
    logs=ROOT/'docs/stage23/logs';logs.mkdir(parents=True,exist_ok=True)
    build=ROOT/'sim_build/stage23';build.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,TMPDIR=str(build))
    if not args.software_only:
        for name in ('iverilog','vvp'):
            if not shutil.which(name):raise SystemExit(f'{name} missing: HDL PENDING')
    jobs=[('parser',parser_suite),('activation',lambda:buffer_suite('x')),('weight',lambda:buffer_suite('w'))]
    jobs += [(f'address_b{b}',lambda b=b:addr_suite(b)) for b in (1,2,3,64,192)]
    jobs += [(f'harness_b{b}',lambda b=b:harness_suite(b)) for b in (1,2,3,64,192)]
    jobs += [('harness_static',lambda:harness_suite(3,1))]
    # Stage1 cycle suites are materialized sequentially, preserving memory bounds.
    stage1=stage1_cycle_suites()
    jobs += [('stage1_rx_cycle',lambda:stage1[0]),('stage1_scale_cycle',lambda:stage1[1])]
    report={'contract':'XW-CONTRACT-STD-001 V1.0','baseline':'4f3fc68f1f59ab83ae2f657356eec35a41d56e22',
            'hdl_executed':not args.software_only,'tests':[],'tools':{},
            'synthesis':'PENDING','vivado_2023_2':'PENDING','platform_ddr_spec':'PENDING'}
    if not args.software_only:
        report['tools']['iverilog']=subprocess.run(['iverilog','-V'],env=env,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.splitlines()[0]
        report['tools']['vvp']=subprocess.run(['vvp','-V'],env=env,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.splitlines()[0]
    for label,make in jobs:
        start=time.time();t=make();vector=build/f'{label}.vec';t.save(vector)
        record=dict(label=label,module=t.name,cycles=len(t.rows),software='PASS',hdl='PENDING',
                    vector_sha256=hashlib.sha256(vector.read_bytes()).hexdigest(),coverage=t.counts)
        if not args.software_only:
            out=build/f'{label}.vvp'
            cmd=['iverilog','-g2001','-Wall','-s',f'tb_{t.name}_cycle','-o',str(out)]
            if t.name in ('xw_ddr_addr_gen','xw_stage23_harness'):
                cmd += ['-P',f'tb_{t.name}_cycle.BURST={t.counts["burst"]}']
            if t.name=='xw_stage23_harness':
                cmd += ['-P',f'tb_{t.name}_cycle.STATIC_MODE={t.counts["static"]}','-f','rtl_sources.f',str(SOURCES[t.name])]
            else:cmd += [str(SOURCES[t.name])]
            cmd += [str(ROOT/'tb'/f'tb_{t.name}_cycle.v')]
            with (logs/f'{label}_hdl.log').open('w') as f:
                f.write('COMMAND '+ ' '.join(cmd)+'\n')
                execute(cmd,f,env)
                sim=['vvp',str(out),f'+VECTORS={vector}']
                if label=='harness_b3':
                    sim.append('+TRACE='+str(logs/'harness_rtl_events.jsonl'))
                f.write('COMMAND '+' '.join(sim)+'\n')
                output=execute(sim,f,env)
                if output.count(f'PASS tb_{t.name}_cycle ')!=1:raise RuntimeError('missing/duplicate PASS')
            record['hdl']='PASS'
        if label=='harness_b3' and not args.software_only:
            record['actual_event_trace']=check_actual_events(t,logs/'harness_rtl_events.jsonl')
        report['tests'].append(record)
        print(f'{label}: software PASS, HDL {record["hdl"]}, {len(t.rows)} cycles, {time.time()-start:.1f}s',flush=True)
        del t
    if not args.software_only:
        negatives=[('parser_params','xw_axis_bfp18_input'),('activation_params','xw_activation_buffer'),
                   ('weight_params','xw_weight_row_buffer'),('burst_unspecified','xw_ddr_addr_gen'),
                   ('burst_large','xw_ddr_addr_gen'),('address_max','xw_ddr_addr_gen')]
        report['negative_elaboration']=[]
        with (logs/'stage23_negative_elaboration.log').open('w') as f:
            for name,module in negatives:
                cmd=['iverilog','-g2001','-s','tb_xw_invalid_'+name,'-o',str(build/'negative.vvp'),
                     str(SOURCES[module]),'tb/negative/tb_xw_invalid_stage23_params.v']
                p=subprocess.run(cmd,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                f.write('COMMAND '+' '.join(cmd)+'\n'+p.stdout)
                if p.returncode==0 or 'XW_INVALID_' not in p.stdout:
                    raise RuntimeError('negative elaboration did not fail at guard: '+name)
                report['negative_elaboration'].append(dict(name=name,result='PASS'))
                f.write('PASS negative elaboration '+name+'\n')
    if not args.software_only:
        with (logs/'review_directed_hdl.log').open('w') as f:
            cmd=['iverilog','-g2001','-Wall','-s','tb_xw_stage23_review','-o',str(build/'review.vvp'),
                 '-f','rtl_sources.f','tb/support/xw_stage23_harness.v','tb/tb_xw_stage23_review.v']
            execute(cmd,f,env)
            result=execute(['vvp',str(build/'review.vvp')],f,env)
            assert result.count('PASS tb_xw_stage23_review')==1
        report['review_directed_hdl']='PASS'
    synthesis=ROOT/'docs/stage23/SYNTHESIS_RESULTS.json'
    if synthesis.exists():
        data=json.loads(synthesis.read_text())
        if all(item.get('source_sha256')==hashlib.sha256((ROOT/'rtl'/f'{item["module"]}.v').read_bytes()).hexdigest()
               for item in data['modules']):
            report['synthesis']='PASS_GENERIC_STRUCTURE_ONLY'
            report['structural_synthesis_reference']='SYNTHESIS_RESULTS.json'
    path=ROOT/'docs/stage23'/('SOFTWARE_RESULTS.json' if args.software_only else 'VERIFICATION_RESULTS.json')
    path.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS Stage2/3 software'+(' ONLY; HDL PENDING' if args.software_only else ' and actual Verilog-2001 PRE/NBA cycle regression'),flush=True)


if __name__=='__main__':main()
