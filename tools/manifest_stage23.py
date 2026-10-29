#!/usr/bin/env python3
"""Build reviewable source diff and full delivered-tree hash manifest.

No git add/commit, no remote mutation. Evidence logs stay as separate files.
"""
import hashlib
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
BASE='4f3fc68f1f59ab83ae2f657356eec35a41d56e22'


def git(*args):
    p=subprocess.run(['git',*args],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode not in (0,1):raise RuntimeError(p.stderr.decode())
    return p


def main():
    tracked=git('diff','--binary',BASE).stdout
    added=git('ls-files','--others','--exclude-standard').stdout.decode().splitlines()
    patch=bytearray(tracked)
    names=[]
    for name in sorted(added):
        p=Path(name)
        if (p.suffix in ('.v','.py','.sh','.md','.json') and
            '/logs/' not in name and p.name not in ('FINAL_SOURCE_MANIFEST.json',)):
            part=git('diff','--no-index','--binary','--','/dev/null',name)
            if part.returncode!=1:raise RuntimeError('new file diff failed '+name)
            patch.extend(part.stdout);names.append(name)
    diff=ROOT/'docs/stage23/SOURCE_CHANGES.patch';diff.write_bytes(patch)
    subprocess.run(['git','-C',str(ROOT.parent/'review-baseline'),'apply','--check',str(diff)],check=True)
    files=git('ls-files','--cached','--others','--exclude-standard').stdout.decode().splitlines()
    manifest={}
    for name in sorted(set(files)):
        if name=='docs/stage23/FINAL_SOURCE_MANIFEST.json':continue
        data=(ROOT/name).read_bytes()
        manifest[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    baseline=json.loads((ROOT/'docs/stage23/BASELINE_FILES.json').read_text())['tracked_files']
    for name,info in baseline.items():
        if name.startswith('docs/standards/') or name in ('rtl/xw_ddr_range_rx.v','rtl/xw_scale_group_cache.v','rtl/xw_job_dim_cfg.v','rtl/xw_fp32_scale_b2.v'):
            assert manifest[name]['sha256']==info['sha256'],('protected source changed',name)
    output=dict(baseline_commit=BASE,patch_apply_check='PASS against clean detached baseline',
                source_diff_new_files=names,files=manifest,
                manifest_self_excluded=True,generated_sim_build='not tracked; vector hashes in VERIFICATION_RESULTS.json')
    (ROOT/'docs/stage23/FINAL_SOURCE_MANIFEST.json').write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
    print(f'PASS source diff apply --check; manifest {len(manifest)} files; standards/four original RTL unchanged')


if __name__=='__main__':main()
