#!/usr/bin/env python3
"""Freeze inspected RC1 bytes; export review evidence, never publish."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'publication/engine'))
import candidate
import pub

def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')

attempt=Path(sys.argv[1]).resolve();work=attempt/'work'
ready=load(attempt/'preview-result.json');assert ready['status']=='PREVIEW_READY'
inspection=load(HERE/'visual-inspection.json')
assert inspection['preview_attempt']==str(attempt.relative_to(ROOT))
assert list(ready['artifacts'].values())==[inspection['pdf_sha256']]
assert inspection['blockers']==[]
for item in inspection['inspected_images']:assert sha(work/item['path'])==item['sha256']
for name,digest in inspection['report_hashes'].items():assert sha(work/name)==digest
write(attempt/'reading-review.json',{'status':'VISUAL_REVIEWED_SELF_REVIEW_NOT_APPROVAL',
    'artifacts':ready['artifacts'],'audit_sha256':ready['audit_sha256'],'visual_inspection':inspection})
frozen=candidate.freeze(ROOT,str(attempt.relative_to(ROOT)),pub,'cpp-handbook-rc1')
folder=Path(frozen['path']);manifest=load(folder/'candidate-manifest.json')
assert sha(folder/'candidate-manifest.json')==load(folder/'candidate-result.json')['manifest_sha256']
for entry in manifest['identity']['files']:assert sha(folder/entry['path'])==entry['sha256']
selected={'run.json','result.json','preview-result.json','preview-audit.json','reading-review.json',
    'candidate-manifest.json','candidate-result.json','evidence/source-catalog.json'}
selected.update(f['path'] for f in manifest['identity']['files'] if f['path'].startswith('output/') or
    (f['path'].startswith('evidence/typeset/') and Path(f['path']).name in
    ('table-map.json','reference-map.json','section-audit.json','reading-components.json','audit.json')))
out=HERE/'candidate';out.mkdir(exist_ok=False)
exported=[]
for name in sorted(selected):
    target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(folder/name,target)
    exported.append({'path':name,'sha256':sha(target),'bytes':target.stat().st_size})
write(out/'export.json',{'role':'REVIEW_EXPORT_NOT_RELEASE_NOT_COMPLETE_CANDIDATE',
    'candidate':str(folder.relative_to(ROOT)),'candidate_id':manifest['candidate_id'],
    'all_candidate_file_hashes_verified':True,'exported':exported,
    'omitted':sorted(f['path'] for f in manifest['identity']['files'] if f['path'] not in selected)})
derived=set(inspection['report_hashes'])|{i['path'] for i in inspection['inspected_images']}
files=[]
for name in sorted(derived):
    target=out/'derived'/name;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(work/name,target)
    files.append({'path':str(target.relative_to(out)),'sha256':sha(target),'bytes':target.stat().st_size})
write(out/'derived-export.json',{'role':'DERIVED_REVIEW_NOT_CANDIDATE_PAYLOAD','files':files})
view=load(out/'preview-audit.json')['views'][0];pdf=out/view['pdf']
contract={'publication_id':'CPP-HANDBOOK','publication_version':'1.0.0','candidate_label':'RC1',
    'title':'Modern C++ 工程学习手册','english_title':'Modern C++ Engineering Handbook',
    'state':'READY_FOR_RELEASE_DECISION','formal_release':False,'publish_authorized':False,
    'content_baseline':'8f479deaf660533b2ad82e1f721eb41a363112b6',
    'visual_profile':'1c11c5940c05fe29c46c4500935d5efb673d46a7',
    'visual_acceptance':'ea2e613b97ddd8a146c7899e7ffde7e80c238e57',
    'accepted_preview':'eb7f5672d1128607d4f34fa34217aefa9ba99b33',
    'implementation_base':'f2880516ea8d71abb6e83f0d463308974e2ae7ca',
    'implementation_identity':'candidate/run.json contains exact dirty input hashes; the review commit is external, not a self hash',
    'candidate_id':manifest['candidate_id'],'pdf':str(pdf.relative_to(HERE)),
    'filename':pdf.name,'bytes':pdf.stat().st_size,'pages':view['pages'],'sha256':sha(pdf),
    'required_readers':['Preview / PDFKit','Chromium / PDFium'],
    'reader_evidence':'reader-smoke.md: Preview observed + Chromium user-reported normal; no claim of automated Chromium validation',
    'reserved_release_record':'publication/releases/cpp-handbook/v1.0.0/',
    'reserved_tag':'cpp-handbook-v1.0.0',
    'limitations':'Frozen visual non-blockers retained; no C++ rerun, CI, PDF/UA, cross-platform or final release claim'}
write(HERE/'release-manifest.json',contract)
with (HERE/'SHA256SUMS').open('x') as f:
    for p in (pdf,HERE/'release-manifest.json'):f.write(sha(p)+'  '+str(p.relative_to(HERE))+'\n')
print(json.dumps(contract,ensure_ascii=False))
