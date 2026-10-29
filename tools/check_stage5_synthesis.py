#!/usr/bin/env python3
"""Check synchronous RAMs/latches/loops; optional xc7 mapping, never timing claim."""
import argparse,json,subprocess,shutil,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
LOG=ROOT/'docs/stage5/logs';BUILD=ROOT/'sim_build/stage5'
NAMES=['xw_output_group_buffer','xw_bfp18_requant','xw_result_buffer','xw_stage5_ctrl']

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--map',action='store_true');a=ap.parse_args()
    if not shutil.which('yosys'):raise SystemExit('yosys unavailable: synthesis PENDING')
    LOG.mkdir(parents=True,exist_ok=True);BUILD.mkdir(parents=True,exist_ok=True)
    records=[];src=' '.join('rtl/'+n+'.v' for n in NAMES)
    for top in NAMES:
        dest=BUILD/(top+'.json')
        script=f'read_verilog {src}; hierarchy -check -top {top}; proc; opt; memory_dff; memory_collect; opt_clean; check -assert; stat; write_json {dest}'
        p=subprocess.run(['yosys','-Q','-T','-p',script],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
        (LOG/(top+'_synthesis.log')).write_text('COMMAND yosys -p '+script+'\n'+p.stdout)
        assert p.returncode==0 and 'Found and reported 0 problems.' in p.stdout,p.stdout[-5000:]
        net=json.loads(dest.read_text());mem=[];types={};ff=0
        for mn,m in net['modules'].items():
            for cn,c in m.get('cells',{}).items():
                typ=c['type'];types[typ]=types.get(typ,0)+1
                assert 'latch' not in typ.lower(),(mn,cn,typ)
                assert typ!='$mul',(top,'unexpected multiplier',cn)
                if typ=='$mem_v2':
                    r=dict(module=mn,name=cn,**{k:int(c['parameters'][k],2) for k in ['WIDTH','SIZE','RD_PORTS','WR_PORTS','RD_CLK_ENABLE','WR_CLK_ENABLE']})
                    assert r['RD_PORTS']==r['WR_PORTS']==r['RD_CLK_ENABLE']==r['WR_CLK_ENABLE']==1,r
                    mem.append(r)
                if typ in ['$dff','$adff','$dffe','$adffe','$sdff','$sdffe','$sdffce']:ff+=len(c['connections']['Q'])
        warnings=[s for s in p.stdout.splitlines() if s.startswith('Warning:')]
        assert not warnings,warnings
        if top=='xw_output_group_buffer':assert [(m['WIDTH'],m['SIZE']) for m in mem]==[(64,128)],mem
        if top=='xw_result_buffer':assert sorted((m['WIDTH'],m['SIZE']) for m in mem)==[(8,96),(144,1536)],mem
        if top=='xw_stage5_ctrl':assert sorted((m['WIDTH'],m['SIZE']) for m in mem)==[(8,96),(64,128),(144,1536)],mem
        records.append(dict(module=top,status='PASS_GENERIC_STRUCTURE',ff_bits=ff,memories=mem,cells=types,latches=0,combinational_loops=0,multipliers=0))
        print('PASS synthesis structure',top,mem,flush=True)
    result=dict(tool=subprocess.run(['yosys','-V'],text=True,capture_output=True).stdout.strip(),modules=records,
                source_sha256={n:hashlib.sha256((ROOT/'rtl'/(n+'.v')).read_bytes()).hexdigest() for n in NAMES},vivado='PENDING',part='NOT_SPECIFIED',timing='PENDING')
    (ROOT/'docs/stage5/SYNTHESIS_RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
    if a.map:
        abc=shutil.which('yosys-abc') or shutil.which('berkeley-abc')
        if not abc:raise SystemExit('ABC missing: xc7 mapping PENDING')
        dest=BUILD/'xc7_mapped.json'
        script=(f'read_verilog {src}; synth_xilinx -top xw_stage5_ctrl -family xc7 -noiopad -noclkbuf -flatten -run begin:map_luts; '
                f'abc -exe {abc} -luts 2:2,3,6:5; clean; ltp -noff; techmap -map +/xilinx/ff_map.v; '
                'xilinx_srl -fixed -minlen 3; techmap -map +/xilinx/lut_map.v -map +/xilinx/cells_map.v -D LUT_WIDTH=6; '
                'xilinx_dffopt; opt_lut_ins -tech xilinx; clean; hierarchy -check; check -assert; stat -tech xilinx; '
                f'write_json {dest}')
        p=subprocess.run(['yosys','-Q','-T','-p',script],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
        (LOG/'xc7_mapping.log').write_text('COMMAND yosys -p '+script+'\n'+p.stdout)
        assert p.returncode==0 and 'Warning: Detected loop' not in p.stdout,p.stdout[-4000:]
        cells=json.loads(dest.read_text())['modules']['xw_stage5_ctrl']['cells'];counts={}
        for c in cells.values():counts[c['type']]=counts.get(c['type'],0)+1
        assert not any(k.startswith('$_') or 'LATCH' in k.upper() or k.startswith('LD') for k in counts),counts
        assert not counts.get('DSP48E1',0),counts
        paths=re.findall(r'Longest topological path.*?length=(\d+)',p.stdout)
        mapped=dict(status='PASS_EXPLORATORY_XC7_MAPPING',family='xc7',part='NOT_SPECIFIED',cells=counts,
                    lut=sum(v for k,v in counts.items() if k.startswith('LUT')),ff=sum(v for k,v in counts.items() if k.startswith('FD')),
                    bram36=counts.get('RAMB36E1',0),bram18=counts.get('RAMB18E1',0),dsp=counts.get('DSP48E1',0),
                    topological_path_cells=int(paths[-1]) if paths else None,
                    note='Topological count is not ns. No device delay/clock/placement/routing. Vivado and 100-150MHz PENDING.',
                    source_sha256=result['source_sha256'])
        (ROOT/'docs/stage5/XC7_MAPPING.json').write_text(json.dumps(mapped,indent=2)+'\n')
        print(json.dumps(mapped,indent=2),flush=True)
if __name__=='__main__':main()
