"""Ticket 4 -- data quality check.

Run before trusting the data for analysis (Ticket 5). Most checks run in SQL
(the table is ~28M rows -- loading it all into pandas would blow up memory), and
the delay-distribution sanity check runs on a random sample via delay_calc.

Usage: python src/data_quality.py
Writes a report to analysis/data_quality_report.md and prints it.
"""
import sqlite3
from datetime import datetime, timedelta

import pandas as pd

DB_PATH = "data/tracker.sqlite"
REPORT_PATH = "analysis/data_quality_report.md"
SAMPLE_SIZE = 400_000
SERVICE_START, SERVICE_END = 5, 23  # STA runs roughly 5am..~1am


def main():
    conn = sqlite3.connect(DB_PATH)
    out = ["# Data Quality Report (Ticket 4)", ""]
    out.append(f"_Generated {datetime.now().isoformat(timespec='seconds')}_")
    out.append("")

    # ---- 1. Volume & span ----
    total, first, last = conn.execute(
        "SELECT COUNT(*), MIN(observed_at), MAX(observed_at) FROM delay_observations"
    ).fetchone()
    out += ["## 1. Volume & span",
            f"- Total observations: **{total:,}**",
            f"- Span: {first[:19]} -> {last[:19]}", ""]

    # ---- 2. Route coverage ----
    seen = conn.execute("SELECT COUNT(DISTINCT route_id) FROM delay_observations").fetchone()[0]
    in_static = conn.execute("SELECT COUNT(DISTINCT route_id) FROM routes").fetchone()[0]
    out += ["## 2. Route coverage",
            f"- Routes observed: **{seen}** of {in_static} in the static schedule",
            f"- {'OK -- many routes; no obvious filtering bug' if seen >= 30 else 'LOW -- possible filtering bug, investigate'}",
            ""]

    # ---- 3. Daily coverage / gap catalog ----
    out.append("## 3. Daily coverage")
    out.append("| Day | Weekday | Rows | Hours | Assessment |")
    out.append("|---|---|---|---|---|")
    for d, n, hrs in conn.execute(
        "SELECT substr(observed_at,1,10), COUNT(*), COUNT(DISTINCT substr(observed_at,1,13)) "
        "FROM delay_observations GROUP BY 1 ORDER BY 1"
    ):
        wd = datetime.fromisoformat(d).strftime("%a")
        assess = "FULL" if hrs >= 18 else ("partial" if hrs >= 8 else "sparse")
        out.append(f"| {d} | {wd} | {n:,} | {hrs}/24 | {assess} |")
    out.append("")

    # service-hour gap catalog across the whole span
    present = {r[0] for r in conn.execute(
        "SELECT DISTINCT substr(observed_at,1,13) FROM delay_observations"
    )}
    start_day = datetime.fromisoformat(first[:10])
    end_day = datetime.fromisoformat(last[:10])
    missing = []
    cur = start_day
    while cur <= end_day + timedelta(days=1):
        if SERVICE_START <= cur.hour <= SERVICE_END:
            if cur.strftime("%Y-%m-%dT%H") not in present:
                missing.append(cur)
        cur += timedelta(hours=1)
    runs = []
    for m in missing:
        if runs and (m - runs[-1][-1]) == timedelta(hours=1):
            runs[-1].append(m)
        else:
            runs.append([m])
    out.append("### Service-hour gaps (>= 2h)")
    big = [r for r in runs if len(r) >= 2]
    if big:
        for r in big:
            out.append(f"- {r[0]:%Y-%m-%d %H:00} -> {r[-1]:%H:59}  ({len(r)}h)")
    else:
        out.append("- None")
    out.append("")

    # ---- 4. trip_id join integrity ----
    static_trips = pd.read_sql("SELECT DISTINCT trip_id FROM trips", conn)
    static_trips["trip_id"] = static_trips["trip_id"].astype(str)
    static_set = set(static_trips["trip_id"])
    obs_trips = pd.read_sql("SELECT DISTINCT trip_id FROM delay_observations", conn)
    obs_trips["trip_id"] = obs_trips["trip_id"].astype(str)
    matched = obs_trips["trip_id"].isin(static_set).mean() * 100
    out += ["## 4. trip_id join integrity",
            f"- {matched:.1f}% of observed trip_ids match the static `trips` table",
            f"- {'OK' if matched >= 90 else 'WARN -- schedule version mismatch; may need route_id+start_date fallback'}",
            ""]
    conn.close()

    # ---- 5. Delay distribution sanity (sampled) ----
    out.append("## 5. Delay distribution (sampled)")
    sample_conn = sqlite3.connect(DB_PATH)
    n_pred = sample_conn.execute(
        "SELECT COUNT(*) FROM delay_observations WHERE predicted_time IS NOT NULL"
    ).fetchone()[0]
    sample_conn.close()
    # load_delays computes delay for the whole table; to stay memory-safe we
    # instead compute on a sample by temporarily filtering. Reuse the join on a
    # random subset via a since= trick isn't possible, so sample rows directly.
    df = _sampled_delays(SAMPLE_SIZE)
    d = df["delay_seconds"].dropna()
    if len(d):
        pct_on_time = (d.abs() <= 120).mean() * 100
        pct_zero = (d == 0).mean() * 100
        out += [
            f"- Sample size with computed delay: {len(d):,}",
            f"- Median: {d.median()/60:+.1f} min | Mean: {d.mean()/60:+.1f} min",
            f"- p10 / p90: {d.quantile(.1)/60:+.1f} / {d.quantile(.9)/60:+.1f} min",
            f"- On-time (within +/-2 min): {pct_on_time:.1f}%",
            f"- Exactly zero: {pct_zero:.1f}%  "
            f"({'suspicious -- delay field may be unpopulated' if pct_zero > 40 else 'OK'})",
            f"- Extreme (|delay| > 30 min): {(d.abs() > 1800).mean()*100:.2f}%  "
            f"({'watch for timezone/parse bug' if (d.abs()>1800).mean()>0.05 else 'OK'})",
            "",
        ]
    else:
        out.append("- No computable delays in sample -- investigate join.")
    out.append("")

    out.append("## Verdict")
    out.append(
        "Usable for a first analysis on the FULL/partial days (Jul 2-7). Sparse "
        "days (Jul 1, 10) and the service-hour gaps above should be excluded or "
        "caveated. Evening coverage is thinner than morning due to sleep gaps."
    )

    report = "\n".join(out)
    import os
    os.makedirs("analysis", exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(report)


def _sampled_delays(n):
    """Compute delay on a random sample of rows, memory-safe."""
    conn = sqlite3.connect(DB_PATH)
    obs = pd.read_sql(
        "SELECT * FROM delay_observations WHERE predicted_time IS NOT NULL "
        "ORDER BY RANDOM() LIMIT ?", conn, params=(n,),
    )
    sched = pd.read_sql("SELECT trip_id, stop_sequence, arrival_time FROM stop_times", conn)
    conn.close()
    return _join_delay(obs, sched)


def _join_delay(obs, sched):
    import numpy as np
    obs["trip_id"] = obs["trip_id"].astype(str)
    sched["trip_id"] = sched["trip_id"].astype(str)
    parts = sched["arrival_time"].str.split(":", expand=True).astype("int32")
    sched["sched_td"] = (pd.to_timedelta(parts[0], unit="h")
                         + pd.to_timedelta(parts[1], unit="m")
                         + pd.to_timedelta(parts[2], unit="s"))
    sched = sched.drop(columns=["arrival_time"])
    m = obs.merge(sched, on=["trip_id", "stop_sequence"], how="left")
    m["predicted_time"] = pd.to_datetime(m["predicted_time"])
    day = m["predicted_time"].dt.normalize()
    cand = pd.concat([day + pd.Timedelta(days=x) + m["sched_td"] for x in (-1, 0, 1)], axis=1)
    diff = cand.sub(m["predicted_time"], axis=0).abs().to_numpy().astype("timedelta64[s]").astype("float64")
    diff[np.isnan(diff)] = np.inf
    best = diff.argmin(axis=1)
    m["scheduled_dt"] = cand.to_numpy()[np.arange(len(m)), best]
    m.loc[m["sched_td"].isna(), "scheduled_dt"] = pd.NaT
    m["delay_seconds"] = (m["predicted_time"] - m["scheduled_dt"]).dt.total_seconds()
    m.loc[m["delay_seconds"].abs() > 3600 * 3, "delay_seconds"] = None
    return m


if __name__ == "__main__":
    main()
