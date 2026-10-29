#!/usr/bin/env python3
"""Audit exact uploaded bytes, all source formats/dependencies, and current hashes."""
import ast,csv,hashlib,json,subprocess,sys,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from cycle_model import prepare

def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    base=json.loads((ROOT/'docs/stage5/UPLOADED_BASELINE.json').read_text())
    protected=[n for n in base['tree'] if (n.startswith('rtl/') and n.endswith('.v')) or n.startswith('docs/standards/') or n=='linear_stream_model/numeric.py']
    for n in protected:assert sha((ROOT/n).read_bytes())==base['tree'][n]['sha256'],('protected bytes changed',n)
    catalog={};imports=set();json_rows=csv_rows=0
    for n,meta in base['tree'].items():
        p=ROOT/n
        assert p.is_file(),n
        data=p.read_bytes();entry=dict(bytes=len(data),sha256=sha(data))
        suffix=p.suffix.lower()
        if suffix in ['.bin','.docx']:
            entry['format']=suffix
        else:
            text=data.decode('utf-8-sig');entry.update(lines=len(text.splitlines()),read='FULL_UTF8')
            if suffix=='.py':
                tree=ast.parse(text,n)
                entry['definitions']=[x.name for x in ast.walk(tree) if isinstance(x,(ast.FunctionDef,ast.ClassDef))]
                for x in ast.walk(tree):
                    if isinstance(x,ast.Import):imports.update(a.name.split('.')[0] for a in x.names)
                    if isinstance(x,ast.ImportFrom) and x.module:imports.add(x.module.split('.')[0])
            elif suffix=='.json':json.loads(text);entry['format']='JSON_FULL_PARSE'
            elif suffix=='.jsonl':
                rows=[json.loads(l) for l in text.splitlines() if l.strip()];json_rows+=len(rows)
                entry.update(format='JSONL_FULL_PARSE',records=len(rows),events=sorted(set(str(x.get('event','')) for x in rows if isinstance(x,dict))))
            elif suffix=='.csv':
                rows=list(csv.reader(text.splitlines()));csv_rows+=len(rows);entry.update(format='CSV_FULL_PARSE',records=len(rows),columns=rows[0] if rows else [])
            elif suffix=='.sh':
                r=subprocess.run(['sh','-n',str(p)],text=True,capture_output=True);assert r.returncode==0,(n,r.stderr)
                entry['format']='SHELL_SYNTAX_PASS'
            elif suffix=='.v':entry.update(format='VERILOG_SOURCE',modules=__import__('re').findall(r'\bmodule\s+(\w+)',text))
            elif suffix in ['.hex','.mem','.vec']:
                for row in text.splitlines():
                    if row.strip() and not row.lstrip().startswith('//'):
                        for field in row.split():int(field,16)
                entry['format']='HEX_FULL_PARSE'
        catalog[n]=entry
    hist=ROOT/'docs/verification/history/fp32_v0_2';image,manifest=prepare(json.loads((ROOT/'examples/fp32_demo_case.json').read_text()))
    assert image==(hist/'ddr_image.bin').read_bytes();assert manifest==json.loads((hist/'ddr_manifest.json').read_text())
    doc=ROOT/'docs/standards/Linear_xW_Stage0_Interface_Verification_Contract_V1.0.docx'
    with zipfile.ZipFile(doc) as z:
        assert z.testzip() is None
        xml=ET.fromstring(z.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        full='\n'.join(''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in xml.findall('.//w:p',ns))
        (ROOT/'docs/stage5/BASELINE_DOCX_EXTRACT.txt').write_text(full)
        docx_parts=len(z.infolist())
    archive_checks=[]
    for p in sorted((ROOT.parent/'upload').glob('*.zip')):
        with zipfile.ZipFile(p) as z:
            assert z.testzip() is None
            assert all(not Path(x.filename).is_absolute() and '..' not in Path(x.filename).parts for x in z.infolist())
            archive_checks.append(dict(name=p.name,sha256=sha(p.read_bytes()),entries=len(z.infolist()),crc='PASS',paths='PASS'))
    style=ROOT.parent/'verilog-rtl-house-style'
    if style.exists():
        for p in style.rglob('*'):
            if p.is_file():assert p.read_bytes()==(ROOT/'tools/rtl_house_style'/p.relative_to(style)).read_bytes()
    # Audit the uploaded dirty tree against HEAD without checking out any version.
    uploaded=zipfile.ZipFile(ROOT.parent/'upload/02-linear-xw-ip-stage01234.zip') if (ROOT.parent/'upload/02-linear-xw-ip-stage01234.zip').exists() else None
    line_endings=[]
    if uploaded:
        for line in base['status'].splitlines():
            n=line[3:];old=uploaded.read('linear-xw-ip/'+n)
            head=subprocess.check_output(['git','show',base['head']+':'+n],cwd=ROOT)
            assert old.replace(b'\r\n',b'\n')==head.replace(b'\r\n',b'\n'),('uploaded semantic change',n)
            line_endings.append(n)
    release=json.loads((ROOT/'docs/standards/Linear_xW_Standards_Release_Manifest_V1.0.json').read_text())
    release_checks=[]
    for n,r in release['files'].items():
        data=(ROOT/'docs/standards'/n).read_bytes()
        release_checks.append(dict(file=n,exact=sha(data)==r['sha256'],lf_normalized=sha(data.replace(b'\r\n',b'\n'))==r['sha256']))
    sources=(ROOT/'rtl_sources.f').read_text().splitlines()
    assert len(sources)==len(set(sources))==16 and all((ROOT/n).is_file() for n in sources)
    result=dict(status='PASS',production_sources=sources,head=base['head'],archives=archive_checks,protected_count=len(protected),protected_unchanged=True,
        uploaded_modifications_line_endings_only=line_endings,baseline_catalog=catalog,imports=sorted(imports),
        historic_ddr_rebuild='PASS',historic_ddr_bytes=len(image),jsonl_records=json_rows,csv_rows=csv_rows,
        docx=dict(parts=docx_parts,crc='PASS',text_extracted=True),release_manifest_checks=release_checks,
        discrepancies=['Historical Stage4 reports reference absent DELIVERY_MANIFEST.json and logs/measurements. Actual baseline tests rerun; current delivery has its own manifest.',
                       'Historical PROJECT_STATUS and Stage4 report HEAD differ from uploaded HEAD. Current audit uses actual uploaded working bytes.',
                       'Old cycle_model.py exposes assumed latencies, so it is not the Stage5 microarchitecture model.',
                       'Historical Stage4 audit expects exactly 12 RTL sources. Stage5 current audit owns the extended 16-source list.'])
    (ROOT/'docs/stage5/AUDIT_RESULTS.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print('PASS Stage5 source audit:',len(catalog),'uploaded files,',len(protected),'protected bytes, all cataloged formats parsed')
if __name__=='__main__':main()
