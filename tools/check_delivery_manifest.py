#!/usr/bin/env python3
"""Validate complete delivered-tree hashes without Git or HDL tools."""
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
manifest=json.loads((root/'docs/stage23/FINAL_SOURCE_MANIFEST.json').read_text())
errors=[]
for name,info in manifest['files'].items():
    p=root/name
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=info['sha256']:
        errors.append(name)
if errors:
    raise SystemExit('FAIL missing/changed files: '+repr(errors))
print('PASS delivery manifest: '+str(len(manifest['files']))+' files')
