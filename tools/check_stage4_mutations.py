#!/usr/bin/env python3
"""Negative HDL experiments: retained tests must detect deliberately broken RTL.

Mutants stay under sim_build; production files are never overwritten.
"""
import subprocess,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent


def main():
    build=ROOT/'sim_build/stage4';mutdir=build/'mutations';mutdir.mkdir(parents=True,exist_ok=True)
    cases=[
      ('masked_nan','xw_b1_dot128','b1',"in_mask[lane] && (in_w[lane*8 +: 7]", "1'b1 && (in_w[lane*8 +: 7]"),
      ('negative_boundary','xw_a2_accum48','a2',"(negative && selected_power)","(1'b0 && selected_power)"),
      ('lost_remote_sticky','xw_a2_accum48','a2','sticky <= low_sticky;','sticky <= 0;'),
      ('fifo_ignores_inflight','xw_b3b_compute_ctrl','controller',"({1'b0, fifo_count} + pending < 4)","({1'b0, fifo_count} < 4)")]
    report=[]
    with (ROOT/'docs/stage4/logs/mutation_hdl.log').open('w') as log:
        for name,module,label,old,new in cases:
            text=(ROOT/'rtl'/(module+'.v')).read_text();assert old in text,name
            path=mutdir/(name+'.v');path.write_text(text.replace(old,new));binary=mutdir/(name+'.vvp')
            cmd=['iverilog','-g2001','-s','tb_'+module+'_cycle','-o',str(binary)]
            cmd += [str(p) for p in sorted((ROOT/'rtl').glob('*.v')) if p.stem!=module]+[str(path),'tb/tb_'+module+'_cycle.v']
            log.write('COMMAND '+' '.join(cmd)+'\n');log.flush()
            p=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            log.write(p.stdout);assert p.returncode==0,p.stdout
            cmd=['vvp',str(binary),'+VECTORS='+str(build/(label+'.vec'))]
            log.write('COMMAND '+' '.join(cmd)+'\n');log.flush()
            p=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
            log.write(p.stdout)
            assert p.returncode==0 and ('FAIL '+module+' ') in p.stdout and ('PASS tb_'+module+'_cycle') not in p.stdout,(name,p.stdout)
            log.write('PASS expected mutant rejected: '+name+'\n');log.flush()
            report.append(dict(name=name,expected='FAIL from real HDL self-check',result='PASS_MUTANT_REJECTED'))
    (ROOT/'docs/stage4/MUTATION_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS 4 deliberate RTL mutants rejected by retained HDL tests')

if __name__=='__main__':main()
