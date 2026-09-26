import copy
import unittest

import verify_handbook as h


def step(code=0, stderr='', timeout=False):
    return dict(returncode=code, stdout='', stderr=stderr, timed_out=timeout)


class Oracles(unittest.TestCase):
    def test_diagnostic_is_not_any_failure(self):
        self.assertTrue(h.diagnosed(step(1, 'constraints not satisfied'), 'constraints not satisfied'))
        for s in [step(0, 'constraints not satisfied'), step(1, 'file not found'),
                  step(-11, 'constraints not satisfied'), step(1, 'constraints not satisfied', True)]:
            self.assertFalse(h.diagnosed(s, 'constraints not satisfied'))

    def test_tsan_requires_code_and_target(self):
        self.assertTrue(h.tsan_detected(step(66, 'WARNING: ThreadSanitizer: data race')))
        for s in [step(0, 'ThreadSanitizer: data race'), step(66, 'unexpected memory mapping'),
                  step(-11, 'ThreadSanitizer: data race'), step(66, 'ThreadSanitizer: data race', True)]:
            self.assertFalse(h.tsan_detected(s))

    def test_layout_is_observed_not_fixed_size(self):
        import json
        for size in (12, 16, 32):
            h.observations('G6-M1', json.dumps(dict(size=size, align=4,
                id_offset=4, value_offset=8, reordered_size=size)))
        with self.assertRaises(ValueError):
            h.observations('G6-M1', '{}')

    def benchmark(self):
        rows = []
        for n in (1024, 65536, 1048576):
            q, r = divmod(n, 251)
            for trial in range(7):
                for layout in ('aos', 'soa'):
                    rows.append(dict(n=n, trial=trial, layout=layout, elapsed_ns=0,
                        checksum=q * 250 * 251 // 2 + r * (r - 1) // 2))
        return rows

    def encode(self, rows):
        import json
        return '\n'.join(json.dumps(row) for row in rows)

    def test_no_speed_threshold(self):
        rows = self.benchmark()
        h.observations('G6-M3', self.encode(rows))
        for row in rows:
            row['elapsed_ns'] = 10**12 if row['layout'] == 'soa' else 1
        h.observations('G6-M3', self.encode(rows))

    def test_benchmark_must_be_complete(self):
        rows = self.benchmark()
        for bad in [rows[:-1], rows + [rows[0]]]:
            with self.assertRaises(ValueError):
                h.observations('G6-M3', self.encode(bad))

    def test_benchmark_must_check_value(self):
        rows = self.benchmark()
        for field, value in [('checksum', 0), ('elapsed_ns', -1), ('layout', 'unknown')]:
            bad = copy.deepcopy(rows)
            bad[0][field] = value
            with self.assertRaises(ValueError):
                h.observations('G6-M3', self.encode(bad))

    def test_allocation_balance(self):
        with self.assertRaises(ValueError):
            h.observations('G6-M2', '{"allocations":2,"deallocations":1,"requested_bytes":16}')

    def test_extraction(self):
        doc = ('<!-- h-lab {"id":"G5-C1","mode":"run"} -->\n'
               '<!-- h-file {"path":"main.cpp"} -->\n```cpp\nint main() {}\n```\n')
        self.assertEqual(h.extract([('test.md', doc)])[0]['files']['main.cpp'], 'int main() {}\n')
        for bad in [doc + doc, doc.replace('main.cpp', '../main.cpp'),
                    doc.replace('"run"', '"invalid"'), doc.replace('h-lab {', 'h-lab !{')]:
            with self.assertRaises(ValueError):
                h.extract([('test.md', bad)])

    def test_current_corpus(self):
        docs = [(p.name, p.read_text()) for p in sorted(h.ROOT.glob('g0[5-7]-*.md'))]
        labs = h.extract(docs)
        self.assertEqual(len(labs), 11)
        self.assertEqual([sum(l['id'].startswith(f'G{i}-') for l in labs)
                          for i in (5, 6, 7)], [5, 3, 3])

    def test_concurrency_needs_oracle(self):
        doc = ('<!-- h-lab {"id":"G7-D1","mode":"concurrency"} -->\n'
               '<!-- h-file {"path":"main.cpp"} -->\n```cpp\nint main() {}\n```\n')
        with self.assertRaises(ValueError):
            h.extract([('test.md', doc)])


if __name__ == '__main__':
    unittest.main()
