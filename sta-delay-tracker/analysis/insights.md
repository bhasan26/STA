# STA Route Reliability -- Findings

_Generated 2026-07-10 19:51 from 247,600 stop-visits (last-prediction-per-stop, schedule echoes removed)._

**Data caveat:** ~6 usable days (Jul 2-7 2026), evenings under-sampled due to collection gaps. Treat as a first pass, not a final verdict.

## Headline
- System-wide on-time rate (within +/-2 min): **59%**
- Median delay across all stop-visits: **+1.0 min**

## 5 least reliable routes (by on-time rate)
| Route | On-time | Avg delay | Stop-visits |
|---|---|---|---|
| 1 | 31% | +17.4 min | 13,401 |
| 32 | 39% | +4.1 min | 7,313 |
| 61 | 41% | +3.6 min | 6,583 |
| 62 | 44% | +2.3 min | 1,888 |
| 9 | 44% | +3.0 min | 10,594 |

## 5 routes running latest (by average delay)
| Route | Avg delay | On-time | Stop-visits |
|---|---|---|---|
| 1 | +17.4 min | 31% | 13,401 |
| 11 | +5.2 min | 65% | 1,501 |
| 32 | +4.1 min | 39% | 7,313 |
| 61 | +3.6 min | 41% | 6,583 |
| 31 | +3.6 min | 52% | 7,099 |

## Worst times of day (system-wide avg delay)
_Hours with < 2,000 stop-visits excluded (overnight noise)._
- **14:00** -- avg +4.4 min late
- **13:00** -- avg +4.0 min late
- **12:00** -- avg +3.8 min late

## Worst route + time combinations
- **Route 1 at 14:00** averages +35.6 min late (879 stop-visits)
- **Route 1 at 12:00** averages +34.4 min late (821 stop-visits)
- **Route 1 at 13:00** averages +33.2 min late (897 stop-visits)
- **Route 1 at 11:00** averages +29.4 min late (555 stop-visits)
- **Route 1 at 10:00** averages +24.5 min late (741 stop-visits)

## Weekday vs weekend
- Weekday avg delay: +2.9 min
- Weekend avg delay: +1.7 min

## Compounding delay (does lateness grow along a route?)
- Route 33: +1.7 min early-stops -> +1.5 min late-stops (flat, -0.2 min)
- Route 28: +1.3 min early-stops -> +1.6 min late-stops (flat, +0.3 min)
- Route 4: +2.7 min early-stops -> +2.4 min late-stops (flat, -0.3 min)
- Route 1: +18.6 min early-stops -> +17.3 min late-stops (shrinks, -1.3 min)
- Route 25: +2.1 min early-stops -> +1.9 min late-stops (flat, -0.2 min)
- Route 9: +2.0 min early-stops -> +3.0 min late-stops (grows, +1.0 min)
- Route 27: +1.1 min early-stops -> +0.1 min late-stops (shrinks, -1.0 min)
- Route 97: +1.5 min early-stops -> +3.6 min late-stops (grows, +2.1 min)

