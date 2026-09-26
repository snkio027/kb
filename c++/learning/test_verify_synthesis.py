import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import verify_synthesis as v

ROOT = Path(__file__).resolve().parents[1]


def step(out='', err='', code=0, timeout=False):
    return dict(stdout=out, stderr=err, returncode=code, timed_out=timeout)


class SynthesisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = [(p.name, p.read_text()) for p in sorted(ROOT.glob('g1[01]-*.md'))]
        cls.labs = v.extract(cls.documents)

    def test_source_identity_and_completeness(self):
        self.assertEqual([x['id'] for x in self.labs], ['G10-R1', 'G11-C1'])
        self.assertEqual([len(x['files']) for x in self.labs], [12, 5])

    def test_duplicate_lab_rejected(self):
        with self.assertRaises(ValueError):
            v.extract(self.documents + self.documents)

    def test_orphan_source_rejected(self):
        name, text = self.documents[0]
        with self.assertRaises(ValueError):
            v.extract([(name, '<!-- s-file {"path":"x.cpp"} -->\n' + text),
                       self.documents[1]])

    def test_unsafe_source_paths_rejected(self):
        name, text = self.documents[0]
        for target in ('../outside.cpp', '/outside.cpp', 'a/./b.cpp', 'a//b.cpp'):
            with self.subTest(path=target), self.assertRaises(ValueError):
                v.extract([(name, text.replace('"include/flow/runtime.hpp"',
                                              '"' + target + '"', 1)),
                           self.documents[1]])

    def test_unknown_mode_rejected(self):
        name, text = self.documents[0]
        with self.assertRaises(ValueError):
            v.extract([(name, text.replace('"mode":"runtime"', '"mode":"arbitrary"')),
                       self.documents[1]])

    def test_mutations_are_distinct_and_do_not_edit_original(self):
        before = copy.deepcopy(self.labs)
        variants = v.mutations(self.labs)
        self.assertEqual(before, self.labs)
        self.assertEqual(len(variants), 4)
        self.assertEqual([x['expected_code'] for x in variants], [10, 21, 31, 30])

    def test_mutation_requires_one_target(self):
        lab = self.labs[0]
        with self.assertRaises(ValueError):
            v.mutation(lab, 'bad', 'src/runtime.cpp', 'not present', 'x', 1)

    def test_mutation_oracle_rejects_success_crash_timeout_and_wrong_failure(self):
        lab = v.mutations(self.labs)[0]
        for run in (step(), step(err='invariant=10\n', code=-6),
                    step(err='invariant=10\n', code=10, timeout=True),
                    step(err='other\n', code=10), step(err='invariant=11\n', code=11)):
            self.assertFalse(v.mutation_rejected(run, lab))
        self.assertTrue(v.mutation_rejected(step(err='invariant=10\n', code=10), lab))

    def test_mixed_generation_requires_prior_allocation_result(self):
        lab = v.mutations(self.labs)[2]
        self.assertFalse(v.mutation_rejected(step(err='control invariant=31\n', code=31), lab))
        self.assertTrue(v.mutation_rejected(step(
            'control verified; tracked_cpp_allocations=0\n', 'control invariant=31\n', 31), lab))

    def test_compile_failure_does_not_count_as_mutation_detection(self):
        with tempfile.TemporaryDirectory() as name, \
                patch.object(v.Session, 'build', return_value=False), \
                patch.object(v.Session, 'run') as run:
            result = v.verify(v.mutations(self.labs)[0], '/not/a/compiler',
                              Path(name) / 'attempt', {}, {})
            run.assert_not_called()
            self.assertFalse(any('rejected' in e['claim'] for e in result['evidence']))

    @staticmethod
    def benchmark(seconds='0.01'):
        return '\n'.join(f'{w},{c},{r},2000,{seconds},384000'
                         for w in (1, 2, 4) for c in (1, 16) for r in range(3))

    def test_measurement_accepts_slow_results_without_speed_threshold(self):
        self.assertEqual(len(v.runtime_observation(self.benchmark('999999'))), 18)

    def test_measurement_rejects_bad_checksum_missing_or_duplicate(self):
        text = self.benchmark()
        for broken in (text.replace('384000', '0', 1),
                       '\n'.join(text.splitlines()[:-1]), text + '\n' + text.splitlines()[0]):
            with self.assertRaises(ValueError):
                v.runtime_observation(broken)

    def test_measurement_rejects_nonfinite_or_nonpositive_time(self):
        for value in ('nan', 'inf', '-1', '0'):
            with self.assertRaises(ValueError):
                v.runtime_observation(self.benchmark(value))

    @staticmethod
    def timing(wake=2_000_000, execution=100):
        missed = int(wake + execution > 1_000_000)
        return 'position=1\n' + '\n'.join(
            f'{i},{wake},{execution},{missed}' for i in range(1000))

    def test_timing_records_all_deadline_misses_without_claiming_failure(self):
        result = v.timing_observation(self.timing())
        self.assertEqual(result['deadline_misses'], 1000)
        self.assertEqual(result['guarantee'], 'timing observation on this machine')

    def test_timing_requires_order_complete_sample_and_consistent_flags(self):
        text = self.timing()
        broken = [text.replace('0,2000000,100,1', '0,2000000,100,0', 1),
                  text.replace('0,2000000', '1,2000000', 1),
                  '\n'.join(text.splitlines()[:-1]), text.replace('position=1', 'position=nan')]
        for value in broken:
            with self.assertRaises(ValueError):
                v.timing_observation(value)

    def test_sanitizer_environments_do_not_cross_override_exit_codes(self):
        base = {'ASAN_OPTIONS': 'exitcode=1', 'UBSAN_OPTIONS': 'exitcode=3',
                'TSAN_OPTIONS': 'exitcode=4', 'KEEP': 'yes'}
        env = v.sanitizer_environment(base, 'tsan')
        self.assertNotIn('ASAN_OPTIONS', env)
        self.assertNotIn('UBSAN_OPTIONS', env)
        self.assertIn('abort_on_error=0', env['TSAN_OPTIONS'])
        self.assertIn('exitcode=66', env['TSAN_OPTIONS'])
        self.assertEqual(env['KEEP'], 'yes')
        self.assertEqual(base['UBSAN_OPTIONS'], 'exitcode=3')

    def test_combined_memory_runtime_uses_consistent_exit_options(self):
        env = v.sanitizer_environment({}, 'asan_ubsan')
        for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS'):
            self.assertIn('exitcode=86', env[key])
            self.assertIn('abort_on_error=0', env[key])
        self.assertNotIn('TSAN_OPTIONS', env)


if __name__ == '__main__':
    unittest.main()
