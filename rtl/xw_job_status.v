`timescale 1ns / 1ps

/* 单槽终态；成功/失败归因由Scheduler完成。 */
module xw_job_status (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         finish_valid,
    output wire         finish_ready,
    input  wire [31:0]  finish_job_id,
    input  wire         finish_ok,
    input  wire [7:0]   finish_error_code,
    output reg          status_valid,
    input  wire         status_ready,
    output reg [31:0]   status_job_id,
    output reg          status_ok,
    output reg [7:0]    status_error_code
);
    /* 不使用消费当沿旁路，槽不能被覆盖。 */
    assign finish_ready = rst_n && !status_valid;

    /* 终态保持到真实接受；reset可取消尚未交付终态。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            status_valid <= 0;
            status_job_id <= 0;
            status_ok <= 0;
            status_error_code <= 0;
        end else if (status_valid) begin
            if (status_ready)
                status_valid <= 0;
        end else if (finish_valid && finish_ready) begin
            status_valid <= 1;
            status_job_id <= finish_job_id;
            status_ok <= finish_ok;
            status_error_code <= finish_error_code;
        end
    end
endmodule
