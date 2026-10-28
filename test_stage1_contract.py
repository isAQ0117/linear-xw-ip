"""Stage 1 software contract tests (separate from HDL simulation results)."""
import random
import unittest

from stage1_contract_model import (DimensionConfig, DdrRangeReceiver,
                                   ScaleGroupCache, DDR_COMMAND, DDR_RESPONSE, ceildiv,
                                   DDR_BUFFER, INTERNAL_FAULT)
from linear_stream_model.numeric import fp32_positive_scale, NumericFault


class TestDimensionConfig(unittest.TestCase):
    def test_static_ignores_physical_nk(self):
        d = DimensionConfig(n_dim=129, k_dim=2049, max_n=65535, max_k=65535)
        o = d.step(job_accept=True, job_n=0, job_k=0)
        self.assertEqual((o['active_n'], o['active_k']), (129, 2049))
        self.assertEqual((o['n_groups'], o['k_blocks']), (2, 17))
        self.assertEqual((o['weight_words_per_row'], o['scale_words_per_group']), (33, 2))
        self.assertTrue(o['cfg_valid'])
        self.assertFalse(o['cfg_error'])
        self.assertFalse(d.step()['cfg_valid'])

    def test_dynamic_invalid_and_next_good(self):
        d = DimensionConfig(static_dim_mode=0, n_dim=1, k_dim=1,
                            max_n=130, max_k=4096)
        for n,k in [(0,1),(1,0),(131,1),(1,4097)]:
            self.assertTrue(d.step(job_accept=True, job_n=n, job_k=k)['cfg_error'])
        self.assertTrue(d.step()['cfg_error'])
        good = d.step(job_accept=True, job_n=128, job_k=4096)
        self.assertEqual((good['n_groups'], good['scale_words_per_group']), (1,2))
        self.assertFalse(good['cfg_error'])

    def test_dynamic_mode_does_not_require_static_dims_inside_limits(self):
        # N_DIM/K_DIM are unused in dynamic mode; only MAX_N/K limit jobs.
        d = DimensionConfig(static_dim_mode=0, n_dim=12288, k_dim=4096,
                            max_n=130, max_k=257)
        o = d.step(job_accept=True, job_n=129, job_k=257)
        self.assertEqual((o['n_groups'], o['k_blocks']), (2,3))
        self.assertFalse(o['cfg_error'])

    def test_max_width(self):
        d = DimensionConfig(n_dim=65535,k_dim=65535,max_n=65535,max_k=65535)
        o = d.step(job_accept=True)
        self.assertEqual((o['n_groups'],o['k_blocks'],o['weight_words_per_row'],o['scale_words_per_group']),
                         (512,512,1024,32))

    def test_illegal_parameters_rejected(self):
        for kw in [dict(static_dim_mode=2), dict(n_dim=0),
                   dict(max_n=0),dict(n_dim=12289),dict(k_dim=65536)]:
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                DimensionConfig(**kw)

    def test_reset_invalidates_result(self):
        d=DimensionConfig(); d.step(job_accept=True)
        o=d.step(rst_n=False)
        self.assertEqual((o['active_n'],o['active_k'],o['cfg_valid']), (0,0,False))


class TestDdrRangeReceiver(unittest.TestCase):
    def new_cmd(self, **kw):
        d = DdrRangeReceiver()
        o = d.step(cmd_valid=True,start=0x100,end=0x108,beats=2,
                   ddr_rd_rdy=True,kind=1,**kw)
        return d,o

    def test_same_edge_beat0_gap_last_and_handoff(self):
        d,o=self.new_cmd(ddr_rd_vld=True,ddr_rd_data=0xDEAD)
        self.assertTrue(o['word_valid'])
        self.assertEqual((o['word_index'],o['word_data']), (0,0xDEAD))
        self.assertTrue(o['busy'])
        self.assertFalse(d.step()['word_valid'])
        o=d.step(ddr_rd_vld=True,ddr_rd_data=0xBEEF)
        self.assertTrue(o['range_done'])
        self.assertEqual((o['word_index'],o['word_data']), (1,0xBEEF))
        self.assertTrue(o['handoff_hold'])
        self.assertFalse(d.outputs(cmd_valid=True,start=0x200,end=0x200,beats=1,
                                   ddr_rd_rdy=True)['ddr_rd_req'])
        self.assertFalse(d.step()['range_done'])
        self.assertTrue(d.outputs(cmd_valid=True,start=0x200,end=0x200,beats=1,
                                  ddr_rd_rdy=True)['ddr_rd_req'])
        o=d.step(cmd_valid=True,start=0x200,end=0x200,beats=1,kind=0,
                 ddr_rd_rdy=True,ddr_rd_vld=True,ddr_rd_data=0xFACE)
        self.assertTrue(o['range_done'])
        self.assertEqual((o['word_index'],o['word_kind']), (0,0))

    def test_invalid_command_sticky_0x20(self):
        d=DdrRangeReceiver()
        o=d.step(cmd_valid=True,start=0x101,end=0x108,beats=2,ddr_rd_rdy=True)
        self.assertEqual(o['range_error_code'], DDR_COMMAND)
        self.assertFalse(d.outputs(cmd_valid=True,start=0x100,end=0x100,beats=1,
                                   ddr_rd_rdy=True)['cmd_ready'])
        for _ in range(10):
            o=d.step(cmd_valid=True,start=0x100,end=0x100,beats=1,
                     ddr_rd_rdy=True,ddr_rd_vld=True)
            self.assertTrue(o['range_error'])
            self.assertEqual(o['range_error_code'],DDR_COMMAND)
            self.assertFalse(o['word_valid'])
        self.assertFalse(d.step(rst_n=False)['range_error'])

    def test_unsolicited_and_extra_response_0x21(self):
        d=DdrRangeReceiver()
        o=d.step(ddr_rd_vld=True,ddr_rd_data=1)
        self.assertEqual(o['range_error_code'],DDR_RESPONSE)
        d.step(rst_n=False)
        o=d.step(cmd_valid=True,start=0x200,end=0x200,beats=1,ddr_rd_rdy=True,
                 ddr_rd_vld=True,ddr_rd_data=2)
        self.assertTrue(o['range_done'])
        self.assertEqual(d.step(ddr_rd_vld=True)['range_error_code'],DDR_RESPONSE)

    def test_reset_gates_command(self):
        d=DdrRangeReceiver()
        self.assertFalse(d.outputs(rst_n=False,cmd_valid=True,start=0,
                                   end=0,beats=1,ddr_rd_rdy=True)['ddr_rd_req'])
        self.assertFalse(d.step(rst_n=False,ddr_rd_vld=True)['range_error'])

    def test_ddr_waits_for_ready(self):
        d=DdrRangeReceiver()
        self.assertFalse(d.outputs(cmd_valid=True,start=0,end=0,beats=1,
                                   ddr_rd_rdy=False)['ddr_rd_req'])
        self.assertFalse(d.step(cmd_valid=True,start=0,end=0,beats=1,
                                ddr_rd_rdy=False)['busy'])
        self.assertTrue(d.step(cmd_valid=True,start=0,end=0,beats=1,
                               ddr_rd_rdy=True)['busy'])

    def test_many_random_ranges(self):
        rng=random.Random(40)
        for _ in range(120):
            beats=rng.randrange(1,11)
            d=DdrRangeReceiver()
            start=8*rng.randrange(0,10000)
            for i in range(beats):
                if i==0:
                    o=d.step(cmd_valid=True,start=start,end=start+8*(beats-1),
                             beats=beats,ddr_rd_rdy=True,ddr_rd_vld=bool(rng.randrange(2)),
                             ddr_rd_data=0x100)
                    if o['word_valid']:
                        self.assertEqual(o['word_index'],0)
                        i0=1
                    else:
                        i0=0
                    break
            for j in range(i0,beats):
                for gap in range(rng.randrange(4)):
                    self.assertFalse(d.step()['word_valid'])
                o=d.step(ddr_rd_vld=True,ddr_rd_data=j)
                self.assertEqual(o['word_index'],j)
            self.assertTrue(o['range_done'])
            self.assertFalse(o['range_error'])


class TestScaleGroupCache(unittest.TestCase):
    def test_two_word_load_reads_and_reload(self):
        c=ScaleGroupCache(max_k=4096)
        c.step(load_begin=True,load_words=2,load_scales=17)
        w=sum(0x3f800000<<(32*i) for i in range(16))
        self.assertFalse(c.step(wr_valid=True,wr_word_index=0,wr_data=w)['loaded'])
        self.assertTrue(c.step(wr_valid=True,wr_word_index=1,wr_data=0x3f80624e)['loaded'])
        self.assertEqual(c.step(rd_req=True,rd_scale_index=16)['rd_scale_bits'],0x3f80624e)
        self.assertEqual(c.step(rd_req=True,rd_scale_index=0)['rd_scale_bits'],0x3f800000)
        self.assertFalse(c.step(load_begin=True,load_words=1,load_scales=1)['loaded'])
        self.assertTrue(c.step(wr_valid=True,wr_word_index=0,wr_data=0x3f800001)['loaded'])
        self.assertEqual(c.step(rd_req=True,rd_scale_index=0)['rd_scale_bits'],0x3f800001)

    def test_write_extra_is_fatal_and_sticky(self):
        c=ScaleGroupCache(max_k=2048)
        c.step(load_begin=True,load_words=1,load_scales=1)
        c.step(wr_valid=True,wr_word_index=0,wr_data=123)
        o=c.step(wr_valid=True,wr_word_index=1,wr_data=456)
        self.assertEqual(o['cache_error_code'],DDR_BUFFER)
        self.assertFalse(o['loaded'])
        for _ in range(3):
            o=c.step(load_begin=True,load_words=1,load_scales=1,rd_req=True)
            self.assertTrue(o['cache_error'])
            self.assertFalse(o['rd_valid'])
        self.assertFalse(c.step(rst_n=False)['cache_error'])

    def test_load_and_first_write_overlap_fatal(self):
        c=ScaleGroupCache()
        o=c.step(load_begin=True,load_words=1,load_scales=1,
                 wr_valid=True,wr_word_index=0,wr_data=0x123)
        self.assertEqual(o['cache_error_code'],INTERNAL_FAULT)
        self.assertEqual(o['words_written'],0)

    def test_early_read_fatal(self):
        c=ScaleGroupCache()
        self.assertEqual(c.step(rd_req=True)['cache_error_code'],INTERNAL_FAULT)

    def test_simultaneous_read_write_fatal(self):
        c=ScaleGroupCache()
        c.step(load_begin=True,load_words=1,load_scales=1)
        o=c.step(wr_valid=True,wr_word_index=0,rd_req=True)
        self.assertEqual(o['cache_error_code'],INTERNAL_FAULT)

    def test_invalid_scale_count_beyond_maxk(self):
        c=ScaleGroupCache(max_k=129)
        # MAX_SCALE_WORDS=1 permits 16 slots, but only 2 K blocks are valid.
        self.assertTrue(c.step(load_begin=True,load_words=1,load_scales=3)['cache_error'])

    def test_read_oob_is_fault(self):
        c=ScaleGroupCache(max_k=4096)
        c.step(load_begin=True,load_words=1,load_scales=2)
        c.step(wr_valid=True,wr_word_index=0,wr_data=0x12345)
        o=c.step(rd_req=True,rd_scale_index=2)
        self.assertEqual(o['cache_error_code'],INTERNAL_FAULT)
        self.assertFalse(o['rd_valid'])

    def test_normal_group_loading_does_not_raise_fault(self):
        rng=random.Random(4)
        c=ScaleGroupCache(max_k=12288)
        for scales in [1,16,17,32,64,96]:
            count=ceildiv(scales,16)
            self.assertFalse(c.step(load_begin=True,load_words=count,
                                    load_scales=scales)['cache_error'])
            values=[rng.randrange(1,2**32) for _ in range(scales)]
            for i in range(count):
                word=sum(val << (32*j) for j,val in enumerate(values[i*16:(i+1)*16]))
                c.step(wr_valid=True,wr_word_index=i,wr_data=word)
            self.assertTrue(c.loaded)
            for i,val in enumerate(values):
                o=c.step(rd_req=True,rd_scale_index=i)
                self.assertTrue(o['rd_valid'])
                self.assertEqual(o['rd_scale_bits'],val)


class TestStage1ReceiverCacheIntegration(unittest.TestCase):
    def test_first_beat_pipelined_to_cache_without_loss(self):
        # A complete two-Beat Scale Group: configure t-1, accept Beat0 t0,
        # accept Beat1 t1, commit last registered Beat t2.
        rx = DdrRangeReceiver()
        cache = ScaleGroupCache(max_k=4096)
        cache.step(load_begin=True, load_words=2, load_scales=17)
        o0 = rx.step(cmd_valid=True, start=0x100, end=0x108,
                     beats=2, kind=0, ddr_rd_rdy=True,
                     ddr_rd_vld=True, ddr_rd_data=sum(
                         0x3f800000 << (32*i) for i in range(16)))
        self.assertTrue(o0['word_valid'])
        self.assertFalse(cache.loaded)
        o1 = rx.step(ddr_rd_vld=True, ddr_rd_data=0x3f80624e)
        cache.step(wr_valid=o0['word_valid'], wr_word_index=o0['word_index'],
                   wr_data=o0['word_data'])
        self.assertTrue(o1['range_done'])
        self.assertFalse(cache.loaded)
        self.assertTrue(rx.handoff_hold)
        o2 = rx.step()
        cache.step(wr_valid=o1['word_valid'], wr_word_index=o1['word_index'],
                   wr_data=o1['word_data'])
        self.assertTrue(cache.loaded)
        self.assertFalse(cache.cache_error)
        self.assertFalse(o2['range_done'])
        self.assertEqual(cache.step(rd_req=True, rd_scale_index=16)['rd_scale_bits'],
                         0x3f80624e)

    def test_reset_while_range_inflight_does_not_prove_ddr_flush(self):
        rx = DdrRangeReceiver()
        rx.step(cmd_valid=True,start=0x100,end=0x110,
                beats=3,ddr_rd_rdy=True,ddr_rd_vld=True)
        self.assertTrue(rx.busy)
        rx.step(rst_n=False)
        # Old physical Beat arriving after reset but outside a new range is
        # detected as 0x21.  The IP cannot infer an external flush by itself.
        self.assertEqual(rx.step(ddr_rd_vld=True)['range_error_code'],DDR_RESPONSE)


class TestB2Numerics(unittest.TestCase):
    def test_decoder_extremes_and_invalid(self):
        self.assertEqual(fp32_positive_scale(0x00000001), (1,-149))
        self.assertEqual(fp32_positive_scale(0x007fffff), ((1<<23)-1,-149))
        self.assertEqual(fp32_positive_scale(0x00800000), (1<<23,-149))
        self.assertEqual(fp32_positive_scale(0x7f7fffff), ((1<<24)-1,104))
        for bits in [0,0x80000000,0xbf800000,0x7f800000,0xff800000,
                     0x7fc00000,0xffffffff]:
            with self.subTest(bits=hex(bits)),self.assertRaises(NumericFault):
                fp32_positive_scale(bits)

if __name__ == '__main__':
    unittest.main()
