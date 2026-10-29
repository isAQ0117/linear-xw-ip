"""Stage 2/3 register-level models. step uses pre-edge inputs, returns NBA state.

Each register and state corresponds to the named Verilog implementation.
No data-level oracle functions are used to implement these models.
"""

class Parser:
    def __init__(self, max_k=12288):
        if not 1 <= max_k <= 65535:
            raise ValueError('MAX_K')
        self.max_k = max_k
        self.reset()

    def reset(self):
        for name in ('active active_id active_k group_id group_offset group_exp input_end '
                     'beat_shift remaining beat_exp beat_final pack_data pack_lanes next_word '
                     'wr_valid wr_data wr_mask wr_exp wr_word_index wr_last done fault error_code').split():
            setattr(self, name, 0)

    def ready(self, **i):
        return int(i.get('rst_n', 1) and not (i.get('abort', 0) or self.fault or i.get('job_begin', 0)) and
                   self.active and not self.input_end and self.remaining == 0 and not self.wr_valid)

    def snapshot(self, **i):
        return {n: int(getattr(self, n)) for n in
                'wr_valid wr_data wr_mask wr_exp wr_word_index wr_last done fault error_code'.split()} | {
                    's_axis_tready': self.ready(**i)}

    def step(self, **i):
        get = lambda n: i.get(n, 0)
        if not i.get('rst_n', 1):
            self.reset()
            return self.snapshot(**i)
        ready = self.ready(**i)
        self.done = 0
        if self.fault or get('abort'):
            self.active = self.wr_valid = self.remaining = 0
            if not self.fault:
                self.fault, self.error_code = 1, 0x40
        elif get('job_begin') and (self.active or self.wr_valid or not 1 <= get('job_k') <= self.max_k):
            self.fault, self.error_code = 1, 0x40
            self.active = self.wr_valid = 0
        elif get('job_begin'):
            self.active, self.active_id, self.active_k = 1, get('job_id'), get('job_k')
            self.group_id = self.group_offset = self.group_exp = self.input_end = 0
            self.remaining = self.pack_data = self.pack_lanes = self.next_word = 0
        elif get('s_axis_tvalid') and ready:
            u, d = get('s_axis_tuser'), get('s_axis_tdata')
            length = min(128, self.active_k-self.group_id*128)
            count = min(28, length-self.group_offset)
            last = self.group_offset+count == length
            final = last and self.group_id*128+length == self.active_k
            exp = (u >> 64) & 255
            if (u >> 104 or (u >> 96) & 255 != 0xb2 or (u >> 89) & 127 or
                    (u >> 57) & 127 or u & 0xffffffff != self.active_id):
                code = 0x10
            elif ((u >> 32) & 65535 != 0 or (u >> 48) & 511 != self.group_id or
                  (u >> 72) & 255 != length or (u >> 80) & 255 != self.group_offset or
                  (self.group_offset != 0 and exp != self.group_exp)):
                code = 0x11
            elif get('s_axis_tkeep') != (1 << ((count*18+7)//8))-1 or d >> (count*18):
                code = 0x12
            elif get('s_axis_tlast') != last or (u >> 88) & 1 != final:
                code = 0x13
            else:
                code = 0
            if code:
                self.fault, self.error_code = 1, code
                self.active = self.wr_valid = self.remaining = 0
            else:
                self.beat_shift, self.remaining = d, count
                self.beat_exp, self.beat_final, self.input_end = exp, int(final), int(final)
                if self.group_offset == 0:
                    self.group_exp = exp
                if last:
                    self.group_id, self.group_offset = (self.group_id+1) & 511, 0
                else:
                    self.group_offset += count
        elif self.wr_valid:
            if get('wr_ready'):
                self.wr_valid = 0
                if self.wr_last:
                    self.done, self.active = 1, 0
        elif self.remaining:
            assembled = self.pack_data | ((self.beat_shift & 0x3ffff) << (self.pack_lanes*18))
            flush = self.pack_lanes == 7 or (self.beat_final and self.remaining == 1)
            if flush:
                self.wr_valid, self.wr_data = 1, assembled
                self.wr_mask, self.wr_exp = (1 << (self.pack_lanes+1))-1, self.beat_exp
                self.wr_word_index, self.wr_last = self.next_word, int(self.beat_final and self.remaining == 1)
                self.next_word += 1
                self.pack_data = self.pack_lanes = 0
            else:
                self.pack_data, self.pack_lanes = assembled, self.pack_lanes+1
            self.beat_shift >>= 18
            self.remaining -= 1
        return self.snapshot(**i)


class Buffer:
    """Shared control skeleton; X stores 144b + exp RAM, W stores 512b.

    The hardware is two separate Verilog modules. No tests use this class to
    construct golden data; both are checked against source arrays/bytes.
    """
    def __init__(self, kind, max_k=12288):
        if kind not in ('x', 'w') or not 1 <= max_k <= 65535:
            raise ValueError('buffer parameters')
        self.kind, self.max_k = kind, max_k
        self.words, self.exponents = {}, {}
        self.ram_read_data = self.ram_read_exp = 0
        self.reset()

    def reset(self):
        for n in ('loaded_reg read_valid_reg loading fault error_code active_k total_words '
                  'read_words written current_exp read_seen read_lane rd_mask').split():
            setattr(self, n, 0)

    def snapshot(self, **i):
        enabled = i.get('rst_n', 1) and not (i.get('abort', 0) or self.fault)
        data = self.ram_read_data if self.kind == 'x' else (self.ram_read_data >> (self.read_lane*64)) & ((1<<64)-1)
        if not self.read_seen:
            data = 0
        if self.kind == 'w':
            for lane in range(8):
                if not (self.rd_mask >> lane) & 1:
                    data &= ~(255 << (lane*8))
        o = dict(loaded=int(enabled and self.loaded_reg), rd_valid=int(enabled and self.read_valid_reg),
                 fault=self.fault, error_code=self.error_code, rd_data=data, rd_mask=self.rd_mask)
        if self.kind == 'x':
            o['rd_exp'] = self.ram_read_exp if self.read_seen else 0
            o['wr_ready'] = int(enabled and self.loading and not (i.get('load_begin', 0) or i.get('rd_req', 0)))
        return o

    def fail(self, code):
        self.fault, self.error_code = 1, code
        self.loaded_reg = self.loading = 0

    def step(self, **i):
        get = lambda n: i.get(n, 0)
        if not i.get('rst_n', 1):
            self.reset()
            return self.snapshot(**i)
        self.read_valid_reg = 0
        begin, wr, rd = get('load_begin'), get('wr_valid'), get('rd_req')
        rindex = get('rd_word_index')
        if self.fault or get('abort'):
            if not self.fault:
                self.fail(0x40)
            self.loaded_reg = self.loading = 0
        elif ((begin and (self.loading or wr or rd)) or (wr and rd) or
              (begin and not 1 <= get('load_k') <= self.max_k) or
              (rd and (not self.loaded_reg or rindex >= self.read_words))):
            self.fail(0x40)
        elif begin:
            self.loaded_reg, self.loading = 0, 1
            self.active_k = get('load_k')
            self.total_words = (self.active_k+(7 if self.kind == 'x' else 63))//(8 if self.kind == 'x' else 64)
            self.read_words = (self.active_k+7)//8
            self.written = 0
        elif wr:
            final = self.written+1 == self.total_words
            mask = (1 << (self.active_k % 8))-1 if final and self.active_k % 8 else 255
            invalid = (not self.loading or get('wr_word_index') != self.written or self.written >= self.total_words)
            if self.kind == 'x':
                invalid |= (get('wr_mask') != mask or get('wr_last') != final or
                            (self.written % 16 and get('wr_exp') != self.current_exp) or
                            (final and self.active_k % 8 and get('wr_data') >> (self.active_k % 8 * 18)))
            if invalid:
                self.fail(0x40 if self.kind == 'x' else 0x23)
            else:
                self.words[self.written] = get('wr_data')
                if self.kind == 'x' and self.written % 16 == 0:
                    self.exponents[self.written//16] = self.current_exp = get('wr_exp')
                self.written += 1
                if final:
                    self.loaded_reg, self.loading = 1, 0
        elif rd:
            self.rd_mask = (1 << (self.active_k % 8))-1 if rindex+1 == self.read_words and self.active_k % 8 else 255
            if self.kind == 'x':
                self.ram_read_data, self.ram_read_exp = self.words[rindex], self.exponents[rindex//16]
            else:
                self.ram_read_data = self.words[rindex//8]
                self.read_lane = rindex % 8
            self.read_seen = 1
            self.read_valid_reg = 1
        return self.snapshot(**i)


class AddrGen:
    IDLE, INIT, REQUEST, RECEIVE, COMMIT, LOADED = range(6)

    def __init__(self, burst, max_n=12288, max_k=12288):
        if not 1 <= burst <= 65535 or not 1 <= max_n <= 65535 or not 1 <= max_k <= 65535:
            raise ValueError('address gen parameters')
        self.burst, self.max_n, self.max_k = burst, max_n, max_k
        self.reset()

    def reset(self):
        for n in ('state configured active_n active_k weight_base scale_base weight_words scale_words '
                  'n_groups k_blocks kind object_base total_words offset cfg_done cfg_error cfg_error_code '
                  'load_done fault error_code').split():
            setattr(self, n, 0)

    def snapshot(self, **i):
        blocked = not i.get('rst_n', 1) or any(i.get(n, 0) for n in ('abort', 'range_error', 'buffer_error')) or self.fault
        beats = min(self.total_words-self.offset, self.burst)
        start = self.object_base + 8*self.offset
        end = (start+8*(beats-1)) % (1 << 64)
        return dict(cfg_done=self.cfg_done, cfg_error=self.cfg_error, cfg_error_code=self.cfg_error_code,
                    load_ready=int(not blocked and self.configured and self.state == self.IDLE and not i.get('cfg_begin', 0)),
                    scale_load_begin=int(not blocked and self.state == self.INIT and not self.kind),
                    weight_load_begin=int(not blocked and self.state == self.INIT and self.kind),
                    load_words=self.total_words, load_scales=self.k_blocks, load_k=self.active_k,
                    load_done=int(self.load_done and not blocked), cmd_valid=int(not blocked and self.state == self.REQUEST and beats != 0 and end < 2**29),
                    cmd_addr_start=start % (1<<29), cmd_addr_end=end % (1<<29), cmd_beats=beats,
                    cmd_kind=self.kind, segment_offset=self.offset, fault=self.fault, error_code=self.error_code)

    def step(self, **i):
        get = lambda n: i.get(n, 0)
        if not i.get('rst_n', 1):
            self.reset()
            return self.snapshot(**i)
        pre = self.snapshot(**i)
        self.cfg_done = self.load_done = 0
        if self.fault:
            self.configured = 0
        elif get('range_error') or get('buffer_error') or get('abort'):
            self.fault = 1
            self.error_code = get('range_error_code') if get('range_error') else get('buffer_error_code') if get('buffer_error') else 0x40
            self.configured = 0
        elif get('cfg_begin') and (self.state != self.IDLE or get('load_valid')):
            self.fault, self.error_code, self.configured = 1, 0x40, 0
        elif get('cfg_begin'):
            n, k, wb, sb = (get(x) for x in ('cfg_n', 'cfg_k', 'cfg_weight_base', 'cfg_scale_base'))
            rw, rs, groups = (k+63)//64, (k+2047)//2048, (n+127)//128
            wend, send = wb+8*n*rw, sb+8*groups*rs
            self.cfg_done, self.cfg_error, self.cfg_error_code, self.configured = 1, 0, 0, 0
            if not 1 <= n <= self.max_n or not 1 <= k <= self.max_k:
                self.cfg_error, self.cfg_error_code = 1, 1
            elif wb % 8 or sb % 8 or wend > 2**29 or send > 2**29 or not (wend <= sb or send <= wb):
                self.cfg_error, self.cfg_error_code = 1, 3
            else:
                self.configured = 1
                self.active_n, self.active_k = n, k
                self.weight_base, self.scale_base = wb, sb
                self.weight_words, self.scale_words, self.n_groups, self.k_blocks = rw, rs, groups, (k+127)//128
        elif self.state == self.IDLE:
            if get('load_valid') and pre['load_ready']:
                kind, idx = get('load_kind'), get('load_index')
                base = (self.weight_base+8*idx*self.weight_words) if kind else self.scale_base+8*idx*self.scale_words
                if idx >= (self.active_n if kind else self.n_groups) or base >= 2**29:
                    self.fault, self.error_code = 1, 0x40
                else:
                    self.kind, self.object_base, self.total_words, self.offset = kind, base, self.weight_words if kind else self.scale_words, 0
                    self.state = self.INIT
        elif self.state == self.INIT:
            self.state = self.REQUEST
        elif self.state == self.REQUEST:
            if pre['cmd_beats'] == 0 or self.object_base+8*(self.offset+pre['cmd_beats']-1) >= 2**29:
                self.fault, self.error_code = 1, 0x20
            elif get('cmd_ready'):
                self.state = self.RECEIVE
        elif self.state == self.RECEIVE:
            if get('range_done'):
                self.state = self.COMMIT
        elif self.state == self.COMMIT:
            if self.offset+pre['cmd_beats'] == self.total_words:
                self.state = self.LOADED
            else:
                self.offset += pre['cmd_beats']
                self.state = self.REQUEST
        elif self.state == self.LOADED:
            if get('buffer_loaded'):
                self.load_done, self.state = 1, self.IDLE
        else:
            self.fault, self.error_code = 1, 0x40
        return self.snapshot(**i)


class Harness:
    """Exact test-harness pipeline including shared two-flop reset release.

    Composed steps use copies of all OLD inter-module outputs; updating a Python
    submodule never creates an accidental same-edge bypass to its consumer.
    """
    IDLE, DIMS, CFG, CHECK, XBEGIN, X, ACCESS, RESULT, LOCK = range(9)

    def __init__(self, burst, max_n=129, max_k=12288, static=0, n_dim=2, k_dim=129):
        from stage1_contract_model import DimensionConfig, DdrRangeReceiver, ScaleGroupCache
        self.p = Parser(max_k)
        self.x = Buffer('x', max_k)
        self.w = Buffer('w', max_k)
        self.a = AddrGen(burst, max_n, max_k)
        self.d = DimensionConfig(static, n_dim, k_dim, max_n, max_k)
        self.r = DdrRangeReceiver()
        self.s = ScaleGroupCache(max_k)
        self.release = 0
        self.reset_control()

    def reset_control(self):
        self.state = self.IDLE
        self.active_id = self.active_m = self.active_tile = self.weight_base = self.scale_base = 0
        self.locked = self.first_code = self.result_valid = self.result_code = 0
        self.scale_owned = self.weight_owned = 0

    def reset_all(self):
        self.release = 0
        self.reset_control()
        for m in (self.p, self.x, self.w, self.a, self.d, self.r, self.s):
            m.reset()

    def signals(self, **i):
        rst = (self.release >> 1) & 1
        faults = [(self.p.fault, self.p.error_code), (self.x.fault, self.x.error_code),
                  (self.w.fault, self.w.error_code), (self.a.fault, self.a.error_code),
                  (self.r.range_error, self.r.range_error_code), (self.s.cache_error, self.s.cache_error_code)]
        fatal = int(self.locked or any(f for f,c in faults))
        fatal_code = min([0x40] + [c for f,c in faults if f])
        access = self.state == self.ACCESS and not fatal
        common = dict(rst_n=rst, abort=fatal)
        ac = dict(common, cfg_begin=int(self.state == self.CFG and not fatal), cfg_n=self.d.active_n,
                  cfg_k=self.d.active_k, cfg_weight_base=self.weight_base, cfg_scale_base=self.scale_base,
                  load_valid=int(i.get('object_valid', 0) and access), load_kind=i.get('object_kind', 0),
                  load_index=i.get('object_index', 0), range_done=int(self.r.range_done),
                  range_error=int(self.r.range_error), range_error_code=self.r.range_error_code,
                  buffer_loaded=int(self.w.loaded_reg if self.a.kind else self.s.loaded),
                  buffer_error=int(self.w.fault or self.s.cache_error),
                  buffer_error_code=self.w.error_code if self.w.fault else self.s.cache_error_code)
        ao = self.a.snapshot(**ac)
        rc = dict(rst_n=rst, cmd_valid=ao['cmd_valid'], start=ao['cmd_addr_start'], end=ao['cmd_addr_end'],
                  beats=ao['cmd_beats'], kind=ao['cmd_kind'], ddr_rd_rdy=i.get('ddr_rd_rdy', 0),
                  ddr_rd_vld=i.get('ddr_rd_vld', 0), ddr_rd_data=i.get('ddr_rd_data', 0))
        ro = self.r.outputs(**{k:v for k,v in rc.items() if k not in ('kind', 'ddr_rd_vld', 'ddr_rd_data')})
        ac['cmd_ready'] = int(ro['cmd_ready'])
        pc = dict(common, job_begin=int(self.state == self.XBEGIN and not fatal), job_id=self.active_id,
                  job_k=self.d.active_k, **{n:i.get(n,0) for n in
                    's_axis_tdata s_axis_tkeep s_axis_tlast s_axis_tuser'.split()},
                  s_axis_tvalid=int(i.get('s_axis_tvalid',0) and self.state == self.X and not fatal))
        xc = dict(common, load_begin=int(self.state == self.XBEGIN and not fatal), load_k=self.d.active_k,
                  wr_valid=int(self.p.wr_valid and not fatal), wr_data=self.p.wr_data, wr_mask=self.p.wr_mask,
                  wr_exp=self.p.wr_exp, wr_word_index=self.p.wr_word_index, wr_last=self.p.wr_last,
                  rd_req=int(i.get('x_rd_req',0) and access), rd_word_index=i.get('x_rd_index',0))
        xo = self.x.snapshot(**xc)
        pc['wr_ready'] = xo['wr_ready']
        po = self.p.snapshot(**pc)
        index = (self.a.offset+self.r.word_index) & 65535
        wc = dict(common, load_begin=ao['weight_load_begin'], load_k=ao['load_k'],
                  wr_valid=int(self.r.word_valid and self.r.word_kind and not fatal),
                  wr_data=self.r.word_data, wr_word_index=index,
                  rd_req=int(i.get('weight_rd_req',0) and access), rd_word_index=i.get('weight_rd_index',0))
        wo = self.w.snapshot(**wc)
        sc = dict(rst_n=rst, load_begin=ao['scale_load_begin'], load_words=ao['load_words'],
                  load_scales=ao['load_scales'], wr_valid=int(self.r.word_valid and not self.r.word_kind and not fatal),
                  wr_data=self.r.word_data, wr_word_index=index,
                  rd_req=int(i.get('scale_rd_req',0) and access and self.scale_owned),
                  rd_scale_index=i.get('scale_rd_index',0))
        job_ready = int(rst and self.state == self.IDLE and not fatal)
        dc = dict(rst_n=rst, job_accept=int(i.get('job_valid',0) and job_ready),
                  job_n=i.get('job_n',0), job_k=i.get('job_k',0))
        outputs = dict(job_ready=job_ready, s_axis_tready=int(po['s_axis_tready'] and self.state == self.X and not fatal),
                       ddr_rd_req=int(ro['ddr_rd_req']), ddr_rd_addra=ro['ddr_rd_addra'], ddr_rd_addrb=ro['ddr_rd_addrb'],
                       object_ready=int(access and ao['load_ready']), object_done=int(ao['load_done'] and not fatal),
                       x_loaded=int(xo['loaded'] and self.state in (self.X,self.ACCESS) and not fatal),
                       scale_loaded=int(self.s.loaded and self.scale_owned and access),
                       weight_loaded=int(wo['loaded'] and self.weight_owned and access),
                       x_rd_valid=xo['rd_valid'], x_rd_data=xo['rd_data'], x_rd_exp=xo['rd_exp'], x_rd_mask=xo['rd_mask'],
                       scale_rd_valid=int(self.s.rd_valid and self.scale_owned and access), scale_rd_bits=self.s.rd_scale_bits,
                       weight_rd_valid=wo['rd_valid'], weight_rd_data=wo['rd_data'], weight_rd_mask=wo['rd_mask'],
                       result_valid=self.result_valid, result_code=self.result_code, fault_lock=fatal)
        return outputs, (pc, xc, wc, ac, rc, sc, dc), fatal, fatal_code

    def snapshot(self, **i):
        return self.signals(**i)[0]

    def step(self, **i):
        if not i.get('rst_n', 1):
            self.reset_all()
            return self.snapshot(**i)
        pre, controls, fatal, code = self.signals(**i)
        pc, xc, wc, ac, rc, sc, dc = controls
        rst = (self.release >> 1) & 1
        if not rst:
            self.reset_control()
        else:
            if ac and self.a.snapshot(**ac)['scale_load_begin']:
                self.scale_owned = 1
            if self.a.snapshot(**ac)['weight_load_begin']:
                self.weight_owned = 1
            if fatal and not self.locked:
                self.locked, self.first_code = 1, code
                self.scale_owned = self.weight_owned = 0
                if self.state not in (self.IDLE,self.LOCK):
                    # A published result is immutable even if a later fault locks the idle path.
                    if not self.result_valid:
                        self.result_valid, self.result_code = 1, code
                    self.state = self.RESULT
                else:
                    self.state = self.LOCK
            elif self.state == self.IDLE:
                if dc['job_accept']:
                    self.active_id, self.active_m, self.active_tile = (i.get(n,0) for n in ('job_id','job_m','job_m_tile'))
                    self.weight_base, self.scale_base = i.get('job_weight_base',0), i.get('job_scale_base',0)
                    self.scale_owned = self.weight_owned = 0
                    self.state = self.DIMS
            elif self.state == self.DIMS and self.d.cfg_valid:
                if self.d.cfg_error or self.active_m != 1 or self.active_tile != 1:
                    self.result_valid, self.result_code, self.state = 1, 1 if self.d.cfg_error else 2, self.RESULT
                else:
                    self.state = self.CFG
            elif self.state == self.CFG:
                self.state = self.CHECK
            elif self.state == self.CHECK and self.a.cfg_done:
                if self.a.cfg_error:
                    self.result_valid, self.result_code, self.state = 1, self.a.cfg_error_code, self.RESULT
                else:
                    self.state = self.XBEGIN
            elif self.state == self.XBEGIN:
                self.state = self.X
            elif self.state == self.X and self.x.loaded_reg and self.p.done:
                self.state = self.ACCESS
            elif self.state == self.ACCESS:
                if i.get('finish_test',0) and self.a.snapshot(**ac)['load_ready'] and not i.get('object_valid',0) and not self.r.busy:
                    self.result_valid, self.result_code, self.state = 1, 0, self.RESULT
            elif self.state == self.RESULT and self.result_valid and i.get('result_ready',0):
                self.result_valid = 0
                self.state = self.LOCK if self.locked else self.IDLE
        for m,c in zip((self.p,self.x,self.w,self.a,self.r,self.s,self.d), controls):
            m.step(**c)
        self.release = ((self.release << 1) | 1) & 3
        return self.snapshot(**i)
