// Linear xW: FFN-compatible, 512-bit DDR range receiver.
// Stage 1 contract: XW-CONTRACT-STD-001 V1.0; Verilog-2001, ANSI ports.
// Single outstanding range; incoming DDR data cannot be backpressured.
module xw_ddr_range_rx (
    input  wire         clk,
    input  wire         rst_n,

    // 内部 Range 命令：上游保持命令直至握手完成。
    input  wire         cmd_valid,
    output wire         cmd_ready,
    input  wire  [28:0] cmd_addr_start,
    input  wire  [28:0] cmd_addr_end,
    input  wire  [15:0] cmd_beats,
    input  wire         cmd_kind,    // 0=scale, 1=weight

    // 冻结的六信号 DDR 物理接口。
    output wire         ddr_rd_req,
    output wire  [28:0] ddr_rd_addra,
    output wire  [28:0] ddr_rd_addrb,
    input  wire         ddr_rd_rdy,
    input  wire [511:0] ddr_rd_data,
    input  wire         ddr_rd_vld,

    // 接收数据：每个有效 Beat 寄存一次，不允许向 DDR 反压。
    output reg          busy,
    output reg          word_valid,
    output reg  [511:0] word_data,
    output reg   [15:0] word_index,
    output reg          word_kind,
    output reg          range_done,
    output reg          range_error,
    // 新增模块内部错误原因端口，顶层 35 个端口保持不变。
    output reg    [7:0] range_error_code
);

    /*
     * =========================================================
     * DDR Range 格式校验与请求握手。
     * =========================================================
     */
    localparam [7:0] ERR_DDR_COMMAND  = 8'h20;
    localparam [7:0] ERR_DDR_RESPONSE = 8'h21;

    reg  [15:0] received_count;
    reg  [15:0] expected_beats;
    reg         active_kind;
    reg         handoff_hold;

    wire [28:0] span;
    wire [28:0] span_beats;
    wire        valid_command;
    wire        request_accepted;
    wire        command_window;

    assign span       = cmd_addr_end - cmd_addr_start;
    assign span_beats = (span >> 3) + 29'd1;
    assign valid_command = (cmd_beats != 16'd0) &&
                           (cmd_addr_start[2:0] == 3'd0) &&
                           (cmd_addr_end[2:0] == 3'd0) &&
                           (cmd_addr_end >= cmd_addr_start) &&
                           (span_beats == {13'd0, cmd_beats});

    // The external DDR request stays a single handshake pulse, as in FFN.
    // A local command cannot start during reset, fault, or last-word handoff.
    assign command_window   = rst_n && !busy && !handoff_hold && !range_error;
    assign cmd_ready        = command_window && ddr_rd_rdy && valid_command;
    assign request_accepted = cmd_valid && cmd_ready;
    assign ddr_rd_req       = request_accepted;
    assign ddr_rd_addra     = cmd_addr_start;
    assign ddr_rd_addrb     = cmd_addr_end;

    /*
     * =========================================================
     * DDR 数据接收寄存器与不可自动清除的严重故障。
     * =========================================================
     * First beat MAY coincide with request acceptance.
     * After the last registered word, handoff_hold blocks a new command
     * for one more rising edge, allowing the downstream register/RAM
     * to consume the final word_valid/range_done without overlap.
     * An unmatched DDR response is a fatal 0x21 fault.  There is no
     * physical response ID or LAST; undetectable DDR protocol violations
     * must still be handled by the system-level recovery guarantee.
     */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy             <= 1'b0;
            received_count   <= 16'd0;
            expected_beats   <= 16'd0;
            active_kind      <= 1'b0;
            handoff_hold     <= 1'b0;
            word_valid       <= 1'b0;
            word_data        <= 512'd0;
            word_index       <= 16'd0;
            word_kind        <= 1'b0;
            range_done       <= 1'b0;
            range_error      <= 1'b0;
            range_error_code <= 8'h00;
        end else begin
            word_valid <= 1'b0;
            range_done <= 1'b0;
            if (handoff_hold)
                handoff_hold <= 1'b0;

            if (range_error) begin
                // Sticky: only a controlled reset can clear a fatal fault.
                busy <= 1'b0;
            end else if (ddr_rd_vld && !busy && !request_accepted) begin
                // Unattributed beat, including during the handoff interval.
                range_error      <= 1'b1;
                range_error_code <= ERR_DDR_RESPONSE;
                busy             <= 1'b0;
            end else if (command_window && cmd_valid && !valid_command) begin
                range_error      <= 1'b1;
                range_error_code <= ERR_DDR_COMMAND;
                busy             <= 1'b0;
            end else if (request_accepted) begin
                expected_beats <= cmd_beats;
                active_kind    <= cmd_kind;
                received_count <= 16'd0;
                if (ddr_rd_vld) begin
                    word_valid <= 1'b1;
                    word_data  <= ddr_rd_data;
                    word_index <= 16'd0;
                    word_kind  <= cmd_kind;
                    if (cmd_beats == 16'd1) begin
                        busy           <= 1'b0;
                        received_count <= 16'd0;
                        range_done     <= 1'b1;
                        handoff_hold   <= 1'b1;
                    end else begin
                        busy           <= 1'b1;
                        received_count <= 16'd1;
                    end
                end else begin
                    busy <= 1'b1;
                end
            end else if (busy && ddr_rd_vld) begin
                word_valid <= 1'b1;
                word_data  <= ddr_rd_data;
                word_index <= received_count;
                word_kind  <= active_kind;
                if (received_count == expected_beats - 16'd1) begin
                    busy           <= 1'b0;
                    received_count <= 16'd0;
                    range_done     <= 1'b1;
                    handoff_hold   <= 1'b1;
                end else begin
                    received_count <= received_count + 16'd1;
                end
            end
        end
    end
endmodule
