#!/usr/bin/env python3
"""Independent constants, parameter extremes, style, and discriminating mutants."""
import json,subprocess,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tools.run_stage5 import run,LOG,BUILD
from test_stage5 import result_suite,controller_suite


def main():
    sources=[ROOT/'rtl'/(n+'.v') for n in ['xw_output_group_buffer','xw_bfp18_requant','xw_result_buffer','xw_stage5_ctrl']]
    tests=[]
    with (LOG/'review_hdl.log').open('w') as log:
        binary=BUILD/'review.vvp';bench=ROOT/'tb/tb_xw_stage5_review.v'
        run(['iverilog','-g2001','-Wall','-s','tb_xw_stage5_review','-o',binary]+sources+[bench],log)
        run(['vvp','-N',binary],log,pass_marker='PASS tb_xw_stage5_review')
        for mod in ['xw_result_buffer','xw_stage5_ctrl']:
            for n in [0,65536]:
                p=BUILD/f'invalid_{mod}_{n}.v';p.write_text(f'module tb_invalid; {mod} #(.MAX_N({n})) dut (); endmodule\n')
                cmd=['iverilog','-g2001','-s','tb_invalid','-o',BUILD/'bad.vvp']+sources+[p]
                log.write('COMMAND '+' '.join(map(str,cmd))+'\n')
                r=subprocess.run(list(map(str,cmd)),cwd=ROOT,text=True,capture_output=True)
                log.write(r.stdout+r.stderr+'EXIT_CODE '+str(r.returncode)+'\n')
                assert r.returncode and 'XW_INVALID_' in r.stderr
        for label,f,n in [('result_1',result_suite,1),('result_65535',result_suite,65535),('controller_257',controller_suite,257)]:
            t=f(n);v=BUILD/(label+'.vec');t.save(v);binary=BUILD/(label+'.vvp')
            run(['iverilog','-g2001','-Wall','-s','tb_'+t.name+'_cycle','-P',f'tb_{t.name}_cycle.TEST_MAX_N={n}','-o',binary]+sources+[ROOT/'tb'/('tb_'+t.name+'_cycle.v')],log)
            cmd=['vvp','-N',binary,'+VECTORS='+str(v)]
            if label.startswith('controller'):cmd+=['+TRACE='+str(LOG/(label+'_rtl_events.jsonl'))]
            run(cmd,log,pass_marker='PASS tb_'+t.name+'_cycle ')
            if label.startswith('controller'):
                actual=[json.loads(s) for s in (LOG/(label+'_rtl_events.jsonl')).read_text().splitlines()];assert actual==t.events
            tests.append(dict(label=label,max_n=n,cycles=len(t.rows),vector_sha256=hashlib.sha256(v.read_bytes()).hexdigest()))
        # Verify the runner cannot mistake $stop, missing PASS, or FAIL+exit0 for success.
        for label,src in [('stop','initial $stop;'),('missing','initial $finish;'),('fail_zero','initial begin $display("FAIL deliberate"); $finish; end')]:
            p=BUILD/('runner_'+label+'.v');p.write_text('module runner_probe; '+src+' endmodule\n')
            binary=BUILD/('runner_'+label+'.vvp');run(['iverilog','-g2001','-s','runner_probe','-o',binary,p],log)
            try:run(['vvp','-N',binary],log,pass_marker='PASS runner_probe')
            except RuntimeError:log.write('PASS expected runner rejection '+label+'\n')
            else:raise AssertionError('runner accepted '+label)
    original={p.name:p.read_text() for p in sources}
    mutations=[]
    plans=[
        ('tie_even','xw_bfp18_requant.v','guard_bit && (sticky_bit || q[0])','guard_bit && sticky_bit','review'),
        ('symmetric_bound','xw_bfp18_requant.v',"rounded > 19'sd131071 || rounded < -19'sd131071","rounded > 19'sd131072 || rounded < -19'sd131072",'review'),
        ('premature_exp','xw_bfp18_requant.v','                        state <= S_READ;',"                        state <= S_READ;\n                        if (nonzero && hmax - 18'sd16 < -18'sd128) begin\n                            fault <= 1;\n                            error_code <= 8'h33;\n                        end",'review'),
        ('double_round','xw_bfp18_requant.v','            quantize = mant[47]',"            if (retried && delta > 1 && delta < 48 && mag != 0) begin\n                q = mag >> (amount - 1'b1);\n                guard_bit = mag[amount - 2'd2];\n                sticky_bit = (mag << (6'd50 - amount)) != 0;\n                if (guard_bit && (sticky_bit || q[0])) q = q + 1'b1;\n                q = (q >> 1) + (q[0] && q[1]);\n            end\n            quantize = mant[47]",'review'),
        ('early_publish','xw_result_buffer.v','assign job_results_ready = enable && visible;','assign job_results_ready = enable && (visible || committed_count != 0);','controller'),
        ('tail_stale','xw_result_buffer.v',"q_index[2:0] == 0 ? 144'd0 : pack_data", "q_index[2:0] == 0 ? 144'hdeadbeef0000000000000000000000000000 : pack_data",'review')]
    for label,name,old,new,kind in plans:
        folder=BUILD/'mutations'/label;folder.mkdir(parents=True,exist_ok=True)
        assert original[name].count(old)==1,(label,original[name].count(old))
        paths=[]
        for p in sources:
            q=folder/p.name;q.write_text(original[p.name].replace(old,new) if p.name==name else original[p.name]);paths.append(q)
        top='tb_xw_stage5_review' if kind=='review' else 'tb_xw_stage5_ctrl_cycle'
        binary=folder/'dut.vvp'
        with (LOG/('mutation_'+label+'.log')).open('w') as log:
            run(['iverilog','-g2001','-s',top,'-o',binary]+paths+[ROOT/'tb'/(top+'.v')],log)
            cmd=['vvp','-N',binary]
            if kind=='controller':cmd+=['+VECTORS='+str(BUILD/'controller.vec'),'+TRACE='+str(folder/'events.jsonl')]
            p=subprocess.run(list(map(str,cmd)),cwd=ROOT,text=True,capture_output=True,timeout=120)
            log.write('COMMAND '+' '.join(map(str,cmd))+'\n'+p.stdout+p.stderr+'EXIT_CODE '+str(p.returncode)+'\n')
            assert p.returncode!=0 and 'FAIL' in p.stdout,(label,p.returncode,p.stdout[-4000:])
            mutations.append(dict(name=label,status='EXPECTED_REJECTION',exit_code=p.returncode))
    report=dict(status='PASS',directed_constants='PASS',parameter_guards=4,alternate_parameter_tests=tests,runner_rejections=3,mutations=mutations)
    (ROOT/'docs/stage5/REVIEW_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS independent review, 4 parameter guards, 3 alternate configurations, 3 runner probes, 6 mutants')
if __name__=='__main__':main()
