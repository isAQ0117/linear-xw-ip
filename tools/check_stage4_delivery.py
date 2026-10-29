#!/usr/bin/env python3
"""Verify distributed snapshot hashes BEFORE rerunning tests that rewrite logs."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--zip',type=Path);a=ap.parse_args()
    m=json.loads((ROOT/'docs/stage4/DELIVERY_MANIFEST.json').read_text())
    bad=[]
    for n,r in m['files'].items():
        p=ROOT/n
        if not p.is_file() or p.stat().st_size!=r['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:bad.append(n)
    assert not bad,('missing/changed distributed snapshot bytes',bad)
    if a.zip:
        with zipfile.ZipFile(a.zip) as z:assert z.testzip() is None
    print('PASS Stage4 delivery snapshot:',len(m['files']),'file hashes; manifest self-excluded')

if __name__=='__main__':main()
