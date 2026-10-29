#!/usr/bin/env python3
"""Validate uploaded protected bytes, existing generated data, and final sources."""
import hashlib,json,zipfile,csv,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def main():
    baseline=json.loads((ROOT/'docs/stage4/UPLOADED_BASELINE.json').read_text())
    protected=[n for n in baseline['files'] if (n.startswith('rtl/') and n.endswith('.v')) or n.startswith('docs/standards/') or n=='linear_stream_model/numeric.py']
    for n in protected:
        assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==baseline['files'][n]['sha256'],('protected bytes changed',n)
    missing=[n for n in baseline['files'] if not (ROOT/n).is_file()];assert not missing,missing
    for n in ['stage4_golden.py','stage4_a2_math.py','stage4_model.py','stage4_integration.py']:
        compile((ROOT/n).read_text(),n,'exec')
    # Independent Golden must not import/call the production arithmetic helpers.
    golden=(ROOT/'stage4_golden.py').read_text()
    assert 'from linear_stream_model' not in golden and 'accumulate_48(' not in golden
    from importlib import util
    spec=util.spec_from_file_location('stage4_cycle_original',ROOT/'cycle_model.py');mod=util.module_from_spec(spec);spec.loader.exec_module(mod)
    case=json.loads((ROOT/'examples/fp32_demo_case.json').read_text());image,manifest=mod.prepare(case)
    hist=ROOT/'docs/verification/history/fp32_v0_2'
    assert image==(hist/'ddr_image.bin').read_bytes()
    assert manifest==json.loads((hist/'ddr_manifest.json').read_text())
    # Source lists must have no missing/duplicate modules.
    sources=(ROOT/'rtl_sources.f').read_text().splitlines();assert len(sources)==len(set(sources))==12
    assert all((ROOT/n).is_file() for n in sources)
    portref=[]
    import sys
    sys.path.insert(0,str(ROOT))
    from tools.gen_stage4_tb import ports
    for n in ['xw_b1_dot128','xw_b2_fp32_pipe','xw_a2_accum48','xw_b3b_compute_ctrl','xw_stage234_harness']:
        ps=ports(n);assert len({x[1] for x in ps})==len(ps)
        portref.append('\n## '+n+'\n\n| Port | Direction | Bits |\n|---|---|---:|\n'+''.join(f'| `{p}` | {d} | {w} |\n' for d,p,w in ps))
    (ROOT/'docs/stage4/PORT_REFERENCE.md').write_text('# 最终RTL端口清单\n\n逐端口从最终ANSI声明提取。signed属性及语义以RTL和INTERFACE_AND_TIMING.md为准。\n'+''.join(portref))
    synth=json.loads((ROOT/'docs/stage4/SYNTHESIS_RESULTS.json').read_text())
    for r in synth['modules']:
        assert r['source_sha256']==hashlib.sha256((ROOT/'rtl'/(r['module']+'.v')).read_bytes()).hexdigest()
    mapping=json.loads((ROOT/'docs/stage4/XC7_MAPPING.json').read_text())
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in mapping['source_sha256'].items())
    result=dict(uploaded_head=baseline['head'],baseline_files=len(baseline['files']),missing=missing,
                protected_files=len(protected),protected_unchanged=True,production_sources=sources,
                historic_ddr_rebuild='PASS',source_signatures_current=True)
    (ROOT/'docs/stage4/AUDIT_RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS Stage4 audit:',len(protected),'protected files byte-identical;',len(baseline['files']),'baseline files retained')

if __name__=='__main__':main()
