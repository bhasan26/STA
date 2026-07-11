import sqlite3
import time
from datetime import datetime
from google.transit import gtfs_realtime_pb2
import requests

RT_URL = "https://gtfsbridge.spokanetransit.com/realtime/TripUpdate/TripUpdates.pb"
DB_PATH = "data/tracker.sqlite"

def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    # WAL lets the dashboard/health-check read concurrently without blocking
    # the poller's writes -- plain "rollback journal" mode was throwing
    # "database is locked" and killing the poller outright (see incident:
    # 23h of dead collection on 2026-07-05/06).
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delay_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id TEXT, route_id TEXT, stop_id TEXT, stop_sequence INTEGER,
            scheduled_time TEXT, predicted_time TEXT, delay_seconds INTEGER,
            observed_at TEXT, day_of_week TEXT, hour_of_day INTEGER
        )
    """)
    conn.commit()
    return conn

def poll_once(conn):
    try:
        resp = requests.get(RT_URL, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{datetime.now()}] Fetch failed: {e}")
        return

    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(resp.content)
    except Exception as e:
        print(f"[{datetime.now()}] Parse failed: {e}")
        return

    now = datetime.now()
    rows = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        tu = entity.trip_update
        trip_id = tu.trip.trip_id
        route_id = tu.trip.route_id
        for stu in tu.stop_time_update:
            delay = None
            predicted_time = None
            if stu.HasField("arrival"):
                if stu.arrival.HasField("delay"):
                    delay = stu.arrival.delay
                if stu.arrival.HasField("time"):
                    predicted_time = datetime.fromtimestamp(stu.arrival.time).isoformat()
            rows.append((
                trip_id, route_id, stu.stop_id, stu.stop_sequence,
                None,  # scheduled_time joined later during analysis via static tables
                predicted_time, delay,
                now.isoformat(), now.strftime("%A"), now.hour
            ))

    if rows:
        for attempt in range(3):
            try:
                conn.executemany("""
                    INSERT INTO delay_observations
                    (trip_id, route_id, stop_id, stop_sequence, scheduled_time,
                     predicted_time, delay_seconds, observed_at, day_of_week, hour_of_day)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, rows)
                conn.commit()
                print(f"[{now}] Logged {len(rows)} stop_time_updates.")
                break
            except sqlite3.OperationalError as e:
                print(f"[{datetime.now()}] DB write failed (attempt {attempt+1}/3): {e}")
                time.sleep(2)
        else:
            print(f"[{datetime.now()}] Giving up on this cycle's write -- data for this cycle is lost, continuing.")
    else:
        print(f"[{now}] No trip_update entities this cycle.")

if __name__ == "__main__":
    conn = init_db()
    while True:
        try:
            poll_once(conn)
        except Exception as e:
            # A single bad cycle must never kill the whole poller -- this is
            # what caused a 23h collection gap (an uncaught "database is
            # locked" OperationalError escaped poll_once and crashed the loop).
            print(f"[{datetime.now()}] Unexpected error in poll_once, continuing: {e}")
        time.sleep(60)
