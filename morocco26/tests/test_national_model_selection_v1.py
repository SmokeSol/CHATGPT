import importlib.util
import math
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'select_national_model_2026_v1.py'
spec = importlib.util.spec_from_file_location('national_v1', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class NationalModelSelectionV1Tests(unittest.TestCase):
    def test_simplex_projection(self):
        x = mod.project_simplex([1.2, -0.1, -0.1])
        self.assertAlmostEqual(sum(x), 1.0, places=12)
        self.assertTrue(all(v >= 0 for v in x))

    def test_history_complete(self):
        h = mod.load_history()
        self.assertEqual(sorted(h), mod.YEARS)
        for y, p in h.items():
            self.assertEqual(len(p), 9)
            self.assertAlmostEqual(sum(p), 1.0, places=10)
            self.assertTrue(all(math.isfinite(v) and v >= 0 for v in p))

    def test_four_folds_and_positive_2026(self):
        x = mod.run()
        self.assertEqual(len(x['scored_folds']), 4)
        self.assertIn(x['winner'], mod.MODELS)
        p = x['forecast_2026']['point_share']
        self.assertAlmostEqual(sum(p.values()), 1.0, places=10)
        self.assertTrue(all(v > 0 for v in p.values()))

    def test_diagnostics_do_not_select(self):
        x = mod.run()
        for d in x['diagnostic_sensitivities'].values():
            self.assertEqual(d['selection_role'], 'DIAGNOSTIC_ONLY_NO_POST_HOC_MODEL_CHANGE')


if __name__ == '__main__':
    unittest.main()
