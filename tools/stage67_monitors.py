"""Actual RTL event monitor and diagnostic forcing confined to testbenches."""
def event(name,fields):
    pairs=[('cycle','%0d','cycles'),('event',name,None),('job_id','%0d','job_id' if name=='JOB_ACCEPT' else 'dut.active_id'),('row','%0d',"16'd0")]+fields
    fmt='{'+','.join('\\"'+k+'\\":'+('\\"'+v+'\\"' if k=='event' or v=='%h' else v) for k,v,a in pairs)+'}'
    args=', '.join(a for k,v,a in pairs if a is not None)
    return '$fdisplay(trace_fd, "'+fmt+'", '+args+');'

def instrumentation():
    decl='''    reg inject_valid;
    reg [2:0] inject_source;
    reg [7:0] inject_code;
    wire [43:0] debug_control;
    wire [47:0] debug_pipeline;
    integer trace_fd;
    reg [8191:0] trace_path;
    reg previous_b1;
    reg previous_b2;
    reg [7:0] previous_error;
    reg previous_lock;
'''
    wiring='''    assign debug_control = {dut.system_release, dut.data_release, dut.scheduler.state, dut.first_error, dut.fault_lock, dut.channel, 1'b0, dut.group_index};
    assign debug_pipeline = {dut.address_generator.state, dut.rx_busy, dut.compute.state, dut.compute.block_index, dut.stage5.state, dut.output_sender.count, dut.output_sender.pending, 1'b0, dut.output_sender.issued};
    /* 仅TB诊断注入：不在生产顶层增加物理端口。 */
    always @(*) begin
        release dut.c_fault;
        release dut.c_code;
        release dut.q_fault;
        release dut.q_code;
        release dut.rx_fault;
        release dut.rx_code;
        release dut.w_fault;
        release dut.w_code;
        release dut.a_fault;
        release dut.a_code;
        if (inject_valid) begin
            case (inject_source)
                0: begin force dut.c_fault = 1'b1; force dut.c_code = inject_code; end
                1: begin force dut.q_fault = 1'b1; force dut.q_code = inject_code; end
                2: begin force dut.rx_fault = 1'b1; force dut.rx_code = inject_code; end
                3: begin force dut.w_fault = 1'b1; force dut.w_code = inject_code; end
                4: begin force dut.a_fault = 1'b1; force dut.a_code = inject_code; end
            endcase
        end
    end
'''
    init='''        previous_b1=0;previous_b2=0;previous_error=0;previous_lock=0;
        if (!$value$plusargs("TRACE=%s",trace_path)) begin $display("FAIL trace path"); $stop; end
        trace_fd=$fopen(trace_path,"w");
        if (!trace_fd) begin $display("FAIL trace open"); $stop; end
'''
    pre='''            if (dut.system_rst_n) begin
'''
    def on(condition,name,fields):return '                if ('+condition+')\n                    '+event(name,fields)+'\n'
    pre+=on('job_valid && job_ready','JOB_ACCEPT',[]).replace('cycles, dut.active_id','cycles, job_id')
    pre+=on('s_axis_tvalid && s_axis_tready','AXIS_IN_ACCEPT',[('group','%0d','s_axis_tuser[56:48]'),('index','%0d','s_axis_tuser[87:80]')])
    pre+=on('ddr_rd_req','DDR_REQ_ACCEPT',[('group','%0d','dut.group_index'),('channel','%0d','dut.channel'),('kind','%0d','dut.cmd_kind'),('start','%0d','ddr_rd_addra'),('end','%0d','ddr_rd_addrb'),('beats','%0d','dut.cmd_beats')])
    pre+=on('ddr_rd_vld','DDR_BEAT',[('group','%0d','dut.group_index'),('channel','%0d','dut.channel'),('index','%0d',"ddr_rd_req ? 16'd0 : dut.receiver.received_count"),('data_hex','%h','ddr_rd_data')])
    pre+=on('dut.load_valid && dut.load_ready','LOAD_ACCEPT',[('kind','%0d','dut.load_kind'),('index','%0d','dut.load_index')])
    pre+=on('dut.compute_valid && dut.compute_ready','COMPUTE_ACCEPT',[('channel','%0d','dut.channel')])
    pre+=on('dut.result_valid && dut.c_result_ready','RESULT_ACCEPT',[('channel','%0d','dut.channel'),('mant','%0d','$signed(dut.result_mant)'),('exp','%0d','$signed(dut.result_exp)')])
    pre+=on('dut.output_start && dut.output_ready','OUTPUT_START',[])
    pre+=on('m_axis_tvalid && m_axis_tready','AXIS_OUT_ACCEPT',[('group','%0d','m_axis_tuser[56:48]'),('index','%0d','m_axis_tuser[87:80]'),('data_hex','%h','m_axis_tdata'),('keep_hex','%h','m_axis_tkeep'),('last','%0d','m_axis_tlast'),('user_hex','%h','m_axis_tuser')])
    pre+=on('status_valid && status_ready','STATUS_ACCEPT',[('status_id','%0d','status_job_id'),('ok','%0d','status_ok'),('code','%0d','status_error_code')])
    pre+='            end\n'
    post='            if (dut.system_rst_n) begin\n'
    post+=on('dut.range_done','RANGE_DONE',[('group','%0d','dut.group_index'),('channel','%0d','dut.channel'),('index','%0d','dut.word_index')])
    post+=on('dut.compute.b1_valid && !previous_b1','B1_VALID',[('channel','%0d','dut.compute.active_channel'),('block','%0d','dut.compute.b1_block'),('raw','%0d','$signed(dut.compute.b1_raw)')])
    post+=on('dut.compute.b2_valid && !previous_b2','B2_VALID',[('channel','%0d','dut.compute.active_channel'),('block','%0d','dut.compute.b2_block'),('term_hex','%h','dut.compute.b2_mant'),('exp','%0d','$signed(dut.compute.b2_exp)')])
    post+=on('dut.compute.a2_update','A2_UPDATE',[('channel','%0d','dut.compute.active_channel'),('block','%0d','dut.compute.a2_block'),('mant','%0d','$signed(dut.compute.a2_mant)'),('exp','%0d','$signed(dut.compute.a2_exp)')])
    post+=on('dut.group_done','GROUP_REQUANT',[('group','%0d','dut.committed_group'),('length','%0d','dut.group_len'),('exp','%0d','$signed(dut.group_exp)')])
    post+=on('(dut.first_error != 0 && previous_error == 0) || dut.fault_lock != previous_lock','FAULT',[('code','%0d',"dut.first_error != 0 ? dut.first_error : dut.raw_code"),('lock','%0d','dut.fault_lock'),('owned','%0d','dut.busy')])
    post+='''            end
            previous_b1=dut.compute.b1_valid;
            previous_b2=dut.compute.b2_valid;
            previous_error=dut.first_error;
            previous_lock=dut.fault_lock;
'''
    return decl,wiring,init,pre,post
