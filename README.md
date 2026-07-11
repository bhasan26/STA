# STA Bus Reliability Tracker

A personal project that tracks how on-time Spokane Transit Authority (STA) buses
really are. It compares each bus's scheduled arrival time against the actual predicted
time from STA's live feed, records that gap over many days, and turns it into plain
answers like "Route 1 is usually 17 minutes late" or "Route 28 to Whitworth runs later
than Route 28 to Downtown."

I wanted to work with a real dataset that nobody had already built a tutorial around
(STA's own feed) and end up with findings I could actually defend.

![dashboard](sta-delay-tracker/docs/dashboard_preview.png)

## What it does

1. Downloads STA's official bus schedule (GTFS static).
2. Every 60 seconds, fetches STA's live feed (GTFS-Realtime) and saves where every bus
   is predicted to arrive.
3. After collecting for a while, it compares predicted times against scheduled times to
   measure delay, and shows the results on a dashboard styled like a real STA bus sign.

## How the data is collected

There are two data sources, both from STA.

- Static schedule (GTFS): a zip file with the routes, trips, and stops, plus the exact
  time a bus is supposed to reach each stop. This changes rarely.
- Live feed (GTFS-Realtime): a `.pb` file STA updates about once a minute with each
  active trip's predicted arrival time at its upcoming stops.

A small Python script (`src/poller.py`) runs in a loop:

```
every 60 seconds:
    download the live feed
    for each bus trip, for each upcoming stop:
        save (trip, route, stop, predicted arrival time, when we saw it)
    write it all to a local SQLite database
```

The poller only records the raw predictions. Working out the actual delay happens later,
during analysis. Keeping the collector simple means it rarely breaks, so it keeps
collecting.

## The tricky part, and how I fixed it

At first the data looked too good, around 90% "on time." That turned out to be a trap.

The live feed only makes a real prediction for stops coming up soon. For stops far in the
future it just repeats the scheduled time, so the predicted time equals the scheduled
time and the delay looks like zero. Because the poller logs every upcoming stop every
minute, most rows were these "schedule echoes" with a fake zero delay, and they dragged
the average toward on-time.

The fix: for each stop visit, keep only the last prediction made right before the bus got
there, since that one is the most accurate. After dropping the echoes, the real
system-wide on-time rate went from a misleading 90% to about 59%. Every number in the
dashboard uses this method.

## What I found (first ~6 days of data)

- System-wide, buses are on time (within 2 minutes) about 59% of the time.
- Route 1 is the clear worst. It is on time only about 31% of the time and runs roughly
  17 minutes late on average, with its worst stretch around midday.
- Direction matters. Route 28 to Whitworth runs later than the same route to Downtown.
- Delay tends to build up along a route. A bus that leaves a couple minutes late usually
  stays late or falls further behind.

These are early numbers. The longer it collects, the more the fine details (per stop, per
hour) can be trusted.

## How to run it yourself

You need Python 3.11 or newer.

```bash
pip install -r sta-delay-tracker/requirements.txt
cd sta-delay-tracker

# 1. get the schedule
python src/fetch_static_gtfs.py
python src/load_static_gtfs.py

# 2. start collecting live data (leave this running for days or weeks)
python src/poller.py

# 3. once you have data, crunch it
python src/build_summary.py

# 4. open the dashboard
streamlit run dashboard.py
```

The dashboard needs collected data before it can show anything, so let the poller run for
a while first. The database is not in this repo because it grows to gigabytes, so
`.gitignore` keeps `data/` and `logs/` out.

## Project structure

```
sta-delay-tracker/
├── dashboard.py              # the Streamlit dashboard (the bus-sign UI)
├── requirements.txt
├── src/
│   ├── fetch_static_gtfs.py  # download the schedule zip
│   ├── load_static_gtfs.py   # load the schedule into SQLite
│   ├── poller.py             # collect the live feed every 60s (the main script)
│   ├── delay_calc.py         # match predicted vs scheduled to get delay
│   ├── data_quality.py       # sanity-check the collected data
│   ├── insights.py           # write out the findings
│   ├── build_summary.py      # precompute fast summary tables for the dashboard
│   ├── health_check.py       # check that the poller is still running
│   └── keep_awake.py         # stop the laptop from sleeping mid-collection
├── docs/feed_notes.md        # notes on the live feed
├── analysis/                 # generated findings and data-quality report
└── assets/                   # dashboard background image and credits
```

## Tech used

Python, SQLite, pandas, Streamlit, and gtfs-realtime-bindings (to read the live feed).

I kept everything simple on purpose. SQLite instead of a big database, and a plain loop
instead of heavier infrastructure, because it is a solo project running on one laptop.

## Limitations

- Only about 6 usable days of data so far, and the laptop slept for part of that, so
  there are gaps (evenings have less data than mornings).
- Finer slices (a single stop, a single hour) have less data behind them, so they are
  noisier.
- Delay comes from the feed's predictions near arrival, not from physically measuring
  when the bus reached the stop.

## Credits

- Bus data: [Spokane Transit Authority](https://www.spokanetransit.com/) GTFS feeds.
- Dashboard background photo: "Spokane City Line bus" by JTRamsey,
  [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Full_Spokane_City_Line_bus_charging_at_SCC_transit_center_October_2023.jpg),
  CC BY-SA 4.0.
