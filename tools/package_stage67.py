#!/usr/bin/env python3
"""Build a review archive, exact uploaded-worktree source patch and SHA manifest.
No Git commits or remote operations. Toolchain downloads are reproducible and
excluded; all generated test vectors, RTL traces, logs and synthesis JSON remain.
"""
import argparse,difflib,hashlib,json,os,subprocess,tarfile,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
DOCS=ROOT/'docs/stage67'

def included(p):
    rel=p.relative_to(ROOT)
    if not p.is_file() or '.git' in rel.parts or '__pycache__' in rel.parts or p.suffix=='.pyc':return False
    if rel.parts[:2]==('sim_build','toolchain') or rel.as_posix()=='docs/stage67_package_result.json':return False
    return True

def source_file(rel):
    if str(rel) in ['Makefile','rtl_sources.f','README.md','REVIEW_STAGE67.md','run_stage67_tb.sh','docs/PROJECT_STATUS.md']:return True
    if rel.parts[0] in ('rtl','tb','tools') and rel.suffix in ('.v','.py','.sh','.tcl','.md'):return True
    if len(rel.parts)==1 and rel.suffix=='.py':return True
    return str(rel) in ['docs/stage67/INTERFACE_AND_RECOVERY.md','docs/stage67/PORT_REFERENCE.md',
                       'docs/stage67/PLATFORM_PROFILE.json','docs/stage67/DELIVERY_REPORT.md','docs/stage67/DESIGN_SELF_REVIEW.md']

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-zip',type=Path,default=ROOT.parent/'upload/01-linear-xw-ip-stage012345.zip')
    ap.add_argument('--output',type=Path,default=ROOT.parent/'linear-xw-stage67-review.tar.gz');a=ap.parse_args()
    with zipfile.ZipFile(a.source_zip) as z:
        base={n[len('linear-xw-ip/'):]:z.read(n) for n in z.namelist() if n.startswith('linear-xw-ip/') and not n.endswith('/') and not n.startswith('linear-xw-ip/.git/')}
    changes=[];patch=[]
    for p in sorted(ROOT.rglob('*')):
        if not included(p) or not source_file(p.relative_to(ROOT)):continue
        rel=p.relative_to(ROOT).as_posix();now=p.read_bytes();old=base.get(rel,b'')
        if now==old:continue
        patch.append('diff --git a/'+rel+' b/'+rel+'\n')
        if rel not in base:patch.append('new file mode '+('100755' if os.access(p,os.X_OK) else '100644')+'\n')
        patch.extend(difflib.unified_diff(old.decode().splitlines(keepends=True),now.decode().splitlines(keepends=True),
                                        fromfile='a/'+rel if rel in base else '/dev/null',tofile='b/'+rel))
        changes.append(rel)
    pp=DOCS/'SOURCE_CHANGES.patch';pp.write_text(''.join(patch))
    with tempfile.TemporaryDirectory(prefix='patch_review_',dir=ROOT/'sim_build/stage67') as tmp:
        tmp=Path(tmp)
        for rel,data in base.items():
            q=tmp/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(data)
        env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(tmp.parent))
        with (DOCS/'logs/patch_apply_check.log').open('w') as log:
            for args in [['--check'],[]]:
                cmd=['git','apply',*args,str(pp)]
                p=subprocess.run(cmd,cwd=tmp,env=env,capture_output=True,text=True)
                log.write('COMMAND '+' '.join(cmd)+'\n'+p.stdout+p.stderr+'EXIT_CODE '+str(p.returncode)+'\n')
                assert p.returncode==0,p.stderr
            assert all((tmp/rel).read_bytes()==(ROOT/rel).read_bytes() for rel in changes)
            log.write('PASS patch applied to uploaded bytes and all changed sources identical\n')
    (DOCS/'SOURCE_CHANGE_INDEX.json').write_text(json.dumps({'baseline':'uploaded ZIP worktree bytes, not historical HEAD','changed_sources':changes,'apply_check':'PASS'},indent=2)+'\n')
    files=[p for p in sorted(ROOT.rglob('*')) if included(p) and p.name not in ('DELIVERY_MANIFEST.json','SHA256SUMS')]
    manifest={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
    (DOCS/'DELIVERY_MANIFEST.json').write_text(json.dumps({'baseline_head':'ab17a13b42ce4e17512e339c8d9b90088adc6002',
        'exclude':'self and SHA256SUMS, caches, downloaded toolchain, Git internals','files':manifest},indent=2)+'\n')
    (DOCS/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+n+'\n' for n,x in manifest.items()))
    files += [DOCS/'DELIVERY_MANIFEST.json',DOCS/'SHA256SUMS']
    with tarfile.open(a.output,'w:gz',compresslevel=6) as tar:
        for p in files:tar.add(p,arcname='linear-xw-ip/'+p.relative_to(ROOT).as_posix(),recursive=False)
    # Read every archive member and validate stored bytes against final manifest.
    with tarfile.open(a.output,'r:gz') as tar:
        members={m.name: m for m in tar.getmembers()}
        assert len(members)==len(files)
        for rel,data in manifest.items():assert hashlib.sha256(tar.extractfile(members['linear-xw-ip/'+rel]).read()).hexdigest()==data['sha256'],rel
    digest=hashlib.sha256(a.output.read_bytes()).hexdigest()
    a.output.with_suffix(a.output.suffix+'.sha256').write_text(digest+'  '+a.output.name+'\n')
    print(json.dumps({'archive':str(a.output.resolve()),'bytes':a.output.stat().st_size,'sha256':digest,'files':len(files),'changed_sources':len(changes),'patch_check':'PASS','archive_byte_check':'PASS'},indent=2))
if __name__=='__main__':main()
