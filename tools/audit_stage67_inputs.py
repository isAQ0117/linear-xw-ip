#!/usr/bin/env python3
"""Recheck explicitly supplied upload ZIPs, Git identity, historical DDR formats."""
import argparse,csv,hashlib,io,json,subprocess,sys,zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from cycle_model import prepare

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-zip',type=Path,default=ROOT.parent/'upload/01-linear-xw-ip-stage012345.zip')
    ap.add_argument('--style-zip',type=Path,default=ROOT.parent/'upload/02-skill.zip');a=ap.parse_args()
    out=ROOT/'docs/stage67';info={'zip':[],'historical_formats':[],'initial_changes':[]}
    for p in [a.source_zip,a.style_zip]:
        data=p.read_bytes()
        with zipfile.ZipFile(p) as z:bad=z.testzip();count=len(z.infolist())
        assert bad is None
        info['zip'].append(dict(name=p.name,sha256=hashlib.sha256(data).hexdigest(),entries=count,crc_bad=bad))
    with zipfile.ZipFile(a.source_zip) as z:
        base={n[len('linear-xw-ip/'):]:z.read(n) for n in z.namelist() if n.startswith('linear-xw-ip/') and not n.endswith('/') and not n.startswith('linear-xw-ip/.git/')}
    info['head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    p=subprocess.run(['git','fsck','--full'],cwd=ROOT,capture_output=True,text=True);assert p.returncode==0
    info['git_fsck']='PASS';info['tracked_files']=len(base)
    for line in json.load(open(out/'BASELINE_AUDIT.json'))['status']:
        n=line[3:]
        if n not in base:continue
        old=subprocess.check_output(['git','show','HEAD:'+n],cwd=ROOT);now=base[n]
        info['initial_changes'].append(dict(path=n,only_line_endings=old.replace(b'\r\n',b'\n')==now.replace(b'\r\n',b'\n')))
    for p in (ROOT/'docs/verification/history/fp32_v0_2').glob('*'):
        b=p.read_bytes();r=dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
        if p.suffix=='.json':r['type']=type(json.loads(b)).__name__
        if p.suffix=='.jsonl':r['records']=sum(1 for s in b.splitlines() if json.loads(s) is not None)
        if p.suffix=='.csv':
            rows=list(csv.reader(io.StringIO(b.decode())));r['rows']=len(rows);r['fields']=rows[0]
        info['historical_formats'].append(r)
    image,manifest=prepare(json.load(open(ROOT/'examples/fp32_demo_case.json')))
    info['historical_ddr_image_rebuilt_equal']=image==(ROOT/'docs/verification/history/fp32_v0_2/ddr_image.bin').read_bytes()
    assert info['historical_ddr_image_rebuilt_equal']
    with zipfile.ZipFile(ROOT/'docs/standards/Linear_xW_Stage0_Interface_Verification_Contract_V1.0.docx') as doc:
        assert doc.testzip() is None
        xml=ET.fromstring(doc.read('word/document.xml'))
        text='\n'.join(''.join(p.itertext()) for p in xml.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))
        (out/'CONTRACT_DOCX_EXTRACT.txt').write_text(text)
    info['docx_container']='PASS'
    (out/'INPUT_INTEGRITY.json').write_text(json.dumps(info,indent=2,ensure_ascii=False)+'\n')
    print('PASS ZIP/Git/history/DDR rebuild; initial tracked changes are line-ending-only:',all(r['only_line_endings'] for r in info['initial_changes']))
if __name__=='__main__':main()
