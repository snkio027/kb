#!/usr/bin/env python3
"""Compare final publication bytes to accepted RC1, excluding generated identity."""
import hashlib
import json
import re
import sys
from pathlib import Path
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[4]
OLD=ROOT/'publication/reviews/rc1/candidate/output/pdf/Modern-Cpp-Engineering-Handbook-v1.0.0.pdf'
attempt=Path(sys.argv[1]).resolve();work=attempt/'work'
ready=json.loads((attempt/'preview-result.json').read_bytes())
assert ready['status']=='PREVIEW_READY'
audit=json.loads((work/'preview-audit.json').read_bytes());view=audit['views'][0]
pdf=work/view['pdf']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(pdf)==view['sha256'] and sha(work/'preview-audit.json')==ready['audit_sha256']
old,new=PdfReader(OLD),PdfReader(pdf)
assert len(old.pages)==len(new.pages)==407
assert new.metadata.title=='Modern C++ 工程学习手册'
assert new.metadata.subject=='CPP-HANDBOOK | v1.0.0 | PUBLICATION EDITION | PUBLICATION'
assert not any(x in str(new.metadata) for x in ('RC1','CANDIDATE','PREVIEW','DRAFT'))
def positions(r):
    return {k:[r.get_destination_page_number(v)+1,float(v.get('/Top',0)),float(v.get('/Left',0))]
            for k,v in r.named_destinations.items()}
a,b=positions(old),positions(new);assert a.keys()==b.keys()
changes=[{'name':k,'old':a[k],'new':b[k]} for k in a if a[k]!=b[k]]
assert not [c for c in changes if c['old'][0]>=12],changes[:10]
def annotations(r):
    result=[]
    for page in r.pages:
        own=[]
        for ref in page.get('/Annots',[]):
            v=ref.get_object();action=v.get('/A',{})
            target=v.get('/Dest') or action.get('/D')
            # This product emits string named destinations and URI actions.
            assert target is None or isinstance(target,str)
            own.append({'rect':list(map(float,v['/Rect'])),'destination':target,
                        'uri':action.get('/URI'),'action':action.get('/S')})
        result.append(own)
    return result
assert annotations(old)==annotations(new),'changed link geometry/target'
def outline(r):
    def walk(items):
        return [walk(v) if isinstance(v,list) else [v.title,r.get_destination_page_number(v)] for v in items]
    return walk(r.outline)
assert outline(old)==outline(new)
def normalized(s):return re.sub(r'\s+','',s)
def strip_identity(s):
    s=normalized(s)
    for marker in ('RELEASE CANDIDATE RC1 · v1.0.0 · 尚未发布','PUBLICATION · v1.0.0 · 正式阅读版',
        '以下状态文字保留冻结 Markdown 当时的历史陈述。当前文件是后续生成的阅读试件，不改变该历史状态，也不表示正式发布获批。',
        '以下状态文字保留冻结 Markdown 当时的历史陈述，不是当前出版状态。正式版出版身份及批准范围以随附发布记录为准。'):
        s=s.replace(normalized(marker),'')
    return s
for n,(x,y) in enumerate(zip(old.pages,new.pages),1):
    text=y.extract_text()
    assert 'PUBLICATION' in text,('missing running identity',n)
    assert not any(marker in text for marker in ('RELEASE CANDIDATE RC1','尚未发布','尚未正式发布','当前文件是后续生成的阅读试件')),(n,text[-160:])
    if n>2:assert strip_identity(x.extract_text())==strip_identity(text),('non-identity text difference',n)
    else:assert 'PUBLICATION EDITION' in text and '1.0.0' in text
result={'status':'IDENTITY_CONTENT_NAVIGATION_PASS','pdf_sha256':sha(pdf),'rc1_sha256':sha(OLD),
    'pages':407,'metadata':dict(new.metadata),'named_destinations':len(b),
    'body_destination_coordinates_equal':True,'generated_coordinate_changes':changes,
    'link_annotations':sum(map(len,annotations(new))),'all_annotation_targets_and_rectangles_equal':True,
    'bookmark_tree_equal':True,'pages_3_to_407_extracted_text_equal_except_generated_identity':True,
    'generated_identity_exceptions':['running footer','source snapshot status note; formatting unchanged'],
    'limits':'Extraction is not pixel proof; first two pages and representative body pages require visual inspection. No new C++ or browser execution implied.'}
with (work/'publication-identity-audit.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(result,ensure_ascii=False))
