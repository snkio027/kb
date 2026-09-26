"""Regression tests for extraction and acceptance oracles, not C++ semantics."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

import verify_g as runner


def document(lab=None, path='main.cpp'):
    lab = lab or {'id': 'G0-L1', 'mode': 'run', 'stdout': ''}
    return ('<!-- g-lab ' + json.dumps(lab) + ' -->\n' +
            '<!-- g-file ' + json.dumps({'path': path}) + ' -->\n' +
            '```cpp\nint main() { return 0; }\n```\n')


def result(code, stderr='', timeout=False):
    return dict(returncode=code, stdout='', stderr=stderr, timed_out=timeout)


class Extraction(unittest.TestCase):
    def test_source_bytes_include_final_newline(self):
        lab = runner.extract([('sample.md', document())])[0]
        self.assertEqual(lab['files']['main.cpp'], 'int main() { return 0; }\n')

    def test_duplicate_id(self):
        with self.assertRaises(ValueError):
            runner.extract([('sample.md', document() * 2)])

    def test_unsafe_file_path(self):
        with self.assertRaises(ValueError):
            runner.extract([('sample.md', document(path='../main.cpp'))])

    def test_orphan_file(self):
        with self.assertRaises(ValueError):
            runner.extract([('sample.md', document().split('-->\n', 1)[1])])

    def test_unsupported_mode(self):
        with self.assertRaises(ValueError):
            runner.extract([('sample.md', document({'id': 'G0-L1', 'mode': 'shell'}))])

    def test_missing_negative_oracle(self):
        with self.assertRaises(ValueError):
            runner.extract([('sample.md', document({'id': 'G0-L1', 'mode': 'compile_fail'}))])

    def test_current_corpus(self):
        docs = [(p.name, p.read_text()) for p in sorted(runner.ROOT.glob('g0[0-4]-*.md'))]
        labs = runner.extract(docs)
        self.assertEqual(len(labs), 13)
        self.assertEqual(len(runner.mutations(labs)), 2)


class Oracles(unittest.TestCase):
    def test_positive_needs_correct_exit(self):
        self.assertTrue(runner.clean_exit(result(0)))
        self.assertFalse(runner.clean_exit(result(1)))

    def test_negative_needs_diagnostic(self):
        self.assertTrue(runner.diagnosed(result(1, 'deleted constructor'), 'deleted'))
        self.assertFalse(runner.diagnosed(result(1, 'missing header'), 'deleted'))

    def test_success_does_not_count_as_rejection(self):
        self.assertFalse(runner.diagnosed(result(0, 'deleted'), 'deleted'))

    def test_signal_does_not_count_as_rejection(self):
        self.assertFalse(runner.diagnosed(result(-6, 'deleted'), 'deleted'))

    def test_timeout_does_not_count_as_rejection(self):
        self.assertFalse(runner.diagnosed(result(1, 'deleted', True), 'deleted'))
        self.assertFalse(runner.clean_exit(result(0, timeout=True)))

    def test_real_child_timeout(self):
        with tempfile.TemporaryDirectory(prefix='kb-g-runner-test-') as tmp:
            observed = runner.command([sys.executable, '-c', 'import time; time.sleep(10)'],
                                      Path(tmp), timeout=0.1)
            self.assertTrue(observed['timed_out'])
            self.assertFalse(runner.clean_exit(observed))


if __name__ == '__main__':
    unittest.main()
