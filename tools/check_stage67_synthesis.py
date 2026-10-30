#!/usr/bin/env python3
"""Real Yosys structure/memory/resource evidence; never labels Vivado timing PASS."""
import argparse,json,sys,shutil
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from tools.run_stage67 import execute,BUILD,LOG

def analyze_mapping(net):
    # synth_xilinx -flatten already removed user hierarchy. Count vendor
    # primitives as resources, never recurse into their simulation models.
    counts=Counter(c['type'] for c in net['modules']['linear_xw_ip']['cells'].values())
    assert not any(n.startswith('$') or n.startswith('LD') for n in counts),counts
    return dict(status='PASS',scope='Yosys xc7 family exploration, no exact FPGA part or placement',cells=dict(counts),
                LUT=sum(v for n,v in counts.items() if n.startswith('LUT')),FF=sum(v for n,v in counts.items() if n.startswith('FD')),
                DSP=counts['DSP48E1'],BRAM36=counts['RAMB36E1'],BRAM18=counts['RAMB18E1'],vivado_timing='Pending')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--map',action='store_true');a=ap.parse_args()
    BUILD.mkdir(parents=True,exist_ok=True);LOG.mkdir(parents=True,exist_ok=True)
    sources=' '.join(str(p.relative_to(ROOT)) for p in sorted((ROOT/'rtl').glob('*.v')))
    dest=BUILD/'structure.json'
    script=f'read_verilog -DXW_SIM_DDR_BURST=3 {sources}; hierarchy -top linear_xw_ip; hierarchy -check; proc; opt; memory_dff; memory_collect; opt_clean; check -assert; stat; write_json {dest}'
    with (LOG/'synthesis_structure.log').open('w') as f:execute(['yosys','-Q','-T','-p',script],f,timeout=1200)
    net=json.loads(dest.read_text());mem=[];latches=[];hist=Counter()
    def visit(name,path):
        for n,c in net['modules'][name]['cells'].items():
            typ=c['type'];p=c.get('parameters',{})
            if typ in net['modules']:visit(typ,path+'/'+n)
            else:
                hist[typ]+=1
                if 'latch' in typ.lower():latches.append(path+'/'+n)
                if typ=='$mem_v2':mem.append(dict(path=path+'/'+n,width=int(p['WIDTH'],2),depth=int(p['SIZE'],2),
                                                read_ports=int(p['RD_PORTS'],2),write_ports=int(p['WR_PORTS'],2),
                                                read_clock=p.get('RD_CLK_ENABLE'),write_clock=p.get('WR_CLK_ENABLE')))
    visit('linear_xw_ip','linear_xw_ip');assert not latches
    report=dict(status='PASS',tool='Yosys 0.23',scope='generic structural synthesis, actual top default capacities',
                latches=latches,cells=dict(hist),memories=mem,memory_bits=sum(m['width']*m['depth'] for m in mem),
                combinational_loops='PASS check -assert',vivado_2023_2='Pending: not installed',part='Pending: user has not specified FPGA part',timing='Pending: no part/clock/IO constraints')
    (ROOT/'docs/stage67/SYNTHESIS_STRUCTURE.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS generic structure',len(mem),'memories',report['memory_bits'],'bits',flush=True)
    if a.map:
        mapped=BUILD/'xc7.json'
        abc=shutil.which('yosys-abc') or shutil.which('berkeley-abc')
        assert abc,'ABC is unavailable'
        script=(f'read_verilog -DXW_SIM_DDR_BURST=3 {sources}; hierarchy -top linear_xw_ip; '
                'synth_xilinx -family xc7 -top linear_xw_ip -noiopad -noclkbuf -flatten -run begin:map_luts; '
                f'abc -exe {abc} -luts 2:2,3,6:5; clean; ltp -noff; '
                'techmap -map +/xilinx/ff_map.v; xilinx_srl -fixed -minlen 3; '
                'techmap -map +/xilinx/lut_map.v -map +/xilinx/cells_map.v -D LUT_WIDTH=6; '
                'xilinx_dffopt; opt_lut_ins -tech xilinx; clean; hierarchy -check; check -assert; stat -tech xilinx; '
                f'write_json {mapped}')
        with (LOG/'xc7_mapping.log').open('w') as f:execute(['yosys','-Q','-T','-p',script],f,timeout=1800)
        mapping=analyze_mapping(json.loads(mapped.read_text()))
        (ROOT/'docs/stage67/XC7_MAPPING.json').write_text(json.dumps(mapping,indent=2)+'\n')
        print('PASS xc7 exploration mapping',mapping,flush=True)
if __name__=='__main__':main()
