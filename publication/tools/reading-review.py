#!/usr/bin/env python3
"""Bind semantic visual fixtures to actual PDF pages; signals are NOT visual approval.

Only reads completed previews; derived PNGs/reports live under attempt/work.
The --compare option matches fixture identities across two reports, never page N.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from pypdf import PdfReader


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def position(reader, key):
    if not hasattr(reader, '_reading_destinations'):
        reader._reading_destinations=reader.named_destinations
    dest = reader._reading_destinations[key]
    return reader.get_destination_page_number(dest) + 1, float(dest['/Top'])


def code_signals(component, positions):
    """Pure classifier, separately mutation-tested with synthetic broken page maps."""
    issues = []
    groups = {}
    for line, (page, y) in enumerate(positions, 1):
        groups.setdefault(page, []).append(line)
    if len(groups) > 1:
        first, last = next(iter(groups.values())), list(groups.values())[-1]
        if len(first) < component['min_head_lines']:
            issues.append('short_code_head')
        if len(last) < component['min_tail_lines']:
            issues.append('short_code_tail')
        tail = [component['source_lines'][n-1] for n in last]
        if all(re.fullmatch(r'[\s}\]);]*', line) for line in tail):
            issues.append('closing_only_code_tail')
    return issues, groups


def inspect(attempt, render=True):
    work = attempt / 'work'
    ready = load(attempt / 'preview-result.json')
    assert ready['status'] == 'PREVIEW_READY', 'unfinished/failed preview is not reviewable'
    assert sha(work / 'preview-audit.json') == ready['audit_sha256']
    report = load(work / 'preview-audit.json')
    catalog = load(work / 'source-catalog.json')
    fixtures = load(Path(__file__).with_name('reading-corpus.json'))['fixtures']
    target = work / 'reading-regression'
    target.mkdir(exist_ok=False)
    result = {'status': 'STRUCTURAL_PASS', 'visual_status': 'NOT_REVIEWED',
              'scope': 'Reading-quality signals, not a visual or technical proof',
              'attempt': str(attempt), 'audit_sha256': ready['audit_sha256'],
              'corpus_sha256': sha(Path(__file__).with_name('reading-corpus.json')),
              'views': [], 'fixtures': [], 'issues': []}
    for view in report['views']:
        pdf = work / view['pdf']
        assert sha(pdf) == view['sha256']
        reader = PdfReader(pdf)
        folder = work / 'typeset' / view['view']
        components = load(folder / 'reading-components.json')
        tables = load(folder / 'table-map.json')
        sections = load(folder / 'section-audit.json')['sections']
        texts = [p.extract_text() for p in reader.pages]
        mapping, issues, wraps = {}, [], []
        for c in components:
            if c['kind'] == 'table':
                a, b = position(reader,c['id']+'-start'), position(reader,c['id']+'-end')
                mapping[c['id']] = list(range(a[0],b[0]+1))
                if c['keep_together'] and a[0] != b[0]:
                    issues.append({'object':c['id'],'signal':'short_table_split'})
                continue
            pos = [position(reader,c['id']+'-L'+str(n)) for n in range(1,c['lines']+1)]
            found, groups = code_signals(c,pos)
            issues.extend({'object':c['id'],'signal':s} for s in found)
            mapping[c['id']] = list(groups)
            if c['kind']=='experiment':
                for page in groups:
                    if c['caption'].replace(' ','') not in texts[page-1].replace(' ','').replace('\n',''):
                        issues.append({'object':c['id'],'page':page,'signal':'missing_experiment_file_identity'})
            for n in range(len(pos)-1):
                if pos[n][0]==pos[n+1][0] and pos[n][1]-pos[n+1][1]>18:
                    wraps.append({'object':c['id'],'source_line':n+1,'page':pos[n][0],
                                  'signal':'wrap_or_chunk_spacing; inspect rendered line'})
        for table in tables:
            if table['layout']!='records':
                continue
            pages=[]
            for row in range(1,len(table['row_text'])+1):
                a=position(reader,table['table']+f'-R{row}-start')[0]
                b=position(reader,table['table']+f'-R{row}-end')[0]
                pages.extend(range(a,b+1))
                if a!=b:
                    fields=[c for c in table['cells'] if c['row']==row]
                    tail=[c for c in fields if position(reader,table['table']+f'-R{row}-F{c["column"]}')[0]==b]
                    if len(tail)<=1:
                        issues.append({'object':table['table'],'row':row,'signal':'record_single_field_tail'})
            mapping[table['table']]=sorted(set(pages))
        first=min(s['start_page'] for s in sections)
        toc=list(range(3,first))
        for page in toc[1:]:
            entries=sum(1 for a in reader.pages[page-1].get('/Annots',[]) if a.get_object().get('/Subtype')=='/Link')
            if entries<=2:
                issues.append({'page':page,'signal':'toc_tail_underfill','link_entries':entries})
        current={'view':view['view'],'pdf':view['pdf'],'sha256':view['sha256'],'pages':view['pages'],
                 'components':mapping,'line_position_checks':sum(c.get('lines',0) for c in components),
                 'wrap_observations':wraps,'issues':issues}
        result['views'].append(current)
        result['issues'].extend(dict(view=view['view'],**i) for i in issues)
        for f in fixtures:
            docs=[d for d in catalog if d['source']['id'] in [s['id'] for s in view['source_identity']]]
            if f.get('document') and not any(d['source']['id']==f['document'] for d in docs):
                continue
            if f.get('view') and view['view'] not in (f['view'], f['view']+'-COMPACT'):
                continue
            pages, bound = [], None
            if f['kind']=='code':
                matches=[c for c in components if c['kind']!='table' and c['id'].startswith(f['document']+'-')
                         and (c['caption']==f['caption'] if 'caption' in f else f['contains'] in '\n'.join(c['source_lines']))]
                assert len(matches)==1,(f,matches)
                bound=matches[0]['id']; pages=mapping[bound]
            elif f['kind']=='table':
                matches=[t for t in tables if t['table'].startswith(f['document']+'-') and
                         (t['section_title']==f['section'] if 'section' in f else t['headers']==f['headers'])]
                assert len(matches)==1,(f,matches)
                bound=matches[0]['table']; pages=mapping[bound]
            elif f['kind']=='heading':
                matches=[s for s in sections if s['document']==f['document'] and s['title']==f['title']]
                assert len(matches)==1,(f,matches)
                bound=matches[0]['anchor']; pages=[position(reader,bound)[0]]
            elif f['kind']=='opening':
                d=next(d for d in docs if d['source']['id']==f['document'])
                bound=next(iter(d['anchors'].values())); pages=[position(reader,bound)[0]]
            elif f['kind']=='destination':
                bound=f['anchor']; pages=[position(reader,bound)[0]]
            elif f['kind']=='toc':
                bound='generated-toc'; pages=toc
            item={'id':f['id'],'view':view['view'],'object':bound,'pages':pages,
                  'pdf_sha256':view['sha256'],'sources':[d['source'] for d in docs], 'renders':[]}
            for page in pages:
                name=f'{view["view"]}-{page:03d}'
                png=target/(name+'.png')
                if render and not png.exists():
                    subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-r','120','-singlefile','-png',str(pdf),str(target/name)],check=True)
                if render:item['renders'].append({'path':png.name,'sha256':sha(png)})
            result['fixtures'].append(item)
    if result['issues']:result['status']='REVIEW_REQUIRED'
    (target/'page-map.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'path':str(target),'status':result['status'],'fixtures':len(result['fixtures']),
                      'issues':result['issues']},ensure_ascii=False))
    return result


def compare(left,right):
    a,b=load(left),load(right)
    keys={(x['id'],x['view']):x for x in a['fixtures']}
    return [{'id':x['id'],'view':x['view'],'left_pages':keys[k]['pages'],'right_pages':x['pages'],
             'left_pdf':keys[k]['pdf_sha256'],'right_pdf':x['pdf_sha256'],
             'meaning':'Semantic side-by-side comparison, not pixel identity or automatic visual approval'}
            for x in b['fixtures'] if (k:=(x['id'],x['view'])) in keys]


def density_compare(path):
    data=load(path)
    keys={(x['id'],x['view']):x for x in data['fixtures']}
    return [{'id':x['id'],'balanced_view':keys[k]['view'],'compact_view':x['view'],
             'balanced_pages':keys[k]['pages'],'compact_pages':x['pages'],
             'balanced_pdf':keys[k]['pdf_sha256'],'compact_pdf':x['pdf_sha256'],
             'meaning':'Same semantic fixture / different spacing; not automatic visual approval'}
            for x in data['fixtures'] if x['view'].endswith('-COMPACT') and
            (k:=(x['id'],x['view'].removesuffix('-COMPACT'))) in keys]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt',nargs='?',type=Path)
    parser.add_argument('--no-render',action='store_true')
    parser.add_argument('--compare',nargs=2,type=Path)
    parser.add_argument('--density-compare',type=Path)
    args=parser.parse_args()
    if args.compare:print(json.dumps(compare(*args.compare),ensure_ascii=False,indent=2))
    elif args.density_compare:print(json.dumps(density_compare(args.density_compare),ensure_ascii=False,indent=2))
    else:inspect(args.attempt.resolve(),not args.no_render)
