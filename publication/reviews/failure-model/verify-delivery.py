#!/usr/bin/env python3
"""Read-only delivered-hash, new Markdown link, and historical artifact check."""
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote,urlsplit

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
RELEASE=ROOT/'publication/releases/cpp-failure-model/v1.0.0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def walk(value):
    if isinstance(value,dict):
        yield value
        for v in value.values():yield from walk(v)
    elif isinstance(value,list):
        for v in value:yield from walk(v)

def main():
    assets=RELEASE/'output/pdf';manifest=load(assets/'release-manifest.json')
    for line in (assets/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);assert sha(assets/name)==digest
    assert manifest['pdf']['sha256']==sha(assets/manifest['pdf']['filename'])
    assert manifest['status']=='PUBLICATION_CANDIDATE' and not manifest['formal_release'] and not manifest['publish_authorized']
    for path,key in [('candidate-manifest.json','candidate_manifest_sha256'),('preview-audit.json','preview_audit_sha256'),
                     ('fm-review/audit.json','structural_audit_sha256'),('visual-inspection.json','visual_inspection_sha256')]:
        assert sha(RELEASE/'evidence'/path)==manifest[key]
    for item in load(RELEASE/'evidence/export.json')['exported']:
        assert sha(RELEASE/'evidence'/item['path'])==item['sha256']
    assert manifest['reader_evidence']==load(HERE/'reader-evidence.json')
    checks=load(HERE/'checks-final/checks.json');assert sha(HERE/'checks-final/checks.json')==manifest['local_checks']['sha256']
    assert all(c['exit_code']==0 for c in checks['commands']) and checks['inputs_unchanged_during_checks']
    for item in checks['protected_files']:assert item['unchanged'] and sha(ROOT/item['path'])==item['sha256']
    for name,digest in checks['checked_inputs'].items():assert sha(ROOT/name)==digest
    for command in checks['commands']:assert sha(HERE/'checks-final'/command['log'])==command['log_sha256']
    tests=sum(int(re.search(r'Ran (\d+) tests',p.read_text())[1]) for p in (HERE/'checks-final').glob('test-*.txt'))
    assert tests==121
    paths=[ROOT/'publication/README.md',HERE/'README.md',RELEASE/'README.md',RELEASE/'release-notes.md',assets/'RELEASE-NOTES.md']
    links=0
    for path in paths:
        ast=json.loads(subprocess.check_output(['pandoc','-f','gfm','-t','json',str(path)]))
        for node in walk(ast):
            if node.get('t') not in ('Link','Image'):continue
            url=urlsplit(node['c'][-1][0])
            if url.scheme or url.netloc:continue
            target=(path.parent/unquote(url.path)).resolve() if url.path else path
            assert target.exists(),(path,node['c'][-1][0]);links+=1
            if url.fragment and target.suffix=='.md':
                other=json.loads(subprocess.check_output(['pandoc','-f','gfm','-t','json',str(target)]))
                anchors={n['c'][1][0] for n in walk(other) if n.get('t')=='Header'}|set(re.findall(r'<a id="([^"]+)"',target.read_text()))
                assert unquote(url.fragment) in anchors
    subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
    print(json.dumps({'status':'PASS','pdf_sha256':manifest['pdf']['sha256'],'tests':tests,'new_and_updated_markdown_files':len(paths),
        'local_links':links,'protected_files':len(checks['protected_files']),'release':'NOT RELEASED'},ensure_ascii=False))
if __name__=='__main__':main()
