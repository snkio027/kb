#!/usr/bin/env python3
"""Capture local publication regressions and exact protected-file comparisons."""
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BASE='45b305eace0f057420587d685cb3f962f3f0552c'
def sha(data):return hashlib.sha256(data).hexdigest()
def main(output):
    output.mkdir(parents=True,exist_ok=False)
    files=sorted((ROOT/'publication/tests').glob('test-*.py'))
    inputs=sorted(p for folder in ('publication/engine','publication/latex','publication/tests','publication/profiles')
                  for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    before={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in inputs}
    commands=[]
    for f in files:
        argv=[sys.executable,'-B',str(f.relative_to(ROOT))]
        run=subprocess.run(argv,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        log=f.stem+'.txt';(output/log).write_bytes(run.stdout)
        commands.append({'argv':argv,'exit_code':run.returncode,'log':log,'log_sha256':sha(run.stdout)})
        print(f.name,run.returncode,flush=True)
    argv=[sys.executable,'-B','c++/learning/check_docs.py']
    run=subprocess.run(argv,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (output/'source-docs.txt').write_bytes(run.stdout)
    commands.append({'argv':argv,'exit_code':run.returncode,'log':'source-docs.txt','log_sha256':sha(run.stdout)})
    run=subprocess.run(['git','diff','--check'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (output/'diff-check.txt').write_bytes(run.stdout)
    commands.append({'argv':['git','diff','--check'],'exit_code':run.returncode,'log':'diff-check.txt','log_sha256':sha(run.stdout)})
    allowed={'publication/README.md',*(str(f.relative_to(ROOT)) for f in files),
             'publication/engine/preview.py','publication/engine/preview_audit.py',
             'publication/engine/source_model.py','publication/engine/filters/blocks.lua'}
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT).decode().splitlines()
    protected=[]
    for name in names:
        if name in allowed:continue
        old=subprocess.check_output(['git','cat-file','blob',BASE+':'+name],cwd=ROOT)
        current=(ROOT/name).read_bytes()
        protected.append({'path':name,'sha256':sha(old),'unchanged':current==old})
    old_dist={n for n in names if n.startswith('design/dist/')}
    current_dist={str(p.relative_to(ROOT)) for p in (ROOT/'design/dist').rglob('*') if p.is_file()}
    result={'status':'LOCAL_CHECKS','base':BASE,'platform':platform.platform(),'python':sys.version,
            'commands':commands,'checked_inputs':before,'inputs_unchanged_during_checks':all(sha((ROOT/n).read_bytes())==h for n,h in before.items()),
            'protected_files':protected,'dist_complete_file_set_equal':old_dist==current_dist,
            'cpp_execution':'NOT RUN','performance':'NOT RUN','concurrency_dynamic':'NOT RUN','ci':'NOT CLAIMED'}
    (output/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    assert all(c['exit_code']==0 for c in commands)
    assert result['inputs_unchanged_during_checks'] and all(p['unchanged'] for p in protected)
    assert result['dist_complete_file_set_equal']
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
