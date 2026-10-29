#!/usr/bin/env python3
"""Generate generic self-checking Verilog-2001 PRE/NBA lockstep benches."""
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SOURCES = {name: ROOT/'rtl'/f'{name}.v' for name in
           ('xw_axis_bfp18_input','xw_activation_buffer','xw_weight_row_buffer','xw_ddr_addr_gen',
            'xw_ddr_range_rx','xw_scale_group_cache')}
SOURCES['xw_stage23_harness'] = ROOT/'tb/support/xw_stage23_harness.v'
PARAMS = {
    'xw_axis_bfp18_input': '.MAX_K(65535)',
    'xw_activation_buffer': '.MAX_K(65535)',
    'xw_weight_row_buffer': '.MAX_K(65535)',
    'xw_ddr_addr_gen': '.MAX_N(65535), .MAX_K(65535), .DDR_MAX_BURST_BEATS(BURST)',
    'xw_scale_group_cache': '.MAX_K(65535)',
    'xw_stage23_harness': '.MAX_N(129), .MAX_K(12288), .DDR_MAX_BURST_BEATS(BURST), .STATIC_DIM_MODE(STATIC_MODE)'
}


def ports(name):
    return [(direction, port, int(hi)+1 if hi else 1) for direction,hi,port in
            re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(?:\[(\d+):0\]\s+)?(\w+)\s*[,\)]',
                       SOURCES[name].read_text(), re.M)]


def bench(name):
    ps = ports(name)
    ins = [(p,w) for d,p,w in ps if d=='input' and p!='clk']
    outs = [(p,w) for d,p,w in ps if d=='output']
    iw, ow = sum(w for p,w in ins), sum(w for p,w in outs)
    concat = lambda p: '{' + ', '.join(x for x,w in p) + '}'
    declarations = '\n'.join(f'    {"reg " if d=="input" else "wire"} [{w-1}:0] {p};' for d,p,w in ps)
    pins = ',\n        '.join(f'.{p}({p})' for d,p,w in ps)
    param = '#('+PARAMS[name]+')' if name in PARAMS else ''
    trace_decl = trace_init = trace_pre = trace_post = trace_close = ''
    if name == 'xw_stage23_harness':
        trace_decl = '''    integer trace_fd;
    reg [4095:0] trace_path;
    reg [31:0] trace_job;
    reg trace_owner;
    reg trace_fault;
'''
        trace_init = '''        trace_fd = 0; trace_job = 0; trace_owner = 0; trace_fault = 0;
        if ($value$plusargs("TRACE=%s", trace_path)) begin
            trace_fd = $fopen(trace_path, "w");
            if (trace_fd == 0) begin $display("FAIL trace open"); $finish; end
        end
'''
        # JSON is emitted from ACTUAL sampled RTL, independently of Python.
        trace_pre = r'''            if (!dut.local_rst_n) begin
                trace_owner = 0; trace_job = 0; trace_fault = 0;
            end
            if (trace_fd && dut.local_rst_n) begin
                if (job_valid && job_ready) begin
                    trace_owner = 1; trace_job = job_id;
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"JOB_ACCEPT\",\"job_id\":%0d}", cycles, trace_job);
                end
                if (s_axis_tvalid && s_axis_tready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"AXIS_IN_ACCEPT\",\"job_id\":%0d,\"row\":0,\"group\":%0d,\"offset\":%0d}", cycles, trace_job, s_axis_tuser[56:48], s_axis_tuser[87:80]);
                if (object_valid && object_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"CACHE_OBJECT_ACCEPT\",\"job_id\":%0d,\"kind\":%0d,\"index\":%0d}", cycles, trace_job, object_kind, object_index);
                if (dut.scale_begin || dut.weight_begin)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"CACHE_INIT\",\"job_id\":%0d,\"kind\":%0d,\"words\":%0d}", cycles, trace_job, dut.weight_begin, dut.load_words);
                if (ddr_rd_req && ddr_rd_rdy)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"DDR_REQ_ACCEPT\",\"job_id\":%0d,\"kind\":%0d,\"start\":%0d,\"end\":%0d,\"beats\":%0d,\"segment_offset\":%0d}", cycles, trace_job, dut.cmd_kind, ddr_rd_addra, ddr_rd_addrb, dut.cmd_beats, dut.offset);
                if (ddr_rd_vld) begin
                    if (trace_owner)
                        $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"DDR_BEAT\",\"job_id\":%0d,\"kind\":%0d,\"beat_index\":%0d,\"logical_word_index\":%0d}", cycles, trace_job, dut.receiver.busy ? dut.receiver.active_kind : dut.cmd_kind, dut.receiver.busy ? dut.receiver.received_count : 0, dut.offset + (dut.receiver.busy ? dut.receiver.received_count : 0));
                    else
                        $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"DDR_BEAT\",\"job_id\":null,\"owned\":false}", cycles);
                end
                if (dut.word_valid && !dut.fatal)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"BUFFER_WRITE\",\"job_id\":%0d,\"kind\":%0d,\"logical_word_index\":%0d}", cycles, trace_job, dut.word_kind, dut.logical_index);
                if (result_valid && result_ready) begin
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"CACHE_TEST_RESULT_ACCEPT\",\"job_id\":%0d,\"error_code\":%0d}", cycles, trace_job, result_code);
                    trace_owner = 0;
                end
            end
'''
        trace_post = r'''            if (trace_fd && dut.local_rst_n) begin
                if (dut.range_done)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RANGE_DONE\",\"job_id\":%0d,\"kind\":%0d,\"beat_index\":%0d}", cycles, trace_job, dut.word_kind, dut.word_index);
                if (object_done)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"CACHE_OBJECT_DONE\",\"job_id\":%0d,\"kind\":%0d}", cycles, trace_job, dut.cmd_kind);
                if (fault_lock && !trace_fault) begin
                    if (trace_owner)
                        $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"FAULT_LOCK\",\"job_id\":%0d,\"error_code\":%0d,\"fault_lock\":true}", cycles, trace_job, dut.fatal_code);
                    else
                        $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"FAULT_LOCK\",\"job_id\":null,\"error_code\":%0d,\"fault_lock\":true}", cycles, dut.fatal_code);
                end
                trace_fault = fault_lock;
            end
'''
        trace_close = '        if (trace_fd) $fclose(trace_fd);\n'
    return f'''`timescale 1ns/1ps
// Auto-generated by tools/gen_stage23_tb.py; actual DUT PRE/NBA lockstep.
// Expected records are additionally checked against independent source data.
module tb_{name}_cycle;
    parameter integer BURST = 3;
    parameter integer STATIC_MODE = 0;
{declarations}
    reg [{iw-1}:0] stimulus;
    reg [{ow-1}:0] expected_pre, expected_post;
    reg [4095:0] vector_path;
    integer fd, scan_count, cycles;
{trace_decl}    {name} {param} dut (
        {pins}
    );
    initial clk = 0;
    always #5 clk = ~clk;
    initial begin
        #100000000;
        $display("FAIL tb_{name}_cycle TIMEOUT");
        $finish;
    end
    initial begin
        rst_n = 1;
        cycles = 0;
{trace_init}        if (!$value$plusargs("VECTORS=%s", vector_path)) begin
            $display("FAIL missing VECTORS"); $finish;
        end
        fd = $fopen(vector_path, "r");
        if (fd == 0) begin $display("FAIL cannot open vectors"); $finish; end
        while (!$feof(fd)) begin
            scan_count = $fscanf(fd, "%h %h %h\\n", stimulus, expected_pre, expected_post);
            if (scan_count != 3) begin $display("FAIL malformed vector cycle=%0d", cycles); $finish; end
            @(negedge clk);
            {concat(ins)} = stimulus;
            #1;
            if ({concat(outs)} !== expected_pre) begin
                $display("FAIL tb_{name}_cycle PRE cycle=%0d", cycles);
                $display("actual=%h expected=%h", {concat(outs)}, expected_pre);
                $finish;
            end
            @(posedge clk);
{trace_pre}            #1;
            if ({concat(outs)} !== expected_post) begin
                $display("FAIL tb_{name}_cycle NBA cycle=%0d", cycles);
                $display("actual=%h expected=%h", {concat(outs)}, expected_post);
                $finish;
            end
{trace_post}            cycles = cycles + 1;
        end
        $fclose(fd);
{trace_close}        if (cycles < 5) begin $display("FAIL empty coverage"); $finish; end
        $display("PASS tb_{name}_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
'''


if __name__ == '__main__':
    check = '--check' in sys.argv
    for name in SOURCES:
        path = ROOT/'tb'/f'tb_{name}_cycle.v'
        text = bench(name)
        if check:
            assert path.read_text() == text, str(path)
        else:
            path.write_text(text)
    print('PASS generated 7 self-checking cycle testbenches' if not check else 'PASS 7 cycle testbenches reproducible')
