#!/usr/bin/env python3
"""Record actual publication identity/regression commands without building PDFs."""
import argparse
import concurrent.futures
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
BASE='2f4caf671bc42e6e3b03a8eda8255e1a392e5798'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main(output):
    output.mkdir(parents=True,exist_ok=False)
    def inputs():
        return [{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())}
                for part in ('engine','latex','profiles','tests')
                for p in sorted((ROOT/'publication'/part).rglob('*'))
                if p.is_file() and '__pycache__' not in p.parts]
    started=datetime.now(timezone.utc).isoformat();before=inputs()
    def run(name):
        command=[sys.executable,'-B','publication/tests/'+name+'.py']
        start=time.monotonic()
        result=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (output/(name+'.txt')).write_bytes(result.stdout)
        print(name,result.returncode,flush=True)
        return {'command':command,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,2),
                'log':name+'.txt','sha256':sha(result.stdout)}
    names=['test-publication-isolation','test-candidate','test-products','test-preview','test-reading','test-full-handbook','test-release-identity','test-publication-identity']
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(run,names))
    command=[sys.executable,'-B','c++/learning/check_docs.py']
    result=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (output/'check-docs.txt').write_bytes(result.stdout)
    results.append({'command':command,'exit_code':result.returncode,'log':'check-docs.txt','sha256':sha(result.stdout)})
    files=subprocess.check_output(['git','ls-tree','-r','--name-only','-z',BASE],cwd=ROOT).decode().split('\0')
    protected=[]
    for name in filter(None,files):
        if name in ('publication/README.md','publication/engine/source_model.py','publication/tests/test-release-identity.py'):continue
        old=subprocess.check_output(['git','cat-file','blob',BASE+':'+name],cwd=ROOT)
        p=ROOT/name;current=p.read_bytes() if p.is_file() and not p.is_symlink() else b''
        protected.append({'path':name,'base_sha256':sha(old),'current_sha256':sha(current),'unchanged':old==current})
    expected={name for name in files if name.startswith('design/dist/')}
    actual={str(p.relative_to(ROOT)) for p in (ROOT/'design/dist').rglob('*') if p.is_file()}
    data={'base':BASE,'platform':platform.platform(),'python':sys.version,'commands':results,
          'started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat(),
          'checked_inputs':before,'inputs_unchanged_during_checks':before==inputs(),
          'protected_files':protected,'dist_complete_file_set_equal':expected==actual,
          'not_run':['C++ experiments','performance measurements','concurrency dynamic tests','formal publish'],
          'meaning':'Local publication regressions; not CI, independent review or technical content revalidation'}
    (output/'checks.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    return int(any(r['exit_code'] for r in results) or not all(p['unchanged'] for p in protected) or expected!=actual or not data['inputs_unchanged_during_checks'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    raise SystemExit(main(parser.parse_args().output.resolve()))
