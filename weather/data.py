"""Download, clean and load the Daegu daily weather history.

Source: Open-Meteo Historical Weather API (ERA5 reanalysis), https://open-meteo.com (CC BY 4.0).

Run:  .venv\\Scripts\\python.exe -m weather.data          (download or update data/daegu_daily.csv)
"""
import io
import json
import urllib.parse
import urllib.request
from datetime import date, timedelta

import pandas as pd

from .config import DATA_FILE, LATITUDE, LONGITUDE, START_DATE, TIMEZONE, VARIABLES

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
# Physically possible ranges for Daegu; values outside are treated as errors.
VALID_RANGES = {"t_mean": (-25, 45), "t_max": (-20, 45), "t_min": (-25, 40), "precip_mm": (0, 500),
                "humidity": (0, 100), "pressure_hpa": (950, 1050), "sunshine_h": (0, 15)}


def download(start, end):
    """Daily data from Open-Meteo for [start, end] as a raw DataFrame."""
    query = urllib.parse.urlencode({
        "latitude": LATITUDE, "longitude": LONGITUDE, "start_date": start, "end_date": end,
        "daily": ",".join(VARIABLES), "timezone": TIMEZONE, "format": "csv",
    })
    with urllib.request.urlopen(f"{ARCHIVE_URL}?{query}", timeout=120) as response:
        text = response.read().decode("utf-8")
    # The CSV starts with a location block, then a blank line, then the daily table.
    table = text.split("\n\n", 1)[1]
    return pd.read_csv(io.StringIO(table))


def clean(raw):
    """Rename columns, convert units, check ranges, fill short gaps, one row per day."""
    df = raw.rename(columns=lambda c: c.split(" (")[0]).rename(columns=VARIABLES | {"time": "date"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates("date").set_index("date").sort_index()
    df["sunshine_h"] = df["sunshine_h"] / 3600  # seconds -> hours
    for column, (low, high) in VALID_RANGES.items():
        df.loc[(df[column] < low) | (df[column] > high), column] = float("nan")
    df = df.asfreq("D")  # make missing days visible as empty rows
    numeric = df.columns
    df[numeric] = df[numeric].interpolate(limit=3, limit_direction="both")
    return df.round(2)


def load():
    """The cleaned history as a DataFrame indexed by date."""
    return pd.read_csv(DATA_FILE, parse_dates=["date"], index_col="date").asfreq("D")


def update(today=None):
    """Download the full history, or only the days missing since the last saved date."""
    end = ((today or date.today()) - timedelta(days=2)).isoformat()  # archive lags about 2 days
    if DATA_FILE.exists():
        existing = load()
        start = (existing.index[-1] + pd.Timedelta(days=1)).date().isoformat()
        if start > end:
            return existing, 0
        new = clean(download(start, end))
        combined = pd.concat([existing, new])
        combined = combined[~combined.index.duplicated(keep="last")]
    else:
        new = combined = clean(download(START_DATE, end))
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(DATA_FILE, index_label="date")
    return combined, len(new)


def quality_report(df):
    """Simple data quality numbers for the README and dashboard."""
    return {
        "first_day": df.index[0].date().isoformat(),
        "last_day": df.index[-1].date().isoformat(),
        "days": int(len(df)),
        "missing_values": int(df.isna().sum().sum()),
    }


if __name__ == "__main__":
    data, added = update()
    print(f"{added} new days. " + json.dumps(quality_report(data)))
