`timescale 1ns/1ps
module tb_xw_ddr_range_rx;
    reg clk; reg rst_n;
    reg cmd_valid; wire cmd_ready;
    reg [28:0] cmd_addr_start; reg [28:0] cmd_addr_end;
    reg [15:0] cmd_beats; reg cmd_kind;
    wire ddr_rd_req; wire [28:0] ddr_rd_addra; wire [28:0] ddr_rd_addrb;
    reg ddr_rd_rdy; reg [511:0] ddr_rd_data; reg ddr_rd_vld;
    wire busy; wire word_valid; wire [511:0] word_data;
    wire [15:0] word_index; wire word_kind; wire range_done; wire range_error;

    xw_ddr_range_rx dut (
        .clk(clk),.rst_n(rst_n),.cmd_valid(cmd_valid),.cmd_ready(cmd_ready),
        .cmd_addr_start(cmd_addr_start),.cmd_addr_end(cmd_addr_end),
        .cmd_beats(cmd_beats),.cmd_kind(cmd_kind),
        .ddr_rd_req(ddr_rd_req),.ddr_rd_addra(ddr_rd_addra),
        .ddr_rd_addrb(ddr_rd_addrb),.ddr_rd_rdy(ddr_rd_rdy),
        .ddr_rd_data(ddr_rd_data),.ddr_rd_vld(ddr_rd_vld),
        .busy(busy),.word_valid(word_valid),.word_data(word_data),
        .word_index(word_index),.word_kind(word_kind),
        .range_done(range_done),.range_error(range_error)
    );
    initial clk=1'b0;
    always #5 clk=~clk;

    initial begin
        rst_n=0;cmd_valid=0;cmd_addr_start=0;cmd_addr_end=0;
        cmd_beats=0;cmd_kind=0;ddr_rd_rdy=1;ddr_rd_data=0;ddr_rd_vld=0;
        repeat(2) @(negedge clk);
        rst_n=1;
        @(negedge clk);
        cmd_valid=1;cmd_addr_start=29'h100;cmd_addr_end=29'h108;
        cmd_beats=16'd2;cmd_kind=1'b1;
        ddr_rd_vld=1;ddr_rd_data=512'hdead;
        #1;
        if (ddr_rd_req !== 1'b1 || ddr_rd_addra !== 29'h100 ||
            ddr_rd_addrb !== 29'h108) begin
            $display("FAIL DDR range request");$finish;
        end
        @(posedge clk); #1;
        if (!word_valid || word_index !== 16'd0 ||
            word_data[31:0] !== 32'hdead || !busy || range_done) begin
            $display("FAIL same-cycle first return beat");$finish;
        end
        @(negedge clk);cmd_valid=0;ddr_rd_vld=0;
        @(posedge clk);#1;
        if (word_valid) begin $display("FAIL DDR idle gap");$finish;end
        @(negedge clk);ddr_rd_vld=1;ddr_rd_data=512'hbeef;
        @(posedge clk);#1;
        if (!word_valid || word_index !== 16'd1 ||
            word_data[31:0] !== 32'hbeef ||
            busy || !range_done || range_error) begin
            $display("FAIL DDR last response beat");$finish;
        end
        @(negedge clk);ddr_rd_vld=0;
        @(negedge clk);
        cmd_valid=1;cmd_addr_start=29'h200;cmd_addr_end=29'h200;
        cmd_beats=16'd1;cmd_kind=1'b0;
        ddr_rd_vld=1;ddr_rd_data=512'hface;
        @(posedge clk);#1;
        if (!word_valid || word_index !== 0 || !range_done ||
            word_kind !== 1'b0 || busy) begin
            $display("FAIL one-beat same-cycle range");$finish;
        end
        @(negedge clk);cmd_valid=0;ddr_rd_vld=0;
        $display("PASS tb_xw_ddr_range_rx");
        $finish;
    end
endmodule
