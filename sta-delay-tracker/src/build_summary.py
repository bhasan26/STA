"""Precompute compact reliability summaries the dashboard reads instantly.

Runs the echo-corrected last-prediction dedup once (see insights.py), then
aggregates at several grains and writes them to a separate summary DB:

  overall          -- one row, system-wide headline
  route_stats      -- per route (rollup, both directions) for the worst list
  route_dir        -- per route + direction (inbound/outbound split)
  route_dir_hour   -- per route + direction + hour (worst-time-of-day)
  stop_stats       -- per route + direction + stop (stop-level reliability)

Direction + headsign come from trips.txt; stop names from stops.txt. No poller
change needed -- every observation already carries trip_id, stop_id, stop_sequence.

Run periodically / on demand: python src/build_summary.py
"""
import sqlite3
from datetime import datetime

import pandas as pd

from insights import load_final_predictions

SUMMARY_DB = "data/summary.sqlite"
TRACKER_DB = "data/tracker.sqlite"
MIN_STOP_N = 30   # don't publish a stop-level number on fewer visits than this


def _agg(df, keys):
    return (df.groupby(keys)
            .agg(n=("delay_seconds", "size"),
                 mean_delay_min=("delay_seconds", lambda s: s.mean() / 60),
                 median_delay_min=("delay_seconds", lambda s: s.median() / 60),
                 on_time_rate=("on_time", "mean"))
            .reset_index())


def main():
    m = load_final_predictions()   # per stop-visit, echoes removed, sparse days excluded

    # enrich with direction/headsign (trips) and stop name (stops)
    conn = sqlite3.connect(TRACKER_DB)
    trips = pd.read_sql("SELECT trip_id, direction_id, trip_headsign FROM trips", conn)
    stops = pd.read_sql("SELECT stop_id, stop_name FROM stops", conn)
    conn.close()
    trips["trip_id"] = trips["trip_id"].astype(str)
    stops["stop_id"] = stops["stop_id"].astype(str)
    m["trip_id"] = m["trip_id"].astype(str)
    m["stop_id"] = m["stop_id"].astype(str)
    m = m.merge(trips, on="trip_id", how="left")
    m = m.merge(stops, on="stop_id", how="left")
    m["trip_headsign"] = m["trip_headsign"].fillna("").astype(str)
    m["stop_name"] = m["stop_name"].fillna(m["stop_id"]).astype(str)
    # direction may be missing on a few unmatched trips -> drop those for dir tables
    m["direction_id"] = m["direction_id"]

    overall = pd.DataFrame([{
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_stop_visits": int(len(m)),
        "n_routes": int(m["route"].nunique()),
        "on_time_rate": float(m["on_time"].mean()),
        "median_delay_min": float(m["delay_seconds"].median() / 60),
        "mean_delay_min": float(m["delay_seconds"].mean() / 60),
        "data_start": m["predicted_time"].min().isoformat(),
        "data_end": m["predicted_time"].max().isoformat(),
    }])

    route_stats = _agg(m, ["route"])

    md = m[m["direction_id"].notna()].copy()
    md["direction_id"] = md["direction_id"].astype(int)
    route_dir = _agg(md, ["route", "direction_id", "trip_headsign"])
    route_dir_hour = _agg(md, ["route", "direction_id", "hour"])

    stop_stats = _agg(md, ["route", "direction_id", "trip_headsign",
                           "stop_id", "stop_name", "stop_sequence"])
    stop_stats = stop_stats[stop_stats["n"] >= MIN_STOP_N]

    conn = sqlite3.connect(SUMMARY_DB)
    overall.to_sql("overall", conn, if_exists="replace", index=False)
    route_stats.to_sql("route_stats", conn, if_exists="replace", index=False)
    route_dir.to_sql("route_dir", conn, if_exists="replace", index=False)
    route_dir_hour.to_sql("route_dir_hour", conn, if_exists="replace", index=False)
    stop_stats.to_sql("stop_stats", conn, if_exists="replace", index=False)
    conn.close()

    print(f"Summary built: {len(route_stats)} routes, {len(route_dir)} route-directions, "
          f"{len(stop_stats)} stop rows, from {overall['n_stop_visits'][0]:,} stop-visits.")


if __name__ == "__main__":
    main()
