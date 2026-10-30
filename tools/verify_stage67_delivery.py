#!/usr/bin/env python3
"""Verify extracted review payload without Git metadata or original uploads."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
manifest=json.load(open(ROOT/'docs/stage67/DELIVERY_MANIFEST.json'))['files']
for name,record in manifest.items():
    p=ROOT/name
    assert p.is_file(),name+' missing'
    assert p.stat().st_size==record['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==record['sha256'],name+' mismatch'
print('PASS extracted delivery SHA256',len(manifest),'files')
