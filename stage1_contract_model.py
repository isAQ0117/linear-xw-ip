"""Stage-1 rising-edge reference models for four foundational RTL modules.

Reference behavior is intentionally local to Stage 1, without inventing a
full Scheduler/Job/Status pipeline.  `step()` consumes PRE-edge inputs and
returns POST-edge output state, equivalent to sampled Verilog NBA updates.
DDR physical recovery requires an external flush guarantee; modeling a local
reset does not claim that stale DDR responses have disappeared.
"""

from dataclasses import dataclass, field

DDR_COMMAND = 0x20
DDR_RESPONSE = 0x21
DDR_BUFFER = 0x23
INTERNAL_FAULT = 0x40


def ceildiv(a, b):
    return (a + b - 1) // b


@dataclass
class DimensionConfig:
    static_dim_mode: int = 1
    n_dim: int = 12288
    k_dim: int = 4096
    max_n: int = 12288
    max_k: int = 12288
    cfg_valid: bool = False
    cfg_error: bool = False
    active_n: int = 0
    active_k: int = 0

    def __post_init__(self):
        if self.static_dim_mode not in (0, 1):
            raise ValueError("STATIC_DIM_MODE must be 0 or 1")
        for field_name in ("n_dim", "k_dim", "max_n", "max_k"):
            v = getattr(self, field_name)
            if not 1 <= v <= 65535:
                raise ValueError(f"invalid compile-time {field_name}={v}")
        if self.static_dim_mode == 1 and (self.n_dim > self.max_n or self.k_dim > self.max_k):
            raise ValueError("static dimensions exceed maximum capacity")

    def reset(self):
        self.cfg_valid = self.cfg_error = False
        self.active_n = self.active_k = 0
        return self.snapshot()

    def step(self, *, job_accept=False, job_n=0, job_k=0, rst_n=True):
        if not rst_n:
            return self.reset()
        self.cfg_valid = bool(job_accept)
        if job_accept:
            if self.static_dim_mode:
                self.active_n, self.active_k = self.n_dim, self.k_dim
                self.cfg_error = False
            else:
                self.active_n, self.active_k = job_n, job_k
                self.cfg_error = (job_n == 0 or job_k == 0 or
                                  job_n > self.max_n or job_k > self.max_k)
        return self.snapshot()

    def snapshot(self):
        return dict(cfg_valid=self.cfg_valid, cfg_error=self.cfg_error,
                    active_n=self.active_n, active_k=self.active_k,
                    n_groups=ceildiv(self.active_n, 128),
                    k_blocks=ceildiv(self.active_k, 128),
                    weight_words_per_row=ceildiv(self.active_k, 64),
                    scale_words_per_group=ceildiv(self.active_k, 2048))


@dataclass
class DdrRangeReceiver:
    busy: bool = False
    handoff_hold: bool = False
    received_count: int = 0
    expected_beats: int = 0
    active_kind: int = 0
    word_valid: bool = False
    word_data: int = 0
    word_index: int = 0
    word_kind: int = 0
    range_done: bool = False
    range_error: bool = False
    range_error_code: int = 0

    def reset(self):
        self.__dict__.update(type(self)().__dict__)

    @staticmethod
    def valid_command(start, end, beats):
        return (1 <= beats <= 65535 and
                0 <= start < (1 << 29) and 0 <= end < (1 << 29) and
                start % 8 == 0 and end % 8 == 0 and end >= start and
                (end - start) // 8 + 1 == beats)

    def outputs(self, *, cmd_valid=False, start=0, end=0, beats=0,
                ddr_rd_rdy=False, rst_n=True):
        window = rst_n and not (self.busy or self.handoff_hold or self.range_error)
        cmd_ready = (window and ddr_rd_rdy and
                     self.valid_command(start, end, beats))
        req = bool(cmd_valid and cmd_ready)
        return dict(cmd_ready=bool(cmd_ready), ddr_rd_req=req,
                    ddr_rd_addra=start, ddr_rd_addrb=end)

    def step(self, *, rst_n=True, cmd_valid=False, start=0, end=0, beats=0,
             kind=0, ddr_rd_rdy=False, ddr_rd_vld=False, ddr_rd_data=0):
        if not rst_n:
            self.reset()
            return self.snapshot()
        signals = self.outputs(cmd_valid=cmd_valid, start=start, end=end,
                               beats=beats, ddr_rd_rdy=ddr_rd_rdy)
        accept = signals["ddr_rd_req"]
        window = not (self.busy or self.handoff_hold or self.range_error)
        previously_busy = self.busy
        self.word_valid = False
        self.range_done = False
        self.handoff_hold = False
        if self.range_error:
            self.busy = False
        elif ddr_rd_vld and not previously_busy and not accept:
            self.range_error = True
            self.range_error_code = DDR_RESPONSE
            self.busy = False
        elif window and cmd_valid and not self.valid_command(start, end, beats):
            self.range_error = True
            self.range_error_code = DDR_COMMAND
            self.busy = False
        elif accept:
            self.expected_beats = beats
            self.active_kind = kind
            self.received_count = 0
            if ddr_rd_vld:
                self.word_valid = True
                self.word_data = ddr_rd_data
                self.word_index = 0
                self.word_kind = kind
                if beats == 1:
                    self.busy = False
                    self.range_done = True
                    self.handoff_hold = True
                else:
                    self.busy = True
                    self.received_count = 1
            else:
                self.busy = True
        elif previously_busy and ddr_rd_vld:
            self.word_valid = True
            self.word_data = ddr_rd_data
            self.word_index = self.received_count
            self.word_kind = self.active_kind
            if self.received_count == self.expected_beats - 1:
                self.busy = False
                self.received_count = 0
                self.range_done = True
                self.handoff_hold = True
            else:
                self.received_count += 1
        return self.snapshot()

    def snapshot(self):
        return dict(busy=self.busy, handoff_hold=self.handoff_hold,
                    received_count=self.received_count,
                    word_valid=self.word_valid, word_data=self.word_data,
                    word_index=self.word_index, word_kind=self.word_kind,
                    range_done=self.range_done, range_error=self.range_error,
                    range_error_code=self.range_error_code)


@dataclass
class ScaleGroupCache:
    max_k: int = 12288
    max_scale_words: int = None
    loaded: bool = False
    cache_error: bool = False
    cache_error_code: int = 0
    rd_valid: bool = False
    rd_scale_bits: int = 0
    expected_words: int = 0
    expected_scales: int = 0
    words_written: int = 0
    words: list = field(default_factory=list)

    def __post_init__(self):
        if not 1 <= self.max_k <= 65535:
            raise ValueError("MAX_K out of range")
        if self.max_scale_words is None:
            self.max_scale_words = ceildiv(self.max_k, 2048)
        if not ceildiv(self.max_k, 2048) <= self.max_scale_words <= 65535:
            raise ValueError("MAX_SCALE_WORDS too small or out of range")
        self.words = [0] * self.max_scale_words

    def reset(self):
        # Memory bits need not be initialized by hardware; model keeps them.
        self.loaded = self.cache_error = self.rd_valid = False
        self.cache_error_code = self.rd_scale_bits = 0
        self.expected_words = self.expected_scales = self.words_written = 0
        return self.snapshot()

    def fault(self, code):
        self.loaded = False
        self.cache_error = True
        self.cache_error_code = code
        self.rd_scale_bits = 0

    def step(self, *, rst_n=True, load_begin=False, load_words=0, load_scales=0,
             wr_valid=False, wr_data=0, wr_word_index=0,
             rd_req=False, rd_scale_index=0):
        if not rst_n:
            return self.reset()
        self.rd_valid = False
        if self.cache_error:
            self.loaded = False
        elif ((load_begin and (wr_valid or rd_req)) or (wr_valid and rd_req)):
            self.fault(INTERNAL_FAULT)
        elif load_begin:
            self.loaded = False
            self.words_written = 0
            self.expected_words = load_words
            self.expected_scales = load_scales
            if not (1 <= load_words <= self.max_scale_words and
                    1 <= load_scales <= ceildiv(self.max_k, 128) and
                    load_words == ceildiv(load_scales, 16)):
                self.fault(INTERNAL_FAULT)
        elif wr_valid:
            if (self.loaded or wr_word_index != self.words_written or
                    wr_word_index >= self.expected_words or
                    wr_word_index >= self.max_scale_words):
                self.fault(DDR_BUFFER)
            else:
                self.words[wr_word_index] = wr_data
                self.words_written += 1
                if self.words_written == self.expected_words:
                    self.loaded = True
        elif rd_req:
            rd_word_index, lane = divmod(rd_scale_index, 16)
            if (self.loaded and rd_scale_index < self.expected_scales and
                    rd_word_index < self.expected_words and
                    rd_word_index < self.max_scale_words):
                self.rd_scale_bits = (self.words[rd_word_index] >> (32 * lane)) & 0xffffffff
                self.rd_valid = True
            else:
                self.fault(INTERNAL_FAULT)
        return self.snapshot()

    def snapshot(self):
        return dict(loaded=self.loaded, cache_error=self.cache_error,
                    cache_error_code=self.cache_error_code,
                    rd_valid=self.rd_valid, rd_scale_bits=self.rd_scale_bits,
                    expected_words=self.expected_words,
                    expected_scales=self.expected_scales,
                    words_written=self.words_written)
