#!/usr/bin/env python3
"""Canonical Stage4 checks outside its register-vector simulation runner."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from tools.run_stage67 import execute,LOG
jobs=[('generated23',[sys.executable,'tools/gen_stage23_tb.py','--check'],None),
      ('generated4',[sys.executable,'tools/gen_stage4_tb.py','--check'],None),
      ('stage4_numeric',[sys.executable,'-m','unittest','-v','test_stage4_numeric'],'OK'),
      ('stage4_review',[sys.executable,'tools/run_stage4_review.py'],'PASS independent HDL review'),
      ('stage4_mutations',[sys.executable,'tools/check_stage4_mutations.py'],None),
      ('stage4_performance',[sys.executable,'tools/report_stage4_performance.py'],None)]
report=[]
for label,cmd,marker in jobs:
    with (LOG/('baseline_'+label+'.log')).open('w') as f:execute(cmd,f,marker,timeout=1200)
    report.append(dict(label=label,status='PASS'));print('PASS baseline extra',label,flush=True)
(ROOT/'docs/stage67/BASELINE_EXTRA.json').write_text(json.dumps(report,indent=2)+'\n')
