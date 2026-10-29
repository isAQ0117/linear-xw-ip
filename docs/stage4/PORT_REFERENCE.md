# 最终RTL端口清单

逐端口从最终ANSI声明提取。signed属性及语义以RTL和INTERFACE_AND_TIMING.md为准。

## xw_b1_dot128

| Port | Direction | Bits |
|---|---|---:|
| `clk` | input | 1 |
| `rst_n` | input | 1 |
| `abort` | input | 1 |
| `in_valid` | input | 1 |
| `in_ready` | output | 1 |
| `in_x` | input | 144 |
| `in_w` | input | 64 |
| `in_mask` | input | 8 |
| `in_exp` | input | 8 |
| `in_block` | input | 16 |
| `in_slice` | input | 4 |
| `in_last` | input | 1 |
| `out_valid` | output | 1 |
| `out_ready` | input | 1 |
| `out_raw` | output | 48 |
| `out_exp` | output | 8 |
| `out_block` | output | 16 |
| `fault` | output | 1 |
| `error_code` | output | 8 |

## xw_b2_fp32_pipe

| Port | Direction | Bits |
|---|---|---:|
| `clk` | input | 1 |
| `rst_n` | input | 1 |
| `abort` | input | 1 |
| `in_valid` | input | 1 |
| `in_ready` | output | 1 |
| `in_raw` | input | 48 |
| `in_exp` | input | 8 |
| `in_scale` | input | 32 |
| `in_block` | input | 16 |
| `out_valid` | output | 1 |
| `out_ready` | input | 1 |
| `out_mant` | output | 72 |
| `out_exp` | output | 12 |
| `out_block` | output | 16 |
| `out_error` | output | 8 |

## xw_a2_accum48

| Port | Direction | Bits |
|---|---|---:|
| `clk` | input | 1 |
| `rst_n` | input | 1 |
| `abort` | input | 1 |
| `clear` | input | 1 |
| `in_valid` | input | 1 |
| `in_ready` | output | 1 |
| `in_mant` | input | 72 |
| `in_exp` | input | 12 |
| `in_block` | input | 16 |
| `busy` | output | 1 |
| `update_valid` | output | 1 |
| `state_mant` | output | 48 |
| `state_exp` | output | 16 |
| `out_block` | output | 16 |
| `special_path` | output | 1 |
| `fault` | output | 1 |
| `error_code` | output | 8 |

## xw_b3b_compute_ctrl

| Port | Direction | Bits |
|---|---|---:|
| `clk` | input | 1 |
| `rst_n` | input | 1 |
| `abort` | input | 1 |
| `req_valid` | input | 1 |
| `req_ready` | output | 1 |
| `req_job` | input | 32 |
| `req_channel` | input | 16 |
| `req_k` | input | 16 |
| `x_loaded` | input | 1 |
| `w_loaded` | input | 1 |
| `s_loaded` | input | 1 |
| `upstream_fault` | input | 1 |
| `upstream_code` | input | 8 |
| `slice_enable` | input | 1 |
| `x_rd_req` | output | 1 |
| `x_rd_index` | output | 16 |
| `x_rd_valid` | input | 1 |
| `x_rd_data` | input | 144 |
| `x_rd_exp` | input | 8 |
| `x_rd_mask` | input | 8 |
| `w_rd_req` | output | 1 |
| `w_rd_index` | output | 16 |
| `w_rd_valid` | input | 1 |
| `w_rd_data` | input | 64 |
| `w_rd_mask` | input | 8 |
| `s_rd_req` | output | 1 |
| `s_rd_index` | output | 16 |
| `s_rd_valid` | input | 1 |
| `s_rd_bits` | input | 32 |
| `result_valid` | output | 1 |
| `result_ready` | input | 1 |
| `result_mant` | output | 48 |
| `result_exp` | output | 16 |
| `result_job` | output | 32 |
| `result_channel` | output | 16 |
| `error_valid` | output | 1 |
| `error_code` | output | 8 |
| `fault_lock` | output | 1 |

## xw_stage234_harness

| Port | Direction | Bits |
|---|---|---:|
| `clk` | input | 1 |
| `rst_n` | input | 1 |
| `abort` | input | 1 |
| `job_valid` | input | 1 |
| `job_ready` | output | 1 |
| `job_id` | input | 32 |
| `job_m` | input | 16 |
| `job_n` | input | 16 |
| `job_k` | input | 16 |
| `job_m_tile` | input | 8 |
| `job_weight_base` | input | 29 |
| `job_scale_base` | input | 29 |
| `s_axis_tdata` | input | 512 |
| `s_axis_tvalid` | input | 1 |
| `s_axis_tready` | output | 1 |
| `s_axis_tkeep` | input | 64 |
| `s_axis_tlast` | input | 1 |
| `s_axis_tuser` | input | 128 |
| `ddr_rd_req` | output | 1 |
| `ddr_rd_addra` | output | 29 |
| `ddr_rd_addrb` | output | 29 |
| `ddr_rd_rdy` | input | 1 |
| `ddr_rd_data` | input | 512 |
| `ddr_rd_vld` | input | 1 |
| `object_valid` | input | 1 |
| `object_ready` | output | 1 |
| `object_kind` | input | 1 |
| `object_index` | input | 16 |
| `object_done` | output | 1 |
| `x_loaded` | output | 1 |
| `w_loaded` | output | 1 |
| `s_loaded` | output | 1 |
| `compute_valid` | input | 1 |
| `compute_ready` | output | 1 |
| `compute_job` | input | 32 |
| `compute_channel` | input | 16 |
| `compute_k` | input | 16 |
| `slice_enable` | input | 1 |
| `result_valid` | output | 1 |
| `result_ready` | input | 1 |
| `result_mant` | output | 48 |
| `result_exp` | output | 16 |
| `result_job` | output | 32 |
| `result_channel` | output | 16 |
| `error_valid` | output | 1 |
| `error_code` | output | 8 |
| `fault_lock` | output | 1 |
