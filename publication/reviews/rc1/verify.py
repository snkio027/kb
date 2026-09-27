#!/usr/bin/env python3
"""Read-only verification of RC1 delivery; does not compile, approve or publish."""
import hashlib
import json
import subprocess
from pathlib import Path
from pypdf import PdfReader

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
contract=load(HERE/'release-manifest.json');out=HERE/'candidate'
assert contract['formal_release'] is False and contract['publish_authorized'] is False
pdf=HERE/contract['pdf'];assert sha(pdf)==contract['sha256']
assert pdf.stat().st_size==contract['bytes']
reader=PdfReader(pdf);assert len(reader.pages)==contract['pages']==407
assert reader.metadata.subject=='CPP-HANDBOOK | v1.0.0 | RELEASE CANDIDATE RC1 | RELEASE_CANDIDATE'
for line in (HERE/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1);assert sha(HERE/name)==digest,name
for entry in load(out/'export.json')['exported']+load(out/'derived-export.json')['files']:
    assert sha(out/entry['path'])==entry['sha256'],entry['path']
assert sha(out/'candidate-manifest.json')==load(out/'candidate-result.json')['manifest_sha256']
manifest=load(out/'candidate-manifest.json')
assert manifest['candidate_id']==contract['candidate_id']
assert load(out/'preview-result.json')['audit_sha256']==sha(out/'preview-audit.json')
assert load(out/'preview-result.json')['artifacts']=={'output/pdf/'+pdf.name:contract['sha256']}
for source in manifest['identity']['publication']['sources']:
    assert source['commit']==source['revision']==contract['content_baseline']
    raw=subprocess.check_output(['git','cat-file','blob',source['commit']+':'+source['path']],cwd=ROOT)
    assert (out/'output/source'/source['path']).read_bytes()==raw
checks=load(HERE/'checks/checks.json')
assert all(c['exit_code']==0 for c in checks['commands'])
assert checks['inputs_unchanged_during_checks'] and checks['dist_complete_file_set_equal']
for c in checks['commands']:assert sha(HERE/'checks'/c['log'])==c['sha256']
for p in checks['checked_inputs']:assert sha(ROOT/p['path'])==p['sha256'],p['path']
for p in checks['protected_files']:
    assert p['unchanged'] and sha(ROOT/p['path'])==p['base_sha256'],p['path']
expected={p['path'] for p in checks['protected_files'] if p['path'].startswith('design/dist/')}
assert expected=={str(p.relative_to(ROOT)) for p in (ROOT/'design/dist').rglob('*') if p.is_file()}
print(json.dumps({'status':'DELIVERY_HASH_AND_SCOPE_PASS','pages':len(reader.pages),
    'protected_files':len(checks['protected_files']),'pdf_sha256':contract['sha256'],
    'reader_evidence':'See reader-smoke.md; not independently re-executed by this checker',
    'formal_release':False},ensure_ascii=False))
