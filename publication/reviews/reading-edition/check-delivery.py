#!/usr/bin/env python3
"""Local reading-edition evidence; no C++ experiments or publication approval."""
import concurrent.futures
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BASE='fed7e085f77721c66076be344652d48eac27f041'
HERE=Path(__file__).resolve().parent


def sha(data):return hashlib.sha256(data).hexdigest()


def main(output):
    output.mkdir(exist_ok=False,parents=True)
    def run(name):
        command=[sys.executable,'-B',f'publication/tests/{name}.py']
        start=time.monotonic()
        done=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (output/(name+'.txt')).write_bytes(done.stdout)
        print(name,done.returncode,flush=True)
        return {'command':command,'exit_code':done.returncode,'seconds':round(time.monotonic()-start,2),
                'log':name+'.txt','sha256':sha(done.stdout)}
    names=['test-publication-isolation','test-candidate','test-products','test-preview','test-reading']
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(run,names))
    files=subprocess.check_output(['git','ls-tree','-r','--name-only','-z',BASE],cwd=ROOT).decode().split('\0')
    protected=[]
    for name in filter(None,files):
        if name.startswith('publication/') and not name.startswith('publication/reviews/v2-pilot/'):
            continue
        original=subprocess.check_output(['git','cat-file','blob',BASE+':'+name],cwd=ROOT)
        p=ROOT/name; current=p.read_bytes() if p.is_file() and not p.is_symlink() else None
        protected.append({'path':name,'base_sha256':sha(original),'current_sha256':sha(current) if current else None,
                          'unchanged':current==original})
    dist_expected={n for n in files if n.startswith('design/dist/')}
    dist_actual={str(p.relative_to(ROOT)) for p in (ROOT/'design/dist').rglob('*') if p.is_file()}
    for command,name in (([sys.executable,'-B','c++/learning/check_docs.py'],'check-docs'),(['git','diff','--check'],'diff-check')):
        done=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (output/(name+'.txt')).write_bytes(done.stdout)
        results.append({'command':command,'exit_code':done.returncode,'log':name+'.txt','sha256':sha(done.stdout)})
    record={'base':BASE,'platform':platform.platform(),'python':sys.version,'commands':results,
            'protected_files':protected,'dist_complete_file_set_equal':dist_expected==dist_actual,
            'not_run':['C++ compile/diagnostic rerun','performance rerun','concurrency dynamic rerun','formal publish'],
            'meaning':'Local publication regression evidence, not CI or content approval'}
    (output/'checks.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    return int(any(r['exit_code'] for r in results) or not all(p['unchanged'] for p in protected) or dist_expected!=dist_actual)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE/'checks')
    raise SystemExit(main(parser.parse_args().output.resolve()))
