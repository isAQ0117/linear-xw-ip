#!/usr/bin/env python3
"""Retest actual uploaded baseline, save exit codes and explicit markers."""
import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from tools.run_stage67 import execute,LOG
LOG.mkdir(parents=True,exist_ok=True)
(ROOT/'sim_build/toolchain/tmp').mkdir(parents=True,exist_ok=True)
os.environ['TMPDIR']=str(ROOT/'sim_build/toolchain/tmp')
jobs=[('stage1',['sh','run_rtl_tb.sh'],'PASS Stage-1 four-module RTL regression'),
      ('stage23',[sys.executable,'tools/run_stage23.py'],None),
      ('stage4',[sys.executable,'tools/run_stage4.py'],None),
      ('stage5',[sys.executable,'tools/run_stage5_all.py'],None)]
report=[]
for label,cmd,marker in jobs:
    with (LOG/('baseline_'+label+'.log')).open('w') as f:execute(cmd,f,marker,timeout=1800)
    report.append(dict(label=label,status='PASS'));print('PASS baseline',label,flush=True)
    (ROOT/'docs/stage67/BASELINE_RETEST.json').write_text(json.dumps(report,indent=2)+'\n')
