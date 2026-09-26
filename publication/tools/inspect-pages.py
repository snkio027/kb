#!/usr/bin/env python3
"""Read-only artifact verification + derived contact sheets in the attempt work dir.

Does not approve visuals. Human inspection scope must be recorded separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('attempt',type=Path)
args=parser.parse_args()
work=args.attempt/'work'
ready=json.loads((args.attempt/'preview-result.json').read_text())
assert ready['status']=='PREVIEW_READY'
assert hashlib.sha256((work/'preview-audit.json').read_bytes()).hexdigest()==ready['audit_sha256']
report=json.loads((work/'preview-audit.json').read_text())
out=work/'visual-inputs'
out.mkdir(exist_ok=False)
inventory=[]
for view in report['views']:
    pdf=work/view['pdf']
    assert hashlib.sha256(pdf.read_bytes()).hexdigest()==view['sha256']
    pages=sorted((work/'renders'/view['view']).glob('page-*.png'))
    assert len(pages)==view['pages']
    for start in range(0,len(pages),20):
        sheet=Image.new('RGB',(800,1460),'#D9DDE1')
        draw=ImageDraw.Draw(sheet)
        for offset,path in enumerate(pages[start:start+20]):
            with Image.open(path) as image:
                image.thumbnail((188,266))
                x=(offset%4)*200+6; y=(offset//4)*292+20
                sheet.paste(image,(x,y))
                draw.text((x,y-16),f'{view["view"]} p{start+offset+1}',fill='black')
        target=out/f'{view["view"]}-{start+1:03d}.png'
        sheet.save(target)
        inventory.append({'view':view['view'],'pages':[start+1,min(start+20,len(pages))],'sheet':str(target)})
print(json.dumps(inventory,ensure_ascii=False,indent=2))
