"""Turn the daily history into model inputs with pandas.

Everything a feature uses is known on day t (today); targets are values on day t + h.
"""
import numpy as np
import pandas as pd

from .config import RAIN_DAY_MM


def season_terms(dates):
    """sin/cos of the day of year (2 harmonics) for a DatetimeIndex -> array (n, 4)."""
    angle = 2 * np.pi * (dates.dayofyear.to_numpy() - 1) / 365.25
    return np.column_stack([np.sin(angle), np.cos(angle), np.sin(2 * angle), np.cos(2 * angle)])


class Climatology:
    """Smooth 'normal' value for each day of the year, fitted by least squares (numpy)."""

    def fit(self, series):
        design = np.column_stack([np.ones(len(series)), season_terms(series.index)])
        self.coef, *_ = np.linalg.lstsq(design, series.to_numpy(dtype=float), rcond=None)
        return self

    def predict(self, dates):
        return np.column_stack([np.ones(len(dates)), season_terms(dates)]) @ self.coef


def build_features(df, normals):
    """Feature table for each day t. `normals` maps column -> fitted Climatology."""
    f = pd.DataFrame(index=df.index)
    for column in ("t_mean", "t_max", "t_min"):
        normal = normals[column].predict(df.index)
        f[f"{column}_anom"] = df[column] - normal          # how unusual today is
        f[f"{column}_anom_1"] = f[f"{column}_anom"].shift(1)  # yesterday
    f["t_mean_anom_7d"] = f["t_mean_anom"].rolling(7).mean()
    f["t_range"] = df["t_max"] - df["t_min"]
    f["pressure"] = df["pressure_hpa"]
    f["pressure_change"] = df["pressure_hpa"].diff()
    f["humidity"] = df["humidity"]
    f["humidity_change"] = df["humidity"].diff()
    f["precip_log"] = np.log1p(df["precip_mm"])
    f["rain_last_3d"] = (df["precip_mm"] >= RAIN_DAY_MM).rolling(3).sum()
    f["sunshine"] = df["sunshine_h"]
    f["wind"] = df["wind_max_kmh"]
    return f


def targets(df, column, horizon, normals):
    """Target anomaly h days ahead (value minus that day's normal), aligned to day t."""
    future = df[column].shift(-horizon)
    future_dates = df.index + pd.Timedelta(days=horizon)
    return future - normals[column].predict(future_dates)


def rain_target(df, horizon):
    """1 if day t + h is a rainy day, else 0 (NaN at the end of the data)."""
    future = df["precip_mm"].shift(-horizon)
    return (future >= RAIN_DAY_MM).astype(float).where(future.notna())
