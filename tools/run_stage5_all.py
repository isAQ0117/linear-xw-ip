#!/usr/bin/env python3
"""Reproducible Stage5 simulation workflow, explicit commands and exit codes."""
import json,os,platform,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tools.run_stage5 import run,LOG,BUILD

def main():
    LOG.mkdir(parents=True,exist_ok=True);BUILD.mkdir(parents=True,exist_ok=True)
    (ROOT/'docs/stage5/ENVIRONMENT.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),
        tools={n:subprocess.run([n,'-V'],capture_output=True,text=True).stdout.splitlines()[:1] if __import__('shutil').which(n) else 'PENDING' for n in ['iverilog','yosys']},
        vivado='PENDING: not installed, part/constraints not supplied',seeds=['0x5182026','0x5181','0x5183','0x5184','0xDD234'],
        thread_note='No external reviewer or agent delegation; final self-review is internal'),indent=2)+'\n')
    jobs=[('generated_benches',[sys.executable,'tools/gen_stage5_tb.py','--check'],'PASS Stage5 generated benches'),
          ('numeric',[sys.executable,'-m','unittest','-v','test_stage5_numeric'],'OK'),
          ('actual_hdl',[sys.executable,'tools/run_stage5.py'],None),
          ('review_regression',[sys.executable,'tools/run_stage5_review.py'],'PASS independent review'),
          ('performance',[sys.executable,'tools/report_stage5_performance.py'],'PASS actual HDL performance'),
          ('readback',[sys.executable,'tools/check_stage5_readback.py'],'PASS actual Result Buffer readback')]
    for label,cmd,marker in jobs:
        with (LOG/(label+'.log')).open('w') as log:run(cmd,log,timeout=600,pass_marker=marker)
        print('PASS',label,flush=True)
    new=['rtl/xw_output_group_buffer.v','rtl/xw_bfp18_requant.v','rtl/xw_result_buffer.v','rtl/xw_stage5_ctrl.v',
         'tb/support/xw_stage45_harness.v','tb/tb_xw_stage5_review.v']
    new+=['tb/tb_'+n+'_cycle.v' for n in ['xw_output_group_buffer','xw_bfp18_requant','xw_result_buffer','xw_stage5_ctrl','xw_stage45_harness']]
    with (LOG/'style.log').open('w') as log:
        run([sys.executable,'tools/rtl_house_style/scripts/check_rtl_style.py']+new,log,pass_marker='0 style issue(s).')
        run([sys.executable,'tools/rtl_house_style/scripts/test_check_rtl_style.py'],log,pass_marker='OK')
    print('PASS Stage5 HDL/numeric/cycle/review/style workflow; synthesis is a separate target',flush=True)
if __name__=='__main__':main()
