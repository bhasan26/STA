"""Ticket 5 -- analysis. Turns raw observations into written insights.

KEY METHODOLOGY (see Ticket 4 / data_quality findings):
The RT feed echoes the scheduled time for stops far in the future (predicted ==
scheduled -> spurious 0 delay), and the poller logs every stop every cycle. So
~2/3 of raw rows are schedule echoes that would dilute delay toward zero.

To measure REAL delay we keep, for each stop-visit (trip_id + stop_sequence +
service date), only the LAST prediction we logged before the bus arrived -- the
most accurate estimate of actual arrival. This "last-prediction-wins" dedup is
done in SQL (memory-safe over ~28M rows) before any averaging.

Sparse days (Jul 1, Jul 10) are excluded. Output -> analysis/insights.md
"""
import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd

DB_PATH = "data/tracker.sqlite"
OUT_PATH = "analysis/insights.md"
ON_TIME_SEC = 120           # within +/-2 min counts as on time
EXCLUDE_DAYS = ("2026-07-01", "2026-07-10")   # sparse -- too little to trust
MIN_OBS_PER_ROUTE = 500     # don't rank a route on a handful of stop-visits
MIN_OBS_PER_HOUR = 2000     # overnight hours have tiny samples + after-midnight
                            # schedule-join noise -> exclude from hour rankings


def load_final_predictions():
    """One row per stop-visit: the last prediction before arrival, with delay."""
    conn = sqlite3.connect(DB_PATH)
    placeholders = ",".join("?" * len(EXCLUDE_DAYS))
    # window function: rank predictions per stop-visit by recency, keep the last
    q = f"""
        WITH ranked AS (
            SELECT trip_id, route_id, stop_id, stop_sequence,
                   predicted_time, observed_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY trip_id, stop_sequence, substr(predicted_time,1,10)
                       ORDER BY observed_at DESC
                   ) AS rn
            FROM delay_observations
            WHERE predicted_time IS NOT NULL
              AND substr(observed_at,1,10) NOT IN ({placeholders})
        )
        SELECT trip_id, route_id, stop_id, stop_sequence, predicted_time, observed_at
        FROM ranked WHERE rn = 1
    """
    df = pd.read_sql(q, conn, params=EXCLUDE_DAYS)
    sched = pd.read_sql("SELECT trip_id, stop_sequence, arrival_time FROM stop_times", conn)
    rname = pd.read_sql("SELECT route_id, route_short_name FROM routes", conn)
    conn.close()

    df["trip_id"] = df["trip_id"].astype(str)
    sched["trip_id"] = sched["trip_id"].astype(str)
    parts = sched["arrival_time"].str.split(":", expand=True).astype("int32")
    sched["sched_td"] = (pd.to_timedelta(parts[0], unit="h")
                         + pd.to_timedelta(parts[1], unit="m")
                         + pd.to_timedelta(parts[2], unit="s"))
    sched = sched.drop(columns=["arrival_time"])

    m = df.merge(sched, on=["trip_id", "stop_sequence"], how="left")
    m["predicted_time"] = pd.to_datetime(m["predicted_time"])
    day = m["predicted_time"].dt.normalize()
    cand = pd.concat([day + pd.Timedelta(days=x) + m["sched_td"] for x in (-1, 0, 1)], axis=1)
    diff = cand.sub(m["predicted_time"], axis=0).abs().to_numpy().astype("timedelta64[s]").astype("float64")
    diff[np.isnan(diff)] = np.inf
    m["scheduled_dt"] = cand.to_numpy()[np.arange(len(m)), diff.argmin(1)]
    m.loc[m["sched_td"].isna(), "scheduled_dt"] = pd.NaT
    m["delay_seconds"] = (m["predicted_time"] - m["scheduled_dt"]).dt.total_seconds()
    m = m[m["delay_seconds"].abs() <= 3600 * 3]     # drop clearly-bad joins

    rname["route_id"] = rname["route_id"].astype(str)
    m["route_id"] = m["route_id"].astype(str)
    m = m.merge(rname, on="route_id", how="left")
    m["route"] = m["route_short_name"].fillna(m["route_id"])
    m["hour"] = m["predicted_time"].dt.hour
    m["weekday"] = m["predicted_time"].dt.day_name()
    m["is_weekend"] = m["weekday"].isin(["Saturday", "Sunday"])
    m["on_time"] = m["delay_seconds"].abs() <= ON_TIME_SEC
    return m


def main():
    m = load_final_predictions()
    out = ["# STA Route Reliability -- Findings", ""]
    out.append(f"_Generated {datetime.now():%Y-%m-%d %H:%M} from {len(m):,} stop-visits "
               f"(last-prediction-per-stop, schedule echoes removed)._")
    out.append("")
    out.append("**Data caveat:** ~6 usable days (Jul 2-7 2026), evenings under-sampled "
               "due to collection gaps. Treat as a first pass, not a final verdict.")
    out.append("")

    # ---- headline ----
    overall_on_time = m["on_time"].mean() * 100
    overall_median = m["delay_seconds"].median() / 60
    out += ["## Headline",
            f"- System-wide on-time rate (within +/-2 min): **{overall_on_time:.0f}%**",
            f"- Median delay across all stop-visits: **{overall_median:+.1f} min**", ""]

    # ---- least reliable routes ----
    g = m.groupby("route").agg(
        n=("delay_seconds", "size"),
        mean_delay=("delay_seconds", "mean"),
        on_time=("on_time", "mean"),
    )
    g = g[g["n"] >= MIN_OBS_PER_ROUTE]
    worst = g.sort_values("on_time").head(5)
    out.append("## 5 least reliable routes (by on-time rate)")
    out.append("| Route | On-time | Avg delay | Stop-visits |")
    out.append("|---|---|---|---|")
    for r, row in worst.iterrows():
        out.append(f"| {r} | {row['on_time']*100:.0f}% | {row['mean_delay']/60:+.1f} min | {int(row['n']):,} |")
    out.append("")

    latest = g.sort_values("mean_delay", ascending=False).head(5)
    out.append("## 5 routes running latest (by average delay)")
    out.append("| Route | Avg delay | On-time | Stop-visits |")
    out.append("|---|---|---|---|")
    for r, row in latest.iterrows():
        out.append(f"| {r} | {row['mean_delay']/60:+.1f} min | {row['on_time']*100:.0f}% | {int(row['n']):,} |")
    out.append("")

    # ---- worst time-of-day windows (system-wide) ----
    hour_stats = m.groupby("hour")["delay_seconds"].agg(["mean", "size"])
    hour_stats = hour_stats[hour_stats["size"] >= MIN_OBS_PER_HOUR]
    worst_hours = (hour_stats["mean"] / 60).sort_values(ascending=False).head(3)
    out.append("## Worst times of day (system-wide avg delay)")
    out.append(f"_Hours with < {MIN_OBS_PER_HOUR:,} stop-visits excluded (overnight noise)._")
    for h, v in worst_hours.items():
        out.append(f"- **{int(h):02d}:00** -- avg {v:+.1f} min late")
    out.append("")

    # ---- worst route x hour combos ----
    rh = m.groupby(["route", "hour"]).agg(n=("delay_seconds", "size"),
                                          mean_delay=("delay_seconds", "mean"))
    # restrict to daytime service hours + a real sample, so overnight after-
    # midnight join noise can't dominate the ranking
    rh = rh.reset_index()
    rh = rh[(rh["n"] >= 200) & (rh["hour"] >= 5) & (rh["hour"] <= 22)]
    rh = rh.set_index(["route", "hour"]).sort_values("mean_delay", ascending=False).head(5)
    out.append("## Worst route + time combinations")
    for (r, h), row in rh.iterrows():
        out.append(f"- **Route {r} at {int(h):02d}:00** averages {row['mean_delay']/60:+.1f} min late "
                   f"({int(row['n']):,} stop-visits)")
    out.append("")

    # ---- weekday vs weekend ----
    wk = m.groupby("is_weekend")["delay_seconds"].mean() / 60
    wd = wk.get(False, float("nan"))
    we = wk.get(True, float("nan"))
    out += ["## Weekday vs weekend",
            f"- Weekday avg delay: {wd:+.1f} min",
            f"- Weekend avg delay: {we:+.1f} min", ""]

    # ---- compounding delay within a trip ----
    out.append("## Compounding delay (does lateness grow along a route?)")
    comp = _compounding(m)
    out.append(comp)
    out.append("")

    import os
    os.makedirs("analysis", exist_ok=True)
    report = "\n".join(out)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(report)


def _compounding(m):
    """Compare avg delay at early vs late stop_sequence for the busiest routes."""
    top = m["route"].value_counts().head(8).index
    lines = []
    for r in top:
        sub = m[m["route"] == r]
        early = sub[sub["stop_sequence"] <= sub["stop_sequence"].quantile(.25)]["delay_seconds"].mean()
        late = sub[sub["stop_sequence"] >= sub["stop_sequence"].quantile(.75)]["delay_seconds"].mean()
        if pd.notna(early) and pd.notna(late):
            growth = (late - early) / 60
            arrow = "grows" if growth > 0.5 else ("shrinks" if growth < -0.5 else "flat")
            lines.append(f"- Route {r}: {early/60:+.1f} min early-stops -> {late/60:+.1f} min late-stops "
                         f"({arrow}, {growth:+.1f} min)")
    return "\n".join(lines) if lines else "- Not enough per-route stop data."


if __name__ == "__main__":
    main()
