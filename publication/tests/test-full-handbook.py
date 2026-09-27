#!/usr/bin/env python3
"""Full-book integration checks; no C++ compilation or layout redesign."""
import copy
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'publication/engine'))
import preview

PROFILE = ROOT/'publication/profiles/cpp-handbook-full'
spec = importlib.util.spec_from_file_location('full_adapter', PROFILE/'adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
FROZEN = '8f479deaf660533b2ad82e1f721eb41a363112b6'
VISUAL = '1c11c5940c05fe29c46c4500935d5efb673d46a7'


def parse(raw):
    return json.loads(subprocess.check_output(['pandoc','-f','markdown-smart','-t','json'],input=raw))


class FullHandbookTests(unittest.TestCase):
    def test_full_source_identity_and_experiment_payload(self):
        config=json.loads((PROFILE/'profile.json').read_text())
        self.assertEqual([s['id'] for s in config['sources']],[f'G{i}' for i in range(13)])
        self.assertEqual(config['views'][0]['documents'],[f'G{i}' for i in range(13)])
        counts={'code':0,'anchors':0,'lab':0,'file':0}
        for source in config['sources']:
            with self.subTest(document=source['id']):
                self.assertEqual(source['revision'],FROZEN)
                raw=subprocess.check_output(['git','cat-file','blob',FROZEN+':'+source['path']],cwd=ROOT)
                ast=parse(raw); before=copy.deepcopy(ast)
                code=[n['c'][1] for n in preview.walk(ast['blocks']) if n.get('t')=='CodeBlock']
                markers=[(m[1],m[2],json.loads(m[3])) for m in re.finditer(r'<!-- ([ghns])-(lab|file) (.*?) -->',raw.decode())]
                meta,aliases,semantic=adapter.adapt(ast,source,preview.text)
                self.assertEqual(code,[n['c'][1] for n in preview.walk(ast['blocks']) if n.get('t')=='CodeBlock'])
                # Raw anchor/marker paragraphs are non-printing metadata. All
                # source printing units and fenced payloads remain identical.
                def printed(value):
                    result=[]
                    for n in preview.walk(value['blocks']):
                        if n.get('t') in ('CodeBlock','Code','Str'):result.append(preview.text(n))
                        elif n.get('t')=='RawInline' and n['c'][1] in adapter._LITERALS.get(source['id'],{}):result.append(n['c'][1])
                    return result
                self.assertEqual(''.join(printed(before)),''.join(printed(ast)))
                self.assertFalse([n for n in preview.walk(ast['blocks']) if n.get('t') in ('RawInline','RawBlock','Cite')])
                self.assertFalse([n for n in preview.walk(ast['blocks']) if n.get('t')=='Span' and 'fullbook-inline-literal' in n['c'][0][1]])
                self.assertEqual(set(aliases),set(re.findall(r'<a id="([^"]+)"></a>',raw.decode())))
                self.assertEqual(markers,[(m['source_namespace'],m['kind'],m['payload']) for m in semantic if m['kind'] in ('lab','file')])
                self.assertEqual(meta['document_id'],source['id'])
                self.assertNotIn('PILOT',meta['status'])
                counts['code']+=len(code); counts['anchors']+=len(aliases)
                for _,kind,_ in markers:counts[kind]+=1
        self.assertEqual(counts,{'code':953,'anchors':1714,'lab':30,'file':68})

    def test_visual_mechanics_frozen(self):
        pilot=json.loads((ROOT/'publication/profiles/cpp-handbook/profile.json').read_text())
        full=json.loads((PROFILE/'profile.json').read_text())
        for key in ('reading','toc_depth','combined_toc_depth','required_headings','index'):
            self.assertEqual(full[key],pilot[key])
        # A Gate section starts a page; a nested "13.1 Final Gate" must not
        # issue another clearpage and strand its parent heading alone.
        pattern=full['new_page_heading_patterns'][0]
        self.assertTrue(re.search(pattern,'13. Final Gate'))
        self.assertFalse(re.search(pattern,'13.1 Final Gate'))
        self.assertEqual((PROFILE/'table-layouts.json').read_bytes(),(ROOT/'publication/profiles/cpp-handbook/table-layouts.json').read_bytes())
        base_theme=(ROOT/'publication/profiles/cpp-handbook/theme.sty').read_text()
        self.assertEqual((PROFILE/'theme.sty').read_text(),base_theme+'% Full-book glyph coverage: same math-arrow fallback as the frozen Pilot.\n'+r'\newunicodechar{↔}{\ensuremath{\leftrightarrow}}'+'\n')
        template=(ROOT/'publication/profiles/cpp-handbook/template.tex').read_text()
        self.assertEqual((PROFILE/'template.tex').read_text(),template.replace('Visual Profile Candidate，尚未冻结','Visual Profile v1.0，已冻结；全书制品待审核'))
        for folder in ('publication/engine','publication/latex','publication/profiles/cpp-handbook'):
            names=subprocess.check_output(['git','ls-tree','-r','--name-only',VISUAL,'--',folder],cwd=ROOT).decode().splitlines()
            for name in names:
                if name in ('publication/engine/preview_audit.py','publication/engine/links.py',
                            'publication/engine/source_model.py','publication/engine/preview.py'):continue  # Cache/alias fixes and RC identity-only extension; bounded by test-release-identity.py, no layout changes.
                self.assertEqual((ROOT/name).read_bytes(),subprocess.check_output(['git','cat-file','blob',VISUAL+':'+name],cwd=ROOT),name)

    def test_destination_cache_preserves_coordinates(self):
        from preview_audit import destination_position
        class Reader:
            accesses=0
            @property
            def named_destinations(self):
                self.accesses+=1
                return {'first':{'/Page':2,'/Top':700},'second':{'/Page':9,'/Top':120}}
            def get_destination_page_number(self,d):return d['/Page']
        reader=Reader();names=reader.named_destinations
        cached=[destination_position(reader,n,names) for n in names]
        self.assertEqual(reader.accesses,1)
        self.assertEqual(cached,[destination_position(reader,n) for n in names])
        self.assertEqual(cached,[(2,-700.0),(9,-120.0)])

    def test_alias_links_use_real_heading_labels(self):
        from links import Resolver
        doc={'id':'G0','relative_path':'c++/g0.md','anchors':{'heading':'G0-canonical'},
             'aliases':{'old-anchor':'heading'},'first_anchor':'G0-canonical'}
        resolver=Resolver([doc],[doc],'https://example.org',None,{},None,None,None,preview.walk)
        self.assertEqual(resolver.resolve('#old-anchor',doc),'#G0-canonical')
        self.assertEqual(resolver.ledger[-1]['source'],'#old-anchor')
        with self.assertRaisesRegex(RuntimeError,'unresolved'):
            resolver.resolve('#missing',doc)

    def test_unknown_namespace_rejected(self):
        raw='# G0 · Test\n\n**版本：** 1.2.1 · test\n\n<!-- x-lab {"id":"G0-L1"} -->\n'
        with self.assertRaisesRegex(RuntimeError,'unrecognized'):
            adapter.adapt(parse(raw.encode()),{'id':'G0','version':'1.2.1'},preview.text)

    def test_unconsumed_or_wrong_namespace_rejected(self):
        base='# G0 · Test\n\n**版本：** 1.2.1 · test\n\n<!-- g-lab {"id":"G0-L1"} -->\n\n'
        for end in ('<!-- g-file {"path":"main.cpp"} -->\n','<!-- s-file {"path":"main.cpp"} -->\n\n```cpp\nint x;\n```\n'):
            with self.subTest(end=end),self.assertRaises(RuntimeError):
                adapter.adapt(parse((base+end).encode()),{'id':'G0','version':'1.2.1'},preview.text)


if __name__=='__main__':unittest.main(verbosity=2)
