"""Poller health check — is data still flowing, and are there gaps?

Run once:      python src/health_check.py
Run hourly:    python src/health_check.py --loop

Appends a snapshot to logs/health.log each run. Designed for the 2-3 week
collection window (guide Ticket 4 / operating notes): confirm the poller is
alive and flag multi-hour gaps that indicate crashes or machine downtime —
without treating expected overnight quiet (no bus service) as a problem.
"""
import sqlite3
import sys
import time
from datetime import datetime, timedelta

DB_PATH = "data/tracker.sqlite"
LOG_PATH = "logs/health.log"

FRESH_THRESHOLD_MIN = 5   # latest observation should be this recent while buses run
GAP_MIN_HOURS = 2         # flag runs of missing hours this long or longer
SERVICE_START_HOUR = 5    # STA service roughly 5am -> ~1am; gaps outside this are "normal"
SERVICE_END_HOUR = 1


def _in_service_window(hour):
    # service spans midnight: 5..23 and 0..1
    return hour >= SERVICE_START_HOUR or hour <= SERVICE_END_HOUR


def run_once():
    now = datetime.now()
    lines = [f"===== Health check {now.isoformat(timespec='seconds')} ====="]
    conn = sqlite3.connect(DB_PATH)

    total, latest = conn.execute(
        "SELECT COUNT(*), MAX(observed_at) FROM delay_observations"
    ).fetchone()
    lines.append(f"Total observations: {total:,}")

    alive = False
    if latest:
        latest_dt = datetime.fromisoformat(latest)
        age_min = (now - latest_dt).total_seconds() / 60
        hour = now.hour
        if age_min <= FRESH_THRESHOLD_MIN:
            alive = True
            status = "ALIVE"
        elif not _in_service_window(hour):
            status = "quiet (outside service hours -- expected)"
        else:
            status = "STALE -- poller may be DOWN"
        lines.append(f"Latest observation: {latest} ({age_min:.1f} min ago) -> {status}")
    else:
        lines.append("No observations logged yet.")

    # last-24h volume + route coverage
    since = (now - timedelta(hours=24)).isoformat()
    row = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT route_id) FROM delay_observations WHERE observed_at >= ?",
        (since,),
    ).fetchone()
    lines.append(f"Last 24h: {row[0]:,} observations across {row[1]} routes")

    # gap detection: which hour-buckets are present in the last ~26h?
    lookback = (now - timedelta(hours=26)).isoformat()
    present = {
        r[0] for r in conn.execute(
            "SELECT DISTINCT substr(observed_at, 1, 13) FROM delay_observations WHERE observed_at >= ?",
            (lookback,),
        ).fetchall()
    }
    conn.close()

    if present:
        first = datetime.strptime(min(present), "%Y-%m-%dT%H")
        last = datetime.strptime(max(present), "%Y-%m-%dT%H")
        missing = []
        cur = first
        while cur <= last:
            key = cur.strftime("%Y-%m-%dT%H")
            if key not in present:
                missing.append(cur)
            cur += timedelta(hours=1)

        # group consecutive missing hours into runs
        runs = []
        for m in missing:
            if runs and (m - runs[-1][-1]) == timedelta(hours=1):
                runs[-1].append(m)
            else:
                runs.append([m])

        concerning = [
            run for run in runs
            if len(run) >= GAP_MIN_HOURS and any(_in_service_window(h.hour) for h in run)
        ]
        if concerning:
            lines.append(f"WARNING: {len(concerning)} multi-hour gap(s) during service hours:")
            for run in concerning:
                lines.append(f"  - {run[0]:%Y-%m-%d %H:00} -> {run[-1]:%H:59} ({len(run)}h missing)")
        else:
            lines.append("No concerning gaps in the last 24h.")

    report = "\n".join(lines)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(report + "\n\n")
    print(report)
    return alive


if __name__ == "__main__":
    if "--loop" in sys.argv:
        while True:
            run_once()
            time.sleep(3600)  # hourly
    else:
        run_once()
