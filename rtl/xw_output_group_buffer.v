`timescale 1ns / 1ps

/* 当前组原始A2 RAM；接收沿同步维护Hmax，不额外扫描。 */
module xw_output_group_buffer (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                cancel,
    input  wire                begin_group,
    input  wire [31:0]          group_job,
    input  wire [15:0]          group_base,
    input  wire [7:0]           group_len,
    input  wire                result_valid,
    output wire                result_ready,
    input  wire signed [47:0]   result_mant,
    input  wire signed [15:0]   result_exp,
    input  wire [31:0]          result_job,
    input  wire [15:0]          result_channel,
    output wire                loaded,
    output reg                 nonzero,
    output reg signed [17:0]   hmax,
    input  wire                rd_req,
    input  wire [6:0]           rd_index,
    output wire                rd_valid,
    output wire signed [47:0]   rd_mant,
    output wire signed [15:0]   rd_exp,
    output reg                 fault
);
    /* 存储与组所有权；RAM数据不复位。 */
    reg [63:0] states [0:127];
    reg [63:0] read_data;
    reg read_pending;
    reg read_seen;
    reg active;
    reg complete;
    reg [31:0] active_job;
    reg [15:0] base;
    reg [7:0] length;
    reg [7:0] count;
    wire take;
    wire bad;
    wire write_enable;
    wire read_enable;
    wire [47:0] magnitude;
    wire signed [17:0] position;

    /* 六级二分前导位编码；零值不参与指数搜索。 */
    function [5:0] leading;
        input [47:0] value;
        reg [47:0] v;
        reg [5:0] n;
        begin
            v = value;
            n = 0;
            if (v[47:32] != 0) begin v = v >> 32; n = n + 32; end
            if (v[31:16] != 0) begin v = v >> 16; n = n + 16; end
            if (v[15:8] != 0) begin v = v >> 8; n = n + 8; end
            if (v[7:4] != 0) begin v = v >> 4; n = n + 4; end
            if (v[3:2] != 0) begin v = v >> 2; n = n + 2; end
            if (v[1] != 0) n = n + 1;
            leading = n;
        end
    endfunction

    assign result_ready = rst_n && !cancel && !fault && active && !complete && !begin_group && !rd_req;
    assign take = result_valid && result_ready;
    assign loaded = rst_n && !cancel && !fault && complete;
    assign magnitude = result_mant[47] ? (~result_mant + 48'd1) : result_mant;
    assign position = $signed({{2{result_exp[15]}}, result_exp}) + $signed({12'd0, leading(magnitude)});
    assign bad = (begin_group && (rd_req || (active && !complete) ||
                  group_len == 0 || group_len > 128 || group_base[6:0] != 0 ||
                  ({1'b0, group_base} + {9'd0, group_len}) > 17'd65535)) ||
                 (take && (result_job != active_job ||
                  {1'b0, result_channel} != ({1'b0, base} + {9'd0, count}))) ||
                 (rd_req && (!complete || rd_index >= length || result_valid && result_ready));
    assign write_enable = take && !bad;
    assign read_enable = rst_n && !cancel && !fault && !begin_group && rd_req && !bad;
    assign rd_valid = rst_n && !cancel && !fault && read_pending;
    assign rd_mant = read_seen ? read_data[47:0] : 48'd0;
    assign rd_exp = read_seen ? read_data[63:48] : 16'd0;

    /* 原生64bit单写口、同步读，不依赖同址读写模式。 */
    always @(posedge clk) begin
        if (write_enable)
            states[count[6:0]] <= {result_exp, result_mant};
        if (read_enable)
            read_data <= states[rd_index];
    end

    /* cancel只撤销本地状态；系统故障由Controller首错锁定。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active <= 0;
            complete <= 0;
            active_job <= 0;
            base <= 0;
            length <= 0;
            count <= 0;
            nonzero <= 0;
            hmax <= 0;
            read_pending <= 0;
            read_seen <= 0;
            fault <= 0;
        end else if (cancel) begin
            active <= 0;
            complete <= 0;
            count <= 0;
            nonzero <= 0;
            hmax <= 0;
            read_pending <= 0;
            read_seen <= 0;
            fault <= 0;
        end else if (fault || bad) begin
            fault <= 1;
            active <= 0;
            complete <= 0;
            read_pending <= 0;
        end else begin
            read_pending <= read_enable;
            if (read_enable)
                read_seen <= 1;
            if (begin_group) begin
                active <= 1;
                complete <= 0;
                active_job <= group_job;
                base <= group_base;
                length <= group_len;
                count <= 0;
                nonzero <= 0;
                hmax <= 0;
                read_seen <= 0;
            end else if (take) begin
                count <= count + 1'b1;
                if (result_mant != 0) begin
                    nonzero <= 1;
                    if (!nonzero || position > hmax)
                        hmax <= position;
                end
                if (count + 1'b1 == length)
                    complete <= 1;
            end
        end
    end
endmodule
