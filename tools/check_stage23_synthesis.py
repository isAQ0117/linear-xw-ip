#!/usr/bin/env python3
"""Yosys front-end/structural checks, NOT Vivado implementation/timing signoff."""
import json
import hashlib
import os
import shutil
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent


def number(bits):
    return int(bits,2)


def main():
    if not shutil.which('yosys'):
        raise SystemExit('yosys unavailable: structural synthesis PENDING')
    build=ROOT/'sim_build/stage23';build.mkdir(parents=True,exist_ok=True)
    logs=ROOT/'docs/stage23/logs'
    results=[]
    for module in ('xw_axis_bfp18_input','xw_activation_buffer','xw_weight_row_buffer','xw_ddr_addr_gen'):
        artifact=build/f'{module}_netlist.json'
        hierarchy=f'hierarchy -check -top {module}'
        if module=='xw_ddr_addr_gen':hierarchy+=' -chparam DDR_MAX_BURST_BEATS 3'
        command=(f'read_verilog rtl/{module}.v; {hierarchy}; proc; opt; memory_dff; '
                 f'memory_collect; opt_clean; check -assert; stat; write_json {artifact}')
        p=subprocess.run(['yosys','-Q','-T','-p',command],cwd=ROOT,text=True,
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        (logs/f'{module}_synthesis.log').write_text('COMMAND yosys -p '+command+'\n'+p.stdout)
        if p.returncode or 'Warning:' in p.stdout or 'Found and reported 0 problems.' not in p.stdout:
            raise RuntimeError(f'{module}: unexpected synthesis diagnostic\n{p.stdout[-4000:]}')
        cells=json.loads(artifact.read_text())['modules'][module]['cells']
        assert not any('latch' in c['type'].lower() for c in cells.values()),'latch inferred'
        memories=[]
        for name,c in cells.items():
            if c['type']=='$mem_v2':
                param=c['parameters']
                info={k:number(param[k]) for k in ('WIDTH','SIZE','RD_PORTS','WR_PORTS','RD_CLK_ENABLE','WR_CLK_ENABLE')}
                assert info['RD_PORTS']==info['WR_PORTS']==1
                assert info['RD_CLK_ENABLE']==info['WR_CLK_ENABLE']==1
                info['name']=name;memories.append(info)
        if module=='xw_activation_buffer':
            assert sorted((x['WIDTH'],x['SIZE']) for x in memories)==[(8,96),(144,1536)]
        if module=='xw_weight_row_buffer':
            assert [(x['WIDTH'],x['SIZE']) for x in memories]==[(512,192)]
        results.append(dict(module=module,result='PASS',check_problems=0,latches=0,memories=memories,
                            source_sha256=hashlib.sha256((ROOT/'rtl'/f'{module}.v').read_bytes()).hexdigest()))
        print('PASS structural synthesis '+module,flush=True)
    version=subprocess.run(['yosys','-V'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.strip()
    (ROOT/'docs/stage23/SYNTHESIS_RESULTS.json').write_text(json.dumps(dict(tool=version,
        scope='generic RTL lowering and clocked memory inference, no technology mapping',
        vivado_2023_2='PENDING',fpga_timing='PENDING',modules=results),indent=2)+'\n')


if __name__=='__main__':main()
