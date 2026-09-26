#!/usr/bin/env python3
"""Capture the eight inspected semantic A/B pairs, not another product build.

A is the immutable 783c7d3 export. B is a directional component proof, before
the final full run. Page numbers locate observations, never fixture identity.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD=HERE.parent/'reading-edition'
CPP=ROOT/'publication/build/preview/b6826fbe3bd59bbc8e2df154fdf147af95af1d5bcf3de28b27462dea543925ea/e894a417267844f09d58c6afb1a4df57'
ESD=ROOT/'publication/build/preview/a7b187e99fe66d6c34f2bfa56391abce4e16c89aece151b37c05e325db84cb8a/4964daa56fb14363a5c532e7dfa68287'
SUITE=ROOT/'publication/build/preview/30ed557a11cf85941a0b1f1f54b1a6342b1a5af17f3e23d74f3391e43814a18e/c6019c023c5c4017a8d1a9111a0252ee'
PAIRS=[
 ('danger-role-binding','cpp-handbook','G7',38,CPP,37,'The source warning now shares the first code page. Long continuation is additionally exercised by the real compile regression.'),
 ('experiment-identity','cpp-handbook','G6',42,CPP,40,'One source identity per experiment file; internal Cxx remains audit-only.'),
 ('empty-template','esd','ESD-REFERENCE-001',26,ESD,26,'State Ownership Register becomes a bounded, named, writable schema with ordered fields, not an invented record.'),
 ('record-baseline','esd','ESD-SUITE-000',6,SUITE,6,'First text baselines align; field spacing has not been compressed.'),
 ('semantic-soft-wrap','esd','ESD-ASSURANCE-001',19,ESD,19,'Break follows the pipe; OPERATIONAL stays whole. Vector continuation cue adds no character.'),
 ('ops-final','esd','ESD-OPS-001',49,ESD,47,'Two-line final page removed; conclusion and closing paragraph share a readable unit.'),
 ('compact-final','cpp-handbook','CPP-PILOT-G6-G7-COMPACT',50,CPP,49,'Keep transition plus reference entry as an end-matter unit. Intentional remaining whitespace is accepted; no font shrink.'),
 ('literal-labels','esd','ESD-METHOD-001',11,ESD,11,'Ordinary literal blocks no longer repeat generated debug captions.')
]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    target=HERE/'component-ab'
    target.mkdir(exist_ok=False)
    items=[]
    for identity,profile,view,a,attempt,b,decision in PAIRS:
        pair={'semantic_purpose':identity,'decision':decision,'selected':'B',
              'scope':'Component self-review, not final PDF acceptance','sides':[]}
        for label,pdf,page in [('A',OLD/profile/'output/pdf'/(view+'-draft.pdf'),a),
                               ('B',attempt/'work/output/pdf'/(view+'-draft.pdf'),b)]:
            output=target/(identity+'-'+label)
            subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-r','120','-singlefile','-png',str(pdf),str(output)],check=True)
            png=output.with_suffix('.png')
            pair['sides'].append({'variant':label,'pdf':str(pdf.relative_to(ROOT)),
                                  'pdf_sha256':sha(pdf),'physical_page':page,
                                  'image':png.name,'image_sha256':sha(png)})
        pair['B_attempt']=str(attempt.relative_to(ROOT))
        pair['B_preparation_id']=json.loads((attempt/'run.json').read_text())['build_id']
        items.append(pair)
    (target/'decisions.json').write_text(json.dumps({
        'baseline':'783c7d3b9b6a1e4f715a960c18e687604143f98b',
        'status':'VISUAL_REVIEWED_SELF_REVIEW_NOT_APPROVAL','pairs':items,
        'subsequent_repairs':['Closing-container running marks were corrected after these proofs.',
                              'Long-template continuation labels were included in generated-label exclusion, with a real two-page regression.'],
        'not_claimed':['Pixel equivalence','Full-run visual acceptance','Independent review']
    },ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
