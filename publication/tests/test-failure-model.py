"""Frozen FM payload and generic GFM/block-target regressions; no C++ execution."""
import copy
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'publication/engine'))
import preview
import pub
from links import Resolver

BASE = '45b305eace0f057420587d685cb3f962f3f0552c'
PROFILE = ROOT/'publication/profiles/cpp-failure-model'
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
adapter=module('fm_adapter',PROFILE/'adapter.py')
fixtures=module('product_fixtures_fm',ROOT/'publication/tests/test-products.py')
def parse(raw):
    return json.loads(subprocess.check_output(['pandoc','-f','gfm','-t','json'],input=raw))
def blob(path):
    return subprocess.check_output(['git','cat-file','blob',BASE+':'+path],cwd=ROOT)

class FailureModelTests(unittest.TestCase):
    def test_exact_payload_and_anchor_positions(self):
        counts={'code':0,'cpp':0,'anchors':0,'headings':0,'test':0,'template':0}
        for source in json.loads((PROFILE/'profile.json').read_text())['sources']:
            self.assertEqual(source['revision'],BASE)
            raw=blob(source['path']);self.assertEqual(raw,(ROOT/source['path']).read_bytes())
            ast=parse(raw);before=copy.deepcopy(ast)
            meta,aliases,semantic=adapter.adapt(ast,source,preview.text)
            self.assertEqual(meta['document_id'],source['id']);self.assertEqual(aliases,{})
            for tag in ('CodeBlock','Code','Str','Table','Link'):
                def payload(tree):
                    return [n['c'][1] if tag=='CodeBlock' else n for n in preview.walk(tree['blocks']) if n.get('t')==tag]
                self.assertEqual(payload(before),payload(ast),source['id']+':'+tag)
            html=re.findall(r'<a id="([^"]+)"></a>',raw.decode())
            explicit=[n for n in preview.walk(ast['blocks']) if n.get('t')=='Span' and 'source-target' in n['c'][0][1]]
            self.assertEqual(html,[n['c'][0][0] for n in explicit])
            for b in ast['blocks']:
                targets=[n for n in preview.walk(b) if n.get('t')=='Span' and 'source-target' in n['c'][0][1]]
                for target in targets:
                    entry=next(e for e in semantic if e['kind']=='source-target' and e['id']==target['c'][0][0])
                    self.assertEqual(entry['target_text'],preview.text(b))
                    self.assertEqual(entry['target_type'],b['t'])
            codes=[n for n in preview.walk(ast['blocks']) if n.get('t')=='CodeBlock']
            counts['code']+=len(codes)
            counts['cpp']+=sum('cpp' in n['c'][0][1] for n in codes)
            counts['anchors']+=len(explicit)
            counts['headings']+=sum(n.get('t')=='Header' for n in preview.walk(ast['blocks']))
            counts['test']+=sum(e['kind']=='test' for e in semantic)
            counts['template']+=sum(e['kind']=='literal-template' for e in semantic)
        self.assertEqual(counts,{'code':527,'cpp':215,'anchors':189,'headings':383,'test':5,'template':2})

    def document(self,ident):
        raw='# Title\n\n<a id="2-外部_输入"></a>\n\n**Specific target**\n\n[here](#2-外部_输入)\n'
        ast=parse(raw.encode());meta,aliases,semantic=adapter.adapt(ast,{'id':ident,'version':'1'},preview.text)
        ids=['title','2-外部_输入']
        return {'id':ident,'ast':ast,'meta':meta,'aliases':aliases,'semantic':semantic,
                'anchors':{i:preview.anchor(ident,i) for i in ids},'first_anchor':preview.anchor(ident,'title'),
                'relative_path':ident+'.md','source':{'commit':BASE}}

    def test_unicode_numeric_duplicate_targets_are_block_local(self):
        docs=[self.document('TEST-A'),self.document('TEST-B')]
        resolver=Resolver(docs,docs,'https://example.invalid',None,{},pub,None,None,preview.walk)
        blocks,_=preview.compose(docs,docs,{}, {},resolver)
        targets=[n['c'][0][0] for n in preview.walk(blocks) if n.get('t')=='Span']
        self.assertEqual(len(set(targets)),2)
        self.assertEqual([r['target'] for r in resolver.ledger],['#'+t for t in targets])
        self.assertTrue(all(t!=d['first_anchor'] for t,d in zip(targets,docs)))
        for d in docs:d['anchors'].pop('2-外部_输入')
        with self.assertRaises((KeyError,RuntimeError)):preview.compose(docs,docs,{}, {},resolver)

    def test_lua_links_directly_to_block_not_previous_section(self):
        doc=self.document('TEST-A')
        resolver=Resolver([doc],[doc],'https://example.invalid',None,{},pub,None,None,preview.walk)
        blocks,_=preview.compose([doc],[doc],{}, {},resolver)
        ast=dict(doc['ast'],blocks=blocks)
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'document.tex'
            subprocess.run(['pandoc','-f','json','-t','latex','--lua-filter',str(ROOT/'publication/engine/filters/blocks.lua'),'-o',str(output)],input=json.dumps(ast).encode(),check=True)
            target=doc['anchors']['2-外部_输入']
            self.assertIn('\\hypertarget{'+target+'}{}',output.read_text())
            self.assertIn('\\hyperlink{'+target+'}',output.read_text())
            self.assertNotIn('\\hyperref['+target+']',output.read_text())

    def test_declared_warning_preserves_exact_label_and_code(self):
        ast=parse(b'# Title\n\nWrong:\n\n```cpp\nint x;\n```\n')
        ast['blocks'][-1]['c'][0][2].append(['reading-bind-label','Wrong:'])
        result=preview.bind_code_roles(copy.deepcopy(ast['blocks']))
        self.assertEqual(len(result),2)
        self.assertEqual(dict(result[-1]['c'][0][2])['reading-source-label'],'Wrong:')
        self.assertEqual(result[-1]['c'][1],'int x;')
        ast['blocks'][-1]['c'][0][2]=[['reading-bind-label','Different']]
        with self.assertRaises(RuntimeError):preview.bind_code_roles(ast['blocks'])

    def test_real_pdf_annotation_points_at_block_and_rejects_old_link(self):
        from pypdf import PdfReader
        doc=self.document('TEST-A')
        resolver=Resolver([doc],[doc],'https://example.invalid',None,{},pub,None,None,preview.walk)
        blocks,_=preview.compose([doc],[doc],{}, {},resolver)
        target=doc['anchors']['2-外部_输入']
        for direct in (True,False):
            tree=dict(doc['ast'],blocks=copy.deepcopy(blocks))
            if not direct:
                for n in preview.walk(tree['blocks']):
                    if n.get('t')=='Link':n['c'][0][2]=[]
            with tempfile.TemporaryDirectory() as folder:
                folder=Path(folder);out=folder/'document.tex'
                subprocess.run(['pandoc','-f','json','-t','latex','--lua-filter',str(ROOT/'publication/engine/filters/blocks.lua'),'-o',str(out)],input=json.dumps(tree).encode(),check=True)
                preamble=(r'\documentclass{article}\usepackage{hyperref}'
                    r'\newcommand{\PreviewSetIdentity}[3]{}\newcommand{\PreviewKeepHeadings}[1]{}'
                    r'\newcommand{\PreviewHeading}[4]{\section{#4}\label{#3}}\begin{document}')
                out.write_text(preamble+out.read_text()+r'\end{document}')
                env=dict(os.environ,TEXMFVAR=str(folder),TEXMFCACHE=str(folder))
                for _ in range(2):
                    result=subprocess.run(['lualatex','--no-shell-escape','-interaction=nonstopmode','-halt-on-error',out.name],cwd=folder,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                    self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')[-2000:])
                reader=PdfReader(folder/'document.pdf')
                actual=[a.get_object().get('/A',{}).get('/D') for p in reader.pages for a in p.get('/Annots',[])]
                self.assertIn(target,reader.named_destinations)
                self.assertEqual(target in actual,direct,'a destination alone must not satisfy body navigation')

    def test_unknown_html_and_unconsumed_marker_rejected(self):
        for raw in ('# Title\n\n<div>unknown</div>','<a id="trailing"></a>',
                    '# Title\n\n<!-- fm-test {"id":"T99"} -->'):
            with self.assertRaises(RuntimeError):adapter.adapt(parse(raw.encode()),{'id':'TEST','version':'1'},preview.text)

    def test_existing_products_composition_unchanged(self):
        # Compare today's composition against the accepted engine on the same
        # adapted inputs. No old evidence JSON is rewritten or rerun as C++.
        old={};exec(compile(blob('publication/engine/preview.py'),'accepted-preview','exec'),old)
        for name in ('esd','cpp-handbook-full','cpp-handbook-v1'):
            folder=ROOT/'publication/profiles'/name
            config=json.loads((folder/'profile.json').read_text())
            adapt=module('legacy_'+name.replace('-','_'),folder/'adapter.py')
            docs=[]
            for source in config['sources']:
                raw=subprocess.check_output(['git','show',source['revision']+':'+source['path']],cwd=ROOT) if source['revision']!='WORKTREE' else (ROOT/source['path']).read_bytes()
                ast=json.loads(subprocess.check_output(['pandoc','-f','markdown-smart','-t','json'],input=raw))
                meta,aliases,semantic=adapt.adapt(ast,source,preview.text)
                ids=[n['c'][1][0] for n in preview.walk(ast['blocks']) if n.get('t')=='Header']
                docs.append(dict(id=source['id'],ast=ast,meta=meta,aliases=aliases,semantic=semantic,
                    anchors={i:preview.anchor(source['id'],i) for i in ids},first_anchor=preview.anchor(source['id'],ids[0]),
                    source=dict(source,commit=BASE),relative_path=source['path'],source_matches_commit=True,source_href='https://example.invalid'))
            class UnchangedResolver:
                def resolve(self,target,doc):return target
            policies=json.loads((folder/'table-layouts.json').read_text())['tables']
            for view in config['views']:
                selected=[d for d in docs if d['id'] in view['documents']]
                args=(docs,selected,view,config,UnchangedResolver(),policies)
                self.assertEqual(old['compose'](*copy.deepcopy(args)),preview.compose(*copy.deepcopy(args)),name)

class ParserPreparationTests(unittest.TestCase):
    setUp=fixtures.ProductTests.setUp
    tearDown=fixtures.ProductTests.tearDown
    git=fixtures.ProductTests.git
    config=fixtures.ProductTests.config
    prepare=fixtures.ProductTests.prepare
    def test_gfm_parser_is_bound_to_input_identity(self):
        _,a=self.prepare();self.config(lambda c:c.update(source_format='gfm'));_,b=self.prepare()
        self.assertNotEqual(a['build_id'],b['build_id'])
    def test_unknown_parser_rejected(self):
        self.config(lambda c:c.update(source_format='gfm+raw_tex'))
        with self.assertRaisesRegex(pub.PreparationError,'source parser'):self.prepare()

if __name__=='__main__':unittest.main(verbosity=2)
