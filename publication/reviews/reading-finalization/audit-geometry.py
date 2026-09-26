#!/usr/bin/env python3
"""Read-only all-page text geometry signal, not a visual-quality proof."""
import argparse
import hashlib
import json
from pathlib import Path
import pdfplumber

def classify(attempt):
    path=attempt/'work/reading-regression/geometry.json'
    report=json.loads(path.read_text())
    explained=[]; unresolved=[]
    for view in report['views']:
        for page in view['pages']:
            for glyph in page['out_of_band']:
                item={'pdf':view['pdf'],'page':page['page'],**glyph}
                if (glyph['text'] in '。，、；：（）？！「」“”' and
                    glyph['x0']>=55.5 and glyph['x1']<=540 and glyph['bottom']<=791):
                    explained.append(dict(item,classification='CJK_PUNCTUATION_HALF_CELL_METRICS'))
                else:unresolved.append(item)
    output={'raw_geometry_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'interpretation':'Bounded classification of CJK punctuation side bearings/protrusion; raw observations remain unchanged. Not a visual proof.',
            'explained':explained,'unresolved':unresolved}
    with path.with_name('geometry-disposition.json').open('x') as f:json.dump(output,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'explained_glyphs':len(explained),'unresolved_glyphs':len(unresolved)}))


def main(attempt):
    work=attempt/'work'
    ready=json.loads((attempt/'preview-result.json').read_text())
    assert ready['status']=='PREVIEW_READY'
    reports=[]
    for artifact, digest in ready['artifacts'].items():
        p=work/artifact
        assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
        pages=[]
        with pdfplumber.open(p) as pdf:
            for n,page in enumerate(pdf.pages,1):
                # Exclude header/footer only. Keep whole body glyph boxes and
                # report, rather than crop away, boundary violations.
                chars=[c for c in page.chars if 56<c['top']<789 and c['text'].strip()]
                bad=[c for c in chars if c['x0']<60 or c['x1']>537 or c['bottom']>791]
                lines={round(c['top']/3) for c in chars}
                pages.append({'page':n,'glyphs':len(chars),'line_bands':len(lines),
                              'body_top':round(min((c['top'] for c in chars),default=0),2),
                              'body_bottom':round(max((c['bottom'] for c in chars),default=0),2),
                              'out_of_band':[{'text':c['text'],'x0':round(c['x0'],2),'x1':round(c['x1'],2),'bottom':round(c['bottom'],2)} for c in bad]})
        reports.append({'pdf':artifact,'sha256':digest,'pages':pages})
    record={'scope':'All-page glyph geometry signal; headers, vectors, overlaps and reading rhythm require visual review',
            'views':reports,'pages_checked':sum(len(r['pages']) for r in reports),
            'flagged_pages':sum(bool(p['out_of_band']) for r in reports for p in r['pages'])}
    path=work/'reading-regression/geometry.json'
    with path.open('x') as f:json.dump(record,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:record[k] for k in ('pages_checked','flagged_pages')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempt',type=Path)
    parser.add_argument('--classify',action='store_true')
    args=parser.parse_args()
    (classify if args.classify else main)(args.attempt.resolve())
