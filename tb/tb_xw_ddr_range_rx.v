`timescale 1ns/1ps
// Stage-1 DDR handshake, first beat, handoff, sticky fault & reset.
module tb_xw_ddr_range_rx;
    reg clk, rst_n, cmd_valid;
    wire cmd_ready;
    reg [28:0] cmd_addr_start, cmd_addr_end;
    reg [15:0] cmd_beats;
    reg cmd_kind;
    wire ddr_rd_req;
    wire [28:0] ddr_rd_addra, ddr_rd_addrb;
    reg ddr_rd_rdy, ddr_rd_vld;
    reg [511:0] ddr_rd_data;
    wire busy, word_valid, word_kind, range_done, range_error;
    wire [511:0] word_data;
    wire [15:0] word_index;
    wire [7:0] range_error_code;

    xw_ddr_range_rx dut (
        .clk(clk), .rst_n(rst_n),
        .cmd_valid(cmd_valid), .cmd_ready(cmd_ready),
        .cmd_addr_start(cmd_addr_start), .cmd_addr_end(cmd_addr_end),
        .cmd_beats(cmd_beats), .cmd_kind(cmd_kind),
        .ddr_rd_req(ddr_rd_req), .ddr_rd_addra(ddr_rd_addra),
        .ddr_rd_addrb(ddr_rd_addrb), .ddr_rd_rdy(ddr_rd_rdy),
        .ddr_rd_data(ddr_rd_data), .ddr_rd_vld(ddr_rd_vld),
        .busy(busy), .word_valid(word_valid), .word_data(word_data),
        .word_index(word_index), .word_kind(word_kind),
        .range_done(range_done), .range_error(range_error),
        .range_error_code(range_error_code)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;
    initial begin
        #50000;
        $display("FAIL tb_xw_ddr_range_rx TIMEOUT");
        $finish;
    end

    task reset_dut;
        begin
            @(negedge clk);
            rst_n = 1'b0;
            cmd_valid = 1'b0;
            ddr_rd_vld = 1'b0;
            repeat (2) @(negedge clk);
            rst_n = 1'b1;
        end
    endtask

    initial begin
        rst_n = 0; cmd_valid = 0;
        cmd_addr_start = 0; cmd_addr_end = 0; cmd_beats = 0;
        cmd_kind = 0; ddr_rd_rdy = 1; ddr_rd_vld = 0; ddr_rd_data = 0;
        // Reset must mask a syntactically valid DDR request.
        cmd_valid = 1; cmd_addr_start = 29'h100;
        cmd_addr_end = 29'h100; cmd_beats = 16'd1;
        #1;
        if (cmd_ready !== 1'b0 || ddr_rd_req !== 1'b0) begin
            $display("FAIL DDR request not masked during reset"); $finish;
        end
        reset_dut();
        @(negedge clk);
        cmd_valid = 1; cmd_addr_start = 29'h100;
        cmd_addr_end = 29'h108; cmd_beats = 16'd2;
        cmd_kind = 1; ddr_rd_vld = 1; ddr_rd_data = 512'hdead;
        #1;
        if (ddr_rd_req !== 1'b1 || ddr_rd_addra !== 29'h100 ||
            ddr_rd_addrb !== 29'h108) begin
            $display("FAIL DDR range request"); $finish;
        end
        @(posedge clk); #1;
        if (word_valid !== 1'b1 || word_index !== 16'd0 ||
            word_data[31:0] !== 32'hdead || busy !== 1'b1 || range_done) begin
            $display("FAIL DDR request-edge first beat"); $finish;
        end
        @(negedge clk); cmd_valid = 0; ddr_rd_vld = 0;
        @(posedge clk); #1;
        if (word_valid !== 1'b0 || busy !== 1'b1) begin
            $display("FAIL DDR gap"); $finish;
        end
        @(negedge clk); ddr_rd_vld = 1; ddr_rd_data = 512'hbeef;
        @(posedge clk); #1;
        if (!word_valid || word_index !== 16'd1 ||
            word_data[31:0] !== 32'hbeef || busy || !range_done || range_error) begin
            $display("FAIL DDR final beat"); $finish;
        end
        // A new valid command cannot be accepted before downstream
        // consumes the registered final word_valid (the next posedge).
        @(negedge clk);
        ddr_rd_vld = 0; cmd_valid = 1;
        cmd_addr_start = 29'h200; cmd_addr_end = 29'h200;
        cmd_beats = 16'd1; cmd_kind = 0;
        #1;
        if (cmd_ready !== 1'b0 || ddr_rd_req !== 1'b0) begin
            $display("FAIL DDR range handoff guard"); $finish;
        end
        @(posedge clk); #1;
        if (range_done !== 1'b0 || cmd_ready !== 1'b1) begin
            $display("FAIL DDR handoff release"); $finish;
        end
        @(negedge clk); ddr_rd_vld = 1; ddr_rd_data = 512'hface;
        @(posedge clk); #1;
        if (!word_valid || !range_done || word_index !== 16'd0 ||
            word_kind !== 1'b0 || busy || range_error) begin
            $display("FAIL 1-beat same-edge DDR range"); $finish;
        end
        @(negedge clk); cmd_valid = 0; ddr_rd_vld = 1;
        @(posedge clk); #1;
        if (range_error !== 1'b1 || range_error_code !== 8'h21 ||
            word_valid !== 1'b0) begin
            $display("FAIL extra DDR beat detection"); $finish;
        end
        @(negedge clk); ddr_rd_vld = 0; cmd_valid = 1;
        #1;
        if (ddr_rd_req !== 1'b0 || cmd_ready !== 1'b0) begin
            $display("FAIL sticky DDR fault gated request"); $finish;
        end
        @(posedge clk); #1;
        if (!range_error || range_error_code !== 8'h21) begin
            $display("FAIL sticky DDR fault held"); $finish;
        end
        reset_dut();
        @(negedge clk); cmd_valid = 1; ddr_rd_vld = 0;
        cmd_addr_start = 29'h101; cmd_addr_end = 29'h108;
        cmd_beats = 16'd2;
        @(posedge clk); #1;
        if (!range_error || range_error_code !== 8'h20 || ddr_rd_req) begin
            $display("FAIL malformed DDR range 0x20"); $finish;
        end
        @(negedge clk); cmd_addr_start = 29'h100;
        @(posedge clk); #1;
        if (!range_error || range_error_code !== 8'h20 || busy) begin
            $display("FAIL invalid command must remain locked"); $finish;
        end
        reset_dut();
        @(negedge clk); ddr_rd_vld = 1; ddr_rd_data = 512'h9988;
        @(posedge clk); #1;
        if (!range_error || range_error_code !== 8'h21 || word_valid) begin
            $display("FAIL unsolicited DDR beat 0x21"); $finish;
        end
        reset_dut();
        // Valid command held while DDR not ready must not be rejected.
        @(negedge clk);
        cmd_valid = 1; ddr_rd_rdy = 0;
        cmd_addr_start = 29'h200; cmd_addr_end = 29'h200;
        cmd_beats = 16'd1; ddr_rd_vld = 0;
        @(posedge clk); #1;
        if (range_error || busy || cmd_ready || ddr_rd_req) begin
            $display("FAIL DDR command wait-for-ready"); $finish;
        end
        @(negedge clk); ddr_rd_rdy = 1;
        @(posedge clk); #1;
        if (!busy || range_error) begin
            $display("FAIL DDR request after READY"); $finish;
        end
        $display("PASS tb_xw_ddr_range_rx");
        $finish;
    end
endmodule
