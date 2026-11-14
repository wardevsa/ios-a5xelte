#!/usr/bin/env python3
"""Pruebas de host de ci_check.verdict (T-0022). python3 -I xnu/drop-v2/test/test_ci_check.py"""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deviceday'))
import ci_check as c

OURS, THEIRS = '0337-herolte-drop-v2.patch', '0334-present-wait-asleep.patch'


class V(unittest.TestCase):
    def test_full_name_applied(self):
        self.assertEqual(c.verdict([OURS], [], '0337-herolte-drop-v2')[0], 0)
        self.assertEqual(c.verdict([OURS], [], OURS)[0], 0)

    def test_other_series_same_number_is_not_a_false_applied(self):
        # el nuestro se salta y el de upstream se aplica: con prefijo diría "aplicado"
        code, lines = c.verdict([THEIRS], [(OURS, 'does not apply')], '0337-herolte-drop-v2')
        self.assertEqual(code, 1, lines)
        self.assertIn('SALTADO', lines[0])

    def test_absent_from_log_when_only_other_with_same_number(self):
        code, lines = c.verdict([THEIRS], [], '0337-herolte-drop-v2')
        self.assertEqual(code, 1); self.assertIn(THEIRS[:-6], lines[0])

    def test_bare_number_is_rejected_as_ambiguous(self):
        for w in ('0334', '0334-'):
            code, lines = c.verdict([OURS, THEIRS], [], w)
            self.assertEqual(code, 2, w); self.assertIn('incompleto', lines[0])

    def test_applied_and_skipped_fails(self):
        self.assertEqual(c.verdict([OURS], [(OURS, 'x')], OURS)[0], 1)

    def test_nothing_in_log(self):
        self.assertEqual(c.verdict([], [], OURS)[0], 1)


if __name__ == '__main__':
    unittest.main()
