# 实际ANSI端口参考
位宽直接由最终RTL读取；语义/握手/复位以INTERFACE_AND_TIMING.md为准。Harness为test-only，并非35-port TOP。

## xw_axis_bfp18_input

| 端口 | 方向 | 位宽 |
|---|---|---:|
| `clk` | 输入 | 1 |
| `rst_n` | 输入 | 1 |
| `abort` | 输入 | 1 |
| `job_begin` | 输入 | 1 |
| `job_id` | 输入 | 32 |
| `job_k` | 输入 | 16 |
| `s_axis_tdata` | 输入 | 512 |
| `s_axis_tvalid` | 输入 | 1 |
| `s_axis_tready` | 输出 | 1 |
| `s_axis_tkeep` | 输入 | 64 |
| `s_axis_tlast` | 输入 | 1 |
| `s_axis_tuser` | 输入 | 128 |
| `wr_valid` | 输出 | 1 |
| `wr_ready` | 输入 | 1 |
| `wr_data` | 输出 | 144 |
| `wr_mask` | 输出 | 8 |
| `wr_exp` | 输出 | 8 |
| `wr_word_index` | 输出 | 16 |
| `wr_last` | 输出 | 1 |
| `done` | 输出 | 1 |
| `fault` | 输出 | 1 |
| `error_code` | 输出 | 8 |

## xw_activation_buffer

| 端口 | 方向 | 位宽 |
|---|---|---:|
| `clk` | 输入 | 1 |
| `rst_n` | 输入 | 1 |
| `abort` | 输入 | 1 |
| `load_begin` | 输入 | 1 |
| `load_k` | 输入 | 16 |
| `wr_valid` | 输入 | 1 |
| `wr_ready` | 输出 | 1 |
| `wr_data` | 输入 | 144 |
| `wr_mask` | 输入 | 8 |
| `wr_exp` | 输入 | 8 |
| `wr_word_index` | 输入 | 16 |
| `wr_last` | 输入 | 1 |
| `loaded` | 输出 | 1 |
| `fault` | 输出 | 1 |
| `error_code` | 输出 | 8 |
| `rd_req` | 输入 | 1 |
| `rd_word_index` | 输入 | 16 |
| `rd_valid` | 输出 | 1 |
| `rd_data` | 输出 | 144 |
| `rd_exp` | 输出 | 8 |
| `rd_mask` | 输出 | 8 |

## xw_ddr_addr_gen

| 端口 | 方向 | 位宽 |
|---|---|---:|
| `clk` | 输入 | 1 |
| `rst_n` | 输入 | 1 |
| `abort` | 输入 | 1 |
| `cfg_begin` | 输入 | 1 |
| `cfg_n` | 输入 | 16 |
| `cfg_k` | 输入 | 16 |
| `cfg_weight_base` | 输入 | 29 |
| `cfg_scale_base` | 输入 | 29 |
| `cfg_done` | 输出 | 1 |
| `cfg_error` | 输出 | 1 |
| `cfg_error_code` | 输出 | 8 |
| `load_valid` | 输入 | 1 |
| `load_ready` | 输出 | 1 |
| `load_kind` | 输入 | 1 |
| `load_index` | 输入 | 16 |
| `scale_load_begin` | 输出 | 1 |
| `weight_load_begin` | 输出 | 1 |
| `load_words` | 输出 | 16 |
| `load_scales` | 输出 | 16 |
| `load_k` | 输出 | 16 |
| `load_done` | 输出 | 1 |
| `cmd_valid` | 输出 | 1 |
| `cmd_ready` | 输入 | 1 |
| `cmd_addr_start` | 输出 | 29 |
| `cmd_addr_end` | 输出 | 29 |
| `cmd_beats` | 输出 | 16 |
| `cmd_kind` | 输出 | 1 |
| `range_done` | 输入 | 1 |
| `range_error` | 输入 | 1 |
| `range_error_code` | 输入 | 8 |
| `buffer_loaded` | 输入 | 1 |
| `buffer_error` | 输入 | 1 |
| `buffer_error_code` | 输入 | 8 |
| `segment_offset` | 输出 | 16 |
| `fault` | 输出 | 1 |
| `error_code` | 输出 | 8 |

## xw_weight_row_buffer

| 端口 | 方向 | 位宽 |
|---|---|---:|
| `clk` | 输入 | 1 |
| `rst_n` | 输入 | 1 |
| `abort` | 输入 | 1 |
| `load_begin` | 输入 | 1 |
| `load_k` | 输入 | 16 |
| `wr_valid` | 输入 | 1 |
| `wr_data` | 输入 | 512 |
| `wr_word_index` | 输入 | 16 |
| `loaded` | 输出 | 1 |
| `fault` | 输出 | 1 |
| `error_code` | 输出 | 8 |
| `rd_req` | 输入 | 1 |
| `rd_word_index` | 输入 | 16 |
| `rd_valid` | 输出 | 1 |
| `rd_data` | 输出 | 64 |
| `rd_mask` | 输出 | 8 |

## xw_stage23_harness

| 端口 | 方向 | 位宽 |
|---|---|---:|
| `clk` | 输入 | 1 |
| `rst_n` | 输入 | 1 |
| `job_valid` | 输入 | 1 |
| `job_ready` | 输出 | 1 |
| `job_id` | 输入 | 32 |
| `job_m` | 输入 | 16 |
| `job_n` | 输入 | 16 |
| `job_k` | 输入 | 16 |
| `job_m_tile` | 输入 | 8 |
| `job_weight_base` | 输入 | 29 |
| `job_scale_base` | 输入 | 29 |
| `s_axis_tdata` | 输入 | 512 |
| `s_axis_tvalid` | 输入 | 1 |
| `s_axis_tready` | 输出 | 1 |
| `s_axis_tkeep` | 输入 | 64 |
| `s_axis_tlast` | 输入 | 1 |
| `s_axis_tuser` | 输入 | 128 |
| `ddr_rd_req` | 输出 | 1 |
| `ddr_rd_addra` | 输出 | 29 |
| `ddr_rd_addrb` | 输出 | 29 |
| `ddr_rd_rdy` | 输入 | 1 |
| `ddr_rd_data` | 输入 | 512 |
| `ddr_rd_vld` | 输入 | 1 |
| `object_valid` | 输入 | 1 |
| `object_ready` | 输出 | 1 |
| `object_kind` | 输入 | 1 |
| `object_index` | 输入 | 16 |
| `object_done` | 输出 | 1 |
| `x_loaded` | 输出 | 1 |
| `scale_loaded` | 输出 | 1 |
| `weight_loaded` | 输出 | 1 |
| `x_rd_req` | 输入 | 1 |
| `x_rd_index` | 输入 | 16 |
| `x_rd_valid` | 输出 | 1 |
| `x_rd_data` | 输出 | 144 |
| `x_rd_exp` | 输出 | 8 |
| `x_rd_mask` | 输出 | 8 |
| `scale_rd_req` | 输入 | 1 |
| `scale_rd_index` | 输入 | 16 |
| `scale_rd_valid` | 输出 | 1 |
| `scale_rd_bits` | 输出 | 32 |
| `weight_rd_req` | 输入 | 1 |
| `weight_rd_index` | 输入 | 16 |
| `weight_rd_valid` | 输出 | 1 |
| `weight_rd_data` | 输出 | 64 |
| `weight_rd_mask` | 输出 | 8 |
| `finish_test` | 输入 | 1 |
| `result_valid` | 输出 | 1 |
| `result_ready` | 输入 | 1 |
| `result_code` | 输出 | 8 |
| `fault_lock` | 输出 | 1 |

## B1消费约定

X读word索引对应K位置8*index。lane i为rd_data[18*i +: 18]，由消费模块作为signed18使用；rd_exp作为signed8使用。Weight lane i为rd_data[8*i +: 8]的FP8原始字节；只有rd_valid且rd_mask[i]时参与后续计算。无效lane为0。rd_req在上升沿t采样，数据/exp/mask/valid于t后有效，下一同步消费模块在t+1沿消费；支持连续每拍一个word。没有输出ready，B1仅在可消费时请求。

```verilog
wire signed [17:0] x_lane0;
wire signed [7:0] x_exponent;
assign x_lane0 = x_rd_data[17:0];
assign x_exponent = x_rd_exp;
```
