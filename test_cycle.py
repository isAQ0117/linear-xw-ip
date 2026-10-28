
import tempfile,json,unittest
from pathlib import Path
from cycle_model import prepare,Simulator,report,demo
class CycleTests(unittest.TestCase):
    def run_case(self,M,N,K,static,ddr_gap,stall):
        J=(K+127)//128;B=(N+127)//128
        case={"job":{"job_id":77,"m":M,"n":N,"k":K,
           "static_dim_mode":int(static),"n_dim":N,"k_dim":K,"max_n":N+1,"max_k":K+1,
           "axis_width_bits":512},
         "activation":{"mantissa":[[(i+3*k)%201-100 for k in range(K)] for i in range(M)],
                "exponents":[[-15+j for j in range(J)] for i in range(M)]},
         "weight":{"fp8_bits":[[(n+2*k)%120 for k in range(K)] for n in range(N)],
                 "scale_fp32_bits":[[0x3f800000+4096*j for j in range(J)] for b in range(B)]}}
        d,man=prepare(case)
        sim=Simulator(case,d,man,ddr_gap=ddr_gap,output_stall_period=stall).run()
        with tempfile.TemporaryDirectory() as t:
            met=report(sim,case,t)
        self.assertTrue(met["b3b_golden_bit_exact"])
        self.assertEqual(met["ddr_requests"],B+N)
        self.assertEqual(met["ddr_return_beats"],B*((J+15)//16)+N*((K+63)//64))
    def test_small_and_boundaries(self):
        for K,N in [(1,1),(127,129),(128,128),(129,129),(257,5)]:
            with self.subTest(k=K,n=N):
                self.run_case(1,N,K,False,1,3)
    def test_batch_weight_reuse(self):self.run_case(3,4,129,True,2,4)
if __name__=="__main__":unittest.main()
