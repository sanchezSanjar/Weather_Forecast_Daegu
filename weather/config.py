"""Location, paths and data columns."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "daegu_daily.csv"
DOCS_DIR = ROOT / "docs"

CITY = "Daegu"
LATITUDE, LONGITUDE = 35.8714, 128.6014
TIMEZONE = "Asia/Seoul"
START_DATE = "2000-01-01"

# Open-Meteo daily variable -> our column name
VARIABLES = {
    "temperature_2m_mean": "t_mean",
    "temperature_2m_max": "t_max",
    "temperature_2m_min": "t_min",
    "precipitation_sum": "precip_mm",
    "rain_sum": "rain_mm",
    "snowfall_sum": "snow_cm",
    "wind_speed_10m_max": "wind_max_kmh",
    "relative_humidity_2m_mean": "humidity",
    "surface_pressure_mean": "pressure_hpa",
    "sunshine_duration": "sunshine_h",
}
RAIN_DAY_MM = 1.0  # a "rainy day" has at least this much precipitation
