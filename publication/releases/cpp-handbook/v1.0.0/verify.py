#!/usr/bin/env python3
"""Read-only package/protected-scope check, optionally against downloaded assets."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from pypdf import PdfReader

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
ASSETS=HERE/'output/pdf'
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
contract=load(ASSETS/'release-manifest.json');pdf=ASSETS/contract['pdf']['filename']
assert sha(pdf)==contract['pdf']['sha256'] and pdf.stat().st_size==contract['pdf']['bytes']
reader=PdfReader(pdf);assert len(reader.pages)==407
assert reader.metadata.subject=='CPP-HANDBOOK | v1.0.0 | PUBLICATION EDITION | PUBLICATION'
for name in ('output/pdf/release-manifest.json','evidence/export.json','checks-final/checks.json','visual-inspection.json','reader-evidence.json'):
    load(HERE/name)
assert sha(HERE/'evidence/export.json')==contract['evidence_export_sha256']
assert sha(HERE/'evidence/candidate-manifest.json')==contract['candidate_manifest_sha256']
assert sha(HERE/'evidence/preview-audit.json')==contract['preview_audit_sha256']
assert sha(HERE/'checks-final/checks.json')==contract['qualification_report_sha256']
assert sha(HERE/'visual-inspection.json')==contract['visual_inspection_sha256']
assert sha(HERE/'reader-smoke.md')==contract['reader_record_sha256']
assert load(HERE/'reader-evidence.json')==contract['reader_evidence']
for item in load(HERE/'evidence/export.json')['exported']:
    assert sha(HERE/'evidence'/item['path'])==item['sha256'],item['path']
checks=load(HERE/'checks-final/checks.json')
assert all(c['exit_code']==0 for c in checks['commands']) and checks['inputs_unchanged_during_checks']
for c in checks['commands']:assert sha(HERE/'checks-final'/c['log'])==c['sha256']
for item in checks['checked_inputs']:assert sha(ROOT/item['path'])==item['sha256'],item['path']
for item in checks['protected_files']:assert item['unchanged'] and sha(ROOT/item['path'])==item['base_sha256'],item['path']
assert {p['path'] for p in checks['protected_files'] if p['path'].startswith('design/dist/')}=={str(p.relative_to(ROOT)) for p in (ROOT/'design/dist').rglob('*') if p.is_file()}
run=load(HERE/'evidence/run.json')
for source in run['identity']['publication']['sources']:
    assert source['commit']==contract['content_baseline']
    raw=subprocess.check_output(['git','show',source['commit']+':'+source['path']],cwd=ROOT)
    assert hashlib.sha256(raw).hexdigest()==source['sha256']
checksums=(ASSETS/'SHA256SUMS').read_text().splitlines()
for line in checksums:
    digest,name=line.split('  ',1);assert sha(ASSETS/name)==digest
if len(sys.argv)>1:
    download=Path(sys.argv[1])
    expected={p.name for p in ASSETS.iterdir() if p.is_file()}
    assert {p.name for p in download.iterdir() if p.is_file()}==expected
    for name in expected:assert sha(download/name)==sha(ASSETS/name),name
print(json.dumps({'status':'PACKAGE_AND_SCOPE_PASS','pdf_sha256':sha(pdf),'pages':407,
    'protected_files':len(checks['protected_files']),'downloaded_assets_compared':len(sys.argv)>1,
    'meaning':'Local integrity/evidence checks, not independent approval or proof of GitHub published state.'}))
