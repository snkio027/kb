#!/usr/bin/env python3
"""Freeze existing full-book bytes with the unchanged v2 candidate path."""
import argparse
import hashlib
import json
import shutil
import subprocess
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
    with p.open('x') as stream:json.dump(v,stream,ensure_ascii=False,indent=2);stream.write('\n')


def main(attempt):
    work=attempt/'work';ready=load(attempt/'preview-result.json')
    assert ready['status']=='PREVIEW_READY'
    inspection=load(HERE/'visual-inspection.json')
    assert inspection['preview_attempt']==str(attempt.relative_to(ROOT))
    for item in inspection['inspected_images']:
        assert sha(work/'full-review'/item['path'])==item['sha256']
    assert inspection['blockers']==[]
    for record in ('full-review/structure.json','reading-regression/page-map.json'):
        assert sha(work/record)==inspection['report_hashes'][record]
    review={'status':'VISUAL_REVIEWED_SELF_REVIEW_NOT_APPROVAL','artifacts':ready['artifacts'],
            'audit_sha256':ready['audit_sha256'],'visual_inspection':inspection}
    write(attempt/'reading-review.json',review)
    frozen=candidate.freeze(ROOT,str(attempt.relative_to(ROOT)),pub,'cpp-handbook-full')
    folder=Path(frozen['path']);manifest=load(folder/'candidate-manifest.json')
    assert sha(folder/'candidate-manifest.json')==load(folder/'candidate-result.json')['manifest_sha256']
    for entry in manifest['identity']['files']:
        assert sha(folder/entry['path'])==entry['sha256']
    selected={'run.json','result.json','preview-result.json','preview-audit.json','reading-review.json',
              'candidate-manifest.json','candidate-result.json','evidence/source-catalog.json'}
    selected.update(f['path'] for f in manifest['identity']['files'] if f['path'].startswith('output/') or
                    (f['path'].startswith('evidence/typeset/') and Path(f['path']).name in
                     ('table-map.json','reference-map.json','section-audit.json','reading-components.json','audit.json')))
    out=HERE/'cpp-handbook-full';out.mkdir(exist_ok=False)
    exported=[]
    for name in sorted(selected):
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(folder/name,target)
        exported.append({'path':name,'sha256':sha(target),'bytes':target.stat().st_size})
    for source in manifest['identity']['publication']['sources']:
        assert source['commit']==source['revision']=='8f479deaf660533b2ad82e1f721eb41a363112b6'
        assert (out/'output/source'/source['path']).read_bytes()==subprocess.check_output(['git','cat-file','blob',source['commit']+':'+source['path']],cwd=ROOT)
    write(out/'export.json',{'role':'REVIEW_EXPORT_NOT_RELEASE_NOT_COMPLETE_CANDIDATE',
          'candidate':str(folder.relative_to(ROOT)),'candidate_id':manifest['candidate_id'],
          'all_candidate_file_hashes_verified':True,'exported':exported,
          'omitted':sorted(f['path'] for f in manifest['identity']['files'] if f['path'] not in selected)})
    for name in ('full-review','reading-regression'):
        shutil.copytree(work/name,out/name)
    derived=[{'path':str(p.relative_to(out)),'sha256':sha(p),'bytes':p.stat().st_size}
             for name in ('full-review','reading-regression') for p in sorted((out/name).rglob('*')) if p.is_file()]
    write(out/'derived-export.json',{'role':'DERIVED_REVIEW_NOT_CANDIDATE_PAYLOAD','files':derived})
    view=load(out/'preview-audit.json')['views'][0]
    write(HERE/'inventory.json',{'profile':'cpp-handbook-full','candidate_id':manifest['candidate_id'],
          'visual_baseline':'1c11c5940c05fe29c46c4500935d5efb673d46a7',
          'content_baseline':'8f479deaf660533b2ad82e1f721eb41a363112b6',
          'pdf':'cpp-handbook-full/'+view['pdf'],'sha256':view['sha256'],'pages':view['pages'],
          'status':'PUBLICATION_CANDIDATE_FOR_REVIEW','formal_release':False})
    history=[]
    logs=HERE/'attempt-logs';logs.mkdir(exist_ok=False)
    for record in sorted((ROOT/'publication/build/preview').glob('*/*/run.json')):
        run=load(record)
        if run['identity'].get('publication',{}).get('profile')!='cpp-handbook-full':continue
        prior=record.parent;terminal=prior/'preview-result.json'
        entry={'attempt':str(prior.relative_to(ROOT)),'started_at':run['started_at'],
               'run_sha256':sha(record),'terminal':load(terminal) if terminal.exists() else None,
               'delivered':prior==attempt}
        if prior!=attempt and entry['terminal'] and entry['terminal']['status']=='PREVIEW_READY':
            entry['disposition']='NOT_DELIVERED: independent body-link audit found missing alias click areas; superseded by repaired candidate'
        for key,name in [('worker','work/worker.log'),('terminal','preview-result.json')]:
            path=prior/name
            if path.exists():
                target=logs/(run['attempt_id']+'-'+key+'.txt')
                shutil.copyfile(path,target)
                entry[key+'_evidence']={'path':str(target.relative_to(HERE)),'sha256':sha(target)}
        history.append(entry)
    write(HERE/'attempt-history.json',{'scope':'This new full-book profile only; intermediate failures/cancellations are not delivered artifacts',
                                     'attempts':sorted(history,key=lambda x:x['started_at'])})
    print(json.dumps(load(HERE/'inventory.json'),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempt',type=Path)
    main(parser.parse_args().attempt.resolve())
