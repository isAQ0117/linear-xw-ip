#!/usr/bin/env python3
"""Independent review TB must reject deliberately restored P0 bugs."""
import os
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent
build=root/'sim_build/stage23';build.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,TMPDIR=str(build))
with (root/'docs/stage23/logs/review_mutation_hdl.log').open('w') as log:
    for name,module in [('P0-01','xw_activation_buffer'),('P0-02','xw_ddr_addr_gen')]:
        source=(root/'rtl'/f'{module}.v').read_text()
        if name=='P0-01':
            old="if (invalid_write) begin\n                    fault <= 1'b1;\n                    error_code <= 8'h40;"
            new=old.replace("8'h40", "8'h23")
        else:
            old='assign load_done = load_done_reg && !blocked;'
            new='assign load_done = load_done_reg;'
        assert old in source
        mutant=build/f'{name}_mutant.v';mutant.write_text(source.replace(old,new))
        binary=build/f'{name}_mutant.vvp'
        sources=[str(p) for p in (root/'rtl').glob('*.v') if p.stem!=module]
        subprocess.run(['iverilog','-g2001','-s','tb_xw_stage23_review','-o',str(binary),
                        *sources,str(mutant),'tb/support/xw_stage23_harness.v','tb/tb_xw_stage23_review.v'],
                       cwd=root,env=env,check=True,capture_output=True,text=True)
        p=subprocess.run(['vvp',str(binary)],cwd=root,env=env,capture_output=True,text=True,timeout=30)
        log.write(name+' deliberately regressed output:\n'+p.stdout)
        assert 'FAIL '+name in p.stdout and 'PASS tb_xw_stage23_review' not in p.stdout,p.stdout
        log.write('PASS: independent TB rejects '+name+' regression\n')
print('PASS two P0 regression mutants rejected by independent HDL test')
