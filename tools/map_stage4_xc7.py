#!/usr/bin/env python3
"""Exploratory Xilinx7-family cell mapping; no selected device or timing signoff."""
import argparse,json,subprocess,shutil,hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--abc',default=shutil.which('yosys-abc') or shutil.which('berkeley-abc'));a=ap.parse_args()
    if not a.abc or not shutil.which('yosys'):raise SystemExit('yosys/ABC missing: mapping PENDING')
    build=ROOT/'sim_build/stage4';build.mkdir(exist_ok=True,parents=True)
    mapped=build/'xc7_mapped.json'
    src=' '.join('rtl/'+n+'.v' for n in ['xw_fp32_scale_b2','xw_b1_dot128','xw_b2_fp32_pipe','xw_a2_accum48','xw_b3b_compute_ctrl'])
    script=(f'read_verilog {src}; synth_xilinx -top xw_b3b_compute_ctrl -family xc7 -noiopad -noclkbuf -flatten -run begin:map_luts; '
        f'abc -exe {a.abc} -luts 2:2,3,6:5; clean; ltp -noff; techmap -map +/xilinx/ff_map.v; '
        'xilinx_srl -fixed -minlen 3; techmap -map +/xilinx/lut_map.v -map +/xilinx/cells_map.v -D LUT_WIDTH=6; '
        'xilinx_dffopt; opt_lut_ins -tech xilinx; clean; hierarchy -check; check -assert; stat -tech xilinx; '
        f'write_json {mapped}')
    p=subprocess.run(['yosys','-Q','-T','-p',script],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240)
    (ROOT/'docs/stage4/logs/xc7_mapping.log').write_text('COMMAND yosys -p '+script+'\n'+p.stdout)
    if p.returncode or 'Warning: Detected loop' in p.stdout:raise RuntimeError(p.stdout[-5000:])
    cells=json.loads(mapped.read_text())['modules']['xw_b3b_compute_ctrl']['cells'];counts={}
    for c in cells.values():counts[c['type']]=counts.get(c['type'],0)+1
    assert not any(k.startswith('$_') for k in counts), counts
    assert counts.get('DSP48E1',0)>=8 and not any('LATCH' in n.upper() or n.startswith('LD') for n in counts)
    paths=re.findall(r'Longest topological path.*?length=(\d+)',p.stdout)
    data=dict(logic_path_cells=int(paths[-1]) if paths else None,logic_path_note='Topological cell count before FF technology mapping; no delay model',
              source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in src.split()},status='PASS_EXPLORATORY_FAMILY_MAPPING',family='xc7',target_part='NOT_SPECIFIED',cells=counts,
              dsp=counts.get('DSP48E1',0),lut=sum(v for k,v in counts.items() if k.startswith('LUT')),
              ff=sum(v for k,v in counts.items() if k.startswith('FD')),bram=sum(v for k,v in counts.items() if k.startswith('RAMB')),
              timing='PENDING: no delay/placement/routing or clock target applied',vivado_2023_2='PENDING')
    (ROOT/'docs/stage4/XC7_MAPPING.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2))

if __name__=='__main__':main()
