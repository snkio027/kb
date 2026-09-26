import copy
import unittest
from unittest.mock import patch

import verify_native as n


def step(code=0, stdout='', stderr='', timeout=False):
    return dict(returncode=code, stdout=stdout, stderr=stderr, timed_out=timeout)


class NativeOracles(unittest.TestCase):
    def fixture(self):
        return ('<!-- n-lab {"id":"G8-B1","mode":"symbols"} -->\n'
                '<!-- n-file {"path":"main.cpp"} -->\n' + n.FENCE +
                'cpp\nint main() {}\n' + n.FENCE + '\n')

    def test_extract_exact_source(self):
        lab = n.extract([('test.md', self.fixture())])[0]
        self.assertEqual(lab['files'], {'main.cpp': 'int main() {}\n'})

    def test_unsafe_paths_rejected(self):
        for path in ['../main.cpp', '/main.cpp', 'a/../../b.cpp', 'a//b.cpp', './b.cpp']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                n.extract([('test.md', self.fixture().replace('main.cpp', path))])

    def test_nested_files_supported(self):
        result = n.extract([('test.md', self.fixture().replace('main.cpp', 'src/main.cpp'))])
        self.assertIn('src/main.cpp', result[0]['files'])

    def test_duplicate_lab_rejected(self):
        with self.assertRaises(ValueError):
            n.extract([('test.md', self.fixture() * 2)])

    def test_orphan_file_rejected(self):
        with self.assertRaises(ValueError):
            n.extract([('test.md', self.fixture().split('\n', 1)[1])])

    def test_malformed_or_wrong_mode_rejected(self):
        for text in [self.fixture().replace('n-lab {', 'n-lab !{'),
                     self.fixture().replace('"symbols"', '"run"')]:
            with self.assertRaises(ValueError):
                n.extract([('test.md', text)])

    def test_runtime_requires_exact_result(self):
        self.assertTrue(n.runtime(step(4), code=4))
        for bad in [step(0), step(-11), step(4, stderr='crash'),
                    step(4, timeout=True), step(4, stdout='unexpected')]:
            self.assertFalse(n.runtime(bad, code=4))

    def test_ctest_accepts_both_summaries(self):
        for text in ['100% tests passed, 0 tests failed out of 1',
                     '100% tests passed out of 2']:
            self.assertTrue(n.ctest_ok(step(stdout=text)))

    def test_ctest_requires_nonempty_success(self):
        for bad in [step(stdout='100% tests passed out of 0'),
                    step(stdout='No tests were found!!!'),
                    step(1, '100% tests passed out of 1'),
                    step(0, '100% tests passed out of 1', timeout=True),
                    step(stdout='50% tests passed out of 2')]:
            self.assertFalse(n.ctest_ok(bad))

    def test_negative_requires_target_diagnostic(self):
        pattern = r'(?is)undefined.*native_sum|native_sum.*undefined'
        self.assertTrue(n.diagnosed(step(1, stderr='Undefined symbols: native_sum'), pattern))
        for bad in [step(0, stderr='Undefined symbols: native_sum'),
                    step(-6, stderr='Undefined symbols: native_sum'),
                    step(1, stderr='file not found'), step(1, stderr='undefined other')]:
            self.assertFalse(n.diagnosed(bad, pattern))

    def test_corpus_and_mutations(self):
        documents = [(p.name, p.read_text()) for p in sorted(n.ROOT.glob('g0[89]-*.md'))]
        labs = n.extract(documents)
        before = copy.deepcopy(labs)
        self.assertEqual({l['id'] for l in labs}, set(n.MODES))
        self.assertEqual(sum(len(l['files']) for l in labs), 20)
        variants = n.mutations(labs)
        self.assertEqual(len(variants), 2)
        self.assertEqual(labs, before)
        self.assertIn('*count = size ? 1 : 0;', variants[0]['files']['decoder.cpp'])
        self.assertNotIn('DEPENDS value.txt', variants[1]['files']['CMakeLists.txt'])

    def test_mutation_site_drift_rejected(self):
        docs = [(p.name, p.read_text()) for p in sorted(n.ROOT.glob('g0[89]-*.md'))]
        labs = n.extract(docs)
        labs[1]['files']['decoder.cpp'] += '\n*count = size;\n'
        with self.assertRaises(ValueError):
            n.mutations(labs)

    def test_search_environment_is_explicit(self):
        with patch.dict(n.os.environ, {'CPATH': '/accidental', 'CMAKE_PREFIX_PATH': '/wrong',
                                      'DYLD_LIBRARY_PATH': '/wrong', 'PATH': '/tools'}, clear=True):
            self.assertEqual(n.environment(), {'PATH': '/tools'})


if __name__ == '__main__':
    unittest.main()
