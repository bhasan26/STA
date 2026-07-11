# Data Quality Report (Ticket 4)

_Generated 2026-07-10T19:39:30_

## 1. Volume & span
- Total observations: **28,257,866**
- Span: 2026-07-01T22:32:41 -> 2026-07-10T19:38:40

## 2. Route coverage
- Routes observed: **44** of 83 in the static schedule
- OK -- many routes; no obvious filtering bug

## 3. Daily coverage
| Day | Weekday | Rows | Hours | Assessment |
|---|---|---|---|---|
| 2026-07-01 | Wed | 236,155 | 2/24 | sparse |
| 2026-07-02 | Thu | 7,872,684 | 19/24 | FULL |
| 2026-07-03 | Fri | 8,131,167 | 18/24 | FULL |
| 2026-07-04 | Sat | 2,264,930 | 10/24 | partial |
| 2026-07-05 | Sun | 3,928,691 | 13/24 | partial |
| 2026-07-06 | Mon | 1,947,677 | 9/24 | partial |
| 2026-07-07 | Tue | 3,825,434 | 10/24 | partial |
| 2026-07-10 | Fri | 55,009 | 1/24 | sparse |

### Service-hour gaps (>= 2h)
- 2026-07-01 05:00 -> 21:59  (17h)
- 2026-07-03 18:00 -> 23:59  (6h)
- 2026-07-04 05:00 -> 13:59  (9h)
- 2026-07-05 13:00 -> 23:59  (11h)
- 2026-07-06 05:00 -> 11:59  (7h)
- 2026-07-06 19:00 -> 21:59  (3h)
- 2026-07-07 10:00 -> 23:59  (14h)
- 2026-07-08 05:00 -> 23:59  (19h)
- 2026-07-09 05:00 -> 23:59  (19h)
- 2026-07-10 05:00 -> 18:59  (14h)
- 2026-07-10 20:00 -> 23:59  (4h)

## 4. trip_id join integrity
- 100.0% of observed trip_ids match the static `trips` table
- OK

## 5. Delay distribution (sampled)
- Sample size with computed delay: 394,403
- Median: +0.0 min | Mean: +0.4 min
- p10 / p90: -0.8 / +0.5 min
- On-time (within +/-2 min): 90.5%
- Exactly zero: 67.1%  (suspicious -- delay field may be unpopulated)
- Extreme (|delay| > 30 min): 0.56%  (OK)


## Verdict
Usable for a first analysis on the FULL/partial days (Jul 2-7). Sparse days (Jul 1, 10) and the service-hour gaps above should be excluded or caveated. Evening coverage is thinner than morning due to sleep gaps.
