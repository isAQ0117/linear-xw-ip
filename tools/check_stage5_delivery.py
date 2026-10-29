#!/usr/bin/env python3
"""Verify the distributed snapshot before tests rewrite logs and reports."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--zip',type=Path);a=ap.parse_args()
    manifest=json.loads((ROOT/'docs/stage5/DELIVERY_MANIFEST.json').read_text())
    for n,r in manifest['files'].items():
        p=ROOT/n
        assert p.is_file() and p.stat().st_size==r['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],n
    if a.zip:
        with zipfile.ZipFile(a.zip) as z:
            assert z.testzip() is None
            for n,r in manifest['files'].items():assert hashlib.sha256(z.read('linear-xw-ip/'+n)).hexdigest()==r['sha256'],n
    print('PASS Stage5 delivery snapshot',len(manifest['files']),'file hashes; manifest self-excluded')
if __name__=='__main__':main()
