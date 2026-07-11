# GTFS-RT Feed Notes (Ticket 1)

## Confirmed working URLs

- **Trip Updates:** `https://gtfsbridge.spokanetransit.com/realtime/TripUpdate/TripUpdates.pb`
- **Vehicle Positions:** `https://gtfsbridge.spokanetransit.com/realtime/vehicle/VehiclePositions.pb`
- **Service Alerts:** `https://gtfsbridge.spokanetransit.com/realtime/Alert/Alerts.pb`

Found via Transitland's feed page for `f-spokanetransitauthority~rt`, then independently verified by
direct HTTP request + protobuf parse (not just trusting the page summary).

## Validation performed

- All three endpoints return `HTTP 200` with valid GTFS-RT protobuf payloads.
- `TripUpdates.pb` fetched twice, 65s apart:
  - Fetch 1: `header.timestamp=1782970136`, 112 `trip_update` entities
  - Fetch 2: `header.timestamp=1782970206` (+70s), 110 `trip_update` entities
  - Timestamp advanced and entity count shifted between fetches → confirmed live, not a cached/static file.
- `VehiclePositions.pb`: 55 `vehicle_position` entities present.

## What's populated (relevant to Ticket 3 poller)

- `trip_update.trip.trip_id`, `route_id`, `start_time`, `start_date`, `direction_id` — present.
- `stop_time_update.stop_sequence`, `stop_id` — present.
- `stop_time_update.arrival.time` and `departure.time` — present (unix timestamps).
- `stop_time_update.arrival.delay` / `departure.delay` — **NOT populated** in sampled entities (only
  `time` is set, no explicit `delay` field). This means the poller must log raw `predicted_time` and
  compute delay later during analysis (Ticket 5) by joining against static `scheduled_time` from
  `stop_times.txt` via `trip_id` + `stop_sequence`, exactly as anticipated in the guide's fallback plan.

## Update cadence

Not precisely measured beyond the two fetches above (~65s apart showed movement); assume roughly
30-60s granularity for polling purposes, matching the guide's `time.sleep(60)` poll interval.

## Auth / rate limits

No API key or auth header required. No rate-limit headers observed in a handful of manual requests.
License: https://www.spokanetransit.com/developers-terms-of-use/ (review before any public
redistribution of derived data; personal/local use for this project is fine).

## Decision

**Ticket 1 PASSED.** `TripUpdates.pb` has real `trip_update` entities with arrival/departure times per
stop — sufficient for computing scheduled-vs-actual delay once joined with the static schedule.
Proceeding to Ticket 3 (poller) using the Trip Updates endpoint as `RT_URL`.
