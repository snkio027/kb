#!/usr/bin/env python3
"""Reading presentation contracts; no C++/performance/concurrency execution."""
import importlib.util
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'publication/engine'))
import preview
spec=importlib.util.spec_from_file_location('reading',ROOT/'publication/tools/reading-review.py')
reading=importlib.util.module_from_spec(spec);spec.loader.exec_module(reading)


class ReadingTests(unittest.TestCase):
    def test_tail_mutation_is_rejected(self):
        c={'source_lines':['statement;']*12+['}']*4,'min_head_lines':4,'min_tail_lines':6}
        bad=[(1,700-n*12) for n in range(12)]+[(2,700-n*12) for n in range(4)]
        issues,_=reading.code_signals(c,bad)
        self.assertIn('short_code_tail',issues)
        self.assertIn('closing_only_code_tail',issues)
        good=[(1,700-n*12) for n in range(9)]+[(2,700-n*12) for n in range(7)]
        self.assertEqual(reading.code_signals(c,good)[0],[])

    def test_head_mutation_is_rejected(self):
        c={'source_lines':['statement;']*16,'min_head_lines':4,'min_tail_lines':6}
        self.assertIn('short_code_head',reading.code_signals(c,[(1,700),(2,700)]+[(2,688-n*12) for n in range(14)])[0])

    def test_semantic_corpus_has_no_physical_page_identity(self):
        fixtures=json.loads((ROOT/'publication/tools/reading-corpus.json').read_text())['fixtures']
        self.assertGreaterEqual(len(fixtures),23)
        self.assertEqual(len({f['id'] for f in fixtures}),len(fixtures))
        for f in fixtures:
            self.assertNotIn('page',f)
            self.assertTrue(f['purpose'])

    def test_explicit_role_binding_preserves_source(self):
        source='[反例 · 未定义行为；仅限 TSan 隔离检测 · G7-D3 · main.cpp]\n\n```cpp\nint value;\n```\n'
        ast=json.loads(subprocess.check_output(['pandoc','-f','markdown','-t','json'],input=source.encode()))
        before=copy.deepcopy(ast)
        result=preview.bind_code_roles(copy.deepcopy(ast['blocks']))
        self.assertEqual(ast,before)
        self.assertEqual(len(result),1)
        attrs=dict(result[0]['c'][0][2])
        self.assertEqual(attrs['reading-role'],'反例')
        self.assertEqual(attrs['reading-source-label'],preview.text(ast['blocks'][0]))
        self.assertEqual(result[0]['c'][1],ast['blocks'][1]['c'][1])
        ast['blocks'][0]=preview.para('Warning inferred from keywords is not a source role')
        self.assertEqual(len(preview.bind_code_roles(ast['blocks'])),2)

    def test_empty_template_has_no_invented_data(self):
        source='## State Ownership Register\n\n|State|Writer|Owner|Recovery|\n|-|-|-|-|\n'
        ast=json.loads(subprocess.check_output(['pandoc','-f','markdown','-t','json'],input=source.encode()))
        ledger=[]
        out=preview.tables_to_records(ast['blocks'],'TEST',ledger)
        t=ledger[0]
        self.assertEqual(t['layout'],'empty-template')
        self.assertEqual(t['template_fields'],['State','Writer','Owner','Recovery'])
        self.assertEqual((t['cells'],t['row_text']),([],[]))
        self.assertIn('PreviewTemplateBox',json.dumps(out))
        self.assertTrue(t['keep_together'])

    def test_role_and_baseline_mutations_rejected(self):
        c={'source_label':'[反例 · D3 · main.cpp]','role':'反例','kind':'experiment',
           'continued_label':'反例 · D3 · main.cpp · continued'}
        self.assertIn('source_role_detached_from_code',reading.identity_signals(c,[(2,700)],(1,100),['','']))
        self.assertIn('missing_continued_semantic_identity',reading.identity_signals(c,[(1,100),(2,700)],(1,130),['','D3 · main.cpp']))
        self.assertEqual(reading.identity_signals(c,[(1,100),(2,700)],(1,130),['',c['continued_label']]),[])
        self.assertTrue(reading.field_alignment((1,700),(1,700)))
        self.assertFalse(reading.field_alignment((1,700),(1,691.2)))
        self.assertFalse(reading.field_alignment((1,700),(2,700)))

    def test_code_labels_have_only_reader_identity(self):
        attrs={'reading-kind':'experiment','reading-caption':'G7-D3 · main.cpp','reading-role':'反例',
               'reading-source-label':'[反例 · 未定义行为 · G7-D3 · main.cpp]','preview-code-id':'G7-C68'}
        first,continued=preview.code_labels(attrs)
        self.assertEqual(first,attrs['reading-source-label'])
        self.assertEqual(continued,'反例 · G7-D3 · main.cpp · continued')
        self.assertNotIn('C68',first+continued)
        self.assertEqual(preview.code_labels({'reading-kind':'literal'})[0],'')

    def test_semantic_token_break_is_not_erased_by_normalization(self):
        self.assertTrue(reading.token_intact('OPERATIONAL',['SECURITY|\nOPERATIONAL|RECOVERY']))
        self.assertFalse(reading.token_intact('OPERATIONAL',['SECURITY|OPE\nRATIONAL|RECOVERY']))
        self.assertFalse(reading.token_intact('OPERATIONAL',['SECURITY|OPE','RATIONAL|RECOVERY']))

    def test_density_does_not_change_body_or_code_fonts(self):
        source=(ROOT/'publication/latex/kb-base.sty').read_text()
        policy=source.split(r'\newcommand{\PreviewDensity}')[1].split('% Contents')[0]
        compact=policy.split(r'\ifstrequal{#1}{compact}')[1]
        self.assertNotIn('fontsize',compact)
        self.assertNotIn('setmainfont',compact)

    def test_lua_preserves_code_and_emits_tail_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'document.tex'
            code='\n'.join(['statement;']*15+['}']*4)
            ast={'pandoc-api-version':[1,23,1,1],'meta':{},'blocks':[{'t':'CodeBlock','c':[['',[],[
                ['preview-code-id','TEST-C01'],['reading-kind','experiment'],['reading-caption','LAB-1 · main.cpp']]],code]}]}
            subprocess.run(['pandoc','-f','json','-t','latex','--lua-filter',str(ROOT/'publication/engine/filters/blocks.lua'),'-o',str(out)],input=json.dumps(ast).encode(),check=True)
            record=json.loads((Path(tmp)/'reading-components.json').read_text())[0]
            self.assertEqual('\n'.join(record['source_lines']),code)
            self.assertEqual(record['closing_tail'],4)
            self.assertLessEqual(record['tail_start'],13)
            self.assertIn('LAB-1',out.read_text())
            self.assertIn('firstnumber=',out.read_text())

    def test_adapter_does_not_change_experiment_bytes(self):
        spec=importlib.util.spec_from_file_location('adapter',ROOT/'publication/profiles/cpp-handbook/adapter.py')
        adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
        for source in json.loads((ROOT/'publication/profiles/cpp-handbook/profile.json').read_text())['sources']:
            raw=subprocess.check_output(['git','show',source['revision']+':'+source['path']],cwd=ROOT)
            ast=json.loads(subprocess.check_output(['pandoc','-f','markdown-smart','-t','json'],input=raw))
            before=[n['c'][1] for n in preview.walk(ast['blocks']) if n.get('t')=='CodeBlock']
            adapter.adapt(ast,source,preview.text)
            after=[n['c'][1] for n in preview.walk(ast['blocks']) if n.get('t')=='CodeBlock']
            self.assertEqual(before,after)
            files=[n for n in preview.walk(ast['blocks']) if n.get('t')=='CodeBlock' and dict(n['c'][0][2]).get('reading-kind')=='experiment']
            self.assertTrue(files)
            self.assertTrue(all('reading-caption' in dict(n['c'][0][2]) for n in files))

    def test_gate_local_label_keeps_with_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'document.tex'
            source='## Final Gate\n\n**D. Mutex / CV**\n\n**9**\n\nWhy does a mutex protect an invariant?\n'
            subprocess.run(['pandoc','-f','markdown','-t','latex','--lua-filter',str(ROOT/'publication/engine/filters/blocks.lua'),'-o',str(out)],input=source.encode(),check=True)
            tex=out.read_text()
            self.assertIn('Needspace{110pt}',tex)
            self.assertLess(tex.index('Needspace{110pt}'),tex.index('D. Mutex'))
            self.assertIn('Why does a mutex protect an invariant?',tex)

    def test_density_comparison_does_not_alias_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'map.json'
            p.write_text(json.dumps({'fixtures':[
                {'id':'one','view':'VIEW','pages':[2],'pdf_sha256':'balanced'},
                {'id':'one','view':'VIEW-COMPACT','pages':[3],'pdf_sha256':'compact'}]}))
            pair=reading.density_compare(p)[0]
            self.assertEqual((pair['balanced_pages'],pair['compact_pages']),([2],[3]))
            self.assertEqual(len(reading.compare(p,p)),2)


if __name__=='__main__':unittest.main(verbosity=2)
