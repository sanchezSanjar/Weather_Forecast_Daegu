"""Regression and classification written from scratch with numpy."""
import numpy as np


class Standardizer:
    def fit(self, X):
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0)
        self.std[self.std == 0] = 1.0
        return self

    def transform(self, X):
        return (X - self.mean) / self.std


class RidgeRegression:
    """Linear regression with L2 penalty, closed form: w = (X'X + aI)^-1 X'y. Intercept is not penalised."""

    def __init__(self, alpha=1.0):
        self.alpha = alpha

    def fit(self, X, y):
        self.scaler = Standardizer().fit(X)
        Z = self.scaler.transform(X)
        self.intercept = y.mean()
        penalty = self.alpha * np.eye(Z.shape[1])
        self.coef = np.linalg.solve(Z.T @ Z + penalty, Z.T @ (y - self.intercept))
        return self

    def predict(self, X):
        return self.scaler.transform(X) @ self.coef + self.intercept


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


class LogisticRegression:
    """Binary logistic regression trained with full-batch gradient descent and L2 penalty."""

    def __init__(self, alpha=1.0, learning_rate=0.5, steps=2000):
        self.alpha, self.learning_rate, self.steps = alpha, learning_rate, steps

    def fit(self, X, y):
        self.scaler = Standardizer().fit(X)
        Z = self.scaler.transform(X)
        n, d = Z.shape
        self.coef, self.intercept = np.zeros(d), np.log(y.mean() / (1 - y.mean()))
        for _ in range(self.steps):
            error = sigmoid(Z @ self.coef + self.intercept) - y
            self.coef -= self.learning_rate * (Z.T @ error / n + self.alpha * self.coef / n)
            self.intercept -= self.learning_rate * error.mean()
        return self

    def predict_proba(self, X):
        return sigmoid(self.scaler.transform(X) @ self.coef + self.intercept)


# ---------------------------------------------------------------- metrics
def mae(y, p):
    return float(np.mean(np.abs(y - p)))


def rmse(y, p):
    return float(np.sqrt(np.mean((y - p) ** 2)))


def brier(y, p):
    """Mean squared error of probabilities (0 = perfect)."""
    return float(np.mean((p - y) ** 2))


def roc_auc(y, p):
    """Probability that a random rainy day gets a higher score than a random dry day."""
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    positives = y == 1
    n_pos, n_neg = positives.sum(), (~positives).sum()
    return float((ranks[positives].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))
