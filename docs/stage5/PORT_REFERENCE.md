# 最终ANSI端口清单

signed属性和握手语义以RTL及INTERFACE_AND_TIMING.md为准。

## xw_output_group_buffer

| Port | Direction | Bits |
|---|---|---:|
| clk | input | 1 |
| rst_n | input | 1 |
| cancel | input | 1 |
| begin_group | input | 1 |
| group_job | input | 32 |
| group_base | input | 16 |
| group_len | input | 8 |
| result_valid | input | 1 |
| result_ready | output | 1 |
| result_mant | input | 48 |
| result_exp | input | 16 |
| result_job | input | 32 |
| result_channel | input | 16 |
| loaded | output | 1 |
| nonzero | output | 1 |
| hmax | output | 18 |
| rd_req | input | 1 |
| rd_index | input | 7 |
| rd_valid | output | 1 |
| rd_mant | output | 48 |
| rd_exp | output | 16 |
| fault | output | 1 |

## xw_bfp18_requant

| Port | Direction | Bits |
|---|---|---:|
| clk | input | 1 |
| rst_n | input | 1 |
| cancel | input | 1 |
| start | input | 1 |
| group_len | input | 8 |
| nonzero | input | 1 |
| hmax | input | 18 |
| rd_req | output | 1 |
| rd_index | output | 7 |
| rd_valid | input | 1 |
| rd_mant | input | 48 |
| rd_exp | input | 16 |
| attempt_begin | output | 1 |
| q_valid | output | 1 |
| q_index | output | 7 |
| q_mant | output | 19 |
| q_last | output | 1 |
| done | output | 1 |
| shared_exp | output | 8 |
| retried | output | 1 |
| fault | output | 1 |
| error_code | output | 8 |

## xw_result_buffer

| Port | Direction | Bits |
|---|---|---:|
| clk | input | 1 |
| rst_n | input | 1 |
| cancel | input | 1 |
| job_begin | input | 1 |
| job_n | input | 16 |
| attempt_begin | input | 1 |
| group_index | input | 9 |
| group_len | input | 8 |
| q_valid | input | 1 |
| q_index | input | 7 |
| q_mant | input | 18 |
| q_last | input | 1 |
| commit | input | 1 |
| commit_exp | input | 8 |
| publish | input | 1 |
| group_committed | output | 1 |
| job_results_ready | output | 1 |
| rd_req | input | 1 |
| rd_ready | output | 1 |
| rd_word_index | input | 16 |
| rd_valid | output | 1 |
| rd_data | output | 144 |
| rd_exp | output | 8 |
| rd_mask | output | 8 |
| rd_index | output | 16 |
| fault | output | 1 |

## xw_stage5_ctrl

| Port | Direction | Bits |
|---|---|---:|
| clk | input | 1 |
| rst_n | input | 1 |
| abort | input | 1 |
| job_start | input | 1 |
| job_ready | output | 1 |
| job_id | input | 32 |
| job_n | input | 16 |
| retire | input | 1 |
| clean_boundary | input | 1 |
| upstream_fault | input | 1 |
| upstream_code | input | 8 |
| upstream_lock | input | 1 |
| result_valid | input | 1 |
| result_ready | output | 1 |
| result_mant | input | 48 |
| result_exp | input | 16 |
| result_job | input | 32 |
| result_channel | input | 16 |
| group_done | output | 1 |
| group_job | output | 32 |
| group_id | output | 9 |
| group_len | output | 8 |
| group_exp | output | 8 |
| job_results_ready | output | 1 |
| error_valid | output | 1 |
| error_code | output | 8 |
| fault_lock | output | 1 |
| rd_req | input | 1 |
| rd_ready | output | 1 |
| rd_word_index | input | 16 |
| rd_valid | output | 1 |
| rd_data | output | 144 |
| rd_exp | output | 8 |
| rd_mask | output | 8 |
| rd_index | output | 16 |

## xw_stage45_harness

| Port | Direction | Bits |
|---|---|---:|
| clk | input | 1 |
| rst_n | input | 1 |
| abort | input | 1 |
| job_valid | input | 1 |
| job_ready | output | 1 |
| job_id | input | 32 |
| job_m | input | 16 |
| job_n | input | 16 |
| job_k | input | 16 |
| job_m_tile | input | 8 |
| job_weight_base | input | 29 |
| job_scale_base | input | 29 |
| s_axis_tdata | input | 512 |
| s_axis_tvalid | input | 1 |
| s_axis_tready | output | 1 |
| s_axis_tkeep | input | 64 |
| s_axis_tlast | input | 1 |
| s_axis_tuser | input | 128 |
| ddr_rd_req | output | 1 |
| ddr_rd_addra | output | 29 |
| ddr_rd_addrb | output | 29 |
| ddr_rd_rdy | input | 1 |
| ddr_rd_data | input | 512 |
| ddr_rd_vld | input | 1 |
| object_valid | input | 1 |
| object_ready | output | 1 |
| object_kind | input | 1 |
| object_index | input | 16 |
| object_done | output | 1 |
| x_loaded | output | 1 |
| w_loaded | output | 1 |
| s_loaded | output | 1 |
| compute_valid | input | 1 |
| compute_ready | output | 1 |
| compute_job | input | 32 |
| compute_channel | input | 16 |
| compute_k | input | 16 |
| slice_enable | input | 1 |
| result_valid | output | 1 |
| result_ready | output | 1 |
| result_mant | output | 48 |
| result_exp | output | 16 |
| result_job | output | 32 |
| result_channel | output | 16 |
| stage4_error_valid | output | 1 |
| stage4_error_code | output | 8 |
| stage4_fault_lock | output | 1 |
| retire | input | 1 |
| rd_req | input | 1 |
| rd_word_index | input | 16 |
| rd_ready | output | 1 |
| rd_valid | output | 1 |
| rd_data | output | 144 |
| rd_exp | output | 8 |
| rd_mask | output | 8 |
| rd_index | output | 16 |
| group_done | output | 1 |
| group_job | output | 32 |
| group_id | output | 9 |
| group_len | output | 8 |
| group_exp | output | 8 |
| job_results_ready | output | 1 |
| error_valid | output | 1 |
| error_code | output | 8 |
| fault_lock | output | 1 |
