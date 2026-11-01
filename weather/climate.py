"""Climate statistics for Daegu with pandas and numpy: normals, heatwaves, rain and warming trend.

Run:  .venv\\Scripts\\python.exe -m weather.climate     (prints and writes docs/climate.json)
"""
import json

import numpy as np

from .config import DOCS_DIR, RAIN_DAY_MM
from .data import load

HEATWAVE_C = 33.0       # KMA heatwave warning level (daily maximum)
EXTREME_HEAT_C = 35.0
TROPICAL_NIGHT_C = 25.0  # night minimum that stays this warm
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def monthly_normals(df):
    """Average month: temperatures, rain and rainy days."""
    by_month = df.groupby(df.index.month)
    years = df.index.year.nunique()
    normals = by_month[["t_mean", "t_max", "t_min", "humidity", "sunshine_h"]].mean()
    normals["precip_mm"] = by_month["precip_mm"].sum() / years
    normals["rain_days"] = by_month["precip_mm"].apply(lambda s: (s >= RAIN_DAY_MM).sum()) / years
    normals.index = MONTHS
    return normals.round(1)


def yearly_summary(df):
    """One row per complete year."""
    complete = df[df.index.year < df.index[-1].year] if df.index[-1].month < 12 else df
    by_year = complete.groupby(complete.index.year)
    summary = by_year.agg(t_mean=("t_mean", "mean"), t_max_record=("t_max", "max"),
                          t_min_record=("t_min", "min"), precip_mm=("precip_mm", "sum"))
    summary["heatwave_days"] = by_year["t_max"].apply(lambda s: int((s >= HEATWAVE_C).sum()))
    summary["extreme_heat_days"] = by_year["t_max"].apply(lambda s: int((s >= EXTREME_HEAT_C).sum()))
    summary["tropical_nights"] = by_year["t_min"].apply(lambda s: int((s >= TROPICAL_NIGHT_C).sum()))
    summary["rain_days"] = by_year["precip_mm"].apply(lambda s: int((s >= RAIN_DAY_MM).sum()))
    summer = complete[complete.index.month.isin([6, 7, 8])]
    summer_rain = summer.groupby(summer.index.year)["precip_mm"].sum()
    summary["summer_rain_share"] = (summer_rain / summary["precip_mm"]).round(2)
    return summary.round(2)


def trend_per_decade(series):
    """Least-squares slope of a yearly series, per 10 years (numpy polyfit)."""
    slope, _ = np.polyfit(series.index.to_numpy(dtype=float), series.to_numpy(dtype=float), 1)
    return float(slope * 10)


def records(df):
    hottest, coldest, wettest = df["t_max"].idxmax(), df["t_min"].idxmin(), df["precip_mm"].idxmax()
    return {
        "hottest_day": {"date": hottest.date().isoformat(), "t_max": float(df.at[hottest, "t_max"])},
        "coldest_night": {"date": coldest.date().isoformat(), "t_min": float(df.at[coldest, "t_min"])},
        "wettest_day": {"date": wettest.date().isoformat(), "precip_mm": float(df.at[wettest, "precip_mm"])},
    }


def summary(df):
    years = yearly_summary(df)
    first, last = years.index[:5], years.index[-5:]
    return {
        "years": f"{years.index[0]}-{years.index[-1]}",
        "mean_temperature_c": round(float(years["t_mean"].mean()), 1),
        "warming_c_per_decade": round(trend_per_decade(years["t_mean"]), 2),
        "heatwave_days_per_decade_change": round(trend_per_decade(years["heatwave_days"]), 1),
        "tropical_nights_per_decade_change": round(trend_per_decade(years["tropical_nights"]), 1),
        "heatwave_days_avg_first_5_years": round(float(years.loc[first, "heatwave_days"].mean()), 1),
        "heatwave_days_avg_last_5_years": round(float(years.loc[last, "heatwave_days"].mean()), 1),
        "annual_precip_mm": round(float(years["precip_mm"].mean())),
        "summer_rain_share": round(float(years["summer_rain_share"].mean()), 2),
        "records": records(df),
    }


if __name__ == "__main__":
    data = load()
    print(monthly_normals(data).to_string())
    print(yearly_summary(data).tail(6).to_string())
    result = summary(data)
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "climate.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
