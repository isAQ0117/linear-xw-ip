`timescale 1ns/1ps
module tb_xw_scale_group_cache;
    reg clk,rst_n,load_begin;
    reg [15:0] load_words,load_scales;
    reg wr_valid;
    reg [511:0] wr_data;
    reg [15:0] wr_word_index;
    wire loaded,cache_error;
    reg rd_req;
    reg [15:0] rd_scale_index;
    wire rd_valid;
    wire [31:0] rd_scale_bits;
    xw_scale_group_cache #(.MAX_K(4096)) dut (
        .clk(clk),.rst_n(rst_n),.load_begin(load_begin),
        .load_words(load_words),.load_scales(load_scales),
        .wr_valid(wr_valid),.wr_data(wr_data),.wr_word_index(wr_word_index),
        .loaded(loaded),.cache_error(cache_error),
        .rd_req(rd_req),.rd_scale_index(rd_scale_index),
        .rd_valid(rd_valid),.rd_scale_bits(rd_scale_bits)
    );
    initial clk=0;
    always #5 clk=~clk;
    initial begin
        rst_n=0;load_begin=0;load_words=0;load_scales=0;
        wr_valid=0;wr_data=0;wr_word_index=0;rd_req=0;rd_scale_index=0;
        repeat(2) @(negedge clk);
        rst_n=1;
        @(negedge clk);
        load_begin=1;load_words=16'd2;load_scales=16'd17;
        @(negedge clk);
        load_begin=0;wr_valid=1;wr_word_index=16'd0;
        wr_data={16{32'h3f800000}};
        @(negedge clk);
        wr_word_index=16'd1;wr_data=512'd0;wr_data[31:0]=32'h3f80624e;
        @(posedge clk);#1;
        if (!loaded || cache_error) begin
            $display("FAIL scale cache loading");$finish;
        end
        @(negedge clk);
        wr_valid=0;rd_req=1;rd_scale_index=16'd16;
        @(posedge clk);#1;
        if (!rd_valid || rd_scale_bits !== 32'h3f80624e) begin
            $display("FAIL FP32 scale cache read 16");$finish;
        end
        @(negedge clk);rd_scale_index=16'd0;
        @(posedge clk);#1;
        if (!rd_valid || rd_scale_bits !== 32'h3f800000) begin
            $display("FAIL FP32 scale cache read zero");$finish;
        end
        $display("PASS tb_xw_scale_group_cache");
        $finish;
    end
endmodule
