"""v2 source/profile/view contracts; no PDF compilation in this suite."""
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'engine'))
import pub
import preview
import source_model
from links import Resolver
spec = importlib.util.spec_from_file_location('isolation', HERE / 'test-publication-isolation.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


class ProductTests(unittest.TestCase):
    setUp = base.IsolationTests.setUp
    tearDown = base.IsolationTests.tearDown
    git = base.IsolationTests.git

    def config(self, change=None):
        path = self.root / 'publication/profiles/fixture/profile.json'
        value = json.loads(path.read_text())
        if change:
            change(value)
            path.write_text(json.dumps(value))
        return value

    def prepare(self):
        outcome = pub.prepare(self.root, 'fixture')
        run = Path(outcome['path'])
        return run, json.loads((run / 'run.json').read_text())

    def test_nested_source_outside_profile_preserves_canonical_identity(self):
        (self.root / 'content/nested').mkdir(parents=True)
        raw = (self.root / '00-fixture.md').read_bytes()
        (self.root / 'content/nested/chapter.md').write_bytes(raw)
        self.config(lambda c: c['sources'][0].update(path='content/nested/chapter.md'))
        run, record = self.prepare()
        identity = record['identity']['publication']['sources'][0]
        self.assertEqual(identity['path'], 'content/nested/chapter.md')
        self.assertEqual((run / 'inputs/sources/content/nested/chapter.md').read_bytes(), raw)

    def test_immutable_revision_ignores_worktree_and_later_head(self):
        commit = self.git('rev-parse', 'HEAD').decode().strip()
        old = (self.root / '00-fixture.md').read_bytes()
        self.config(lambda c: c['sources'][0].update(revision=commit))
        (self.root / '00-fixture.md').write_text('not the frozen bytes')
        self.git('add', '.')
        self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                 '-c','commit.gpgsign=false','-c','core.hooksPath=/dev/null','commit','-qm','later')
        run, record = self.prepare()
        identity = record['identity']['publication']['sources'][0]
        self.assertEqual(identity['commit'], commit)
        self.assertEqual((run / 'inputs' / identity['snapshot_path']).read_bytes(), old)
        source_model.verify_live_inputs(run, self.root, pub)

    def test_branch_or_short_revision_is_rejected(self):
        for revision in ('HEAD', 'main', '8f479de'):
            self.config(lambda c: c['sources'][0].update(revision=revision))
            with self.assertRaises(pub.PreparationError):
                self.prepare()

    def test_symlink_git_source_is_rejected(self):
        (self.root / 'link.md').symlink_to('00-fixture.md')
        self.git('add','link.md')
        self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                 '-c','commit.gpgsign=false','-c','core.hooksPath=/dev/null','commit','-qm','link')
        commit=self.git('rev-parse','HEAD').decode().strip()
        self.config(lambda c: c['sources'][0].update(path='link.md',revision=commit))
        with self.assertRaises(pub.PreparationError): self.prepare()

    def test_source_path_traversal_is_rejected(self):
        for path in ('../outside.md','/tmp/source.md','nested/../00-fixture.md'):
            self.config(lambda c: c['sources'][0].update(path=path))
            with self.assertRaises(pub.PreparationError): self.prepare()

    def test_profile_bytes_alone_change_identity(self):
        context=pub.git_context(self.root)
        with mock.patch.object(pub,'git_context',return_value=context):
            _, first=self.prepare()
            theme=self.root/'publication/profiles/fixture/theme.sty'
            theme.write_text(theme.read_text()+'\n% changed profile only\n')
            _, second=self.prepare()
        self.assertNotEqual(first['build_id'],second['build_id'])
        self.assertEqual(first['identity']['publication']['sources'],second['identity']['publication']['sources'])

    def test_different_profile_same_markdown_changes_identity(self):
        shutil.copytree(self.root/'publication/profiles/fixture',self.root/'publication/profiles/alternate')
        path=self.root/'publication/profiles/alternate/profile.json'
        value=json.loads(path.read_text()); value['id']='alternate'; path.write_text(json.dumps(value))
        first=pub.prepare(self.root,'fixture'); second=pub.prepare(self.root,'alternate')
        self.assertNotEqual(first['build_id'],second['build_id'])

    def test_profile_drift_after_preparation_refused(self):
        run,_=self.prepare()
        self.config(lambda c:c.update(toc_depth=2))
        with self.assertRaisesRegex(pub.PreparationError,'publication input drift'):
            source_model.verify_live_inputs(run,self.root,pub)
        self.assertFalse((run/'preview-result.json').exists())

    def test_profile_drift_during_prepare_refused(self):
        original=pub.write_bytes
        def drift(fd,name,data):
            original(fd,name,data)
            if name=='run.json': self.config(lambda c:c.update(toc_depth=2))
        with mock.patch.object(pub,'write_bytes',side_effect=drift), self.assertRaises(pub.PreparationError): self.prepare()

    def test_views_select_same_source_without_duplication(self):
        first=pub.prepare(self.root,'fixture',['TEST-0'])
        second=pub.prepare(self.root,'fixture',['ESD-HANDBOOK'])
        a=json.loads((Path(first['path'])/'run.json').read_text())['identity']['publication']
        b=json.loads((Path(second['path'])/'run.json').read_text())['identity']['publication']
        self.assertEqual(a['sources'],b['sources'])
        self.assertNotEqual(first['build_id'],second['build_id'])
        with self.assertRaises(pub.PreparationError): pub.prepare(self.root,'fixture',['UNKNOWN'])

    def test_combined_and_standalone_reference_policy(self):
        docs=[{'id':f'D{i}','relative_path':f'book/{i}.md','source_href':f'https://example.org/frozen/{i}.md',
               'anchors':{'section':f'D{i}-s'},'aliases':{f'explicit-{i}':'section'},'first_anchor':f'D{i}-s'} for i in range(2)]
        combined=Resolver(docs,docs,'https://example.org',self.root,{},pub,preview.command,self.root,preview.walk)
        single=Resolver(docs,docs[:1],'https://example.org',self.root,{},pub,preview.command,self.root,preview.walk)
        self.assertEqual(combined.resolve('1.md#explicit-1',docs[0]),'#explicit-1')
        self.assertEqual(single.resolve('1.md#explicit-1',docs[0]),'https://example.org/frozen/1.md#explicit-1')
        with self.assertRaises(RuntimeError): combined.resolve('1.md#missing',docs[0])

    def test_unresolved_repository_link_rejected(self):
        doc={'id':'D','relative_path':'00-fixture.md','source':{'commit':self.git('rev-parse','HEAD').decode().strip()}}
        r=Resolver([],[],'https://example.org',self.root,{},pub,preview.command,self.root,preview.walk)
        with self.assertRaises(pub.PreparationError): r.resolve('missing.md',doc)


class AdapterTests(unittest.TestCase):
    def load(self,name):
        spec=importlib.util.spec_from_file_location('adapter_'+name,HERE.parent/'profiles'/name/'adapter.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

    def parse(self,raw):
        return json.loads(subprocess.check_output(['pandoc','-f','markdown-smart','-t','json'],input=raw))

    def test_frozen_handbook_anchors_and_code_are_preserved(self):
        repo=HERE.parents[1]; commit='8f479deaf660533b2ad82e1f721eb41a363112b6'
        config=json.loads((HERE.parent/'profiles/cpp-handbook/profile.json').read_text())
        for source in config['sources']:
            raw=subprocess.check_output(['git','-C',str(repo),'cat-file','blob',commit+':'+source['path']])
            ast=self.parse(raw)
            code=[n['c'][1] for n in preview.walk(ast['blocks']) if n.get('t')=='CodeBlock']
            meta,aliases,semantic=self.load('cpp-handbook').adapt(ast,source,preview.text)
            self.assertEqual(set(aliases),set(re.findall(r'<a id="([^"]+)"></a>',raw.decode())))
            self.assertEqual(code,[n['c'][1] for n in preview.walk(ast['blocks']) if n.get('t')=='CodeBlock'])
            self.assertEqual(meta['document_id'],source['id'])
            self.assertEqual(sum(o['kind']=='lab' for o in semantic),len(re.findall(r'<!-- h-lab ',raw.decode())))

    def test_product_metadata_cannot_be_confused(self):
        prose=b'# G6 \xc2\xb7 Title\n\n**\xe7\x89\x88\xe6\x9c\xac\xef\xbc\x9a** 1.1.1 \xc2\xb7 test\n'
        with self.assertRaises(RuntimeError): self.load('esd').adapt(self.parse(prose),{'id':'G6'},preview.text)
        front=b'---\ntitle: Test\ndocument_id: ESD\nstatus: DRAFT\nversion: 1\n---\n# Title\n'
        with self.assertRaises(RuntimeError): self.load('cpp-handbook').adapt(self.parse(front),{'id':'G6','version':'1.1.1'},preview.text)

    def test_unknown_raw_html_is_not_silently_removed(self):
        raw='# G6 · Title\n\n**版本：** 1.1.1 · test\n\n<script>bad</script>\n'
        with self.assertRaises(RuntimeError): self.load('cpp-handbook').adapt(self.parse(raw.encode()),{'id':'G6','version':'1.1.1'},preview.text)


if __name__=='__main__': unittest.main(verbosity=2)
