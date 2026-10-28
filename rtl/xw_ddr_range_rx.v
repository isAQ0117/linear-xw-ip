// Old FFN-compatible DDR range request / 512-bit response receiver.
// Verilog-2001. One outstanding range. No DDR return-side READY.
// Supports first response beat on the same clock edge as request acceptance.
// Command address generation is the scheduler's responsibility.
module xw_ddr_range_rx (
    /*
     * =========================================================
     * 时钟与复位
     * =========================================================
     */
    input  wire                 clk,
    input  wire                 rst_n,

    /*
     * =========================================================
     * DDR 区间命令接口
     * =========================================================
     */
    input  wire                 cmd_valid,
    output wire                 cmd_ready,
    input  wire [28:0]          cmd_addr_start,
    input  wire [28:0]          cmd_addr_end,
    input  wire [15:0]          cmd_beats,
    input  wire                 cmd_kind, // 0=scale, 1=weight

    /*
     * =========================================================
     * DDR 区间读取接口
     * =========================================================
     */
    output wire                 ddr_rd_req,
    output wire [28:0]          ddr_rd_addra,
    output wire [28:0]          ddr_rd_addrb,
    input  wire                 ddr_rd_rdy,
    input  wire [511:0]         ddr_rd_data,
    input  wire                 ddr_rd_vld,

    /*
     * =========================================================
     * 接收数据与状态输出
     * =========================================================
     */
    output reg                  busy,
    output reg                  word_valid,
    output reg  [511:0]         word_data,
    output reg  [15:0]          word_index,
    output reg                  word_kind,
    output reg                  range_done,
    output reg                  range_error
);

    /*
     * =========================================================
     * 区间读取状态与 Beat 计数寄存器
     * =========================================================
     */
    reg [15:0] received_count;
    reg [15:0] expected_beats;
    reg active_kind;


    /*
     * =========================================================
     * 地址跨度校验与命令握手信号
     * =========================================================
     */
    wire [28:0] span;
    wire [28:0] span_beats;
    wire valid_command;
    wire request_accepted;

    /*
     * 检查 DDR 起止地址的 8 单位对齐、顺序和 Beat 数。
     */
    assign span = cmd_addr_end - cmd_addr_start;
    assign span_beats = (span >> 3) + 29'd1;
    assign valid_command = (cmd_beats != 16'd0) &&
                           (cmd_addr_start[2:0] == 3'd0) &&
                           (cmd_addr_end[2:0] == 3'd0) &&
                           (cmd_addr_end >= cmd_addr_start) &&
                           (span_beats == {13'd0, cmd_beats});

    // Old FFN contract: ready does not depend combinationally on ddr_rd_req.
    assign cmd_ready = (!busy) && ddr_rd_rdy && valid_command;
    assign request_accepted = cmd_valid && cmd_ready;
    assign ddr_rd_req = request_accepted;
    assign ddr_rd_addra = cmd_addr_start;
    assign ddr_rd_addrb = cmd_addr_end;

    /*
     * 维护单笔 DDR 区间读取；支持命令接受当拍返回首 Beat。
     * 逐 Beat 登记数据和索引，完成时生成 range_done，异常时报错。
     */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0;
            received_count <= 16'd0;
            expected_beats <= 16'd0;
            active_kind <= 1'b0;
            word_valid <= 1'b0;
            word_data <= 512'd0;
            word_index <= 16'd0;
            word_kind <= 1'b0;
            range_done <= 1'b0;
            range_error <= 1'b0;
        end else begin
            word_valid <= 1'b0;
            range_done <= 1'b0;
            // This error is sticky until reset or the next accepted command.
            if (cmd_valid && !busy && !valid_command)
                range_error <= 1'b1;
            if (request_accepted) begin
                range_error <= 1'b0;
                expected_beats <= cmd_beats;
                received_count <= 16'd0;
                active_kind <= cmd_kind;
                if (ddr_rd_vld) begin
                    // Response beat zero on the very same accept edge.
                    word_valid <= 1'b1;
                    word_data <= ddr_rd_data;
                    word_index <= 16'd0;
                    word_kind <= cmd_kind;
                    if (cmd_beats == 16'd1) begin
                        busy <= 1'b0;
                        received_count <= 16'd0;
                        range_done <= 1'b1;
                    end else begin
                        busy <= 1'b1;
                        received_count <= 16'd1;
                    end
                end else
                    busy <= 1'b1;
            end else if (busy) begin
                if (ddr_rd_vld) begin
                    word_valid <= 1'b1;
                    word_data <= ddr_rd_data;
                    word_index <= received_count;
                    word_kind <= active_kind;
                    if (received_count == expected_beats - 16'd1) begin
                        busy <= 1'b0;
                        received_count <= 16'd0;
                        range_done <= 1'b1;
                    end else
                        received_count <= received_count + 16'd1;
                end
            end else if (ddr_rd_vld) begin
                // Unattributed DDR response. Protocol violation.
                range_error <= 1'b1;
            end
        end
    end
endmodule
