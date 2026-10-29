#!/usr/bin/env python3
"""Independent directed review and expected parameter-elaboration failures."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tools.run_stage4 import run


def main():
    build=ROOT/'sim_build/stage4';build.mkdir(exist_ok=True,parents=True)
    with (ROOT/'docs/stage4/logs/review_hdl.log').open('w') as log:
        cmd=['iverilog','-g2001','-Wall','-s','tb_xw_stage4_review','-o',str(build/'review.vvp')]
        cmd += [str(p) for p in sorted((ROOT/'rtl').glob('*.v'))]+['tb/tb_xw_stage4_review.v']
        run(cmd,log)
        out=run(['vvp',str(build/'review.vvp')],log)
        assert out.count('PASS tb_xw_stage4_review')==1
        for value in ['0','65536']:
            name=build/('invalid_'+value+'.v');name.write_text('module tb_invalid; xw_b3b_compute_ctrl #(.MAX_K('+value+')) dut (); endmodule\n')
            cmd=['iverilog','-g2001','-s','tb_invalid','-o',str(build/'bad.vvp')]+[str(p) for p in sorted((ROOT/'rtl').glob('*.v'))]+[str(name)]
            log.write('COMMAND '+' '.join(cmd)+'\n')
            p=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            log.write(p.stdout)
            assert p.returncode!=0 and 'XW_INVALID_COMPUTE_PARAMETERS' in p.stdout
            log.write('PASS expected invalid MAX_K '+value+' elaboration failure\n')
    print('PASS independent HDL review and 2 parameter guards')

if __name__=='__main__':main()
