#!/usr/bin/env python3
"""Static FFN-inspired Verilog-2001 RTL style checker (not a HDL parser).

Usage: python check_rtl_style.py rtl/ module.v [--json]
Checks: ANSI ports, explicit wire/reg type, one port per item, declaration
placement, 4-space indentation, no tabs, comments before always, no SV-only
keywords. No source code is modified.
"""
import argparse
import json
import re
import sys
from pathlib import Path

MODULE_RE = re.compile(r"\bmodule\s+(?:automatic\s+)?([A-Za-z_][A-Za-z_0-9$]*)\b")
ENDMODULE_RE = re.compile(r"\bendmodule\b")
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9$]*|\S")
DECL_WORDS = {
    "wire", "reg", "integer", "genvar", "parameter", "localparam",
    "tri", "tri0", "tri1", "wand", "wor", "trireg", "supply0",
    "supply1", "time", "real", "realtime", "event",
}
LOGIC_WORDS = {"assign", "always", "initial", "generate", "function", "task", "defparam"}
SV_ONLY_RE = re.compile(
    r"\b(always_ff|always_comb|always_latch|logic|typedef|interface|endinterface|"
    r"package|endpackage|struct|enum|bit|byte|shortint|longint)\b"
)
PORT_START_RE = re.compile(r"\s*(input|output|inout)\s+(wire|reg|tri|wand|wor)\b")
INSTANCE_START_RE = re.compile(
    r"(?m)^[ \t]*([A-Za-z_][A-Za-z_0-9$]*)\s+"
    r"(?:#\s*\(|[A-Za-z_][A-Za-z_0-9$]*\s*\()"
)
INSTANCE_EXCLUDE = DECL_WORDS | LOGIC_WORDS | {
    "if", "else", "for", "while", "case", "casex", "casez", "repeat",
    "wait", "begin", "end", "endcase", "endgenerate", "endfunction", "endtask",
    "input", "output", "inout", "default", "end", "endmodule",
}


def mask_noncode(s):
    """Keep positions/newlines while replacing comments and quoted strings."""
    out = list(s)
    i = 0
    n = len(s)
    state = "code"
    while i < n:
        c = s[i]
        d = s[i + 1] if i + 1 < n else ""
        if state == "code":
            if c == "/" and d == "/":
                out[i] = out[i + 1] = " "
                i += 2
                state = "line"
                continue
            if c == "/" and d == "*":
                out[i] = out[i + 1] = " "
                i += 2
                state = "block"
                continue
            if c == '"':
                out[i] = " "
                state = "string"
                i += 1
                continue
        elif state == "line":
            if c == "\n":
                state = "code"
            else:
                out[i] = " "
            i += 1
            continue
        elif state == "block":
            if c == "*" and d == "/":
                out[i] = out[i + 1] = " "
                i += 2
                state = "code"
                continue
            if c != "\n":
                out[i] = " "
            i += 1
            continue
        elif state == "string":
            if c == "\\":
                out[i] = " "
                if i + 1 < n:
                    if s[i + 1] != "\n":
                        out[i + 1] = " "
                    i += 2
                else:
                    i += 1
                continue
            if c == '"':
                state = "code"
            if c != "\n":
                out[i] = " "
            i += 1
            continue
        i += 1
    return "".join(out)


def skip_ws(s, i):
    while i < len(s) and s[i].isspace():
        i += 1
    return i


def matching_paren(s, start):
    """Find matching ')' starting at '(', aware of all nested parens."""
    if start >= len(s) or s[start] != "(":
        return None
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def port_items(ports, start_offset):
    """Split by top-level commas, retaining start absolute offsets."""
    items = []
    start = 0
    nesting = []
    opens = {"(": ")", "[": "]", "{": "}"}
    for i, c in enumerate(ports):
        if c in opens:
            nesting.append(opens[c])
        elif nesting and c == nesting[-1]:
            nesting.pop()
        elif c == "," and not nesting:
            items.append((ports[start:i], start_offset + start))
            start = i + 1
    if ports[start:].strip() or not items:
        items.append((ports[start:], start_offset + start))
    return items


def find_modules(s):
    """Locate module interfaces without requiring third-party Verilog parser."""
    pos = 0
    while True:
        m = MODULE_RE.search(s, pos)
        if not m:
            return
        name = m.group(1)
        p = skip_ws(s, m.end())
        if p < len(s) and s[p] == "#":
            p = skip_ws(s, p + 1)
            if p >= len(s) or s[p] != "(":
                yield name, None, None, None, None, "malformed parameter header", m.start()
                pos = m.end()
                continue
            end = matching_paren(s, p)
            if end is None:
                yield name, None, None, None, None, "unclosed parameter header", m.start()
                return
            p = skip_ws(s, end + 1)
        port_range = None
        if p < len(s) and s[p] == "(":
            end = matching_paren(s, p)
            if end is None:
                yield name, None, None, None, None, "unclosed module port list", m.start()
                return
            port_range = (p + 1, end)
            p = skip_ws(s, end + 1)
        if p >= len(s) or s[p] != ";":
            yield name, None, None, None, None, "missing ';' after module header", m.start()
            pos = m.end()
            continue
        endmod = ENDMODULE_RE.search(s, p + 1)
        if not endmod:
            yield name, port_range, p + 1, None, None, "missing endmodule", m.start()
            return
        yield name, port_range, p + 1, endmod.start(), endmod.end(), None, m.start()
        pos = endmod.end()


def loc(s, off):
    return s.count("\n", 0, off) + 1


def problem(problems, path, module, line, code, message):
    problems.append(dict(file=str(path), module=module, line=line, code=code, message=message))


def preceding_comment(lines, line_index):
    """An always statement must have a comment immediately above it."""
    idx = line_index - 1
    while idx >= 0 and not lines[idx].strip():
        idx -= 1
    if idx < 0:
        return False
    t = lines[idx].strip()
    return t.startswith("//") or t.endswith("*/")


def check_body(body, raw_body, absolute_body_start, entire_file, path, name, problems):
    """Conservatively detect *module-scope* declarations after executable logic."""
    # Recognize submodule instantiation when it appears at a root-level line.
    instances = set()
    for m in INSTANCE_START_RE.finditer(body):
        if m.group(1) not in INSTANCE_EXCLUDE:
            instances.add(m.start(1))

    begin_depth = case_depth = fun_depth = task_depth = gen_depth = fork_depth = 0
    logic_seen = False
    for m in TOKEN_RE.finditer(body):
        word = m.group()
        at_root = not (begin_depth or case_depth or fun_depth or task_depth or gen_depth or fork_depth)
        if at_root and m.start() in instances:
            logic_seen = True
        if at_root and word in DECL_WORDS and logic_seen:
            problem(problems, path, name, loc(entire_file, absolute_body_start + m.start()),
                    "DECL_AFTER_LOGIC", f"模块级 {word} 声明出现在逻辑/例化之后，应集中移至接口后")
        if at_root and word in LOGIC_WORDS:
            logic_seen = True
        # Scope tracking keeps declarations in always/function/generate local scopes exempt.
        if word == "begin":
            begin_depth += 1
        elif word == "end":
            begin_depth = max(0, begin_depth - 1)
        elif word in ("case", "casez", "casex"):
            case_depth += 1
        elif word == "endcase":
            case_depth = max(0, case_depth - 1)
        elif word == "function":
            fun_depth += 1
        elif word == "endfunction":
            fun_depth = max(0, fun_depth - 1)
        elif word == "task":
            task_depth += 1
        elif word == "endtask":
            task_depth = max(0, task_depth - 1)
        elif word == "generate":
            gen_depth += 1
        elif word == "endgenerate":
            gen_depth = max(0, gen_depth - 1)
        elif word == "fork":
            fork_depth += 1
        elif word in ("join", "join_any", "join_none"):
            fork_depth = max(0, fork_depth - 1)

    lines = raw_body.splitlines()
    for m in re.finditer(r"\balways\b", body):
        body_line = body.count("\n", 0, m.start())
        if not preceding_comment(lines, body_line):
            problem(problems, path, name, loc(entire_file, absolute_body_start + m.start()),
                    "ALWAYS_COMMENT", "always 之前缺少紧邻的用途说明注释")
    for m in SV_ONLY_RE.finditer(body):
        problem(problems, path, name, loc(entire_file, absolute_body_start + m.start()),
                "SYSTEMVERILOG_ONLY", f"禁止使用 SystemVerilog 专有关键字 {m.group()}")


def check_one(path):
    source = path.read_text(encoding="utf-8-sig")
    masked = mask_noncode(source)
    issues = []
    for lnum, line in enumerate(source.splitlines(), 1):
        if "\t" in line:
            problem(issues, path, "", lnum, "TAB", "使用 4 个空格缩进，禁止 Tab")
        if line.rstrip() != line:
            problem(issues, path, "", lnum, "TRAILING_WHITESPACE", "行末存在多余空格")
    for name, ports, body_start, body_end, _, error, mstart in find_modules(masked):
        if error:
            problem(issues, path, name, loc(source, mstart), "MODULE_HEADER", error)
            continue
        if ports is not None:
            content = masked[ports[0]:ports[1]]
            if content.strip():
                for segment, seg_offset in port_items(content, ports[0]):
                    if not segment.strip():
                        problem(issues, path, name, loc(source, seg_offset), "EMPTY_PORT", "端口项为空")
                        continue
                    start = seg_offset + len(segment) - len(segment.lstrip())
                    if not PORT_START_RE.match(segment):
                        problem(issues, path, name, loc(source, start), "NON_ANSI_PORT",
                                "每个端口需在 module 括号内单独写 input/output/inout wire/reg ...")
                    # Require a new line and 4-space indent for each port declaration.
                    line_start = source.rfind("\n", 0, start) + 1
                    column = start - line_start
                    if column != 4:
                        problem(issues, path, name, loc(source, start), "PORT_INDENT",
                                f"端口声明建议为 4 空格缩进，实际为 {column}")
        else:
            # A port-less module is valid and needn't use a parenthesized list.
            pass
        check_body(masked[body_start:body_end], source[body_start:body_end],
                   body_start, source, path, name, issues)
    return issues


def list_files(paths):
    res = []
    for name in paths:
        p = Path(name)
        if not p.exists():
            raise FileNotFoundError(name)
        if p.is_dir():
            res.extend(sorted(p.rglob("*.v")))
        elif p.suffix.lower() == ".v":
            res.append(p)
        else:
            raise ValueError(f"not a .v file or directory: {p}")
    return sorted(set(res))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+", help="Verilog .v files and/or directories")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args(argv)
    try:
        files = list_files(args.paths)
        if not files:
            raise ValueError("no Verilog files found")
        problems = []
        for file in files:
            problems.extend(check_one(file))
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(dict(files_checked=len(files), violations=len(problems),
                              issues=problems), ensure_ascii=False, indent=2))
    else:
        print(f"Checked {len(files)} Verilog file(s); {len(problems)} style issue(s).")
        for issue in problems:
            print(f"{issue['file']}:{issue['line']} [{issue['module']}] "
                  f"{issue['code']}: {issue['message']}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
