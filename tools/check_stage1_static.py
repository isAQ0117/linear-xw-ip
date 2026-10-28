#!/usr/bin/env python3
"""Structural, NOT HDL-elaboration, checks for Stage-1 RTL and testbenches.

An optional --baseline points to the original FP32 V0.2 rtl directory so
B2's assignment expression identities can be compared textually.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_PORTS = {
    'xw_job_dim_cfg': 13,
    'xw_ddr_range_rx': 22,
    'xw_scale_group_cache': 15,
    'xw_fp32_scale_b2': 6,
}


def strip_comments_and_strings(code):
    code = re.sub(r'/\*.*?\*/', ' ', code, flags=re.S)
    code = re.sub(r'//[^\n]*', ' ', code)
    return re.sub(r'"(?:\\.|[^"\\])*"', '""', code)


def assignments(code):
    src = strip_comments_and_strings(code)
    return {name: re.sub(r'\s+', '', rhs)
            for name, rhs in re.findall(r'\bassign\s+(\w+)\s*=\s*(.*?);',src,re.S)}


def balanced(code):
    src = strip_comments_and_strings(code)
    errors = []
    stack = []
    pairs = {')':'(', ']':'[', '}':'{'}
    for ch in src:
        if ch in '([{':
            stack.append(ch)
        elif ch in ')]}':
            if not stack or stack.pop() != pairs[ch]:
                errors.append('unbalanced bracket')
                break
    if stack:
        errors.append('unclosed brackets')
    for a,b in [('module','endmodule'),('begin','end'),
                ('generate','endgenerate'),('task','endtask')]:
        if len(re.findall(r'\b'+a+r'\b',src)) != len(re.findall(r'\b'+b+r'\b',src)):
            errors.append('unbalanced '+a+'/'+b)
    return errors


def extract_ansi_ports(src, module_name):
    match = re.search(r'\bmodule\s+' + re.escape(module_name) + r'\b', src)
    if not match:
        return None
    pos = match.end()
    while pos < len(src) and src[pos].isspace():
        pos += 1
    if pos < len(src) and src[pos] == '#':
        pos += 1
        while pos < len(src) and src[pos].isspace():
            pos += 1
        if pos >= len(src) or src[pos] != '(':
            return None
        nesting = 0
        while pos < len(src):
            if src[pos] == '(':
                nesting += 1
            elif src[pos] == ')':
                nesting -= 1
                if nesting == 0:
                    pos += 1
                    break
            pos += 1
    while pos < len(src) and src[pos].isspace():
        pos += 1
    if pos >= len(src) or src[pos] != '(':
        return None
    start = pos + 1
    nesting = 1
    pos += 1
    while pos < len(src):
        if src[pos] == '(':
            nesting += 1
        elif src[pos] == ')':
            nesting -= 1
            if nesting == 0:
                return src[start:pos]
        pos += 1
    return None


def run():
    p=argparse.ArgumentParser()
    p.add_argument('--baseline', type=Path)
    args=p.parse_args()
    failures=[]
    result={'check_type':'STRUCTURAL_ONLY_NOT_HDL_COMPILATION','modules':{},'errors':[]}
    for name,port_count in EXPECTED_PORTS.items():
        path=ROOT/'rtl'/f'{name}.v'
        code=path.read_text('utf-8')
        src=strip_comments_and_strings(code)
        portlist=extract_ansi_ports(src, name)
        if portlist is None:
            failures.append(f'{name}: cannot find ANSI port list')
            continue
        ports=re.findall(r'\b(?:input|output|inout)\b\s+(?:wire|reg)?\s*(?:signed\s+)?(?:\[.*?\]\s*)?(\w+)\s*(?:,|$)',portlist,re.S)
        if len(ports)!=port_count or len(set(ports))!=port_count:
            failures.append(f'{name}: expected {port_count} ports, got {len(ports)}: {ports}')
        if balanced(code):
            failures.extend(f'{name}: {msg}' for msg in balanced(code))
        if re.search(r'\b(?:logic|always_ff|always_comb|typedef|interface)\b',src):
            failures.append(f'{name}: SystemVerilog-only keyword')
        result['modules'][name]={'ports':len(ports),'name_list':ports,'balanced':not balanced(code)}
    for path in sorted((ROOT/'tb').rglob('*.v')):
        for err in balanced(path.read_text('utf-8')):
            failures.append(f'tb/{path.name}: {err}')
    if args.baseline:
        old=assignments((args.baseline/'xw_fp32_scale_b2.v').read_text('utf-8'))
        new=assignments((ROOT/'rtl'/'xw_fp32_scale_b2.v').read_text('utf-8'))
        differences={k:dict(original=old.get(k),new=new.get(k))
                     for k in sorted(set(old)|set(new)) if old.get(k)!=new.get(k)}
        result['b2_assignment_identity']={'checked':True,'differences':differences}
        if differences:
            failures.append('B2 arithmetic expression changed')
    else:
        result['b2_assignment_identity']={'checked':False}
    result['errors']=failures
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if failures:
        raise SystemExit(1)
    print('PASS structural Stage-1 checks (not HDL compilation)')

if __name__=='__main__':
    run()
