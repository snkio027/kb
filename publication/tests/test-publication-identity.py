#!/usr/bin/env python3
"""Publication v1 changes generated identity only, never publishes via preview."""
import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'publication/engine'))
import pub
import preview
BASE='2f4caf671bc42e6e3b03a8eda8255e1a392e5798'
OLD=ROOT/'publication/profiles/cpp-handbook-rc1'
NEW=ROOT/'publication/profiles/cpp-handbook-v1'
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
fixtures=module('product_fixtures_v1',ROOT/'publication/tests/test-products.py')

class PublicationIdentityTests(unittest.TestCase):
    def test_historical_engine_patch_is_one_identity_channel_only(self):
        old=subprocess.check_output(['git','show',BASE+':publication/engine/source_model.py'],cwd=ROOT).decode()
        old=old.replace("    if config.get('artifact_channel', 'PREVIEW') not in ('PREVIEW', 'RELEASE_CANDIDATE'):",
            "    # PUBLICATION is a typeset identity, not a publish operation or approval.\n"
            "    if config.get('artifact_channel', 'PREVIEW') not in ('PREVIEW', 'RELEASE_CANDIDATE', 'PUBLICATION'):")
        accepted='45b305eace0f057420587d685cb3f962f3f0552c'
        self.assertEqual(old,subprocess.check_output(['git','show',accepted+':publication/engine/source_model.py'],cwd=ROOT).decode())
        for path in subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'--','publication/engine','publication/latex'],cwd=ROOT).decode().splitlines():
            if path.endswith('/source_model.py'):continue
            self.assertEqual(subprocess.check_output(['git','show',accepted+':'+path],cwd=ROOT),subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT))

    def test_profile_is_identity_only(self):
        a=json.loads((OLD/'profile.json').read_text());b=json.loads((NEW/'profile.json').read_text())
        a.update(id='cpp-handbook-v1',artifact_channel='PUBLICATION')
        a['views'][0]['status']='PUBLICATION EDITION'
        self.assertEqual(a,b)
        self.assertEqual((OLD/'table-layouts.json').read_bytes(),(NEW/'table-layouts.json').read_bytes())

    def test_template_and_theme_only_replace_identity_text(self):
        a=(OLD/'template.tex').read_text()
        for old,new in [('RELEASE CANDIDATE RC1','PUBLICATION EDITION'),
            ('本件为 v1.0.0 发布候选 RC1，尚未正式发布。','本件为 v1.0.0 正式阅读版。发布身份与校验摘要见随附发布记录。'),
            ('正式阅读版候选 · 尚未发布','正式阅读版 · v1.0.0'),
            ('RC1 待发布决策','出版版本 v1.0.0')]:a=a.replace(old,new)
        self.assertEqual(a,(NEW/'template.tex').read_text())
        a=(OLD/'theme.sty').read_text().replace('C++ handbook pilot, not frozen','C++ handbook publication identity').replace('RELEASE CANDIDATE RC1','PUBLICATION').replace('尚未发布','正式阅读版')
        note=('\n% Source status is historical; publication status lives in the release record.\n'
              r'\renewcommand{\PreviewSourceNote}[1]{\begin{PreviewQuote}\sffamily\fontsize{9}{12}\selectfont SOURCE SNAPSHOT CONTENT · #1\par 以下状态文字保留冻结 Markdown 当时的历史陈述，不是当前出版状态。正式版出版身份及批准范围以随附发布记录为准。\end{PreviewQuote}}'+'\n')
        a=a.replace('\\newunicodechar{↔}{\\ensuremath{\\leftrightarrow}}\n',
                    '\\newunicodechar{↔}{\\ensuremath{\\leftrightarrow}}\n'+note)
        self.assertEqual(a,(NEW/'theme.sty').read_text())

    def test_all_13_adapted_sources_identical(self):
        old=module('rc1_adapter',OLD/'adapter.py');new=module('pub_adapter',NEW/'adapter.py')
        for source in json.loads((NEW/'profile.json').read_text())['sources']:
            with self.subTest(id=source['id']):
                raw=subprocess.check_output(['git','show',source['revision']+':'+source['path']],cwd=ROOT)
                ast=json.loads(subprocess.check_output(['pandoc','-f','markdown-smart','-t','json'],input=raw))
                other=copy.deepcopy(ast)
                self.assertEqual(old.adapt(ast,source,preview.text),new.adapt(other,source,preview.text))
                self.assertEqual(ast,other)

class PreparationOnlyTests(unittest.TestCase):
    setUp=fixtures.ProductTests.setUp
    tearDown=fixtures.ProductTests.tearDown
    git=fixtures.ProductTests.git
    config=fixtures.ProductTests.config
    prepare=fixtures.ProductTests.prepare
    def test_publication_identity_does_not_publish(self):
        self.config(lambda c:c.update(artifact_channel='PUBLICATION'))
        run,record=self.prepare()
        self.assertEqual(json.loads((run/'result.json').read_text())['status'],'PREPARED')
        self.assertEqual(record['identity']['policy']['publish'],'DISABLED')
        self.assertFalse((self.root/'publication/releases').exists())

if __name__=='__main__':unittest.main(verbosity=2)
