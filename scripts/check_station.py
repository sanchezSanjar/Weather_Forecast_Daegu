"""Check the Open-Meteo history against real measurements of the Daegu weather station (WMO 47143).

Station data: Meteostat bulk daily data (https://meteostat.net, CC BY-NC 4.0).
Writes docs/station_check.json.

Run:  .venv\\Scripts\\python.exe scripts\\check_station.py
"""
import io
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from weather.config import DOCS_DIR  # noqa: E402
from weather.data import load  # noqa: E402

STATION_URL = "https://bulk.meteostat.net/v2/daily/47143.csv.gz"
STATION_COLUMNS = ["date", "t_mean", "t_min", "t_max", "precip_mm", "snow_mm", "wind_dir", "wind_kmh",
                   "gust_kmh", "pressure_hpa", "sunshine_min"]


def main():
    with urllib.request.urlopen(STATION_URL, timeout=120) as response:
        station = pd.read_csv(io.BytesIO(response.read()), compression="gzip", header=None,
                              names=STATION_COLUMNS, parse_dates=["date"], index_col="date")
    model = load()
    result = {"station": "Daegu WMO 47143 (Meteostat)", "columns": {}}
    for column in ("t_mean", "t_min", "t_max", "pressure_hpa"):
        both = pd.concat([model[column], station[column]], axis=1, keys=["open_meteo", "station"]).dropna()
        diff = both["open_meteo"] - both["station"]
        result["columns"][column] = {
            "days_compared": int(len(both)),
            "correlation": round(float(np.corrcoef(both["open_meteo"], both["station"])[0, 1]), 3),
            "mean_abs_diff": round(float(diff.abs().mean()), 2),
            "bias": round(float(diff.mean()), 2),
        }
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "station_check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
