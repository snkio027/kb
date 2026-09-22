#!/usr/bin/env python3
"""Candidate destination/commit failure regressions; no PDF compilation."""
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import candidate
import pub

spec = importlib.util.spec_from_file_location('isolation', HERE / 'test-publication-isolation.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


class CandidateIsolationTests(unittest.TestCase):
    git = base.IsolationTests.git
    tearDown = base.IsolationTests.tearDown

    def setUp(self):
        base.IsolationTests.setUp(self)
        self.relative = 'build/preview/' + 'a' * 64 + '/' + 'b' * 32
        (self.root / self.relative).mkdir(parents=True)
        self.files = {'output/pdf/test.pdf': b'fixture', 'output/source/test.md': b'raw source'}
        self.source = {'build_id': 'a' * 64, 'attempt_id': 'b' * 32, 'identity': {'source': {'commit': 'c' * 40, 'dirty': True}}}
        self.ready = {'execution_id': 'd' * 64}

    def freeze(self, side_effect=None):
        with mock.patch.object(candidate, 'payload', return_value=(self.files, self.source, self.ready), side_effect=side_effect):
            return candidate.freeze(self.root, self.relative, pub)

    def terminals(self):
        return [json.loads(p.read_text()) for p in (self.root / 'build/candidate').glob('*/*/candidate-result.json')]

    def test_success_and_repeat_keep_dist_and_previous_candidate(self):
        first = self.freeze()
        frozen = base.tree_bytes(Path(first['path']))
        second = self.freeze()
        self.assertNotEqual(first['path'], second['path'])
        self.assertEqual(first['candidate_id'], second['candidate_id'])
        self.assertEqual(frozen, base.tree_bytes(Path(first['path'])))
        self.assertFalse(self.terminals()[0]['formal_release'])

    def test_candidate_directory_symlink_rejected(self):
        (self.root / 'build/candidate').symlink_to(self.dist, target_is_directory=True)
        with self.assertRaises(OSError):
            self.freeze()

    def test_preview_directory_symlink_rejected(self):
        linked = self.root / ('build/preview/' + 'e' * 64)
        linked.symlink_to(self.dist, target_is_directory=True)
        with self.assertRaises(OSError):
            candidate.freeze(self.root, str(linked.relative_to(self.root)) + '/' + 'b' * 32, pub)

    def test_unsafe_and_absolute_preview_paths_rejected(self):
        for path in ('../dist', '/tmp/run', self.relative + '/..'):
            with self.assertRaises(pub.PreparationError):
                candidate.freeze(self.root, path, pub)

    def test_source_drift_never_commits_success(self):
        first = (self.files, self.source, self.ready)
        second = ({**self.files, 'extra': b'changed'}, self.source, self.ready)
        with self.assertRaisesRegex(pub.PreparationError, 'changed during'):
            self.freeze(side_effect=[first, second])
        self.assertEqual(self.terminals()[0]['status'], 'FAILED')

    def test_cancel_during_copy_commits_cancelled_not_success(self):
        write = pub.write_bytes
        def interrupted(fd, name, data):
            if name.endswith('test.md'):
                raise pub.Cancelled(15)
            return write(fd, name, data)
        with mock.patch.object(pub, 'write_bytes', side_effect=interrupted), self.assertRaises(pub.Cancelled):
            self.freeze()
        self.assertEqual(self.terminals()[0]['status'], 'CANCELLED')

    def test_terminal_fsync_failure_leaves_no_success(self):
        write = pub.write_json
        def fail_terminal(fd, name, value):
            if name.endswith('.pending') and value.get('status') == 'CANDIDATE_PREPARED_FOR_REVIEW':
                with mock.patch.object(pub.os, 'fsync', side_effect=OSError('injected EIO')):
                    return write(fd, name, value)
            return write(fd, name, value)
        with mock.patch.object(pub, 'write_json', side_effect=fail_terminal), self.assertRaises(OSError):
            self.freeze()
        self.assertEqual(self.terminals()[0]['status'], 'FAILED')

    def test_error_after_commit_retains_same_fact(self):
        link = os.link
        def committed(*args, **kwargs):
            link(*args, **kwargs)
            raise OSError('injected after link')
        with mock.patch.object(pub.os, 'link', side_effect=committed):
            result = self.freeze()
        self.assertEqual(result['status'], 'CANDIDATE_PREPARED_FOR_REVIEW')
        self.assertEqual(self.terminals()[0]['status'], result['status'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
