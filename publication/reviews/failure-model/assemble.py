#!/usr/bin/env python3
"""Export checked FM candidate bytes for review; never tag, upload or publish."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
RELEASE=ROOT/'publication/releases/cpp-failure-model/v1.0.0'
BASE='45b305eace0f057420587d685cb3f962f3f0552c'
sys.path.insert(0,str(ROOT/'publication/engine'))
import candidate
import pub
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,value):
    with p.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def main(attempt):
    work=attempt/'work';ready=load(attempt/'preview-result.json')
    inspection=load(HERE/'visual-inspection.json');review=load(work/'fm-review/audit.json')
    assert ready['status']=='PREVIEW_READY'
    assert inspection['attempt']==str(attempt.relative_to(ROOT))
    assert inspection['status']=='VISUAL_REVIEWED' and not inspection['blockers']
    assert review['status']=='STRUCTURAL_PASS' and not review['issues']
    pdfname='Modern-Cpp-Failure-Semantics-Handbook-v1.0.0.pdf'
    assert ready['artifacts']=={'output/pdf/'+pdfname:inspection['pdf_sha256']}
    assert review['pdf_sha256']==inspection['pdf_sha256']
    for item in inspection['images']:assert sha(work/item['path'])==item['sha256']
    checks=load(HERE/'checks-final/checks.json')
    assert all(c['exit_code']==0 for c in checks['commands'])
    assert checks['inputs_unchanged_during_checks'] and checks['dist_complete_file_set_equal']
    assert all(p['unchanged'] for p in checks['protected_files'])
    for name,digest in checks['checked_inputs'].items():assert sha(ROOT/name)==digest
    write(attempt/'reading-review.json',{'artifacts':ready['artifacts'],'audit_sha256':ready['audit_sha256'],
        'status':'VISUAL_REVIEWED_SELF_REVIEW','inspection':inspection,
        'fm_audit_sha256':sha(work/'fm-review/audit.json')})
    frozen=candidate.freeze(ROOT,str(attempt.relative_to(ROOT)),pub,'cpp-failure-model')
    folder=Path(frozen['path']);manifest=load(folder/'candidate-manifest.json')
    for item in manifest['identity']['files']:assert sha(folder/item['path'])==item['sha256']
    assert sha(folder/'candidate-manifest.json')==load(folder/'candidate-result.json')['manifest_sha256']
    output=RELEASE/'output/pdf';output.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(folder/'output/pdf'/pdfname,output/pdfname)
    evidence=RELEASE/'evidence';evidence.mkdir(exist_ok=False)
    selected={'run.json','result.json','preview-result.json','preview-audit.json','reading-review.json',
              'candidate-manifest.json','candidate-result.json','evidence/source-catalog.json'}
    selected.update(i['path'] for i in manifest['identity']['files'] if i['path'].startswith('evidence/typeset/') and
        Path(i['path']).name in ('table-map.json','reference-map.json','section-audit.json','reading-components.json','audit.json'))
    exported=[]
    def export(source,relative):
        target=evidence/relative;target.parent.mkdir(parents=True,exist_ok=True)
        assert not target.exists();shutil.copyfile(source,target)
        exported.append({'path':relative,'bytes':target.stat().st_size,'sha256':sha(target)})
    for name in sorted(selected):export(folder/name,name)
    for p in sorted((work/'fm-review').iterdir()):export(p,'fm-review/'+p.name)
    export(HERE/'visual-inspection.json','visual-inspection.json')
    export(HERE/'reader-evidence.json','reader-evidence.json')
    rendered=[{'path':str(p.relative_to(work)),'sha256':sha(p)} for p in sorted((work/'renders/CPP-FAILURE-MODEL').glob('page-*.png'))]
    assert len(rendered)==review['pages']
    write(evidence/'all-page-render-inventory.json',rendered)
    history=[]
    for path in sorted((ROOT/'publication/build/preview').glob('*/*/run.json')):
        run=load(path)
        if run['identity'].get('publication',{}).get('profile')!='cpp-failure-model':continue
        terminal=path.with_name('preview-result.json')
        history.append({'attempt':str(path.parent.relative_to(ROOT)),'preparation_id':run['build_id'],
            'result':load(terminal) if terminal.exists() else 'NO_TERMINAL',
            'selected':path.parent==attempt})
    write(evidence/'attempt-history.json',history)
    historical=[]
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'--','c++/failure-model/review'],cwd=ROOT).decode().splitlines()
    for name in names:
        raw=subprocess.check_output(['git','cat-file','blob',BASE+':'+name],cwd=ROOT)
        assert raw==(ROOT/name).read_bytes()
        historical.append({'path':name,'commit':BASE,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'role':'HISTORICAL_TECHNICAL_EVIDENCE_NOT_RERUN_NOT_BOOK_BODY'})
    write(evidence/'historical-technical-evidence.json',historical)
    write(evidence/'export.json',{'role':'SELECTED_EVIDENCE_EXPORT_NOT_FULL_BUILD','candidate_id':manifest['candidate_id'],
        'candidate_path':str(folder.relative_to(ROOT)),'exported':exported,
        'omitted_candidate_files':[i['path'] for i in manifest['identity']['files'] if i['path'] not in selected and i['path']!='output/pdf/'+pdfname]})
    shutil.copyfile(RELEASE/'release-notes.md',output/'RELEASE-NOTES.md')
    contract={'publication_id':'CPP-FAILURE-MODEL','publication_version':'1.0.0',
        'title':'C++23 失败语义工程手册','english_title':'Modern C++ Failure Semantics Handbook',
        'status':'PUBLICATION_CANDIDATE','formal_release':False,'publish_authorized':False,
        'content_baseline':BASE,'content_role':'ACCEPTED / FM SERIES REVIEW CLOSED',
        'visual_profile':'v1.0 / 1c11c5940c05fe29c46c4500935d5efb673d46a7',
        'visual_acceptance':'ea2e613b97ddd8a146c7899e7ffde7e80c238e57',
        'pdf':{'filename':pdfname,'sha256':sha(output/pdfname),'bytes':(output/pdfname).stat().st_size,'pages':review['pages']},
        'sources':review['source_checks'],'preparation_id':manifest['identity']['preparation_id'],
        'execution_id':manifest['identity']['execution_id'],'candidate_id':manifest['candidate_id'],
        'build_binding':'Actual captured source, profile, engine, tools and fonts; not HEAD alone. No cross-machine deterministic-build claim.',
        'candidate_manifest_sha256':sha(evidence/'candidate-manifest.json'),
        'preview_audit_sha256':sha(evidence/'preview-audit.json'),
        'structural_audit_sha256':sha(evidence/'fm-review/audit.json'),
        'visual_inspection_sha256':sha(evidence/'visual-inspection.json'),
        'reader_evidence':load(HERE/'reader-evidence.json'),
        'local_checks':{'path':'publication/reviews/failure-model/checks-final/checks.json','sha256':sha(HERE/'checks-final/checks.json')},
        'technical_evidence':'Historical only; no C++ compilation, performance or concurrency rerun',
        'proposed_distribution':{'repository':'snkio027/kb','tag':'cpp-failure-model-v1.0.0','tag_created':False,'github_release_created':False},
        'remaining_gate':'Centralized candidate review and explicit final publish authorization; retain reader qualification limits.',
        'known_limitations':inspection['known_nonblocking_visual_limitations']+['Preview partial; Chrome user-reported pass without version detail.','No PDF/UA, CI or cross-platform certification.']}
    write(output/'release-manifest.json',contract)
    with (output/'SHA256SUMS').open('x') as f:
        for name in (pdfname,'release-manifest.json','RELEASE-NOTES.md'):f.write(sha(output/name)+'  '+name+'\n')
    print(json.dumps({'candidate_id':manifest['candidate_id'],'sha256':sha(output/pdfname),'pages':review['pages'],'status':'PUBLICATION_CANDIDATE_NOT_RELEASED'}))
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
