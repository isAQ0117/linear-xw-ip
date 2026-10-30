#!/usr/bin/env python3
"""Uploaded-byte/source/ABI/profile audit, not a substitute for simulation."""
import ast,hashlib,json,re,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    baseline=json.load(open(ROOT/'docs/stage67/BASELINE_SHA256.json'));protected=[n for n in baseline if n.startswith('rtl/') and n.endswith('.v') or n.startswith('docs/standards/') or n=='linear_stream_model/numeric.py']
    assert all(sha((ROOT/n).read_bytes())==baseline[n] for n in protected)
    top=(ROOT/'rtl/linear_xw_ip.v').read_text();header=top.split(');',1)[0]
    parameters=re.findall(r'parameter integer (\w+)\s*=',header)
    assert parameters==['STATIC_DIM_MODE','N_DIM','K_DIM','MAX_N','MAX_K','MAX_M','MAX_M_TILE','P_N','P_K','AXIS_DATA_W']
    ps=re.findall(r'\b(input|output)\s+wire\s+(?:\[(\d+):0\]\s+)?(\w+)\s*[,\n]',header+'\n')
    expected={'clk':('input',1),'rst_n':('input',1),'job_valid':('input',1),'job_ready':('output',1),'job_id':('input',32),
        'job_m':('input',16),'job_n':('input',16),'job_k':('input',16),'job_m_tile':('input',8),'job_weight_base':('input',29),'job_scale_base':('input',29),
        'busy':('output',1),'status_valid':('output',1),'status_ready':('input',1),'status_job_id':('output',32),'status_ok':('output',1),'status_error_code':('output',8),
        'ddr_rd_req':('output',1),'ddr_rd_addra':('output',29),'ddr_rd_addrb':('output',29),'ddr_rd_rdy':('input',1),'ddr_rd_data':('input',512),'ddr_rd_vld':('input',1)}
    for prefix in ('s','m'):
        for name,width in [('tdata',512),('tvalid',1),('tready',1),('tkeep',64),('tlast',1),('tuser',128)]:
            expected[prefix+'_axis_'+name]=('input' if (prefix=='s') != (name=='tready') else 'output',width)
    actual={n:(d,int(w)+1 if w else 1) for d,w,n in ps};assert actual==expected and len(ps)==35
    release=json.load(open(ROOT/'docs/standards/Linear_xW_Standards_Release_Manifest_V1.0.json'));standards=[]
    for name,record in release['files'].items():
        b=(ROOT/'docs/standards'/name).read_bytes()
        standards.append(dict(file=name,raw_matches=sha(b)==record['sha256'],LF_matches=sha(b.replace(b'\r\n',b'\n'))==record['sha256'],actual_sha256=sha(b)))
    skill=[]
    style_zip=ROOT.parent/'upload/02-skill.zip'
    if style_zip.exists():
        with zipfile.ZipFile(style_zip) as z:
            assert z.testzip() is None
            for n in z.namelist():
                q=ROOT/'tools/rtl_house_style'/Path(n).relative_to('verilog-rtl-house-style')
                skill.append(dict(file=n,sha256=sha(z.read(n)),repository_copy_equal=q.exists() and q.read_bytes()==z.read(n)))
        skill_provenance='actual attached Skill ZIP'
    else:
        prior=json.load(open(ROOT/'docs/stage67/AUDIT_RESULTS.json'))['skill']
        for record in prior:
            q=ROOT/'tools/rtl_house_style'/Path(record['file']).relative_to('verilog-rtl-house-style')
            skill.append(dict(file=record['file'],sha256=record['sha256'],repository_copy_equal=q.exists() and sha(q.read_bytes())==record['sha256']))
        skill_provenance='recorded uploaded Skill SHA256; ZIP not included in review archive'
    assert all(r['repository_copy_equal'] for r in skill)
    initial=json.load(open(ROOT/'docs/stage67/BASELINE_AUDIT.json'))
    git_root=subprocess.run(['git','rev-parse','--show-toplevel'],cwd=ROOT,capture_output=True,text=True)
    own_git=git_root.returncode==0 and Path(git_root.stdout.strip()).resolve()==ROOT.resolve()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip() if own_git else initial['head']
    head_provenance='actual Git HEAD' if own_git else 'recorded uploaded HEAD; review archive excludes Git internals'
    diff=subprocess.check_output(['git','diff','--ignore-space-at-eol','--numstat'],cwd=ROOT).decode() if own_git else 'Review archive: use exact-upload SOURCE_CHANGES.patch and its retained apply-check evidence'
    p=ROOT/'docs/stage67/AUDIT_RESULTS.json'
    p.write_text(json.dumps(dict(status='PASS',head=head,head_provenance=head_provenance,skill_provenance=skill_provenance,
        uploaded_worktree_used=True,initial_status=initial['status'],protected_files=protected,protected_unchanged=len(protected),
        top_parameters=parameters,top_ports=actual,source_count=len(list((ROOT/'rtl').glob('*.v'))),standards=standards,skill=skill,
        semantic_diff_numstat=diff,dependencies='Python standard library; actual Icarus 11.0, Yosys 0.23; optional Vivado2023.2 pending'),indent=2,ensure_ascii=False)+'\n')
    print('PASS audit',len(protected),'protected files, 10 parameters, 35 ports')
if __name__=='__main__':main()
