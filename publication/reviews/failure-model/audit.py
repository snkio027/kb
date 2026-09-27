#!/usr/bin/env python3
"""FM whole-book fidelity, block destinations, body annotations and page fixtures.

Machine signals are not visual acceptance or a C++ technical rerun.
"""
import collections
import hashlib
import importlib.util
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote,urlsplit
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'publication/engine'))
import preview
import preview_audit
spec=importlib.util.spec_from_file_location('reading_signals',ROOT/'publication/tools/reading-review.py')
signals=importlib.util.module_from_spec(spec);spec.loader.exec_module(signals)
BASE='45b305eace0f057420587d685cb3f962f3f0552c'
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(attempt):
    ready=load(attempt/'preview-result.json');assert ready['status']=='PREVIEW_READY'
    work=attempt/'work';assert sha(work/'preview-audit.json')==ready['audit_sha256']
    audit=load(work/'preview-audit.json');view,=audit['views'];pdf=work/view['pdf']
    assert sha(pdf)==view['sha256']
    reader=PdfReader(pdf);names=reader.named_destinations
    pages=preview_audit.pdf_fragments(reader)
    texts=[p.extract_text() for p in reader.pages]
    catalog=load(work/'source-catalog.json')
    assert [d['source']['id'] for d in catalog]==['FM-GUIDE']+[f'FM-{n}' for n in range(10)]
    folder=work/'typeset'/view['view']
    sections=load(folder/'section-audit.json')['sections']
    components=load(folder/'reading-components.json')
    refs=load(folder/'reference-map.json')
    issues=[];fixtures=[];target_checks=[];source_checks=[]
    def position(key):
        d=names[key];return reader.get_destination_page_number(d)+1,float(d['/Top'])
    def fixture(identity,purpose,keys):
        fixtures.append({'id':identity,'purpose':purpose,'targets':keys,'pages':sorted({position(k)[0] for k in keys})})
    for doc in catalog:
        source=doc['source'];ident=source['id'];assert source['commit']==BASE
        raw=subprocess.check_output(['git','cat-file','blob',BASE+':'+source['path']],cwd=ROOT)
        assert raw==(work/'output/source'/source['path']).read_bytes()==(ROOT/source['path']).read_bytes()
        parsed=json.loads(subprocess.check_output(['pandoc','-f','gfm','-t','json'],input=raw))
        adapted=load(work/'source-ast'/f'{ident}.json')
        codes=lambda a:[n['c'][1] for n in preview.walk(a['blocks']) if n.get('t')=='CodeBlock']
        assert codes(parsed)==codes(adapted)
        original_targets=re.findall(r'<a id="([^"]+)"></a>',raw.decode())
        explicit=[s for s in doc['semantic'] if s['kind']=='source-target']
        assert original_targets==[s['id'] for s in explicit]
        source_checks.append({'id':ident,'path':source['path'],'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'fenced_blocks':len(codes(parsed)),'explicit_anchors':len(explicit),'byte_exact':True})
        own=[s for s in sections if s['document']==ident]
        fixture(ident+'-opening','chapter-navigation',[own[0]['anchor']])
        for entry in explicit:
            key=doc['anchors'][entry['id']];start=preview_audit.destination_position(reader,key,names)
            _,region,_=preview_audit.window(pages,start,(start[0]+1,0),(),preview.normalize)
            expected=preview.normalize(entry['target_text'])
            # Point at the actual block, not merely somewhere in its chapter.
            match=region.startswith(expected[:100])
            target_checks.append({'document':ident,'source_id':entry['id'],'pdf_target':key,
                'page':start[0]+1,'kind':entry['target_type'],'starts_with_source_block':match})
            if not match:issues.append({'target':key,'signal':'block_target_position','expected':entry['target_text']})
        if ident=='FM-GUIDE':fixture('failure-contract','contract-field-relations',[doc['anchors']['review-contract']])
    body_links=collections.Counter();expected_links=collections.Counter()
    starts=[(next(s['start_page'] for s in sections if s['document']==d['source']['id']),d['source']['id']) for d in catalog]
    byid={d['source']['id']:d for d in catalog};bypath={d['source']['path']:d for d in catalog}
    for number,page in enumerate(reader.pages,1):
        owner=next((i for start,i in reversed(starts) if start<=number),None)
        for ref in page.get('/Annots',[]):
            a=ref.get_object();target=a.get('/Dest') or a.get('/A',{}).get('/D')
            if isinstance(target,str) and owner:body_links[(owner,target)]+=1
    cross=0
    for entry in refs:
        if entry['kind']!='SAME_VIEW_INTERNAL':continue
        src=byid[entry['from']]['source']['path'];u=urlsplit(entry['source'])
        dst=posixpath.normpath(posixpath.join(posixpath.dirname(src),unquote(u.path))) if u.path else src
        doc=bypath[dst];fragment=unquote(u.fragment)
        target=doc['anchors'][fragment] if fragment else next(iter(doc['anchors'].values()))
        assert entry['target']=='#'+target and target in names
        expected_links[(entry['from'],target)]+=1;cross+=src!=dst
    assert not expected_links-body_links,dict(expected_links-body_links)
    for c in components:
        if c['kind']=='table':
            if c['keep_together'] and position(c['id']+'-start')[0]!=position(c['id']+'-end')[0]:
                issues.append({'object':c['id'],'signal':'short_table_split'})
            continue
        pos=[position(c['id']+'-L'+str(n)) for n in range(1,c['lines']+1)]
        found,groups=signals.code_signals(c,pos)
        if c.get('source_label'):
            found+=signals.identity_signals(c,pos,position(c['id']+'-role'),texts)
            fixture(c['id']+'-role','explicit-negative-example-binding',[c['id']+'-role',c['id']+'-L1'])
        if c['kind']=='experiment':
            for page in groups:
                if preview.normalize(c['caption']) not in preview.normalize(texts[page-1]):found.append('missing_experiment_identity')
            fixture(c['id']+'-experiment','experiment-continuation',[c['id']+'-L1',c['id']+'-L'+str(c['lines'])])
        issues.extend({'object':c['id'],'signal':f} for f in found)
        if c['id'].startswith('FM-9-') and c['lines']>=30:
            fixture(c['id']+'-template','literal-template-identity-and-continuation',[c['id']+'-L1',c['id']+'-L'+str(c['lines'])])
    fixtures.append({'id':'front-and-exit','purpose':'cover-control-toc-last','targets':[],
                     'pages':[1,2,3,starts[0][0]-1,len(reader.pages)]})
    out=work/'fm-review';out.mkdir(exist_ok=False)
    renders=[]
    for n in sorted({p for f in fixtures for p in f['pages']}):
        image=out/f'page-{n:03}'
        subprocess.run(['pdftoppm','-f',str(n),'-l',str(n),'-r','110','-singlefile','-png',str(pdf),str(image)],check=True)
        path=image.with_suffix('.png');renders.append({'page':n,'path':str(path.relative_to(work)),'sha256':sha(path)})
    result={'status':'STRUCTURAL_PASS' if not issues else 'REVIEW_REQUIRED','visual_status':'NOT_REVIEWED',
        'pdf':view['pdf'],'pdf_sha256':view['sha256'],'pages':len(reader.pages),'source_checks':source_checks,
        'source_target_checks':target_checks,'body_link_occurrences_checked':sum(expected_links.values()),
        'cross_chapter_references_checked':cross,'body_link_policy':'Owning chapter + target + multiplicity; TOC excluded, not click-by-click UI testing.',
        'source_sections_checked':len(sections),'fenced_blocks':sum(s['fenced_blocks'] for s in source_checks),
        'cpp_blocks':215,'explicit_targets':len(target_checks),'fixtures':fixtures,'images':renders,'issues':issues,
        'limitations':['No C++/performance/TSan rerun.','Dynamic PDF reader smoke is separate.','Text normalization is not a proof of code indentation or visual meaning.']}
    (out/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','pages','fenced_blocks','explicit_targets','body_link_occurrences_checked','cross_chapter_references_checked','issues')},ensure_ascii=False))
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
