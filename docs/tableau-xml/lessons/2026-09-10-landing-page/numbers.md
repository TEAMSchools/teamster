# Landing page numbers: tiles vs source BANs

Probe: `ZZ-REVIEW 2026-09-10 AGHS landing page PROBE` in GPA-monitor-temp,
parameters at their defaults (`p_Region` = `All`). Values parsed from the view
CSV.

| Measure                  | Tile sheet                   | Tile value                | Source sheet                          | Source value              | Equal |
| ------------------------ | ---------------------------- | ------------------------- | ------------------------------------- | ------------------------- | ----- |
| % Y1 GPA at or above 3.0 | `LP - Tile Y1 GPA`           | 69% (0.69)                | `Y1 Landing - BAN Network ≥3.0`       | 69% (0.69)                | yes   |
| % Y1 Failing 2 or more   | `LP - Tile Course Failures`  | 8% (0.08)                 | `Y1 Landing - BAN Network Failing ≥2` | 8% (0.08)                 | yes   |
| % at 3.0+                | `LP - Tile Cumulative GPA`   | 0.484261501 (0.484261501) | `GPA - BAN % 3.0+`                    | 0.484261501 (0.484261501) | yes   |
| % healthy                | `LP - Tile Gradebook Health` | 15% (0.15)                | `BAN Network`                         | 15% (0.15)                | yes   |
| Students still needed    | `LP - Tile Cumulative GPA`   | 0 (0.0)                   | `GPA - BAN Students needed`           | 0 (0.0)                   | yes   |

## Region strips

| Strip sheet                   | Regions                  | Values                                 |
| ----------------------------- | ------------------------ | -------------------------------------- |
| `LP - Strip Y1 GPA`           | Camden, Newark, Paterson | Camden=58%; Newark=74%; Paterson=52%   |
| `LP - Strip Course Failures`  | Camden, Newark, Paterson | Camden=16%; Newark=6%; Paterson=4%     |
| `LP - Strip Cumulative GPA`   | Camden, Newark           | Camden=0.484848485; Newark=0.484076433 |
| `LP - Strip Gradebook Health` | Camden, Newark, Paterson | Camden=3%; Newark=20%; Paterson=6%     |

- Three MS/HS strips share a region set: yes (Camden, Newark, Paterson)
- Cumulative strip regions: Camden, Newark; strict subset of the other three:
  yes
