#!/usr/bin/env python3
"""Generic RTL structure checks; optional exploratory xc7 mapping, never Vivado."""
import json,subprocess,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
LOG=ROOT/'docs/stage4/logs';BUILD=ROOT/'sim_build/stage4'


def main():
    if not shutil.which('yosys'):raise SystemExit('yosys unavailable: generic synthesis PENDING')
    BUILD.mkdir(parents=True,exist_ok=True);LOG.mkdir(parents=True,exist_ok=True)
    modules=['xw_b1_dot128','xw_b2_fp32_pipe','xw_a2_accum48','xw_b3b_compute_ctrl']
    records=[]
    for top in modules:
        dest=BUILD/(top+'.json')
        sources=' '.join('rtl/'+n+'.v' for n in ([top] if top in ['xw_b1_dot128','xw_a2_accum48'] else [top,'xw_fp32_scale_b2'] if top=='xw_b2_fp32_pipe' else modules+['xw_fp32_scale_b2']))
        script=f'read_verilog {sources}; hierarchy -check -top {top}; proc; opt; memory_dff; memory_collect; opt_clean; check -assert; stat; write_json {dest}'
        p=subprocess.run(['yosys','-Q','-T','-p',script],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        (LOG/(top+'_synthesis.log')).write_text('COMMAND yosys -p '+script+'\n'+p.stdout)
        if p.returncode or 'Found and reported 0 problems.' not in p.stdout:raise RuntimeError(top+' synthesis failure\n'+p.stdout[-4000:])
        net=json.loads(dest.read_text());types={};mul=[];mem=[];ff=0
        for mn,mod in net['modules'].items():
            for n,c in mod.get('cells',{}).items():
                typ=c['type'];types[typ]=types.get(typ,0)+1
                assert 'latch' not in typ.lower(),(top,mn,n,typ)
                if typ=='$mul':mul.append({k:int(c['parameters'][k],2) for k in ['A_WIDTH','B_WIDTH','Y_WIDTH','A_SIGNED','B_SIGNED']})
                if typ=='$mem_v2':mem.append(dict(module=mn,name=n,**{k:int(c['parameters'][k],2) for k in ['WIDTH','SIZE','RD_PORTS','WR_PORTS','RD_CLK_ENABLE','WR_CLK_ENABLE']}))
                if typ in ['$dff','$adff','$dffe','$adffe','$sdff','$sdffe','$sdffce','$aldff','$aldffe','$dffsr','$dffsre']:ff+=len(c['connections']['Q'])
        warnings=[s for s in p.stdout.splitlines() if s.startswith('Warning:')]
        # Yosys's standard frontend lowering of short register arrays is expected.
        unexpected=[s for s in warnings if not ('Replacing memory' in s and any(x in s for x in ['product','pair_sum','half_sum','block_pipe','exp_pipe']))]
        assert not unexpected,unexpected
        if top=='xw_b1_dot128':assert len(mul)==8
        if top=='xw_a2_accum48':assert not mul and not mem
        if top=='xw_b3b_compute_ctrl':assert any(m['WIDTH']==253 and m['SIZE']==4 for m in mem)
        records.append(dict(module=top,result='PASS_GENERIC_STRUCTURE',latches=0,combinational_loops=0,check_problems=0,
            generic_ff_bits=ff,multipliers=mul,memories=mem,cells=types,warnings=warnings,
            source_sha256=hashlib.sha256((ROOT/'rtl'/(top+'.v')).read_bytes()).hexdigest()))
        print('PASS generic structure',top,flush=True)
    report=dict(tool=subprocess.run(['yosys','-V'],text=True,capture_output=True).stdout.strip(),modules=records,
                vivado='PENDING',target_part='NOT_SPECIFIED',timing='PENDING',scope='Generic lowering; device resources require mapping/implementation')
    (ROOT/'docs/stage4/SYNTHESIS_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
