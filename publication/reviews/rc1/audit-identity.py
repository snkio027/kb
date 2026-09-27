#!/usr/bin/env python3
"""Check new candidate identity and quantify navigation geometry against preview."""
import hashlib
import json
import sys
from pathlib import Path
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT/'publication/reviews/full-handbook/cpp-handbook-full/output/pdf/CPP-HANDBOOK-draft.pdf'
attempt=Path(sys.argv[1]).resolve()
ready=json.loads((attempt/'preview-result.json').read_bytes())
audit=json.loads((attempt/'work/preview-audit.json').read_bytes())
assert ready['status']=='PREVIEW_READY'
view=audit['views'][0]; pdf=attempt/'work'/view['pdf']
assert hashlib.sha256(pdf.read_bytes()).hexdigest()==view['sha256']
assert pdf.name=='Modern-Cpp-Engineering-Handbook-v1.0.0.pdf'
old,new=PdfReader(OLD),PdfReader(pdf)
assert len(old.pages)==len(new.pages)==407
assert new.metadata.title=='Modern C++ 工程学习手册'
assert new.metadata.subject=='CPP-HANDBOOK | v1.0.0 | RELEASE CANDIDATE RC1 | RELEASE_CANDIDATE'
assert 'PREVIEW' not in str(new.metadata) and 'DRAFT' not in str(new.metadata)
def positions(reader):
    return {k:[reader.get_destination_page_number(v)+1,float(v.get('/Top',0)),float(v.get('/Left',0))]
            for k,v in reader.named_destinations.items()}
a,b=positions(old),positions(new)
assert set(a)==set(b)
changes=[{'destination':k,'old':a[k],'new':b[k]} for k in a if a[k]!=b[k]]
# Identity changes may move generated front matter. Frozen body navigation
# must keep page and target position; this does not prove pixel equality.
body_changes=[c for c in changes if c['old'][0]>=12]
assert not body_changes, body_changes[:10]
for page in (0,1):
    value=new.pages[page].extract_text()
    assert 'RELEASE CANDIDATE RC1' in value and '1.0.0' in value
    assert 'candidate.1' not in value and 'PREVIEW' not in value
result={'status':'IDENTITY_AND_BODY_NAVIGATION_PASS','pdf_sha256':view['sha256'],
    'pages':len(new.pages),'metadata':dict(new.metadata),'named_destinations':len(b),
    'destination_set_equal':True,'body_destination_coordinates_equal':True,
    'generated_front_matter_coordinate_changes':changes,
    'old_pdf_sha256':hashlib.sha256(OLD.read_bytes()).hexdigest(),
    'limits':'No pixel-equivalence claim; source AST equality is separately tested. Per-page RC identity checked by engine. No C++ rerun.'}
target=attempt/'work/identity-audit.json'
with target.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items() if k!='generated_front_matter_coordinate_changes'},ensure_ascii=False))
