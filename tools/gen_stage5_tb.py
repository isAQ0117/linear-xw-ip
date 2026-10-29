#!/usr/bin/env python3
"""Generate pure Verilog-2001 fail-closed PRE/NBA benches, with real RTL trace."""
import re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
NAMES=['xw_output_group_buffer','xw_bfp18_requant','xw_result_buffer','xw_stage5_ctrl','xw_stage45_harness']

def ports(name):
    p=ROOT/('tb/support' if name.endswith('harness') else 'rtl')/(name+'.v')
    return [(d,n,int(w)+1 if w else 1) for d,w,n in re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(?:signed\s+)?(?:\[(\d+):0\]\s+)?(\w+)\s*[,\)]',p.read_text(),re.M)]

def bench(name):
    ps=ports(name);ins=[(n,w) for d,n,w in ps if d=='input' and n!='clk'];outs=[(n,w) for d,n,w in ps if d=='output']
    concat=lambda fs:'{'+', '.join(n for n,w in fs)+'}'
    decl='\n'.join(f'    {"reg " if d=="input" else "wire"} [{w-1}:0] {n};' for d,n,w in ps)
    pins=',\n'.join(f'        .{n}({n})' for d,n,w in ps)
    monitor=''
    postmonitor=''
    if name in ['xw_stage5_ctrl','xw_stage45_harness']:
        root='dut' if name=='xw_stage5_ctrl' else 'dut.stage5'
        c=root
        fields=lambda event,args,fmt:f'$fdisplay(trace_fd, "{{\\"cycle\\":%0d,\\"event\\":\\"{event}\\",\\"job_id\\":%0d,\\"group\\":%0d{fmt}}}", cycles, {args});'
        base=f'{c}.active_job, {c}.current_group'
        monitor=f'''
            if (rst_n) begin
                if ({c}.start_accept)
                    {fields('JOB_ACCEPT',f'{c}.job_id, 0, {c}.job_n',',\\"n\\":%0d')}
                if ({c}.result_valid && {c}.result_ready)
                    {fields('RESULT_ACCEPT',f'{c}.result_job, {c}.result_channel >> 7, {c}.result_channel, $signed({c}.result_mant), $signed({c}.result_exp)',',\\"channel\\":%0d,\\"mant\\":%0d,\\"exp\\":%0d')}
                if ({c}.attempt_begin)
                    {fields('ATTEMPT_BEGIN',base+f', {c}.quant_start ? 0 : {c}.retried',',\\"retry\\":%0d')}
                if ({c}.ram_req)
                    {fields('GROUP_RAM_READ',base+f', {c}.ram_index',',\\"index\\":%0d')}
                if ({c}.q_valid)
                    {fields('QUANT_ACCEPT',base+f', {c}.q_index, $signed({c}.q_mant), {c}.q_last, {c}.retried',',\\"index\\":%0d,\\"mant\\":%0d,\\"last\\":%0d,\\"retry\\":%0d')}
                if ({c}.result_buffer.write_enable)
                    {fields('RESULT_WORD_WRITE',base+f', {c}.result_buffer.write_index, {c}.result_buffer.assembled',',\\"index\\":%0d,\\"data_hex\\":\\"%h\\"')}
                if ({c}.result_buffer.commit_enable)
                    {fields('GROUP_COMMIT',base+f', $signed({c}.quant_exp)',',\\"exp\\":%0d')}
            end
'''
        postmonitor=f'''
            if (rst_n) begin
                if ({c}.q_valid)
                    {fields('QUANT_VALID',base+f', {c}.q_index, $signed({c}.q_mant), {c}.retried',',\\"index\\":%0d,\\"mant\\":%0d,\\"retry\\":%0d')}
                if ({c}.quant_done)
                    {fields('REQUANT_DONE',base+f', $signed({c}.quant_exp)',',\\"exp\\":%0d')}
                if ({c}.rd_valid)
                    {fields('RESULT_READ',f'{c}.active_job, {c}.rd_index >> 4, {c}.rd_index, {c}.rd_data, $signed({c}.rd_exp), {c}.rd_mask',',\\"index\\":%0d,\\"data_hex\\":\\"%h\\",\\"exp\\":%0d,\\"mask\\":%0d')}
                if ({c}.group_done)
                    {fields('GROUP_REQUANT',f'{c}.group_job, {c}.group_id, {c}.group_len, $signed({c}.group_exp)',',\\"length\\":%0d,\\"exp\\":%0d')}
                if ({c}.job_results_ready && !previous_visible)
                    {fields('JOB_RESULTS_READY',base,'')}
                if ({c}.error_valid && !previous_error)
                    {fields('ERROR',base+f', {c}.error_code, {c}.fault_lock',',\\"code\\":%0d,\\"lock\\":%0d')}
            end
            previous_visible = {c}.job_results_ready;
            previous_error = {c}.error_valid;
'''
    parameter_decl='    parameter integer TEST_MAX_N = 12288;\n' if name in ['xw_result_buffer','xw_stage5_ctrl'] else ''
    parameter_inst=' #(.MAX_N(TEST_MAX_N))' if parameter_decl else ''
    td='    integer trace_fd;\n    reg [4095:0] trace_path;\n    reg previous_visible;\n    reg previous_error;\n' if monitor else ''
    ti='''        previous_visible = 0;
        previous_error = 0;
        if (!$value$plusargs("TRACE=%s", trace_path)) begin
            $display("FAIL missing TRACE"); $stop;
        end
        trace_fd = $fopen(trace_path, "w");
        if (!trace_fd) begin $display("FAIL trace open"); $stop; end
''' if monitor else ''
    return f'''`timescale 1ns / 1ps
/* 自动生成：下降沿驱动，上升沿前后逐拍检查；vvp -N使$stop非零退出。 */
module tb_{name}_cycle;
{parameter_decl}    /* 全端口驱动与期望。 */
{decl}
    reg [{sum(w for n,w in ins)-1}:0] stimulus;
    reg [{sum(w for n,w in outs)-1}:0] expected_pre;
    reg [{sum(w for n,w in outs)-1}:0] expected_post;
    reg [4095:0] vector_path;
    integer fd;
    integer scanned;
    integer cycles;
{td}
    {name}{parameter_inst} dut (
{pins}
    );

    /* 公共时钟。 */
    always #5 clk = ~clk;

    /* 仿真级硬超时。 */
    initial begin
        #100000000;
        $display("FAIL timeout");
        $stop;
    end

    /* 同时比较所有公开输出，不能将软件PASS充当HDL结果。 */
    initial begin
        clk = 0;
        rst_n = 1;
        cycles = 0;
{ti}        if (!$value$plusargs("VECTORS=%s", vector_path)) begin
            $display("FAIL missing VECTORS"); $stop;
        end
        fd = $fopen(vector_path, "r");
        if (!fd) begin $display("FAIL vector open"); $stop; end
        while (!$feof(fd)) begin
            scanned = $fscanf(fd, "%h %h %h\\n", stimulus, expected_pre, expected_post);
            if (scanned != 3) begin $display("FAIL malformed vectors"); $stop; end
            @(negedge clk);
            {concat(ins)} = stimulus;
            #1;
            if ({concat(outs)} !== expected_pre) begin
                $display("FAIL {name} PRE cycle=%0d actual=%h expected=%h", cycles, {concat(outs)}, expected_pre);
                $stop;
            end
            @(posedge clk);
{monitor}            #1;
            if ({concat(outs)} !== expected_post) begin
                $display("FAIL {name} NBA cycle=%0d actual=%h expected=%h", cycles, {concat(outs)}, expected_post);
                $stop;
            end
{postmonitor}            cycles = cycles + 1;
        end
        $fclose(fd);
        if (cycles < 5) begin $display("FAIL empty vectors"); $stop; end
        $display("PASS tb_{name}_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
'''

def main():
    for name in NAMES:
        p=ROOT/'tb'/('tb_'+name+'_cycle.v');s=bench(name)
        if '--check' in sys.argv:assert p.read_text()==s,p
        else:p.write_text(s)
    print('PASS Stage5 generated benches',len(NAMES))
if __name__=='__main__':main()
