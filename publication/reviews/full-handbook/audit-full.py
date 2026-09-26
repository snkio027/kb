#!/usr/bin/env python3
"""Bind full-book structure, source links and representative pages to final bytes.

These are bounded checks and sample selection, never visual approval.
"""
import argparse
import hashlib
import json
import posixpath
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[3]


def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main(attempt):
    ready=load(attempt/'preview-result.json');assert ready['status']=='PREVIEW_READY'
    work=attempt/'work';audit=load(work/'preview-audit.json')
    assert sha(work/'preview-audit.json')==ready['audit_sha256']
    view=audit['views'][0];assert len(audit['views'])==1
    pdf=work/view['pdf'];assert sha(pdf)==view['sha256']
    reader=PdfReader(pdf);names=reader.named_destinations
    catalog=load(work/'source-catalog.json')
    assert [d['source']['id'] for d in catalog]==[f'G{i}' for i in range(13)]
    by_path={d['source']['path']:d for d in catalog}
    by_id={d['source']['id']:d for d in catalog}
    folder=work/'typeset'/view['view']
    sections=load(folder/'section-audit.json')['sections']
    components=load(folder/'reading-components.json')
    references=load(folder/'reference-map.json')
    assert sum(c['kind']!='table' for c in components)==953
    assert sum(len(d['aliases']) for d in catalog)==1714
    assert sum(m['kind']=='lab' for d in catalog for m in d['semantic'])==30
    assert sum(m['kind']=='file' for d in catalog for m in d['semantic'])==68
    destinations=set();body_links=Counter();expected_links=Counter()
    chapter_starts=[(next(s['start_page'] for s in sections if s['document']==d['source']['id']),d['source']['id']) for d in catalog]
    for number,page in enumerate(reader.pages,1):
        owner=next((ident for start,ident in reversed(chapter_starts) if number>=start),None)
        for annotation in page.get('/Annots',[]):
            annotation=annotation.get_object()
            target=annotation.get('/Dest') or annotation.get('/A',{}).get('/D')
            if isinstance(target,str):
                destinations.add(target)
                if owner:body_links[(owner,target)]+=1
    cross=internal=0
    for entry in references:
        if entry['kind']!='SAME_VIEW_INTERNAL':continue
        source=by_id[entry['from']]['source']['path'];uri=urlsplit(entry['source'])
        target=posixpath.normpath(posixpath.join(posixpath.dirname(source),unquote(uri.path))) if uri.path else source
        doc=by_path[target];fragment=unquote(uri.fragment)
        expected=(doc['anchors'].get(fragment) or doc['anchors'].get(doc['aliases'].get(fragment))) if fragment else next(iter(doc['anchors'].values()))
        assert expected and entry['target']=='#'+expected and expected in destinations
        expected_links[(entry['from'],expected)]+=1
        internal+=1;cross+=source!=target
    # Cover/TOC links must not stand in for missing body links. Require all
    # source-link occurrences in the owning chapter, including repeated links.
    assert not (expected_links-body_links),dict(expected_links-body_links)
    def page(anchor):return reader.get_destination_page_number(names[anchor])+1
    def position(anchor):return (page(anchor),float(names[anchor]['/Top']))
    for doc in catalog:
        for alias,heading in doc['aliases'].items():
            assert position(alias)==position(doc['anchors'][heading])
    chapters=[];fixtures=[]
    def fixture(identity,purpose,anchors):
        pages=sorted(set(page(a) for a in anchors))
        fixtures.append({'id':identity,'purpose':purpose,'anchors':anchors,'pages':pages})
    for doc in catalog:
        ident=doc['source']['id'];own=[s for s in sections if s['document']==ident]
        chapters.append({'id':ident,'title':doc['metadata']['title'],'first_page':own[0]['start_page'],
                         'last_page':None,
                         'sections':len(own),'version':doc['source']['version']})
        fixture(ident+'-opening','chapter-navigation',[own[0]['anchor']])
        labs=[c for c in components if c['kind']=='experiment' and c['id'].startswith(ident+'-')]
        if labs:
            longest=max(labs,key=lambda c:c['lines'])
            fixture(ident+'-long-experiment','experiment-continuation',
                    [longest['id']+'-L1',longest['id']+'-L'+str(max(1,longest['lines']//2)),longest['id']+'-L'+str(longest['lines'])])
        else:
            fixture(ident+'-review-protocol','source-section',[own[len(own)//2]['anchor']])
        if ident in ('G0','G2','G3','G4','G9','G12'):
            gate=next(s for s in own if 'Final Gate' in s['title'])
            fixture(ident+'-gate','final-gate',[gate['anchor']])
    danger=next(c for c in components if c.get('caption')=='G7-D3 · main.cpp')
    fixture('G7-danger','danger-role-binding',[danger['id']+'-role',danger['id']+'-L1'])
    danger=next(c for c in components if c.get('caption')=='G1-L2 · main.cpp')
    fixture('G1-danger','danger-role-binding',[danger['id']+'-role',danger['id']+'-L1'])
    for doc_id,title in [('G8','8.2'),('G9','5.1'),('G12','8. 编译期')]:
        section=next(s for s in sections if s['document']==doc_id and s['title'].startswith(title))
        fixture(doc_id+'-integration-boundary','literal-or-heading-integration',[section['anchor']])
    for i,chapter in enumerate(chapters):
        chapter['last_page']=chapters[i+1]['first_page']-1 if i+1<len(chapters) else len(reader.pages)
    fixtures.append({'id':'front-matter','purpose':'cover-control-toc','anchors':['generated-preface','generated-toc'],
                     'pages':[1,2,3,chapters[0]['first_page']-1]})
    fixtures.append({'id':'book-exit','purpose':'final-reference','anchors':[], 'pages':[len(reader.pages)]})
    target=work/'full-review';target.mkdir(exist_ok=False)
    selected=sorted({p for f in fixtures for p in f['pages']})
    renders=[]
    for n in selected:
        name=f'page-{n:03d}'
        subprocess.run(['pdftoppm','-f',str(n),'-l',str(n),'-r','120','-singlefile','-png',str(pdf),str(target/name)],check=True)
        renders.append({'page':n,'path':name+'.png','sha256':sha(target/(name+'.png'))})
    result={'status':'STRUCTURAL_PASS','visual_status':'NOT_REVIEWED','pdf':view['pdf'],'pdf_sha256':view['sha256'],
            'pages':len(reader.pages),'chapters':chapters,'explicit_aliases':1714,'code_blocks':953,
            'experiment_labs':30,'experiment_files':68,'internal_references_checked':internal,
            'cross_chapter_references_checked':cross,'source_sections_checked':len(sections),
            'body_internal_link_occurrences_checked':sum(expected_links.values()),
            'body_link_policy':'Per owning chapter + canonical destination + multiplicity; generated front-matter excluded. Not a click-by-click visual proof.',
            'top_level_bookmarks':view['top_level_bookmarks'],'fixtures':fixtures,'renders':renders,
            'policy':'Frozen visual mechanics; full-book integration and actual destination checks. External web reachability and C++ execution not tested.'}
    (target/'structure.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','pages','source_sections_checked','internal_references_checked','cross_chapter_references_checked','top_level_bookmarks')},ensure_ascii=False))
    print('representative images:',len(renders))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempt',type=Path)
    main(parser.parse_args().attempt.resolve())
