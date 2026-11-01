import unittest

import numpy as np

from weather.models import LogisticRegression, RidgeRegression, brier, mae, roc_auc


class RidgeTest(unittest.TestCase):
    def test_matches_least_squares_without_penalty(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(200, 4))
        y = X @ np.array([2.0, -1.0, 0.5, 3.0]) + 7 + rng.normal(scale=0.1, size=200)
        model = RidgeRegression(alpha=0.0).fit(X, y)
        design = np.column_stack([np.ones(200), X])
        expected, *_ = np.linalg.lstsq(design, y, rcond=None)
        self.assertTrue(np.allclose(model.predict(X), design @ expected))

    def test_penalty_shrinks_coefficients(self):
        rng = np.random.default_rng(1)
        X = rng.normal(size=(100, 3))
        y = X @ np.array([1.0, 2.0, 3.0])
        small = RidgeRegression(alpha=0.1).fit(X, y)
        large = RidgeRegression(alpha=1000).fit(X, y)
        self.assertLess(np.abs(large.coef).sum(), np.abs(small.coef).sum())


class LogisticTest(unittest.TestCase):
    def test_learns_a_simple_rule(self):
        rng = np.random.default_rng(2)
        X = rng.normal(size=(500, 2))
        y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(float)
        p = LogisticRegression(alpha=0.01, steps=3000).fit(X, y).predict_proba(X)
        self.assertGreater(((p > 0.5) == y).mean(), 0.95)
        self.assertGreater(roc_auc(y, p), 0.98)


class MetricsTest(unittest.TestCase):
    def test_metrics(self):
        y = np.array([0.0, 0.0, 1.0, 1.0])
        self.assertEqual(roc_auc(y, np.array([0.1, 0.2, 0.8, 0.9])), 1.0)
        self.assertEqual(roc_auc(y, np.array([0.9, 0.8, 0.2, 0.1])), 0.0)
        self.assertAlmostEqual(brier(y, np.array([0.0, 0.0, 1.0, 1.0])), 0.0)
        self.assertAlmostEqual(mae(np.array([1.0, 3.0]), np.array([2.0, 1.0])), 1.5)


if __name__ == "__main__":
    unittest.main()
