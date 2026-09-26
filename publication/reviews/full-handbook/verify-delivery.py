#!/usr/bin/env python3
"""Read-only byte, navigation-evidence and documentation verification."""
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import unquote,urlsplit
from pypdf import PdfReader

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]


def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    inventory=load(HERE/'inventory.json');out=HERE/'cpp-handbook-full'
    pdf=HERE/inventory['pdf'];assert sha(pdf)==inventory['sha256']
    reader=PdfReader(pdf);assert len(reader.pages)==inventory['pages'] and reader.outline
    manifest=load(out/'candidate-manifest.json')
    assert sha(out/'candidate-manifest.json')==load(out/'candidate-result.json')['manifest_sha256']
    files={f['path']:f for f in manifest['identity']['files']}
    for entry in load(out/'export.json')['exported']:
        p=out/entry['path'];assert sha(p)==entry['sha256'] and p.stat().st_size==entry['bytes']
        if entry['path'] in files:assert entry==files[entry['path']]
    for entry in load(out/'derived-export.json')['files']:
        p=out/entry['path'];assert sha(p)==entry['sha256'] and p.stat().st_size==entry['bytes']
    for attempt in load(HERE/'attempt-history.json')['attempts']:
        for key in ('worker_evidence','terminal_evidence'):
            if key in attempt:assert sha(HERE/attempt[key]['path'])==attempt[key]['sha256']
    for source in manifest['identity']['publication']['sources']:
        raw=subprocess.check_output(['git','cat-file','blob',source['commit']+':'+source['path']],cwd=ROOT)
        assert raw==(out/'output/source'/source['path']).read_bytes()==(ROOT/source['path']).read_bytes()
    for entry in load(out/'run.json')['identity']['inputs']:
        if entry['path'].startswith('publication/'):assert sha(ROOT/entry['path'])==entry['sha256']
    inspection=load(HERE/'visual-inspection.json')
    assert inspection==load(out/'reading-review.json')['visual_inspection']
    for entry in inspection['inspected_images']:assert sha(out/'full-review'/entry['path'])==entry['sha256']
    for path,digest in inspection['report_hashes'].items():assert sha(out/path)==digest
    checks=load(HERE/'delivery-checks/checks.json')
    assert checks['inputs_unchanged_during_checks']
    for entry in checks['commands']:
        assert entry['exit_code']==0 and sha(HERE/'delivery-checks'/entry['log'])==entry['sha256']
    for entry in checks['checked_inputs']:assert sha(ROOT/entry['path'])==entry['sha256']
    for entry in checks['protected_files']:assert entry['unchanged'] and sha(ROOT/entry['path'])==entry['base_sha256']
    expected={e['path'] for e in checks['protected_files'] if e['path'].startswith('design/dist/')}
    assert expected=={str(p.relative_to(ROOT)) for p in (ROOT/'design/dist').rglob('*') if p.is_file()}
    def walk(v):
        if isinstance(v,dict):
            yield v
            for child in v.values():yield from walk(child)
        elif isinstance(v,list):
            for child in v:yield from walk(child)
    links=0
    for path in (ROOT/'publication/README.md',HERE/'README.md'):
        ast=json.loads(subprocess.check_output(['pandoc','-f','gfm','-t','json',str(path)]))
        for node in walk(ast):
            if node.get('t')=='Link':
                target=urlsplit(node['c'][2][0])
                if target.scheme or not target.path:continue
                assert not target.fragment
                assert (path.parent/unquote(target.path)).exists();links+=1
    report=load(out/'full-review/structure.json')
    print(json.dumps({'pdfs':1,'pages':len(reader.pages),'sources':13,'hash_bindings':'MATCH',
                      'protected_files_unchanged':len(checks['protected_files']),
                      'inspected_images':len(inspection['inspected_images']),
                      'internal_references_checked':report['internal_references_checked'],
                      'cross_chapter_references_checked':report['cross_chapter_references_checked'],
                      'local_file_links_checked':links,'formal_release':False},indent=2))


if __name__=='__main__':main()
