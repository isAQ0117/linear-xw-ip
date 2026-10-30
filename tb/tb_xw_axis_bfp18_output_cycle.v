`timescale 1ns / 1ps
module tb_xw_axis_bfp18_output_cycle;
    reg clk;
    reg rst_n;
    reg start;
    wire start_ready;
    reg [31:0] job_id;
    reg [15:0] job_n;
    reg halt;
    wire output_done;
    wire fault;
    reg rd_ready;
    wire rd_req;
    wire [15:0] rd_word_index;
    reg rd_valid;
    reg [143:0] rd_data;
    reg [7:0] rd_exp;
    reg [7:0] rd_mask;
    reg [15:0] rd_index;
    wire [511:0] m_axis_tdata;
    wire m_axis_tvalid;
    reg m_axis_tready;
    wire [63:0] m_axis_tkeep;
    wire m_axis_tlast;
    wire [127:0] m_axis_tuser;
    integer fd;
    integer scanned;
    integer cycles;
    reg [8191:0] filename;
    reg [229:0] stimulus;
    reg [725:0] expected_pre;
    reg [725:0] expected_post;
    xw_axis_bfp18_output  dut (.clk(clk), .rst_n(rst_n), .start(start), .start_ready(start_ready), .job_id(job_id), .job_n(job_n), .halt(halt), .output_done(output_done), .fault(fault), .rd_ready(rd_ready), .rd_req(rd_req), .rd_word_index(rd_word_index), .rd_valid(rd_valid), .rd_data(rd_data), .rd_exp(rd_exp), .rd_mask(rd_mask), .rd_index(rd_index), .m_axis_tdata(m_axis_tdata), .m_axis_tvalid(m_axis_tvalid), .m_axis_tready(m_axis_tready), .m_axis_tkeep(m_axis_tkeep), .m_axis_tlast(m_axis_tlast), .m_axis_tuser(m_axis_tuser));
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
            {rst_n, start, job_id, job_n, halt, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index, m_axis_tready}=stimulus;
            #1;
            if ({start_ready, output_done, fault, rd_req, rd_word_index, m_axis_tdata, m_axis_tvalid, m_axis_tkeep, m_axis_tlast, m_axis_tuser} !== expected_pre) begin
                $display("FAIL PRE cycle=%0d actual=%h expected=%h",cycles,{start_ready, output_done, fault, rd_req, rd_word_index, m_axis_tdata, m_axis_tvalid, m_axis_tkeep, m_axis_tlast, m_axis_tuser},expected_pre); $stop;
            end
            @(posedge clk);
            #1;
            if ({start_ready, output_done, fault, rd_req, rd_word_index, m_axis_tdata, m_axis_tvalid, m_axis_tkeep, m_axis_tlast, m_axis_tuser} !== expected_post) begin
                $display("FAIL NBA cycle=%0d actual=%h expected=%h",cycles,{start_ready, output_done, fault, rd_req, rd_word_index, m_axis_tdata, m_axis_tvalid, m_axis_tkeep, m_axis_tlast, m_axis_tuser},expected_post); $stop;
            end
            cycles=cycles+1;
        end
        if (cycles<5) begin $display("FAIL empty"); $stop; end
        $display("PASS tb_xw_axis_bfp18_output_cycle cycles=%0d",cycles);$finish;
    end
endmodule
