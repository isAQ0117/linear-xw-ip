#!/usr/bin/env python3
"""Independent known answer, illegal configurations and discriminating RTL mutants."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from tools.run_stage67 import execute,BUILD,LOG

def known_answer():
    with (LOG/'known_answer.log').open('w') as f:
        execute(['iverilog','-g2001','-DXW_SIM_DDR_BURST=3','-s','tb_linear_xw_ip_known_answer','-o',BUILD/'known.vvp','-f','rtl_sources.f','tb/tb_linear_xw_ip_known_answer.v'],f)
        execute(['vvp','-N',BUILD/'known.vvp'],f,'PASS tb_linear_xw_ip_known_answer')

def main():
    BUILD.mkdir(parents=True,exist_ok=True);LOG.mkdir(parents=True,exist_ok=True);known_answer()
    guards=[];sources=sorted((ROOT/'rtl').glob('*.v'))
    plans=[('missing_profile',[],''),('ambiguous',['-DXW_SIM_DDR_BURST=3','-DXW_PLATFORM_DDR_BURST=2'],''),
           ('zero_burst',['-DXW_SIM_DDR_BURST=0'],''),('large_burst',['-DXW_SIM_DDR_BURST=65536'],''),
           ('bad_pk',['-DXW_SIM_DDR_BURST=3'],'.P_K(4)'),('bad_pn',['-DXW_SIM_DDR_BURST=3'],'.P_N(2)'),
           ('bad_axis',['-DXW_SIM_DDR_BURST=3'],'.AXIS_DATA_W(256)'),('bad_mode',['-DXW_SIM_DDR_BURST=3'],'.STATIC_DIM_MODE(2)'),
           ('bad_output_capacity',['-DXW_SIM_DDR_BURST=3'],'OUTPUT_0')]
    for name,defs,param in plans:
        tb=BUILD/(name+'.v')
        if param=='OUTPUT_0':source='module tb_invalid; xw_axis_bfp18_output #(.MAX_N(0)) dut (); endmodule\n'
        else:source='module tb_invalid; linear_xw_ip #(.N_DIM(1), .K_DIM(1)'+(', '+param if param else '')+') dut (); endmodule\n'
        tb.write_text(source);cmd=['iverilog','-g2001',*defs,'-s','tb_invalid','-o',BUILD/'invalid.vvp',*sources,tb]
        p=subprocess.run(list(map(str,cmd)),cwd=ROOT,text=True,capture_output=True)
        (LOG/(name+'.log')).write_text('COMMAND '+' '.join(map(str,cmd))+'\n'+p.stdout+p.stderr+'EXIT_CODE '+str(p.returncode)+'\n')
        assert p.returncode and 'XW_' in p.stderr,(name,p.stderr)
        guards.append(dict(label=name,status='EXPECTED_ELABORATION_REJECTION',exit_code=p.returncode))
    mutants=[
        ('output_overwrite','xw_axis_bfp18_output',"(!m_axis_tvalid || m_axis_tready)","1'b1",'axis_output'),
        ('early_done','xw_axis_bfp18_output','                    if (flush) begin','                    if (flush) begin\n                        if (tensor_last) output_done <= 1;','axis_output'),
        ('always_last','xw_axis_bfp18_output','m_axis_tlast <= group_last;','m_axis_tlast <= 1;','axis_output'),
        ('wrong_offset','xw_axis_bfp18_output',"tensor_last, offset,","tensor_last, rd_word_index[7:0],",'axis_output'),
        ('ignore_result_ready','xw_linear_scheduler','if (result_valid && result_ready)','if (result_valid)','scheduler'),
        ('skip_group_commit','xw_linear_scheduler','state <= S_GROUP;','state <= S_WEIGHT_REQ;','scheduler'),
        ('ignore_stage5_ready','xw_linear_scheduler','datapath_online && stage5_ready && compute_ready','datapath_online && compute_ready','scheduler'),
        ('overwrite_first_error','xw_linear_scheduler','observed_fault && first_error == 0 && state != S_STATUS','observed_fault && state != S_STATUS','scheduler'),
        ('status_drop_stall','xw_job_status','if (status_ready)',"if (1'b1)",'job_status')]
    killed=[]
    for label,mod,old,new,vec in mutants:
        src=ROOT/'rtl'/(mod+'.v');text=src.read_text();assert text.count(old)==1,(label,text.count(old))
        folder=BUILD/'mutations'/label;folder.mkdir(parents=True,exist_ok=True);mut=folder/src.name;mut.write_text(text.replace(old,new))
        binary=folder/'dut.vvp';tb=ROOT/'tb'/('tb_'+mod+'_cycle.v')
        with (LOG/('mutation_'+label+'.log')).open('w') as f:
            execute(['iverilog','-g2001','-DXW_SIM_DDR_BURST=3','-s','tb_'+mod+'_cycle','-o',binary,*[p for p in sources if p!=src],mut,tb],f)
            cmd=['vvp','-N',binary,'+VECTORS='+str(BUILD/(vec+'.vec'))]
            p=subprocess.run(list(map(str,cmd)),cwd=ROOT,text=True,capture_output=True,timeout=120)
            f.write('COMMAND '+' '.join(map(str,cmd))+'\n'+p.stdout+p.stderr+'EXIT_CODE '+str(p.returncode)+'\n')
            assert p.returncode!=0 and 'FAIL' in p.stdout,(label,p.returncode,p.stdout[-2000:])
        killed.append(dict(label=label,status='MUTANT_REJECTED',exit_code=p.returncode))
    with (LOG/'house_style.log').open('w') as f:
        execute([sys.executable,'tools/rtl_house_style/scripts/check_rtl_style.py',*[str(ROOT/'rtl'/(n+'.v')) for n in ['xw_axis_bfp18_output','xw_job_status','xw_linear_scheduler','linear_xw_ip']],
                 *[str(ROOT/'tb'/n) for n in ['tb_xw_axis_bfp18_output_cycle.v','tb_xw_job_status_cycle.v','tb_xw_linear_scheduler_cycle.v','tb_linear_xw_ip_cycle.v','tb_linear_xw_ip_known_answer.v']]],f,'0 style issue(s).')
    report=dict(status='PASS',known_answer='PASS actual RTL 1x1 unity, no cycle model expected answer',guards=guards,mutations=killed,house_style='PASS')
    (ROOT/'docs/stage67/REVIEW_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS independent known-answer,',len(guards),'parameter guards,',len(killed),'mutants, style')
if __name__=='__main__':main()
