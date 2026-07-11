"""Joins logged RT observations against the static schedule to compute delay_seconds.

The RT feed doesn't populate stop_time_update.arrival.delay directly (confirmed in
Ticket 1 / docs/feed_notes.md), so delay is derived here: pair each observation's
predicted_time with the static scheduled arrival_time (trip_id + stop_sequence),
using the observation's own date since GTFS scheduled times can exceed 24:00:00
for after-midnight service. Vectorized throughout — this runs on every dashboard
refresh against a table that grows continuously for weeks.
"""
import sqlite3
import numpy as np
import pandas as pd

DB_PATH = "data/tracker.sqlite"


def _parse_scheduled_timedelta(time_col):
    parts = time_col.str.split(":", expand=True).astype("int32")
    return pd.to_timedelta(parts[0], unit="h") + pd.to_timedelta(parts[1], unit="m") + pd.to_timedelta(parts[2], unit="s")


def load_delays(db_path=DB_PATH, since=None):
    conn = sqlite3.connect(db_path)
    if since is not None:
        obs = pd.read_sql(
            "SELECT * FROM delay_observations WHERE predicted_time IS NOT NULL AND observed_at >= ?",
            conn, params=(since,),
        )
    else:
        obs = pd.read_sql(
            "SELECT * FROM delay_observations WHERE predicted_time IS NOT NULL", conn
        )
    sched = pd.read_sql(
        "SELECT trip_id, stop_sequence, arrival_time FROM stop_times", conn
    )
    conn.close()

    if obs.empty:
        return obs.assign(delay_seconds=pd.Series(dtype="float64"))

    obs["trip_id"] = obs["trip_id"].astype(str)
    sched["trip_id"] = sched["trip_id"].astype(str)
    sched["sched_td"] = _parse_scheduled_timedelta(sched["arrival_time"])
    sched = sched.drop(columns=["arrival_time"])

    merged = obs.merge(sched, on=["trip_id", "stop_sequence"], how="left")
    merged["predicted_time"] = pd.to_datetime(merged["predicted_time"])
    service_day = merged["predicted_time"].dt.normalize()

    candidates = pd.concat(
        [service_day + pd.Timedelta(days=d) + merged["sched_td"] for d in (-1, 0, 1)],
        axis=1,
    )
    candidates.columns = ["prev", "same", "next"]
    diff_seconds = candidates.sub(merged["predicted_time"], axis=0).abs().to_numpy().astype("timedelta64[s]").astype("float64")
    diff_seconds[np.isnan(diff_seconds)] = np.inf
    best_idx = diff_seconds.argmin(axis=1)
    merged["scheduled_dt"] = candidates.to_numpy()[np.arange(len(merged)), best_idx]
    merged.loc[merged["sched_td"].isna(), "scheduled_dt"] = pd.NaT

    merged["delay_seconds"] = (
        merged["predicted_time"] - merged["scheduled_dt"]
    ).dt.total_seconds()

    # Drop clearly-bad joins (e.g. schedule version mismatches) rather than let
    # multi-hour artifacts distort averages.
    merged.loc[merged["delay_seconds"].abs() > 3600 * 3, "delay_seconds"] = None

    return merged.drop(columns=["sched_td"])


if __name__ == "__main__":
    import time
    t0 = time.time()
    df = load_delays()
    print(f"Rows: {len(df)}, with computed delay: {df['delay_seconds'].notna().sum()}, took {time.time()-t0:.2f}s")
    print(df["delay_seconds"].describe())
