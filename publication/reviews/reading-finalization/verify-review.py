#!/usr/bin/env python3
"""Read-only review export verification, including frozen source and visual bindings."""
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit
from pypdf import PdfReader

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(path):return json.loads(path.read_bytes())


def main():
    count=pages=images=geometry_pages=classified_glyphs=fixture_bindings=0
    inspection=load(HERE/'visual-inspection.json')
    for product in load(HERE/'inventory.json'):
        folder=HERE/product['profile']
        manifest=load(folder/'candidate-manifest.json')
        ready=load(folder/'preview-result.json')
        assert sha((folder/'candidate-manifest.json').read_bytes())==load(folder/'candidate-result.json')['manifest_sha256']
        assert sha((folder/'preview-audit.json').read_bytes())==ready['audit_sha256']
        candidate_files={f['path']:f for f in manifest['identity']['files']}
        for f in load(folder/'export.json')['exported']:
            data=(folder/f['path']).read_bytes()
            assert len(data)==f['bytes'] and sha(data)==f['sha256']
            if f['path'] in candidate_files:assert f==candidate_files[f['path']]
        for f in load(folder/'derived-export.json')['files']:
            data=(folder/f['path']).read_bytes();assert len(data)==f['bytes'] and sha(data)==f['sha256']
            images+=f['path'].endswith('.png')
        review=load(folder/'reading-review.json')
        assert review['page_map_sha256']==sha((folder/'visual-regression/page-map.json').read_bytes())
        assert review['artifacts']==ready['artifacts'] and review['audit_sha256']==ready['audit_sha256']
        assert review['structural_status']=='STRUCTURAL_PASS'
        mapping=load(folder/'visual-regression/page-map.json')
        assert mapping['status']=='STRUCTURAL_PASS'
        assert mapping['corpus_sha256']==sha((ROOT/'publication/tools/reading-corpus.json').read_bytes())
        fixture_bindings+=len(mapping['fixtures'])
        geometry=load(folder/'visual-regression/geometry.json')
        disposition=load(folder/'visual-regression/geometry-disposition.json')
        assert disposition['raw_geometry_sha256']==sha((folder/'visual-regression/geometry.json').read_bytes())
        assert not disposition['unresolved']
        for view in geometry['views']:
            assert ready['artifacts'][view['pdf']]==view['sha256']
        geometry_pages+=geometry['pages_checked']
        classified_glyphs+=len(disposition['explained'])
        assert review['visual_inspection']==inspection['products'][product['profile']]
        for entry in review['visual_inspection']['inspected_images']:
            assert sha((folder/'visual-regression'/entry['path']).read_bytes())==entry['sha256']
        for source in manifest['identity']['publication']['sources']:
            raw=subprocess.check_output(['git','cat-file','blob',source['commit']+':'+source['path']],cwd=ROOT)
            assert raw==(folder/'output/source'/source['path']).read_bytes()
            assert sha(raw)==source['sha256']
            if product['profile']=='cpp-handbook':assert source['revision']=='8f479deaf660533b2ad82e1f721eb41a363112b6'
        for entry in load(folder/'run.json')['identity']['inputs']:
            if entry['path'].startswith('publication/'):
                assert sha((ROOT/entry['path']).read_bytes())==entry['sha256'],entry['path']
        for a in product['artifacts']:
            p=HERE/a['path'];assert sha(p.read_bytes())==a['sha256']
            r=PdfReader(p);assert len(r.pages)==a['pages'] and r.outline
            count+=1;pages+=len(r.pages)
    assert count==12
    assert geometry_pages==pages
    # Intermediate A/B images are evidence of component choices, not the final
    # candidate PDFs. Only the old A PDFs are part of this portable Git export.
    pairs=load(HERE/'component-ab/decisions.json')['pairs']
    for pair in pairs:
        for side in pair['sides']:
            assert sha((HERE/'component-ab'/side['image']).read_bytes())==side['image_sha256']
            if side['variant']=='A':assert sha((ROOT/side['pdf']).read_bytes())==side['pdf_sha256']
    checks=load(HERE/'final-checks/checks.json')
    for command in checks['commands']:
        assert command['exit_code']==0
        assert sha((HERE/'final-checks'/command['log']).read_bytes())==command['sha256']
    for entry in checks['protected_files']:
        assert entry['unchanged']
        assert sha((ROOT/entry['path']).read_bytes())==entry['base_sha256']
    dist_expected={p['path'] for p in checks['protected_files'] if p['path'].startswith('design/dist/')}
    dist_actual={str(p.relative_to(ROOT)) for p in (ROOT/'design/dist').rglob('*') if p.is_file()}
    assert dist_expected==dist_actual
    # Parse only maintained navigation, not immutable attached source snapshots.
    markdown=[ROOT/'publication/README.md',HERE/'README.md',HERE/'visual-profile.md']
    links=0
    def walk(value):
        if isinstance(value,dict):
            yield value
            for child in value.values():yield from walk(child)
        elif isinstance(value,list):
            for child in value:yield from walk(child)
    for path in markdown:
        ast=json.loads(subprocess.check_output(['pandoc','-f','gfm','-t','json',str(path)]))
        for node in walk(ast):
            if node.get('t')=='Link':
                target=urlsplit(node['c'][2][0])
                if target.scheme or not target.path:continue
                assert (path.parent/unquote(target.path)).exists(),(path,target.path)
                assert not target.fragment,'anchor checker not implemented; do not claim checked'
                links+=1
    json_files=list(HERE.rglob('*.json'))
    for path in json_files:load(path)
    assert sum(len(p['inspected_images']) for p in inspection['products'].values())==inspection['inspected_image_count']
    print(json.dumps({'artifacts':count,'pages':pages,'derived_images':images,'hash_bindings':'MATCH',
                      'source_snapshots':'UNCHANGED','inspected_images':inspection['inspected_image_count'],
                      'maintained_markdown_parsed':len(markdown),'local_links_checked':links,
                      'semantic_fixture_bindings':fixture_bindings,'component_ab_pairs':len(pairs),
                      'geometry_pages':geometry_pages,'classified_cjk_glyph_signals':classified_glyphs,
                      'unresolved_geometry_signals':0,'protected_files_unchanged':len(checks['protected_files']),
                      'json_files_parsed':len(json_files),'formal_release':False},indent=2))


if __name__=='__main__':main()
