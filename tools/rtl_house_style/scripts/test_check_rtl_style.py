#!/usr/bin/env python3
"""Unit tests for conservative style checking."""
import tempfile
import unittest
from pathlib import Path

from check_rtl_style import check_one, mask_noncode, port_items, find_modules

GOOD = '''`timescale 1ns / 1ps
module mymod #(
    parameter integer W = 5
) (
    input  wire         clk,
    input  wire         rst_n,
    output reg  [W-1:0] data
);
    /* 内部状态 */
    reg [1:0] state;
    wire allow;

    /* 组合就绪判断 */
    assign allow = (state == 0);

    /* 寄存状态和输出 */
    always @(posedge clk) begin
        if (!rst_n) begin
            state <= 0;
            data <= 0;
        end else if (allow) begin
            state <= 1;
            data <= data + 1'b1;
        end
    end
endmodule
'''

BAD = '''module old_style (clk, data);
    input clk;
    output reg data;
    assign x = clk;
    reg later;
    always @(posedge clk) begin
        data <= clk;
    end
endmodule
'''

GENERATE = '''module generated (
    input wire clk,
    output wire out
);
    genvar k;
    generate
        if (1) begin : f
            wire local_w;
            assign local_w = clk;
            assign out = local_w;
        end
    endgenerate
endmodule
'''

INSTANCE = '''module w (
    input wire a,
    output wire b
);
    buf u_buf (b, a);
    wire late;
endmodule
'''


class CheckerTests(unittest.TestCase):
    def check(self, source):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'test.v'
            p.write_text(source, encoding='utf-8')
            return check_one(p)

    def test_good(self):
        self.assertEqual([], self.check(GOOD))

    def test_template(self):
        src = Path(__file__).resolve().parents[1] / 'assets' / 'verilog2001_module_template.v'
        self.assertEqual([], check_one(src))

    def test_bad_nonansi_late_always_comment(self):
        issues = self.check(BAD)
        codes = {i['code'] for i in issues}
        self.assertIn('NON_ANSI_PORT', codes)
        self.assertIn('DECL_AFTER_LOGIC', codes)
        self.assertIn('ALWAYS_COMMENT', codes)

    def test_module_instance_then_wire(self):
        self.assertIn('DECL_AFTER_LOGIC', {i['code'] for i in self.check(INSTANCE)})

    def test_generate_local_declaration_allowed(self):
        self.assertEqual([], self.check(GENERATE))

    def test_comments_masked(self):
        s = '/* always reg */\nwire a; // logic\n'
        c = mask_noncode(s)
        self.assertNotIn('always', c)
        self.assertNotIn('logic', c)
        self.assertIn('wire a;', c)

    def test_verilog2001_only(self):
        s = GOOD.replace('wire allow;', 'logic allow;')
        self.assertIn('SYSTEMVERILOG_ONLY', {i['code'] for i in self.check(s)})

    def test_tabs(self):
        self.assertIn('TAB', {i['code'] for i in self.check(GOOD.replace('    reg [1:0]', '\treg [1:0]'))})

    def test_port_without_explicit_direction(self):
        s = GOOD.replace('input  wire         rst_n,', 'rst_n,')
        self.assertIn('NON_ANSI_PORT', {i['code'] for i in self.check(s)})


if __name__ == '__main__':
    unittest.main()
