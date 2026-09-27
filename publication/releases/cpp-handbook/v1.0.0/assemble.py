#!/usr/bin/env python3
"""One-shot v1.0.0 package from inspected bytes; no compiler or network calls."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'publication/engine'))
import candidate
import pub
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
attempt=Path(sys.argv[1]).resolve();work=attempt/'work'
inspection=load(HERE/'visual-inspection.json');ready=load(attempt/'preview-result.json')
assert inspection['attempt']==str(attempt.relative_to(ROOT))
assert ready['status']=='PREVIEW_READY' and ready['artifacts']=={'output/pdf/Modern-Cpp-Engineering-Handbook-v1.0.0.pdf':inspection['pdf_sha256']}
assert inspection['status']=='VISUAL_REVIEWED' and not inspection['blockers']
for entry in inspection['images']:assert sha(work/entry['path'])==entry['sha256']
for name,digest in inspection['reports'].items():assert sha(work/name)==digest
checks=load(HERE/'checks-final/checks.json')
assert all(c['exit_code']==0 for c in checks['commands']) and checks['inputs_unchanged_during_checks']
assert all(v['unchanged'] for v in checks['protected_files']) and checks['dist_complete_file_set_equal']
for item in checks['checked_inputs']:assert sha(ROOT/item['path'])==item['sha256']
write(attempt/'reading-review.json',{'artifacts':ready['artifacts'],'audit_sha256':ready['audit_sha256'],
    'status':'VISUAL_REVIEWED_SELF_REVIEW','inspection':inspection})
frozen=candidate.freeze(ROOT,str(attempt.relative_to(ROOT)),pub,'cpp-handbook-v1')
folder=Path(frozen['path']);manifest=load(folder/'candidate-manifest.json')
for entry in manifest['identity']['files']:assert sha(folder/entry['path'])==entry['sha256']
assert sha(folder/'candidate-manifest.json')==load(folder/'candidate-result.json')['manifest_sha256']
evidence=HERE/'evidence';evidence.mkdir(exist_ok=False)
selected={'run.json','result.json','preview-result.json','preview-audit.json','reading-review.json',
    'candidate-manifest.json','candidate-result.json','evidence/source-catalog.json'}
selected.update(f['path'] for f in manifest['identity']['files'] if f['path'].startswith('evidence/typeset/') and
    Path(f['path']).name in ('table-map.json','reference-map.json','section-audit.json','reading-components.json','audit.json'))
exported=[]
for name in sorted(selected):
    target=evidence/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(folder/name,target)
    exported.append({'path':name,'sha256':sha(target),'bytes':target.stat().st_size})
derived=set(inspection['reports'])|{v['path'] for v in inspection['images']}
for name in sorted(derived):
    target=evidence/'derived'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(work/name,target)
    exported.append({'path':str(target.relative_to(evidence)),'sha256':sha(target),'bytes':target.stat().st_size})
assets=HERE/'output/pdf';assets.mkdir(parents=True,exist_ok=False)
pdf=assets/'Modern-Cpp-Engineering-Handbook-v1.0.0.pdf'
shutil.copyfile(folder/'output/pdf'/pdf.name,pdf);assert sha(pdf)==inspection['pdf_sha256']
write(evidence/'export.json',{'role':'SELECTED_EVIDENCE_EXPORT_NOT_COMPLETE_BUILD',
    'candidate_path':str(folder.relative_to(ROOT)),'candidate_id':manifest['candidate_id'],
    'all_local_candidate_file_hashes_verified':True,'exported':exported,
    'omitted_candidate_files':sorted(v['path'] for v in manifest['identity']['files'] if v['path'] not in selected and v['path']!='output/pdf/'+pdf.name)})
shutil.copyfile(HERE/'release-notes.md',assets/'RELEASE-NOTES.md')
contract={'publication_id':'CPP-HANDBOOK','publication_version':'1.0.0',
    'title':'Modern C++ 工程学习手册','english_title':'Modern C++ Engineering Handbook',
    'pdf':{'filename':pdf.name,'sha256':sha(pdf),'bytes':pdf.stat().st_size,'pages':407},
    'content_baseline':'8f479deaf660533b2ad82e1f721eb41a363112b6',
    'visual_profile':'1c11c5940c05fe29c46c4500935d5efb673d46a7',
    'visual_acceptance':'ea2e613b97ddd8a146c7899e7ffde7e80c238e57',
    'accepted_rc1_commit':'2f4caf671bc42e6e3b03a8eda8255e1a392e5798',
    'rc1_pdf_sha256':'c011cc4ecddcb20892b0753539356af42c8b2eb636dd2b40b9934bab5af98d0c',
    'build_base_commit':'2f4caf671bc42e6e3b03a8eda8255e1a392e5798',
    'build_identity':'Exact working inputs and tools bound by run.json and preview-audit.json; not the base commit alone.',
    'preparation_id':manifest['identity']['preparation_id'],'execution_id':manifest['identity']['execution_id'],
    'frozen_payload_id':manifest['candidate_id'],
    'candidate_manifest_sha256':sha(evidence/'candidate-manifest.json'),
    'preview_audit_sha256':sha(evidence/'preview-audit.json'),
    'evidence_export_sha256':sha(evidence/'export.json'),
    'qualification_report_sha256':sha(HERE/'checks-final/checks.json'),
    'visual_inspection_sha256':sha(HERE/'visual-inspection.json'),
    'reader_record_sha256':sha(HERE/'reader-smoke.md'),
    'authorization':{'source':'User approval in this conversation on 2026-09-27',
        'scope':'Identity-only correction, new-byte checks, direct GitHub Release under cpp-handbook-v1.0.0 without further step approvals; content/layout/history unchanged.'},
    'destination':{'repository':'snkio027/kb','tag':'cpp-handbook-v1.0.0',
        'release_url':'https://github.com/snkio027/kb/releases/tag/cpp-handbook-v1.0.0'},
    'distribution_status':'See GitHub published state and repository publication-receipt.json; packaging is not proof of upload.',
    'reader_evidence':load(HERE/'reader-evidence.json'),
    'known_limitations':['Accepted TOC/Gate whitespace, occasional label positions, long-code wraps and chapter-ending rhythm remain.',
        'Source historical status text preserved; publication identity is separate.',
        'No C++/performance/concurrency rerun, no CI, PDF/UA or cross-platform certification.']}
write(assets/'release-manifest.json',contract)
with (assets/'SHA256SUMS').open('x') as f:
    for path in (pdf,assets/'release-manifest.json',assets/'RELEASE-NOTES.md'):f.write(sha(path)+'  '+path.name+'\n')
print(json.dumps({'pdf_sha256':sha(pdf),'bytes':pdf.stat().st_size,'candidate_id':manifest['candidate_id'],
    'assets':str(assets.relative_to(ROOT))},ensure_ascii=False))
