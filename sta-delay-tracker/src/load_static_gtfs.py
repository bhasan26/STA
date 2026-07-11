import pandas as pd
import sqlite3

DB_PATH = "data/tracker.sqlite"
GTFS_DIR = "data/gtfs_static"

def main():
    conn = sqlite3.connect(DB_PATH)
    for name in ["routes", "trips", "stop_times", "stops", "calendar"]:
        df = pd.read_csv(f"{GTFS_DIR}/{name}.txt")
        df.to_sql(name, conn, if_exists="replace", index=False)
        print(f"Loaded {name}: {len(df)} rows")
    conn.close()

if __name__ == "__main__":
    main()
