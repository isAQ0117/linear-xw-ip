# Stage 6/7 实际端口清单

由最终生产源码的ANSI头部提取；内部端口不计入冻结35-port顶层。

## xw_axis_bfp18_output

|Direction|Name|Width|Signed|
|---|---|---:|---|
|input|clk|1|no|
|input|rst_n|1|no|
|input|start|1|no|
|output|start_ready|1|no|
|input|job_id|32|no|
|input|job_n|16|no|
|input|halt|1|no|
|output|output_done|1|no|
|output|fault|1|no|
|input|rd_ready|1|no|
|output|rd_req|1|no|
|output|rd_word_index|16|no|
|input|rd_valid|1|no|
|input|rd_data|144|no|
|input|rd_exp|8|no|
|input|rd_mask|8|no|
|input|rd_index|16|no|
|output|m_axis_tdata|512|no|
|output|m_axis_tvalid|1|no|
|input|m_axis_tready|1|no|
|output|m_axis_tkeep|64|no|
|output|m_axis_tlast|1|no|
|output|m_axis_tuser|128|no|

## xw_job_status

|Direction|Name|Width|Signed|
|---|---|---:|---|
|input|clk|1|no|
|input|rst_n|1|no|
|input|finish_valid|1|no|
|output|finish_ready|1|no|
|input|finish_job_id|32|no|
|input|finish_ok|1|no|
|input|finish_error_code|8|no|
|output|status_valid|1|no|
|input|status_ready|1|no|
|output|status_job_id|32|no|
|output|status_ok|1|no|
|output|status_error_code|8|no|

## xw_linear_scheduler

|Direction|Name|Width|Signed|
|---|---|---:|---|
|input|clk|1|no|
|input|rst_n|1|no|
|input|job_valid|1|no|
|output|job_ready|1|no|
|input|job_id|32|no|
|input|job_m|16|no|
|input|job_n|16|no|
|input|job_k|16|no|
|input|job_m_tile|8|no|
|input|job_weight_base|29|no|
|input|job_scale_base|29|no|
|output|busy|1|no|
|output|active_id|32|no|
|output|active_n|16|no|
|output|active_k|16|no|
|output|weight_base|29|no|
|output|scale_base|29|no|
|output|channel|16|no|
|output|group_index|9|no|
|output|cfg_begin|1|no|
|input|cfg_done|1|no|
|input|cfg_error|1|no|
|input|cfg_error_code|8|no|
|input|datapath_online|1|no|
|output|job_start|1|no|
|input|stage5_ready|1|no|
|input|x_loaded|1|no|
|input|input_done|1|no|
|output|x_complete|1|no|
|output|load_valid|1|no|
|input|load_ready|1|no|
|output|load_kind|1|no|
|output|load_index|16|no|
|input|load_done|1|no|
|output|compute_valid|1|no|
|input|compute_ready|1|no|
|input|result_valid|1|no|
|input|result_ready|1|no|
|input|group_done|1|no|
|input|committed_group|9|no|
|input|job_results_ready|1|no|
|output|output_start|1|no|
|input|output_ready|1|no|
|input|output_done|1|no|
|output|finish_valid|1|no|
|input|finish_ready|1|no|
|output|finish_ok|1|no|
|output|finish_code|8|no|
|input|status_accept|1|no|
|input|fault_valid|1|no|
|input|fault_code|8|no|
|input|fault_system|1|no|
|input|clean_boundary|1|no|
|output|first_error|8|no|
|output|fault_lock|1|no|
|output|cancel_datapath|1|no|
|output|clear_datapath|1|no|

## linear_xw_ip

|Direction|Name|Width|Signed|
|---|---|---:|---|
|input|clk|1|no|
|input|rst_n|1|no|
|input|job_valid|1|no|
|output|job_ready|1|no|
|input|job_id|32|no|
|input|job_m|16|no|
|input|job_n|16|no|
|input|job_k|16|no|
|input|job_m_tile|8|no|
|input|job_weight_base|29|no|
|input|job_scale_base|29|no|
|output|busy|1|no|
|output|status_valid|1|no|
|input|status_ready|1|no|
|output|status_job_id|32|no|
|output|status_ok|1|no|
|output|status_error_code|8|no|
|input|s_axis_tdata|512|no|
|input|s_axis_tvalid|1|no|
|output|s_axis_tready|1|no|
|input|s_axis_tkeep|64|no|
|input|s_axis_tlast|1|no|
|input|s_axis_tuser|128|no|
|output|m_axis_tdata|512|no|
|output|m_axis_tvalid|1|no|
|input|m_axis_tready|1|no|
|output|m_axis_tkeep|64|no|
|output|m_axis_tlast|1|no|
|output|m_axis_tuser|128|no|
|output|ddr_rd_req|1|no|
|output|ddr_rd_addra|29|no|
|output|ddr_rd_addrb|29|no|
|input|ddr_rd_rdy|1|no|
|input|ddr_rd_data|512|no|
|input|ddr_rd_vld|1|no|

