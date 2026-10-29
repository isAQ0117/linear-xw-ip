#!/usr/bin/env python3
"""Build a complete review snapshot and source diff relative to uploaded bytes."""
import difflib,hashlib,json,stat,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    baseline=json.loads((ROOT/'docs/stage5/UPLOADED_BASELINE.json').read_text())
    names=set(baseline['tree'])
    for pattern in ['stage5*.py','test_stage5*.py','run_stage5_tb.sh','REVIEW_STAGE5.md','rtl/xw_output_group_buffer.v','rtl/xw_bfp18_requant.v','rtl/xw_result_buffer.v','rtl/xw_stage5_ctrl.v','tb/tb_xw_*stage5*.v','tb/tb_xw_*stage45*.v','tb/tb_xw_output_group_buffer_cycle.v','tb/tb_xw_bfp18_requant_cycle.v','tb/tb_xw_result_buffer_cycle.v','tb/support/xw_stage45_harness.v','tools/*stage5*.py','tools/vivado_stage5.tcl']:
        names.update(str(p.relative_to(ROOT)) for p in ROOT.glob(pattern) if p.is_file())
    names.update(str(p.relative_to(ROOT)) for p in (ROOT/'docs/stage5').rglob('*') if p.is_file())
    names.update(str(p.relative_to(ROOT)) for p in (ROOT/'sim_build/stage5').glob('*') if p.is_file() and p.suffix in ['.vec','.json','.jsonl'])
    excluded={'docs/stage5/DELIVERY_MANIFEST.json','docs/stage5/SOURCE_CHANGES.patch'}
    source_ext={'.v','.py','.sh','.tcl','.md','.f'}
    patch=[];changes=[]
    archive=ROOT.parent/'upload/02-linear-xw-ip-stage01234.zip'
    with zipfile.ZipFile(archive) as z:
        for n in sorted(names-excluded):
            p=ROOT/n
            if p.suffix not in source_ext or n.startswith('sim_build/') or '/logs/' in n:continue
            old=z.read('linear-xw-ip/'+n) if n in baseline['tree'] else b''
            new=p.read_bytes()
            if old==new:continue
            changes.append(n)
            patch.extend(difflib.unified_diff(old.decode('utf-8').splitlines(keepends=True),new.decode('utf-8').splitlines(keepends=True),fromfile='a/'+n if old else '/dev/null',tofile='b/'+n))
    diff=ROOT/'docs/stage5/SOURCE_CHANGES.patch';diff.write_text(''.join(patch));names.add(str(diff.relative_to(ROOT)))
    # Check the actual diff against an isolated copy, never reset the user tree.
    checkroot=ROOT.parent/'stage5_patch_baseline';checkroot.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for n in baseline['tree']:
            p=checkroot/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read('linear-xw-ip/'+n))
    r=subprocess.run(['git','apply','--check',str(diff)],cwd=checkroot,text=True,capture_output=True)
    assert r.returncode==0,r.stdout+r.stderr
    log=ROOT/'docs/stage5/logs/source_patch_check.log';log.write_text('COMMAND git apply --check SOURCE_CHANGES.patch\n'+r.stdout+r.stderr+'EXIT_CODE '+str(r.returncode)+'\nPASS source diff applies to uploaded working bytes\n');names.add(str(log.relative_to(ROOT)))
    # Confirm normal evidence and synthesis signatures before freezing hashes.
    status=json.loads((ROOT/'docs/stage5/FINAL_STATUS.json').read_text())
    assert all(status[k]=='PASS' for k in ['RTL_Implemented','Numeric_Golden','Python_Cycle_Model','HDL_Module_Simulation','Stage4_5_Integration','Synthesis_Structure'])
    for file in ['SYNTHESIS_RESULTS','XC7_MAPPING']:
        d=json.loads((ROOT/'docs/stage5'/f'{file}.json').read_text())
        for n,h in d['source_sha256'].items():assert sha((ROOT/'rtl'/(n+'.v')).read_bytes())==h,n
    names.discard('docs/stage5/DELIVERY_MANIFEST.json')
    manifest=dict(baseline_head=baseline['head'],baseline='uploaded working bytes',source_changes=changes,
                  note='Full sources, actual vectors/logs/events/netlists; tools and compiled executables reproducible and excluded. Manifest self-excluded.',
                  files={n:dict(bytes=(ROOT/n).stat().st_size,sha256=sha((ROOT/n).read_bytes())) for n in sorted(names)})
    mpath=ROOT/'docs/stage5/DELIVERY_MANIFEST.json';mpath.write_text(json.dumps(manifest,indent=2)+'\n')
    out=ROOT.parent/'linear-xw-ip-stage5-review.zip'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for n in sorted(names|{'docs/stage5/DELIVERY_MANIFEST.json'}):
            p=ROOT/n;info=zipfile.ZipInfo('linear-xw-ip/'+n,date_time=(2026,10,29,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(stat.S_IMODE(p.stat().st_mode)|stat.S_IFREG)<<16;z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(out) as z:assert z.testzip() is None
    print(json.dumps(dict(path=str(out),bytes=out.stat().st_size,sha256=sha(out.read_bytes()),files=len(names)+1,source_changes=len(changes)),indent=2))
if __name__=='__main__':main()
