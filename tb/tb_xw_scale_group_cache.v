`timescale 1ns/1ps
// Stage-1 FP32 Scale cache load/read/rollback/fatal contract checks.
module tb_xw_scale_group_cache;
    reg clk, rst_n, load_begin;
    reg [15:0] load_words, load_scales;
    reg wr_valid;
    reg [511:0] wr_data;
    reg [15:0] wr_word_index;
    wire loaded, cache_error;
    wire [7:0] cache_error_code;
    reg rd_req;
    reg [15:0] rd_scale_index;
    wire rd_valid;
    wire [31:0] rd_scale_bits;

    xw_scale_group_cache #(.MAX_K(4096)) dut (
        .clk(clk), .rst_n(rst_n), .load_begin(load_begin),
        .load_words(load_words), .load_scales(load_scales),
        .wr_valid(wr_valid), .wr_data(wr_data),
        .wr_word_index(wr_word_index), .loaded(loaded),
        .cache_error(cache_error), .cache_error_code(cache_error_code),
        .rd_req(rd_req), .rd_scale_index(rd_scale_index),
        .rd_valid(rd_valid), .rd_scale_bits(rd_scale_bits)
    );

    initial clk = 0;
    always #5 clk = ~clk;
    initial begin
        #50000;
        $display("FAIL tb_xw_scale_group_cache TIMEOUT");
        $finish;
    end

    task reset_dut;
        begin
            @(negedge clk);
            rst_n = 0; load_begin = 0; wr_valid = 0; rd_req = 0;
            repeat (2) @(negedge clk);
            rst_n = 1;
        end
    endtask

    initial begin
        rst_n = 0; load_begin = 0; load_words = 0;
        load_scales = 0; wr_valid = 0; wr_data = 0;
        wr_word_index = 0; rd_req = 0; rd_scale_index = 0;
        reset_dut();
        @(negedge clk);
        load_begin = 1; load_words = 16'd2; load_scales = 16'd17;
        @(posedge clk); #1;
        if (loaded || cache_error) begin
            $display("FAIL initial Scale load header"); $finish;
        end
        @(negedge clk);
        load_begin = 0; wr_valid = 1; wr_word_index = 0;
        wr_data = {16{32'h3f800000}};
        @(posedge clk); #1;
        if (loaded || cache_error) begin
            $display("FAIL Scale first Word"); $finish;
        end
        @(negedge clk);
        wr_word_index = 1; wr_data = 512'd0;
        wr_data[31:0] = 32'h3f80624e;
        @(posedge clk); #1;
        if (!loaded || cache_error) begin
            $display("FAIL Scale final Word"); $finish;
        end
        @(negedge clk); wr_valid = 0; rd_req = 1; rd_scale_index = 16'd16;
        @(posedge clk); #1;
        if (!rd_valid || rd_scale_bits !== 32'h3f80624e) begin
            $display("FAIL Scale read lane16"); $finish;
        end
        @(negedge clk); rd_scale_index = 0;
        @(posedge clk); #1;
        if (!rd_valid || rd_scale_bits !== 32'h3f800000) begin
            $display("FAIL Scale read lane0"); $finish;
        end
        // A normal group transition must remain legal (not a fatal fault).
        @(negedge clk);
        rd_req = 0; load_begin = 1; load_words = 1; load_scales = 1;
        @(posedge clk); #1;
        if (loaded || cache_error || rd_valid) begin
            $display("FAIL legal Group reload"); $finish;
        end
        @(negedge clk);
        load_begin = 0; wr_valid = 1; wr_word_index = 0;
        wr_data = 512'h3f800001;
        @(posedge clk); #1;
        if (!loaded || cache_error) begin
            $display("FAIL Scale new Group Word"); $finish;
        end
        // Extra unsolicited write is a fatal 0x23, invalidating the cache.
        @(negedge clk); wr_word_index = 1;
        @(posedge clk); #1;
        if (!cache_error || loaded || cache_error_code !== 8'h23) begin
            $display("FAIL Scale extra Word 0x23"); $finish;
        end
        @(negedge clk);
        wr_valid = 0; rd_req = 1; rd_scale_index = 0;
        @(posedge clk); #1;
        if (rd_valid || !cache_error || cache_error_code !== 8'h23) begin
            $display("FAIL invalid Scale read after fault"); $finish;
        end
        @(negedge clk); rd_req = 0; load_begin = 1;
        @(posedge clk); #1;
        if (!cache_error || loaded || cache_error_code !== 8'h23) begin
            $display("FAIL Scale load_begin incorrectly cleared fault"); $finish;
        end
        reset_dut();
        @(negedge clk);
        load_begin = 1; load_words = 1; load_scales = 1;
        wr_valid = 1; wr_word_index = 0; wr_data = 512'hdead;
        @(posedge clk); #1;
        if (!cache_error || cache_error_code !== 8'h40 || loaded) begin
            $display("FAIL Scale load_begin/write overlap"); $finish;
        end
        reset_dut();
        @(negedge clk); rd_req = 1; rd_scale_index = 0;
        @(posedge clk); #1;
        if (!cache_error || cache_error_code !== 8'h40 || rd_valid) begin
            $display("FAIL Scale early read"); $finish;
        end
        reset_dut();
        @(negedge clk);
        load_begin = 1; load_words = 1; load_scales = 17;
        @(posedge clk); #1;
        if (!cache_error || cache_error_code !== 8'h40) begin
            $display("FAIL Scale invalid word count vs scale count"); $finish;
        end
        $display("PASS tb_xw_scale_group_cache");
        $finish;
    end
endmodule
