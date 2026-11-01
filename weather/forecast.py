"""Train, evaluate and run the Daegu forecast models.

Time split (no shuffling, the future never leaks into training):
    train 2000-2019 · validation 2020-2022 (choose the penalty) · test 2023-today (final score)

Run:  .venv\\Scripts\\python.exe -m weather.forecast evaluate   (writes docs/metrics.json)
      .venv\\Scripts\\python.exe -m weather.forecast predict    (7-day forecast from the last day)
"""
import json
import sys

import numpy as np
import pandas as pd

from .config import DOCS_DIR, RAIN_DAY_MM
from .data import load
from .features import Climatology, build_features, rain_target, targets
from .models import LogisticRegression, RidgeRegression, brier, mae, roc_auc

TRAIN_END, VALID_END = "2019-12-31", "2022-12-31"
HORIZONS = range(1, 8)
TEMPERATURES = ("t_max", "t_min")
ALPHAS = (0.1, 1.0, 10.0, 100.0, 1000.0)
Z80 = 1.2816  # half-width of an 80% normal interval, in standard deviations


def fit_normals(df, end):
    part = df.loc[:end]
    return {column: Climatology().fit(part[column]) for column in ("t_mean", "t_max", "t_min")}


def xy(features, target, start=None, end=None):
    """Rows of (features, target) inside [start, end] without missing values."""
    table = features.assign(_y=target).loc[start:end].dropna()
    return table.drop(columns="_y").to_numpy(), table["_y"].to_numpy()


def month_rain_frequency(df, end):
    rainy = (df.loc[:end, "precip_mm"] >= RAIN_DAY_MM)
    return rainy.groupby(rainy.index.month).mean()


def evaluate(df):
    """Scores on the 2023+ test period against simple baselines."""
    report = {"split": {"train": f"2000-{TRAIN_END[:4]}", "validation": "2020-2022",
                        "test": f"2023-{df.index[-1].date()}"}, "temperature": {}, "rain": {}}
    tune_normals, final_normals = fit_normals(df, TRAIN_END), fit_normals(df, VALID_END)
    tune_features, final_features = build_features(df, tune_normals), build_features(df, final_normals)
    test_start = pd.Timestamp(VALID_END) + pd.Timedelta(days=1)

    for column in TEMPERATURES:
        rows = {}
        for h in HORIZONS:
            # 1) choose alpha on validation
            y_tune = targets(df, column, h, tune_normals)
            X_tr, y_tr = xy(tune_features, y_tune, end=TRAIN_END)
            X_va, y_va = xy(tune_features, y_tune, start="2020-01-01", end=VALID_END)
            scores = {a: mae(y_va, RidgeRegression(a).fit(X_tr, y_tr).predict(X_va)) for a in ALPHAS}
            alpha = min(scores, key=scores.get)
            spread = float(np.std(y_va - RidgeRegression(alpha).fit(X_tr, y_tr).predict(X_va)))
            # 2) refit on train + validation, score on test (in degrees, not anomalies)
            y_final = targets(df, column, h, final_normals)
            X_fit, y_fit = xy(final_features, y_final, end=VALID_END)
            X_te, y_te = xy(final_features, y_final, start=test_start)
            test_index = final_features.assign(_y=y_final).loc[test_start:].dropna().index
            target_dates = test_index + pd.Timedelta(days=h)
            normal = final_normals[column].predict(target_dates)
            truth = y_te + normal
            model = normal + RidgeRegression(alpha).fit(X_fit, y_fit).predict(X_te)
            persistence = df[column].reindex(test_index).to_numpy()
            rows[h] = {"alpha": alpha, "mae_model": round(mae(truth, model), 2),
                       "mae_persistence": round(mae(truth, persistence), 2),
                       "mae_climatology": round(mae(truth, normal), 2),
                       "interval_80": round(Z80 * spread, 2), "test_days": int(len(truth))}
        report["temperature"][column] = rows

    rain_freq = month_rain_frequency(df, VALID_END)
    for h in HORIZONS:
        y_all = rain_target(df, h)
        X_tr, y_tr = xy(tune_features, y_all, end=TRAIN_END)
        X_va, y_va = xy(tune_features, y_all, start="2020-01-01", end=VALID_END)
        scores = {a: brier(y_va, LogisticRegression(a).fit(X_tr, y_tr).predict_proba(X_va)) for a in ALPHAS}
        alpha = min(scores, key=scores.get)
        X_fit, y_fit = xy(final_features, y_all, end=VALID_END)
        X_te, y_te = xy(final_features, y_all, start=test_start)
        test_index = final_features.assign(_y=y_all).loc[test_start:].dropna().index
        p = LogisticRegression(alpha).fit(X_fit, y_fit).predict_proba(X_te)
        clim = rain_freq.reindex((test_index + pd.Timedelta(days=h)).month).to_numpy()
        today_rain = (df["precip_mm"].reindex(test_index) >= RAIN_DAY_MM).astype(float).to_numpy()
        brier_model, brier_clim = brier(y_te, p), brier(y_te, clim)
        report["rain"][h] = {"alpha": alpha, "brier_model": round(brier_model, 3),
                             "brier_climatology": round(brier_clim, 3),
                             "brier_persistence": round(brier(y_te, today_rain), 3),
                             "skill_vs_climatology": round(1 - brier_model / brier_clim, 3),
                             "auc": round(roc_auc(y_te, p), 3),
                             "accuracy": round(float(((p >= 0.5) == y_te).mean()), 3),
                             "test_days": int(len(y_te))}
    return report


class Forecaster:
    """Final models trained on all data; forecasts the 7 days after the last observed day."""

    def __init__(self, metrics=None):
        self.metrics = metrics or load_metrics()

    def _alpha(self, kind, key, h):
        try:
            table = self.metrics[kind][key] if kind == "temperature" else self.metrics["rain"]
            return float(table[str(h)]["alpha"])
        except (KeyError, TypeError):
            return 10.0

    def fit(self, df):
        self.df = df
        self.normals = fit_normals(df, None)
        self.features = build_features(df, self.normals)
        self.temperature, self.rain = {}, {}
        for column in TEMPERATURES:
            for h in HORIZONS:
                X, y = xy(self.features, targets(df, column, h, self.normals))
                self.temperature[column, h] = RidgeRegression(self._alpha("temperature", column, h)).fit(X, y)
        for h in HORIZONS:
            X, y = xy(self.features, rain_target(df, h))
            self.rain[h] = LogisticRegression(self._alpha("rain", None, h)).fit(X, y)
        return self

    def predict(self):
        today = self.features.index[-1]
        x = self.features.iloc[[-1]].to_numpy()
        rows = []
        for h in HORIZONS:
            day = today + pd.Timedelta(days=h)
            row = {"date": day, "rain_prob": float(self.rain[h].predict_proba(x)[0])}
            for column in TEMPERATURES:
                normal = float(self.normals[column].predict(pd.DatetimeIndex([day]))[0])
                value = normal + float(self.temperature[column, h].predict(x)[0])
                width = self._interval(column, h)
                row.update({column: value, f"{column}_low": value - width, f"{column}_high": value + width,
                            f"{column}_normal": normal})
            rows.append(row)
        return pd.DataFrame(rows).set_index("date")

    def _interval(self, column, h):
        try:
            return float(self.metrics["temperature"][column][str(h)]["interval_80"])
        except (KeyError, TypeError):
            return 2.0 + 0.3 * h


def load_metrics():
    path = DOCS_DIR / "metrics.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "predict"
    data = load()
    if command == "evaluate":
        result = evaluate(data)
        DOCS_DIR.mkdir(exist_ok=True)
        (DOCS_DIR / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
    else:
        print(f"Forecast from {data.index[-1].date()}:")
        print(Forecaster().fit(data).predict().round(1).to_string())
