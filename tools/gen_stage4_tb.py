#!/usr/bin/env python3
"""Emit style-compliant pure Verilog2001 PRE/NBA self-checking benches."""
import re
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
NAMES=['xw_b1_dot128','xw_b2_fp32_pipe','xw_a2_accum48']


def ports(name):
    path=ROOT/'rtl'/f'{name}.v'
    if name=='xw_stage234_harness':path=ROOT/'tb/support'/f'{name}.v'
    return [(d,n,int(h)+1 if h else 1) for d,h,n in re.findall(
        r'^\s*(input|output)\s+(?:wire|reg)\s+(?:signed\s+)?(?:\[(\d+):0\]\s+)?(\w+)\s*[,\)]',path.read_text(),re.M)]


def bench(name):
    ps=ports(name);ins=[(n,w) for d,n,w in ps if d=='input' and n!='clk'];outs=[(n,w) for d,n,w in ps if d=='output']
    concat=lambda fs:'{'+', '.join(n for n,w in fs)+'}'
    decl='\n'.join(f'    {"reg " if d=="input" else "wire"} [{w-1}:0] {n};' for d,n,w in ps)
    pins=',\n'.join(f'        .{n}({n})' for d,n,w in ps)
    trace=''
    trace_pre=''
    if name=='xw_stage234_harness':
        trace_pre=r'''
            if (rst_n && dut.storage.local_rst_n) begin
                if (compute_valid && compute_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"COMPUTE_ACCEPT\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"k\":%0d}", cycles, compute_job, compute_channel, compute_channel[15:7], compute_k);
                if (dut.core.x_rd_req)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RAM_READ\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d,\"slice\":%0d,\"index\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.block_index, dut.core.issued, dut.core.x_rd_index);
                if (dut.core.b1_input && dut.core.b1_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"B1_ACCEPT\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d,\"slice\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.head_block, dut.core.head_slice);
                if (dut.core.b1_valid && dut.core.b1_out_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"B2_ACCEPT\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.b1_block);
                if (dut.core.accumulator.in_valid && dut.core.accumulator.in_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"A2_ACCEPT\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.b2_block);
                if (result_valid && result_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RESULT_ACCEPT\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d}", cycles, result_job, result_channel, result_channel[15:7]);
            end
'''
        trace=r'''
            if (rst_n) begin
                if (dut.core.b1_valid && !previous_b1)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"B1_VALID\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d,\"raw\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.b1_block, $signed(dut.core.b1_raw));
                if (dut.core.b2_valid && !previous_b2)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"B2_VALID\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d,\"term_mant_hex\":\"%h\",\"term_exp\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.b2_block, dut.core.b2_mant, $signed(dut.core.b2_exp));
                if (dut.core.a2_update)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"A2_UPDATE\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d,\"mant\":%0d,\"exp\":%0d,\"special\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.a2_block, $signed(dut.core.a2_mant), $signed(dut.core.a2_exp), dut.core.a2_special);
            end
            if (rst_n && dut.storage.local_rst_n && result_valid && !previous_result)
                $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RESULT_VALID\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"mant\":%0d,\"exp\":%0d}", cycles, result_job, result_channel, result_channel[15:7], $signed(result_mant), $signed(result_exp));
            if (rst_n && dut.storage.local_rst_n && dut.core.active) begin
                if (dut.core.fifo_count + dut.core.pending > 4) begin
                    $display("FAIL actual FIFO reservation overflow"); $finish;
                end
                $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"FIFO_LEVEL\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d,\"count\":%0d,\"pending\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.block_index, dut.core.fifo_count, dut.core.pending);
            end
            previous_result = rst_n && result_valid;
            previous_b1 = rst_n && dut.core.b1_valid;
            previous_b2 = rst_n && dut.core.b2_valid;
'''
    trace_decl='    integer trace_fd;\n    reg [4095:0] trace_path;\n    reg previous_b1;\n    reg previous_b2;\n    reg previous_result;\n' if trace else ''
    trace_init='''        previous_b1 = 0;
        previous_b2 = 0;
        previous_result = 0;
        if (!$value$plusargs("TRACE=%s", trace_path)) begin
            $display("FAIL missing TRACE"); $finish;
        end
        trace_fd = $fopen(trace_path, "w");
        if (!trace_fd) begin $display("FAIL trace open"); $finish; end
''' if trace else ''
    return f'''`timescale 1ns / 1ps
/* 自动生成；完整比较沿前组合输出及沿后NBA，期望另经数学Golden检查。 */
module tb_{name}_cycle;
    /* 驱动与观测端口。 */
{decl}
    reg [{sum(w for n,w in ins)-1}:0] stimulus;
    reg [{sum(w for n,w in outs)-1}:0] expected_pre;
    reg [{sum(w for n,w in outs)-1}:0] expected_post;
    reg [4095:0] vector_path;
    integer fd;
    integer scanned;
    integer cycles;
{trace_decl}
    {name} dut (
{pins}
    );

    /* 统一时钟。 */
    always #5 clk = ~clk;

    /* 仿真超时必须失败，禁止用挂起冒充错误处理。 */
    initial begin
        #100000000;
        $display("FAIL timeout");
        $finish;
    end

    /* 在下降沿驱动，稳定后比较PRE，上升沿后比较NBA。 */
    initial begin
        clk = 0;
        rst_n = 1;
        cycles = 0;
{trace_init}        if (!$value$plusargs("VECTORS=%s", vector_path)) begin
            $display("FAIL missing VECTORS"); $finish;
        end
        fd = $fopen(vector_path, "r");
        if (!fd) begin $display("FAIL vectors open"); $finish; end
        while (!$feof(fd)) begin
            scanned = $fscanf(fd, "%h %h %h\\n", stimulus, expected_pre, expected_post);
            if (scanned != 3) begin $display("FAIL malformed vectors"); $finish; end
            @(negedge clk);
            {concat(ins)} = stimulus;
            #1;
            if ({concat(outs)} !== expected_pre) begin
                $display("FAIL {name} PRE cycle=%0d actual=%h expected=%h", cycles, {concat(outs)}, expected_pre);
                $finish;
            end
            @(posedge clk);
{trace_pre}            #1;
            if ({concat(outs)} !== expected_post) begin
                $display("FAIL {name} NBA cycle=%0d actual=%h expected=%h", cycles, {concat(outs)}, expected_post);
                $finish;
            end
{trace}            cycles = cycles + 1;
        end
        $fclose(fd);
        if (cycles < 5) begin $display("FAIL empty vectors"); $finish; end
        $display("PASS tb_{name}_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
'''


if __name__=='__main__':
    names=NAMES+([n for n in ['xw_b3b_compute_ctrl','xw_stage234_harness'] if (ROOT/('rtl' if n!='xw_stage234_harness' else 'tb/support')/(n+'.v')).exists()])
    for n in names:
        p=ROOT/'tb'/f'tb_{n}_cycle.v';txt=bench(n)
        if '--check' in sys.argv:assert p.read_text()==txt
        else:p.write_text(txt)
    print('PASS Stage4 generated benches',len(names))
