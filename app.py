"""Weather Forecast Daegu dashboard (Streamlit): 7-day forecast, heat and climate trends, history, accuracy."""
import json
import os
import threading

import altair as alt
import pandas as pd
import streamlit as st

from weather.climate import (EXTREME_HEAT_C, HEATWAVE_C, monthly_normals, records, trend_per_decade,
                             yearly_summary)
from weather.config import CITY, DOCS_DIR
from weather.data import load, quality_report, update
from weather.forecast import Forecaster, load_metrics

st.set_page_config(page_title="Weather Forecast Daegu", page_icon="🌤️", layout="wide")
st.markdown("""
<style>
  .block-container {max-width: 1280px; padding-top: 1.4rem;}
  .hero {padding: 1.2rem 1.6rem; border-radius: 18px; color: #fff;
         background: linear-gradient(120deg, #1d4e89, #3a86c8 60%, #f4a259);}
  .hero h1 {margin: 0; font-size: 1.9rem;} .hero p {margin: .3rem 0 0; opacity: .92;}
  .day {background: #fff; border: 1px solid #dde6f0; border-radius: 16px; padding: .9rem .6rem;
        text-align: center; height: 100%;}
  .day .name {font-weight: 700; color: #1d4e89;} .day .date {color: #6b7a8c; font-size: .8rem;}
  .day .icon {font-size: 2rem; margin: .2rem 0;}
  .day .hi {font-size: 1.35rem; font-weight: 800; color: #d9534f;} .day .lo {font-size: 1rem; color: #3a86c8;}
  .day .rain {font-size: .85rem; color: #1d4e89; margin-top: .2rem;}
  div[data-testid="stMetric"] {background: #fff; border: 1px solid #dde6f0; padding: .8rem 1rem; border-radius: 14px;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def get_data(version):
    return load()


@st.cache_resource(show_spinner="Training the forecast models…")
def get_forecaster(version):
    return Forecaster().fit(get_data(version))


def weather_icon(rain_prob, t_max):
    if rain_prob >= 0.6:
        return "🌧️"
    if rain_prob >= 0.35:
        return "🌦️"
    if t_max >= HEATWAVE_C:
        return "🥵"
    return "☀️" if rain_prob < 0.15 else "⛅"


if "version" not in st.session_state:
    st.session_state.version = 0
df = get_data(st.session_state.version)
quality = quality_report(df)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown(f"### 🌤️ {CITY}, South Korea")
    st.caption("35.87° N, 128.60° E")
    st.metric("Data until", quality["last_day"])
    st.caption(f"{quality['days']:,} days since {quality['first_day']}")
    if st.button("Update data", icon=":material/refresh:", width="stretch"):
        with st.spinner("Downloading new days…"):
            try:
                _, added = update()
                st.session_state.version += 1
                st.success(f"{added} new day(s) added.")
                st.rerun()
            except Exception as exc:  # offline or API error
                st.error(f"Update failed (offline?): {exc}")
    st.divider()
    st.caption("Data: Open-Meteo (ERA5), CC BY 4.0. Models: ridge and logistic regression written "
               "in numpy. Statistical forecast, not an official KMA forecast.")
    if st.button("Quit app", icon=":material/power_settings_new:", width="stretch"):
        st.info("Weather Forecast Daegu has stopped. You can close this tab.")
        threading.Timer(0.8, lambda: os._exit(0)).start()
        st.stop()

st.markdown(f'<div class="hero"><h1>Weather Forecast {CITY}</h1>'
            f'<p>7-day forecast and 26 years of climate data for Korea\'s hottest city</p></div>',
            unsafe_allow_html=True)
st.write("")
tab_fc, tab_climate, tab_history, tab_acc = st.tabs(
    ["🌤️ 7-day forecast", "🔥 Heat & climate", "📅 History", "🎯 Model accuracy"])

# ---------------------------------------------------------------- forecast
with tab_fc:
    forecast = get_forecaster(st.session_state.version).predict()
    st.caption(f"Forecast made from the last observed day, {quality['last_day']}.")
    for column, (day, row) in zip(st.columns(len(forecast)), forecast.iterrows()):
        column.markdown(
            f'<div class="day"><div class="name">{day:%a}</div><div class="date">{day:%b %d}</div>'
            f'<div class="icon">{weather_icon(row.rain_prob, row.t_max)}</div>'
            f'<div class="hi">{row.t_max:.0f}°</div><div class="lo">{row.t_min:.0f}°</div>'
            f'<div class="rain">💧 {row.rain_prob:.0%}</div></div>', unsafe_allow_html=True)
    st.write("")
    left, right = st.columns([3, 2], gap="large")
    with left:
        recent = df.loc[df.index[-14]:, ["t_max", "t_min"]].assign(kind="Observed")
        future = forecast[["t_max", "t_min"]].assign(kind="Forecast")
        both = pd.concat([recent, future]).reset_index(names="date")
        long = both.melt(["date", "kind"], ["t_max", "t_min"], "series", "temp")
        long["series"] = long["series"].map({"t_max": "High", "t_min": "Low"})
        bands = forecast.reset_index(names="date")
        low = min(bands["t_min_low"].min(), long["temp"].min()) - 2
        high = max(bands["t_max_high"].max(), long["temp"].max()) + 2
        y_scale = alt.Scale(domain=[low, high], zero=False)
        base = alt.Chart(bands).encode(x=alt.X("date:T", title=None))
        chart = alt.layer(
            base.mark_area(opacity=.15, color="#d9534f").encode(
                y=alt.Y("t_max_low:Q", scale=y_scale, title="°C"), y2="t_max_high:Q"),
            base.mark_area(opacity=.15, color="#3a86c8").encode(y=alt.Y("t_min_low:Q", scale=y_scale), y2="t_min_high:Q"),
            base.mark_line(strokeDash=[3, 3], color="#9aa7b5").encode(y=alt.Y("t_max_normal:Q", scale=y_scale)),
            base.mark_line(strokeDash=[3, 3], color="#9aa7b5").encode(y=alt.Y("t_min_normal:Q", scale=y_scale)),
            alt.Chart(long).mark_line(point=True).encode(
                x=alt.X("date:T", title=None), y=alt.Y("temp:Q", scale=y_scale, title="°C"),
                color=alt.Color("series:N", scale=alt.Scale(range=["#d9534f", "#3a86c8"]),
                                legend=alt.Legend(orient="top", title=None)),
                strokeDash=alt.StrokeDash("kind:N", scale=alt.Scale(domain=["Observed", "Forecast"],
                                                                    range=[[1, 0], [5, 3]]),
                                          legend=alt.Legend(orient="top", title=None)),
                tooltip=["date:T", "series:N", alt.Tooltip("temp:Q", format=".1f", title="°C"), "kind:N"]),
        ).properties(height=320, title="Last 14 days and next 7 days")
        st.altair_chart(chart, width="stretch")
        st.caption("Shaded: 80% forecast range · dashed grey: normal for the date")
    with right:
        table = forecast[["t_max", "t_min", "rain_prob", "t_max_normal"]].copy()
        table.index = table.index.strftime("%a %b %d")
        table["vs normal"] = (table["t_max"] - table["t_max_normal"]).map(lambda v: f"{v:+.1f}°")
        table = table.drop(columns="t_max_normal").rename(
            columns={"t_max": "High °C", "t_min": "Low °C", "rain_prob": "Rain"})
        st.dataframe(table.style.format({"High °C": "{:.1f}", "Low °C": "{:.1f}", "Rain": "{:.0%}"}),
                     width="stretch")
        st.caption("Rain = chance of at least 1 mm. Each day's range: 80% of past errors were smaller.")

# ---------------------------------------------------------------- climate
with tab_climate:
    years = yearly_summary(df)
    rec = records(df)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Warming per decade", f"+{trend_per_decade(years['t_mean']):.2f} °C")
    k2.metric(f"Heatwave days ≥{HEATWAVE_C:.0f}°C",
              f"{years['heatwave_days'].iloc[-5:].mean():.0f} / year",
              f"{years['heatwave_days'].iloc[-5:].mean() - years['heatwave_days'].iloc[:5].mean():+.0f} vs 2000-04",
              delta_color="inverse")
    k3.metric(f"Hottest day · {rec['hottest_day']['date']}", f"{rec['hottest_day']['t_max']:.1f} °C")
    k4.metric(f"Coldest night · {rec['coldest_night']['date']}", f"{rec['coldest_night']['t_min']:.1f} °C")
    left, right = st.columns(2, gap="large")
    with left:
        heat = years.reset_index(names="year")[["year", "heatwave_days", "extreme_heat_days", "tropical_nights"]]
        heat_long = heat.melt("year", var_name="kind", value_name="days")
        heat_long["kind"] = heat_long["kind"].map({
            "heatwave_days": f"Heatwave days (≥{HEATWAVE_C:.0f}°C)",
            "extreme_heat_days": f"Extreme heat (≥{EXTREME_HEAT_C:.0f}°C)",
            "tropical_nights": "Tropical nights (min ≥25°C)"})
        st.altair_chart(alt.Chart(heat_long).mark_bar().encode(
            x=alt.X("year:O", title=None), y="days:Q", xOffset="kind:N",
            color=alt.Color("kind:N", scale=alt.Scale(range=["#f4a259", "#d9534f", "#7b4fa0"]),
                            legend=alt.Legend(orient="bottom", title=None, columns=1, labelLimit=300)),
            tooltip=["year", "kind", "days"]).properties(height=330, title="Hot days per year"), width="stretch")
    with right:
        warm = years.reset_index(names="year")[["year", "t_mean"]]
        line = alt.Chart(warm).mark_line(point=True, color="#d9534f").encode(
            x=alt.X("year:O", title=None), y=alt.Y("t_mean:Q", title="Mean °C", scale=alt.Scale(zero=False)),
            tooltip=["year", alt.Tooltip("t_mean:Q", format=".2f")])
        trend = line.transform_regression("year", "t_mean").mark_line(strokeDash=[5, 4], color="#1d4e89")
        st.altair_chart((line + trend).properties(height=330, title="Yearly mean temperature and trend"),
                        width="stretch")
    normals = monthly_normals(df).reset_index(names="month")
    months = list(normals["month"])
    temps = alt.Chart(normals).mark_line(point=True).transform_fold(["t_max", "t_min"], ["series", "°C"]).encode(
        x=alt.X("month:N", sort=months, title=None), y="°C:Q",
        color=alt.Color("series:N", scale=alt.Scale(range=["#d9534f", "#3a86c8"]), legend=None))
    rain = alt.Chart(normals).mark_bar(opacity=.35, color="#3a86c8").encode(
        x=alt.X("month:N", sort=months), y=alt.Y("precip_mm:Q", title="Rain mm"))
    st.altair_chart(alt.layer(rain, temps).resolve_scale(y="independent").properties(
        height=280, title="Average year: high/low temperature and monthly rain (monsoon in Jul-Aug)"),
        width="stretch")

# ---------------------------------------------------------------- history
with tab_history:
    first, last = df.index[0].date(), df.index[-1].date()
    start, end = st.slider("Period", min_value=first, max_value=last,
                           value=(last - pd.Timedelta(days=365).to_pytimedelta(), last), format="YYYY-MM-DD")
    part = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Average", f"{part['t_mean'].mean():.1f} °C")
    k2.metric("Highest", f"{part['t_max'].max():.1f} °C")
    k3.metric("Lowest", f"{part['t_min'].min():.1f} °C")
    k4.metric("Rain", f"{part['precip_mm'].sum():.0f} mm")
    plot = part.reset_index()[["date", "t_max", "t_min", "precip_mm"]]
    temp_lines = alt.Chart(plot).transform_fold(["t_max", "t_min"], ["series", "°C"]).mark_line().encode(
        x=alt.X("date:T", title=None), y="°C:Q",
        color=alt.Color("series:N", scale=alt.Scale(range=["#d9534f", "#3a86c8"]), legend=None))
    rain_bars = alt.Chart(plot).mark_bar(color="#3a86c8", opacity=.4).encode(
        x="date:T", y=alt.Y("precip_mm:Q", title="Rain mm"))
    st.altair_chart(alt.layer(rain_bars, temp_lines).resolve_scale(y="independent").properties(height=330),
                    width="stretch")
    st.download_button("Download this period (CSV)", part.to_csv().encode("utf-8"),
                       file_name=f"daegu_{start}_{end}.csv", mime="text/csv")

# ---------------------------------------------------------------- accuracy
with tab_acc:
    metrics = load_metrics()
    if not metrics:
        st.info("Run `python -m weather.forecast evaluate` to measure the models.")
    else:
        split = metrics["split"]
        st.caption(f"Trained on {split['train']}, tuned on {split['validation']}, "
                   f"scored on {split['test']} (never seen in training).")
        rows = []
        for column, label in (("t_max", "High"), ("t_min", "Low")):
            for h, r in metrics["temperature"][column].items():
                rows += [{"target": label, "days ahead": int(h), "method": name, "MAE °C": r[key]}
                         for name, key in (("Model", "mae_model"), ("Same as today", "mae_persistence"),
                                           ("Normal for the date", "mae_climatology"))]
        acc = pd.DataFrame(rows)
        st.altair_chart(alt.Chart(acc).mark_line(point=True).encode(
            x=alt.X("days ahead:O"), y=alt.Y("MAE °C:Q", title="Average error °C"),
            color=alt.Color("method:N", scale=alt.Scale(range=["#1d4e89", "#9aa7b5", "#f4a259"]),
                            legend=alt.Legend(orient="top", title=None)),
            column=alt.Column("target:N", title=None),
            tooltip=["target", "days ahead", "method", "MAE °C"]).properties(width=380, height=260))
        rain_rows = pd.DataFrame(metrics["rain"]).T
        rain_rows.index.name = "days ahead"
        st.markdown("**Rain tomorrow and later**: skill = how much better than the usual rain chance "
                    "for that month (Brier score). AUC 0.5 = guessing, 1.0 = perfect.")
        st.dataframe(rain_rows[["skill_vs_climatology", "auc", "accuracy", "brier_model", "brier_climatology"]]
                     .rename(columns={"skill_vs_climatology": "Skill", "auc": "AUC", "accuracy": "Accuracy",
                                      "brier_model": "Brier model", "brier_climatology": "Brier climatology"}),
                     width="stretch")
    station = DOCS_DIR / "station_check.json"
    if station.exists():
        check = json.loads(station.read_text(encoding="utf-8"))["columns"]
        st.markdown(f"**Data check** against the real Daegu weather station: daily mean temperature "
                    f"correlation {check['t_mean']['correlation']}, average difference "
                    f"{check['t_mean']['mean_abs_diff']} °C over {check['t_mean']['days_compared']:,} days.")
