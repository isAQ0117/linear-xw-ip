#!/usr/bin/env python3
"""Build exact uploaded-byte source diff, verify apply, hash and zip deliverables.

No Git add/commit or remote writes. Downloaded tool binaries and repeated
baseline checkout are not part of the project artifact. Actual Stage4 vectors,
compiled sims and synthesis netlists ARE included for independent inspection.
"""
import argparse,difflib,hashlib,json,os,subprocess,zipfile,io
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent


def include(path):
    p=path.relative_to(ROOT)
    if '.git' in p.parts or '__pycache__' in p.parts or p.suffix=='.pyc':return False
    if p.parts[0]=='sim_build':return len(p.parts)>2 and p.parts[1]=='stage4'
    return True


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--original-zip',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args()
    output=a.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    baseline=json.loads((ROOT/'docs/stage4/UPLOADED_BASELINE.json').read_text())
    original={}
    with zipfile.ZipFile(a.original_zip) as z:
        assert z.testzip() is None
        for n,info in baseline['files'].items():
            b=z.read('linear-xw-ip/'+n);assert hashlib.sha256(b).hexdigest()==info['sha256'];original[n]=b
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p))
    exclusions={'docs/stage4/SOURCE_CHANGES.patch','docs/stage4/DELIVERY_MANIFEST.json'}
    changes=[];patch=[]
    for p in files:
        n=p.relative_to(ROOT).as_posix()
        if n in exclusions or '/logs/' in '/'+n or n.startswith('sim_build/'):continue
        old=original.get(n,b'');new=p.read_bytes()
        if old==new:continue
        if p.suffix not in ['.v','.py','.sh','.md','.json','.f','.yaml','.tcl'] and p.name!='Makefile':continue
        patch.extend(difflib.unified_diff(old.decode('utf-8').splitlines(True),new.decode('utf-8').splitlines(True),
            fromfile='a/'+n if n in original else '/dev/null',tofile='b/'+n))
        changes.append(n)
    patch_path=ROOT/'docs/stage4/SOURCE_CHANGES.patch';patch_path.write_text(''.join(patch))
    # This folder is outside the project Git tree, containing only uploaded tracked bytes.
    replay=output.parent/'patch_apply_check';replay.mkdir(parents=True,exist_ok=True)
    for n,b in original.items():
        p=replay/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(output.parent))
    check=subprocess.run(['git','apply','--check',str(patch_path)],cwd=replay,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    assert check.returncode==0,check.stdout
    inventory={}
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and include(p) and p.relative_to(ROOT).as_posix()!='docs/stage4/DELIVERY_MANIFEST.json':
            b=p.read_bytes();inventory[p.relative_to(ROOT).as_posix()]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
    manifest=dict(baseline_head=baseline['head'],baseline='uploaded actual bytes; 20 CRLF differences preserved',
                  source_diff_apply_check='PASS against uploaded tracked-byte tree',source_diff_files=changes,
                  files=inventory,manifest_self_excluded=True,
                  note='Check hashes BEFORE reproducing tests; regenerated logs/paths/tool versions may change.')
    (ROOT/'docs/stage4/DELIVERY_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    archive_buffer=io.BytesIO()
    with zipfile.ZipFile(archive_buffer,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(ROOT.rglob('*')):
            if p.is_file() and include(p):z.write(p,'linear-xw-ip/'+p.relative_to(ROOT).as_posix())
    archive_bytes=archive_buffer.getvalue()
    temporary=output.with_suffix('.tmp')
    temporary.write_bytes(archive_bytes)
    temporary.replace(output)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        for n,r in inventory.items():assert hashlib.sha256(z.read('linear-xw-ip/'+n)).hexdigest()==r['sha256']
    subprocess.run(['python3','tools/check_stage4_delivery.py','--zip',str(output)],cwd=ROOT,check=True)
    print(json.dumps(dict(archive=str(output),bytes=output.stat().st_size,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                         files=len(inventory)+1,patch_files=len(changes),patch_apply='PASS',zip_crc='PASS'),indent=2))

if __name__=='__main__':main()
