`timescale 1ns / 1ps
module tb_xw_job_status_cycle;
    reg clk;
    reg rst_n;
    reg finish_valid;
    wire finish_ready;
    reg [31:0] finish_job_id;
    reg finish_ok;
    reg [7:0] finish_error_code;
    wire status_valid;
    reg status_ready;
    wire [31:0] status_job_id;
    wire status_ok;
    wire [7:0] status_error_code;
    integer fd;
    integer scanned;
    integer cycles;
    reg [8191:0] filename;
    reg [43:0] stimulus;
    reg [42:0] expected_pre;
    reg [42:0] expected_post;
    xw_job_status  dut (.clk(clk), .rst_n(rst_n), .finish_valid(finish_valid), .finish_ready(finish_ready), .finish_job_id(finish_job_id), .finish_ok(finish_ok), .finish_error_code(finish_error_code), .status_valid(status_valid), .status_ready(status_ready), .status_job_id(status_job_id), .status_ok(status_ok), .status_error_code(status_error_code));
    /* 仿真唯一时钟。 */
    always #5 clk = ~clk;
    initial begin
        clk=0;cycles=0;

        if (!$value$plusargs("VECTORS=%s",filename)) begin $display("FAIL no vector"); $stop; end
        fd=$fopen(filename,"r");
        if (!fd) begin $display("FAIL open"); $stop; end
        while (!$feof(fd)) begin
            scanned=$fscanf(fd,"%h %h %h\n",stimulus,expected_pre,expected_post);
            if (scanned!=3) begin $display("FAIL malformed"); $stop; end
            @(negedge clk);
            {rst_n, finish_valid, finish_job_id, finish_ok, finish_error_code, status_ready}=stimulus;
            #1;
            if ({finish_ready, status_valid, status_job_id, status_ok, status_error_code} !== expected_pre) begin
                $display("FAIL PRE cycle=%0d actual=%h expected=%h",cycles,{finish_ready, status_valid, status_job_id, status_ok, status_error_code},expected_pre); $stop;
            end
            @(posedge clk);
            #1;
            if ({finish_ready, status_valid, status_job_id, status_ok, status_error_code} !== expected_post) begin
                $display("FAIL NBA cycle=%0d actual=%h expected=%h",cycles,{finish_ready, status_valid, status_job_id, status_ok, status_error_code},expected_post); $stop;
            end
            cycles=cycles+1;
        end
        if (cycles<5) begin $display("FAIL empty"); $stop; end
        $display("PASS tb_xw_job_status_cycle cycles=%0d",cycles);$finish;
    end
endmodule
