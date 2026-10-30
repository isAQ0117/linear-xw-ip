#!/usr/bin/env python3
"""Fail-closed Verilog-2001 PRE/NBA comparisons; all vectors are reproducible."""
import argparse,hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
BUILD=ROOT/'sim_build/stage67';LOG=ROOT/'docs/stage67/logs'

def ports(module):
    s=(ROOT/'rtl'/f'{module}.v').read_text().split(');',1)[0]
    r=[]
    for dr,sg,w,n in re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(signed\s+)?(?:\[(\d+:\d+)\]\s*)?(\w+)\s*[,\n]',s+'\n'):
        width=abs(int(w.split(':')[0])-int(w.split(':')[1]))+1 if w else 1
        if n!='clk':r.append((dr,n,width))
    return r

def pack(fields,values):
    v=0
    for n,w in fields:v=(v<<w)|(int(values.get(n,0))&((1<<w)-1))
    return v

class Trace:
    def __init__(self,name,model):
        self.name=name;self.model=model;ps=ports(name)
        self.ins=[(n,w) for d,n,w in ps if d=='input'];self.outs=[(n,w) for d,n,w in ps if d=='output']
        assert self.ins and self.outs,(name,ps)
        self.rows=[];self.events=[];self.counts={};self.defaults={'rst_n':1}
    def tick(self,**kw):
        i=dict(self.defaults,**kw)
        if not i.get('rst_n',1):self.model.reset()
        pre=self.model.snapshot(**i)
        self.model.step(**i);post=self.model.snapshot(**i)
        self.rows.append((pack(self.ins,i),pack(self.outs,pre),pack(self.outs,post)))
        return pre,post
    def reset(self):self.tick(rst_n=0);self.tick(rst_n=0);self.tick()
    def save(self,path):path.write_text(''.join('%x %x %x\n'%r for r in self.rows))

def bench(t,parameters=''):
    ps=ports(t.name);decl=['    reg clk;'];conn=['.clk(clk)']
    for d,n,w in ps:
        decl.append(f'    {"reg" if d=="input" else "wire"} '+(f'[{w-1}:0] ' if w>1 else '')+n+';');conn.append(f'.{n}({n})')
    idecl=iwiring=iinit=ipre=ipost=''
    if t.name=='linear_xw_ip':
        from tools.stage67_monitors import instrumentation
        idecl,iwiring,iinit,ipre,ipost=instrumentation()
    cat=lambda fs:'{'+', '.join(n for n,w in fs)+'}'
    a,b=sum(w for n,w in t.ins),sum(w for n,w in t.outs)
    return f'''`timescale 1ns / 1ps
module tb_{t.name}_cycle;
{chr(10).join(decl)}
{idecl}    integer fd;
    integer scanned;
    integer cycles;
    reg [8191:0] filename;
    reg [{a-1}:0] stimulus;
    reg [{b-1}:0] expected_pre;
    reg [{b-1}:0] expected_post;
    {t.name} {parameters} dut ({', '.join(conn)});
{iwiring}    /* 仿真唯一时钟。 */
    always #5 clk = ~clk;
    initial begin
        clk=0;cycles=0;
{iinit}
        if (!$value$plusargs("VECTORS=%s",filename)) begin $display("FAIL no vector"); $stop; end
        fd=$fopen(filename,"r");
        if (!fd) begin $display("FAIL open"); $stop; end
        while (!$feof(fd)) begin
            scanned=$fscanf(fd,"%h %h %h\\n",stimulus,expected_pre,expected_post);
            if (scanned!=3) begin $display("FAIL malformed"); $stop; end
            @(negedge clk);
            {cat(t.ins)}=stimulus;
            #1;
            if ({cat(t.outs)} !== expected_pre) begin
                $display("FAIL PRE cycle=%0d actual=%h expected=%h",cycles,{cat(t.outs)},expected_pre); $stop;
            end
            @(posedge clk);
{ipre}            #1;
            if ({cat(t.outs)} !== expected_post) begin
                $display("FAIL NBA cycle=%0d actual=%h expected=%h",cycles,{cat(t.outs)},expected_post); $stop;
            end
{ipost}            cycles=cycles+1;
        end
        if (cycles<5) begin $display("FAIL empty"); $stop; end
        $display("PASS tb_{t.name}_cycle cycles=%0d",cycles);$finish;
    end
endmodule
'''

def execute(cmd,log,marker=None,timeout=600):
    log.write('COMMAND '+' '.join(map(str,cmd))+'\n');log.flush()
    p=subprocess.run(list(map(str,cmd)),cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    log.write(p.stdout+'\nEXIT_CODE '+str(p.returncode)+'\n');log.flush()
    if p.returncode or 'FAIL' in p.stdout or marker and p.stdout.count(marker)!=1:
        raise RuntimeError(str(cmd)+'\n'+p.stdout[-5000:])
    return p.stdout

def simulate(t,label,parameters='',burst=3):
    BUILD.mkdir(parents=True,exist_ok=True);LOG.mkdir(parents=True,exist_ok=True)
    vec=BUILD/(label+'.vec');t.save(vec)
    tb=ROOT/'tb'/f'tb_{t.name}_cycle.v';tb.write_text(bench(t,parameters))
    binary=BUILD/(label+'.vvp')
    with (LOG/(label+'.log')).open('w') as f:
        execute(['iverilog','-g2001','-Wall',f'-DXW_SIM_DDR_BURST={burst}','-s','tb_'+t.name+'_cycle','-o',binary]+sorted((ROOT/'rtl').glob('*.v'))+[tb],f)
        cmd=['vvp','-N',binary,'+VECTORS='+str(vec)]
        if t.name=='linear_xw_ip':cmd+=['+TRACE='+str(LOG/(label+'_rtl_events.jsonl'))]
        execute(cmd,f,'PASS tb_'+t.name+'_cycle ')
        if t.name=='linear_xw_ip':
            actual=[json.loads(line) for line in (LOG/(label+'_rtl_events.jsonl')).read_text().splitlines()]
            expected=t.events
            assert actual==expected,next(((a,b) for a,b in zip(actual,expected) if a!=b),(len(actual),len(expected)))
            (LOG/(label+'_model_events.jsonl')).write_text(''.join(json.dumps(e)+'\n' for e in expected))
            f.write('PASS actual RTL event sequence == cycle model '+str(len(actual))+'\n')
    return dict(label=label,cycles=len(t.rows),coverage=t.counts,status='PASS',sha256=hashlib.sha256(vec.read_bytes()).hexdigest())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',default='6');a=ap.parse_args()
    for n in ('iverilog','vvp'):
        if not shutil.which(n):raise SystemExit(n+' missing: Pending')
    from test_stage6 import output_suite,status_suite
    if a.stage=='6':
        tests=[simulate(output_suite(),'axis_output'),simulate(status_suite(),'job_status')]
    elif a.stage=='fault':
        from test_stage7 import fault_suite
        tests=[simulate(fault_suite(),'integration_fault','#(.STATIC_DIM_MODE(0), .N_DIM(2), .K_DIM(129))')]
    elif a.stage=='retry':
        from test_stage7 import retry_suite
        tests=[simulate(retry_suite(),'integration_retry','#(.STATIC_DIM_MODE(0), .N_DIM(2), .K_DIM(129))')]
    elif a.stage=='extended':
        from test_stage7 import integration_suite
        tests=[simulate(integration_suite(0,3,True),'integration_max_n','#(.STATIC_DIM_MODE(0), .N_DIM(2), .K_DIM(129))')]
    else:
        from test_stage7 import scheduler_suite,integration_suite
        tests=[simulate(scheduler_suite(),'scheduler', '#(.STATIC_DIM_MODE(0), .N_DIM(2), .K_DIM(129))')]
        for static,burst in [(0,3),(1,3),(0,1),(0,2),(0,64)]:
            tests.append(simulate(integration_suite(static,burst),f'integration_s{static}_b{burst}',f'#(.STATIC_DIM_MODE({static}), .N_DIM(2), .K_DIM(129))',burst))
    (ROOT/'docs/stage67'/('STAGE'+a.stage+'_RESULTS.json')).write_text(json.dumps(tests,indent=2)+'\n')
    print('PASS Stage'+a.stage,[(r['label'],r['cycles']) for r in tests])
if __name__=='__main__':main()
