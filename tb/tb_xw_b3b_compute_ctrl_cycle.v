`timescale 1ns / 1ps
/* 自动生成；完整比较沿前组合输出及沿后NBA，期望另经数学Golden检查。 */
module tb_xw_b3b_compute_ctrl_cycle;
    /* 驱动与观测端口。 */
    reg  [0:0] clk;
    reg  [0:0] rst_n;
    reg  [0:0] abort;
    reg  [0:0] req_valid;
    wire [0:0] req_ready;
    reg  [31:0] req_job;
    reg  [15:0] req_channel;
    reg  [15:0] req_k;
    reg  [0:0] x_loaded;
    reg  [0:0] w_loaded;
    reg  [0:0] s_loaded;
    reg  [0:0] upstream_fault;
    reg  [7:0] upstream_code;
    reg  [0:0] slice_enable;
    wire [0:0] x_rd_req;
    wire [15:0] x_rd_index;
    reg  [0:0] x_rd_valid;
    reg  [143:0] x_rd_data;
    reg  [7:0] x_rd_exp;
    reg  [7:0] x_rd_mask;
    wire [0:0] w_rd_req;
    wire [15:0] w_rd_index;
    reg  [0:0] w_rd_valid;
    reg  [63:0] w_rd_data;
    reg  [7:0] w_rd_mask;
    wire [0:0] s_rd_req;
    wire [15:0] s_rd_index;
    reg  [0:0] s_rd_valid;
    reg  [31:0] s_rd_bits;
    wire [0:0] result_valid;
    reg  [0:0] result_ready;
    wire [47:0] result_mant;
    wire [15:0] result_exp;
    wire [31:0] result_job;
    wire [15:0] result_channel;
    wire [0:0] error_valid;
    wire [7:0] error_code;
    wire [0:0] fault_lock;
    reg [347:0] stimulus;
    reg [174:0] expected_pre;
    reg [174:0] expected_post;
    reg [4095:0] vector_path;
    integer fd;
    integer scanned;
    integer cycles;

    xw_b3b_compute_ctrl dut (
        .clk(clk),
        .rst_n(rst_n),
        .abort(abort),
        .req_valid(req_valid),
        .req_ready(req_ready),
        .req_job(req_job),
        .req_channel(req_channel),
        .req_k(req_k),
        .x_loaded(x_loaded),
        .w_loaded(w_loaded),
        .s_loaded(s_loaded),
        .upstream_fault(upstream_fault),
        .upstream_code(upstream_code),
        .slice_enable(slice_enable),
        .x_rd_req(x_rd_req),
        .x_rd_index(x_rd_index),
        .x_rd_valid(x_rd_valid),
        .x_rd_data(x_rd_data),
        .x_rd_exp(x_rd_exp),
        .x_rd_mask(x_rd_mask),
        .w_rd_req(w_rd_req),
        .w_rd_index(w_rd_index),
        .w_rd_valid(w_rd_valid),
        .w_rd_data(w_rd_data),
        .w_rd_mask(w_rd_mask),
        .s_rd_req(s_rd_req),
        .s_rd_index(s_rd_index),
        .s_rd_valid(s_rd_valid),
        .s_rd_bits(s_rd_bits),
        .result_valid(result_valid),
        .result_ready(result_ready),
        .result_mant(result_mant),
        .result_exp(result_exp),
        .result_job(result_job),
        .result_channel(result_channel),
        .error_valid(error_valid),
        .error_code(error_code),
        .fault_lock(fault_lock)
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
        if (!$value$plusargs("VECTORS=%s", vector_path)) begin
            $display("FAIL missing VECTORS"); $finish;
        end
        fd = $fopen(vector_path, "r");
        if (!fd) begin $display("FAIL vectors open"); $finish; end
        while (!$feof(fd)) begin
            scanned = $fscanf(fd, "%h %h %h\n", stimulus, expected_pre, expected_post);
            if (scanned != 3) begin $display("FAIL malformed vectors"); $finish; end
            @(negedge clk);
            {rst_n, abort, req_valid, req_job, req_channel, req_k, x_loaded, w_loaded, s_loaded, upstream_fault, upstream_code, slice_enable, x_rd_valid, x_rd_data, x_rd_exp, x_rd_mask, w_rd_valid, w_rd_data, w_rd_mask, s_rd_valid, s_rd_bits, result_ready} = stimulus;
            #1;
            if ({req_ready, x_rd_req, x_rd_index, w_rd_req, w_rd_index, s_rd_req, s_rd_index, result_valid, result_mant, result_exp, result_job, result_channel, error_valid, error_code, fault_lock} !== expected_pre) begin
                $display("FAIL xw_b3b_compute_ctrl PRE cycle=%0d actual=%h expected=%h", cycles, {req_ready, x_rd_req, x_rd_index, w_rd_req, w_rd_index, s_rd_req, s_rd_index, result_valid, result_mant, result_exp, result_job, result_channel, error_valid, error_code, fault_lock}, expected_pre);
                $finish;
            end
            @(posedge clk);
            #1;
            if ({req_ready, x_rd_req, x_rd_index, w_rd_req, w_rd_index, s_rd_req, s_rd_index, result_valid, result_mant, result_exp, result_job, result_channel, error_valid, error_code, fault_lock} !== expected_post) begin
                $display("FAIL xw_b3b_compute_ctrl NBA cycle=%0d actual=%h expected=%h", cycles, {req_ready, x_rd_req, x_rd_index, w_rd_req, w_rd_index, s_rd_req, s_rd_index, result_valid, result_mant, result_exp, result_job, result_channel, error_valid, error_code, fault_lock}, expected_post);
                $finish;
            end
            cycles = cycles + 1;
        end
        $fclose(fd);
        if (cycles < 5) begin $display("FAIL empty vectors"); $finish; end
        $display("PASS tb_xw_b3b_compute_ctrl_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
