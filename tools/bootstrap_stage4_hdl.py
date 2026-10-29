#!/usr/bin/env python3
"""Optional reproducible local Linux-amd64 tools, no root/system installation.

Normal machines can use their installed iverilog/vvp/yosys. This bootstrap is
for this restricted environment (no /proc/self/exe and unwritable /tmp).
Fetched Debian packages are pinned by SHA256; a changed download fails closed.
"""
import argparse,hashlib,os,platform,shlex,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
PACKAGES={
 'iverilog':('https://deb.debian.org/debian/pool/main/i/iverilog/iverilog_11.0-1.1+b1_amd64.deb','14d9d14dc8256fd89667fb68c3bd93f1c57310b9c95b33fb0d4b7719c887ae2f'),
 'yosys':('https://deb.debian.org/debian/pool/main/y/yosys/yosys_0.23-6_amd64.deb','00cb3419d9c2e8964e588cbfa8a46b8d0ff4b391083a53a82d49ec1c2766330b'),
 'tcl':('https://deb.debian.org/debian/pool/main/t/tcl8.6/libtcl8.6_8.6.13+dfsg-2_amd64.deb','976c4235b816635e1756016f3adbabb634e8b97a9f6b97cf901be099e4fd2487'),
 'abc':('https://deb.debian.org/debian/pool/main/b/berkeley-abc/berkeley-abc_1.01+20221019git70cb339+dfsg-4_amd64.deb','647287c7cfe518af90dbfea71316484aa0ca7cdac130450a1a17b9030a118e58')}
SHIM=r'''#define _GNU_SOURCE
#include <unistd.h>
#include <dlfcn.h>
#include <stdlib.h>
#include <string.h>
ssize_t readlink(const char *p, char *buf, size_t n) {
 const char *q=getenv("XW_TOOL_EXEC");
 if(q && (!strcmp(p,"/proc/self/exe") || !strcmp(p,"/proc/curproc/file"))) {
  size_t m=strlen(q); if(m>n)m=n; memcpy(buf,q,m); return m;
 }
 ssize_t (*f)(const char*,char*,size_t)=dlsym(RTLD_NEXT,"readlink");
 return f(p,buf,n);
}
'''


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--with-yosys',action='store_true');ap.add_argument('--prefix',type=Path,default=ROOT/'sim_build/toolchain');a=ap.parse_args()
    assert platform.machine()=='x86_64' and platform.system()=='Linux','bootstrap supports Linux x86_64 only'
    p=a.prefix.resolve();p.mkdir(parents=True,exist_ok=True)
    for n in ['iverilog']+(['yosys','tcl','abc'] if a.with_yosys else []):
        url,h=PACKAGES[n];deb=p/(n+'.deb')
        if not deb.exists():subprocess.run(['curl','--fail','-L','--connect-timeout','15','--max-time','120','-o',str(deb),url],check=True)
        assert hashlib.sha256(deb.read_bytes()).hexdigest()==h,'download hash mismatch: '+n
        subprocess.run(['dpkg-deb','-x',str(deb),str(p)],check=True)
    (p/'pathshim.c').write_text(SHIM)
    subprocess.run(['gcc','-shared','-fPIC','-o',str(p/'pathshim.so'),str(p/'pathshim.c'),'-ldl'],check=True)
    (p/'tmp').mkdir(exist_ok=True);(p/'bin').mkdir(exist_ok=True)
    names=['iverilog','vvp']+(['yosys','berkeley-abc'] if a.with_yosys else [])
    for n in names:
        q=shlex.quote
        executable=p/'usr/bin'/n
        options=' -B '+q(str(p/'usr/lib/x86_64-linux-gnu/ivl')) if n=='iverilog' else ''
        wrapper=(f'#!/bin/sh\nexport TMPDIR={q(str(p/"tmp"))}\n'
            f'export LD_LIBRARY_PATH={q(str(p/"usr/lib/x86_64-linux-gnu"))}${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}\n'
            f'export LD_PRELOAD={q(str(p/"pathshim.so"))}\nexport XW_TOOL_EXEC={q(str(executable))}\n'
            f'exec {q(str(executable))}{options} "$@"\n')
        path=p/'bin'/n;path.write_text(wrapper);path.chmod(0o755)
    print('export PATH='+shlex.quote(str(p/'bin'))+':$PATH')

if __name__=='__main__':main()
