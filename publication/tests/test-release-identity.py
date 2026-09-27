#!/usr/bin/env python3
"""RC1 identity-only extension: source/layout invariants and safe output names."""
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'publication/engine'))
import pub
import preview

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

base = module('product_fixtures', ROOT/'publication/tests/test-products.py')
OLD = ROOT/'publication/profiles/cpp-handbook-full'
NEW = ROOT/'publication/profiles/cpp-handbook-rc1'

class IdentityTests(unittest.TestCase):
    def test_engine_extension_is_exactly_the_reviewed_identity_patch(self):
        # Fixed file digests bind the small diff against f288051. Any later
        # modification must deliberately re-review this bounded exception.
        expected = {
            'preview.py': '2bea5d17da01e5e9694a15aa3d55a3d8c175e67547891c37c0394185a0895b0b',
            'source_model.py': '96531e5aca91ba1823b331cd99b9040934000739ab5095028579f301b532e6df',
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT/'publication/engine'/name).read_bytes()).hexdigest(), digest)

    def test_profile_diff_is_identity_only(self):
        old = json.loads((OLD/'profile.json').read_text())
        new = json.loads((NEW/'profile.json').read_text())
        old.update(id='cpp-handbook-rc1', artifact_channel='RELEASE_CANDIDATE')
        old['dependencies'].append('publication/profiles/cpp-handbook-full/adapter.py')
        old['views'][0].update(subtitle='Modern C++ Engineering Handbook', version='1.0.0',
            status='RELEASE CANDIDATE RC1', filename='Modern-Cpp-Engineering-Handbook-v1.0.0.pdf')
        self.assertEqual(old, new)
        self.assertEqual((OLD/'table-layouts.json').read_bytes(), (NEW/'table-layouts.json').read_bytes())

    def test_template_and_theme_preserve_dimensions_and_mechanics(self):
        template = (OLD/'template.tex').read_text()
        for a,b in [
            ('PREVIEW / DRAFT','RELEASE CANDIDATE RC1'),
            ('本件仅供阅读与评审，未获正式发布批准。','本件为 v1.0.0 发布候选 RC1，尚未正式发布。'),
            ('非权威阅读视图','正式阅读版候选 · 尚未发布'),
            ('Visual Profile v1.0，已冻结；全书制品待审核','Visual Profile v1.0，已冻结；RC1 待发布决策')]:
            template = template.replace(a,b)
        self.assertEqual(template, (NEW/'template.tex').read_text())
        old = (OLD/'theme.sty').read_text()
        new = (NEW/'theme.sty').read_text()
        self.assertTrue(new.startswith(old))
        extra = new[len(old):]
        self.assertNotRegex(extra, r'\\(?:setlength|geometry|newcommand|renewcommand|definecolor|needspace|clearpage)')
        self.assertEqual(extra.count('\\fancyfoot'),3)
        self.assertEqual(extra.count('\\fancypagestyle'),1)

    def test_all_source_asts_aliases_and_semantics_unchanged(self):
        old = module('accepted_adapter', OLD/'adapter.py')
        new = module('rc_adapter', NEW/'adapter.py')
        for source in json.loads((NEW/'profile.json').read_text())['sources']:
            with self.subTest(document=source['id']):
                raw = subprocess.check_output(['git','cat-file','blob',source['revision']+':'+source['path']],cwd=ROOT)
                ast = json.loads(subprocess.check_output(['pandoc','-f','markdown-smart','-t','json'],input=raw))
                other = copy.deepcopy(ast)
                a, aliases, semantic = old.adapt(ast, source, preview.text)
                b, aliases2, semantic2 = new.adapt(other, source, preview.text)
                a.update(status='ACCEPTED CONTENT', subtitle='Professional Handbook')
                self.assertEqual(a,b)
                self.assertEqual((ast,aliases,semantic),(other,aliases2,semantic2))

class SafeIdentityTests(unittest.TestCase):
    setUp = base.ProductTests.setUp
    tearDown = base.ProductTests.tearDown
    git = base.ProductTests.git
    config = base.ProductTests.config
    prepare = base.ProductTests.prepare

    def test_unsafe_or_non_pdf_names_rejected(self):
        for name in ('../dist/a.pdf','/tmp/a.pdf','nested/a.pdf','a.txt','.pdf',None,4):
            with self.subTest(name=name):
                self.config(lambda c:c['views'][0].update(filename=name))
                with self.assertRaisesRegex(pub.PreparationError,'artifact filename'):self.prepare()

    def test_casefold_collision_rejected(self):
        self.config(lambda c:c['views'][0].update(filename='Same.pdf'))
        self.config(lambda c:c['views'][1].update(filename='same.pdf'))
        with self.assertRaisesRegex(pub.PreparationError,'artifact filename'):self.prepare()

    def test_release_channel_cannot_be_declared(self):
        for channel in ('RELEASED','BASELINE','',None):
            self.config(lambda c:c.update(artifact_channel=channel))
            with self.assertRaisesRegex(pub.PreparationError,'formal publication stays closed'):self.prepare()

    def test_candidate_identity_is_preparable_not_published(self):
        self.config(lambda c:c.update(artifact_channel='RELEASE_CANDIDATE'))
        self.config(lambda c:c['views'][0].update(filename='Handbook-v1.0.0.pdf'))
        run, record = self.prepare()
        self.assertEqual(json.loads((run/'result.json').read_text())['status'],'PREPARED')
        self.assertFalse((run/'preview-result.json').exists())

if __name__ == '__main__':unittest.main(verbosity=2)
