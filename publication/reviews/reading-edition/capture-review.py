#!/usr/bin/env python3
"""Freeze reviewed preview bytes, then export a declared Git-review subset.

Reuses the v2 candidate/capture implementation, not a second publication path.
Derived regression PNGs are separately hash-bound, not called candidate evidence.
"""
import argparse
import importlib.util
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

spec=importlib.util.spec_from_file_location('v2_capture',HERE.parent/'v2-pilot/capture-review.py')
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
capture.HERE=HERE


def main(attempts):
    inspection=json.loads((HERE/'visual-inspection.json').read_text())
    inventory=[]
    for attempt in attempts:
        run=json.loads((attempt/'run.json').read_text())
        profile=run['identity']['publication']['profile']
        ready=json.loads((attempt/'preview-result.json').read_text())
        mapping=json.loads((attempt/'work/reading-regression/page-map.json').read_text())
        assert ready['status']=='PREVIEW_READY' and mapping['status']=='STRUCTURAL_PASS'
        assert mapping['audit_sha256']==ready['audit_sha256']
        visual=inspection['products'][profile]
        assert visual['preview_attempt']==str(attempt.relative_to(ROOT))
        for entry in visual['inspected_images']:
            assert capture.sha((attempt/'work/reading-regression'/entry['path']).read_bytes())==entry['sha256']
        review={'status':'VISUAL_REVIEWED_SELF_REVIEW_NOT_APPROVAL','artifacts':ready['artifacts'],
                'audit_sha256':ready['audit_sha256'],'structural_status':mapping['status'],
                'page_map_sha256':capture.sha((attempt/'work/reading-regression/page-map.json').read_bytes()),
                'visual_inspection':visual,'limitations':inspection['limitations']}
        with (attempt/'reading-review.json').open('x') as f:json.dump(review,f,ensure_ascii=False,indent=2);f.write('\n')
        frozen=candidate.freeze(ROOT,str(attempt.relative_to(ROOT)),pub,profile)
        folder=Path(frozen['path'])
        inventory.append(capture.capture(folder))
        out=HERE/profile
        export=json.loads((out/'export.json').read_text())
        for source in sorted((folder/'evidence/typeset').glob('*/reading-components.json')):
            path=str(source.relative_to(folder)); raw=source.read_bytes()
            destination=out/path; destination.parent.mkdir(exist_ok=True,parents=True)
            with destination.open('xb') as stream:stream.write(raw)
            export['exported'].append({'path':path,'sha256':capture.sha(raw),'bytes':len(raw)})
            export['omitted'].remove(path)
        (out/'export.json').write_text(json.dumps(export,ensure_ascii=False,indent=2)+'\n')
        derived=out/'visual-regression';shutil.copytree(attempt/'work/reading-regression',derived)
        bindings=[{'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':capture.sha(p.read_bytes())}
                  for p in sorted(derived.rglob('*')) if p.is_file()]
        (out/'derived-export.json').write_text(json.dumps({'role':'DERIVED_VISUAL_REVIEW_NOT_CANDIDATE_PAYLOAD','files':bindings},indent=2)+'\n')
        print(profile,frozen['candidate_id'],flush=True)
    with (HERE/'inventory.json').open('x') as f:json.dump(inventory,f,ensure_ascii=False,indent=2);f.write('\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempts',nargs=2,type=Path)
    main([p.resolve() for p in parser.parse_args().attempts])
