# DDI: unexplained row groups to run down

From the `ask-owner` render for #6415. These differences have no cause yet, so
they are not owner questions. A new session runs them down with the
`cube-validation` skill: `sort` for trace leads, then `explain` per comparison
and bucket. The saved run is local to the codespace that made it, and BigQuery
time travel to its moment ends 2026-11-22 22:34 UTC. A new session elsewhere
starts with `compare --all`, then `sort`.

Groups under 10 rows are counted, not listed. Columns the validator masks
(dates, and every column of a small group) are left out of the cell.

| Comparison                                  | Bucket         | Groups of 10+ rows | Groups under 10 rows |
| ------------------------------------------- | -------------- | ------------------ | -------------------- |
| `avg_percent_correct__standards_over_time`  | cube_only      | 485                | 4                    |
| `avg_percent_correct__standards_over_time`  | dashboard_only | 82                 | 44                   |
| `avg_percent_correct__standards_over_time`  | dims_differ    | 62                 | 1                    |
| `count_assessments__standards_over_time`    | cube_only      | 485                | 4                    |
| `count_assessments__standards_over_time`    | dashboard_only | 82                 | 44                   |
| `count_assessments__standards_over_time`    | dims_differ    | 62                 | 1                    |
| `count_students__score_distribution`        | cube_only      | 205                | 1                    |
| `count_students__score_distribution`        | dashboard_only | 47                 | 0                    |
| `count_students__score_distribution`        | dims_differ    | 46                 | 27                   |
| `grade_goal_distance__grid_grade`           | cube_only      | 4                  | 3                    |
| `grade_goal_distance__grid_grade`           | dashboard_only | 1                  | 27                   |
| `grade_goal_distance__grid_grade`           | dims_differ    | 0                  | 7                    |
| `pct_proficient__dki_grid`                  | cube_only      | 4                  | 4                    |
| `pct_proficient__dki_grid`                  | dashboard_only | 2                  | 34                   |
| `pct_proficient__dki_grid`                  | dims_differ    | 0                  | 8                    |
| `pct_proficient__dki_standards_grid`        | cube_only      | 16                 | 17                   |
| `pct_proficient__dki_standards_grid`        | dashboard_only | 14                 | 252                  |
| `pct_proficient__dki_standards_grid`        | dims_differ    | 0                  | 5                    |
| `pct_students_at_level__dki_bars`           | cube_only      | 4                  | 4                    |
| `pct_students_at_level__dki_bars`           | dashboard_only | 2                  | 40                   |
| `pct_students_at_level__dki_bars`           | dims_differ    | 0                  | 13                   |
| `pct_students_at_level__dki_standards_bars` | cube_only      | 16                 | 18                   |
| `pct_students_at_level__dki_standards_bars` | dashboard_only | 13                 | 278                  |
| `pct_students_at_level__dki_standards_bars` | dims_differ    | 0                  | 5                    |
| `pct_taken__assessments_over_time`          | cube_only      | 2                  | 0                    |
| `pct_taken__assessments_over_time`          | dashboard_only | 16                 | 3                    |
| `pct_taken__assessments_over_time`          | dims_differ    | 1                  | 13                   |
| `region_goal_distance__lines_all`           | cube_only      | 5                  | 0                    |
| `region_goal_distance__lines_all`           | dashboard_only | 5                  | 7                    |
| `school_goal_distance__lines_all`           | cube_only      | 7                  | 1                    |
| `school_goal_distance__lines_all`           | dashboard_only | 2                  | 22                   |
| `school_goal_distance__lines_all`           | dims_differ    | 0                  | 1                    |

## `avg_percent_correct__standards_over_time`, cube_only

| Rows   | Cell                                                                 | Trace lead |
| ------ | -------------------------------------------------------------------- | ---------- |
| 669120 | `academic_year=2024,academic_subject=Mathematics,#4`                 | yes        |
| 635764 | `academic_year=2023,academic_subject=Mathematics,#4`                 | yes        |
| 509828 | `academic_year=2024,academic_subject=Text Study,#4`                  | yes        |
| 401667 | `academic_year=2023,academic_subject=Text Study,#4`                  | yes        |
| 371234 | `academic_year=2018,academic_subject=Mathematics,#4`                 | yes        |
| 358816 | `academic_year=2022,academic_subject=Mathematics,#4`                 | yes        |
| 283361 | `academic_year=2019,academic_subject=Mathematics,#4`                 | yes        |
| 270140 | `academic_year=2022,academic_subject=Text Study,#4`                  | yes        |
| 264425 | `academic_year=2019,academic_subject=Text Study`                     | yes        |
| 248390 | `academic_year=2021,academic_subject=Mathematics,#4`                 | yes        |
| 243966 | `academic_year=2025,academic_subject=Reading`                        | yes        |
| 234480 | `academic_year=2018,academic_subject=Text Study`                     | yes        |
| 227739 | `academic_year=2021,academic_subject=Text Study,#4`                  | yes        |
| 221230 | `academic_year=2024,academic_subject=Reading`                        | yes        |
| 188891 | `academic_year=2023,academic_subject=Reading`                        | yes        |
| 179291 | `academic_year=2019,academic_subject=Text Study,#4`                  | yes        |
| 177648 | `academic_year=2023,academic_subject=Science`                        | yes        |
| 174705 | `academic_year=2024,academic_subject=Science`                        | yes        |
| 173741 | `academic_year=2018,academic_subject=Text Study,#4`                  | yes        |
| 162830 | `academic_year=2020,academic_subject=Mathematics,#4`                 | yes        |
| 159147 | `academic_year=2017,academic_subject=Mathematics,#4`                 | yes        |
| 156490 | `academic_year=2024,academic_subject=Science,#4`                     | yes        |
| 155619 | `academic_year=2022,academic_subject=Text Study`                     | yes        |
| 129361 | `academic_year=2024,academic_subject=Mathematics,#3`                 | yes        |
| 125478 | `academic_year=2021,academic_subject=Text Study`                     | yes        |
| 121015 | `academic_year=2015,academic_subject=Writing,#3`                     | yes        |
| 119112 | `academic_year=2020,academic_subject=Text Study,#4`                  | yes        |
| 117135 | `academic_year=2023,academic_subject=Mathematics,#3`                 | yes        |
| 116939 | `academic_year=2023,academic_subject=Text Study`                     | yes        |
| 116227 | `academic_year=2022,academic_subject=Science`                        | yes        |
| 106941 | `academic_year=2017,academic_subject=Text Study,#4`                  | yes        |
| 106164 | `academic_year=2025,academic_subject=Math`                           | yes        |
| 104314 | `academic_year=2024,academic_subject=Text Study,#3`                  | yes        |
| 104171 | `academic_year=2023,academic_subject=Mathematics`                    | yes        |
| 96436  | `academic_year=2024,academic_subject=Math`                           | yes        |
| 95506  | `academic_year=2020,academic_subject=Text Study`                     | yes        |
| 94652  | `academic_year=2023,academic_subject=Math`                           | yes        |
| 92973  | `academic_year=2022,academic_subject=Mathematics,#2`                 | yes        |
| 92908  | `academic_year=2023,academic_subject=Science,#4`                     | yes        |
| 91748  | `academic_year=2022,academic_subject=Math`                           | yes        |
| 88842  | `academic_year=2022,academic_subject=Mathematics,#3`                 | yes        |
| 88434  | `academic_year=2022,academic_subject=Reading`                        | yes        |
| 87992  | `academic_year=2016,academic_subject=Text Study`                     | yes        |
| 87031  | `academic_year=2026,academic_subject=Reading`                        | yes        |
| 84728  | `academic_year=2021,academic_subject=Math`                           | yes        |
| 80540  | `academic_year=2023,academic_subject=Social Studies,#4`              | yes        |
| 76100  | `academic_year=2024,academic_subject=Social Studies,#3`              | yes        |
| 75105  | `academic_year=2022,academic_subject=Mathematics`                    | yes        |
| 72685  | `academic_year=2021,academic_subject=Mathematics`                    | yes        |
| 71745  | `academic_year=2021,academic_subject=Science`                        | yes        |
| 71443  | `academic_year=2015,academic_subject=Text Study,#4`                  | yes        |
| 71047  | `academic_year=2019,academic_subject=Writing,#4`                     | yes        |
| 70772  | `academic_year=2020,academic_subject=Math`                           | yes        |
| 69392  | `academic_year=2021,academic_subject=Social Studies`                 | yes        |
| 69184  | `academic_year=2023,academic_subject=Mathematics,#2`                 | yes        |
| 68798  | `academic_year=2022,academic_subject=Text Study,#2`                  | yes        |
| 67662  | `academic_year=2021,academic_subject=Reading`                        | yes        |
| 66269  | `academic_year=2023,academic_subject=Text Study,#3`                  | yes        |
| 64815  | `academic_year=2019,academic_subject=Mathematics,#2`                 | yes        |
| 63638  | `academic_year=2022,academic_subject=Writing,#4`                     | yes        |
| 63024  | `academic_year=2016,academic_subject=Mathematics,#4`                 | yes        |
| 61631  | `academic_year=2021,academic_subject=Mathematics,#3`                 | yes        |
| 57384  | `academic_year=2017,academic_subject=Text Study`                     | yes        |
| 56436  | `academic_year=2016,academic_subject=Text Study,#4`                  | yes        |
| 55482  | `academic_year=2019,academic_subject=Mathematics,#3`                 | yes        |
| 53054  | `academic_year=2018,academic_subject=Mathematics,#3`                 | yes        |
| 52460  | `academic_year=2022,academic_subject=Science,#4`                     | yes        |
| 52348  | `academic_year=2025,academic_subject=Reading,#2`                     | yes        |
| 52257  | `academic_year=2023,academic_subject=Text Study,#2`                  | yes        |
| 51525  | `academic_year=2024,academic_subject=Text Study`                     | yes        |
| 51076  | `academic_year=2023,academic_subject=Social Studies`                 | yes        |
| 50022  | `academic_year=2021,academic_subject=Mathematics,#2`                 | yes        |
| 47883  | `academic_year=2022,academic_subject=Text Study,#3`                  | yes        |
| 47476  | `academic_year=2024,academic_subject=Reading,#2`                     | yes        |
| 44434  | `academic_year=2016,academic_subject=Writing,#3`                     | yes        |
| 43780  | `academic_year=2018,academic_subject=Mathematics`                    | yes        |
| 43617  | `academic_year=2023,academic_subject=Writing,#4`                     | yes        |
| 43366  | `academic_year=2020,academic_subject=Mathematics`                    | yes        |
| 39747  | `academic_year=2020,academic_subject=Science`                        | yes        |
| 39661  | `academic_year=2021,academic_subject=Text Study,#3`                  | yes        |
| 38627  | `academic_year=2020,academic_subject=Mathematics,#3`                 | yes        |
| 37668  | `academic_year=2026,academic_subject=Math`                           | yes        |
| 37641  | `academic_year=2024,academic_subject=Science,#3`                     | yes        |
| 35153  | `academic_year=2018,academic_subject=Text Study,#3`                  | yes        |
| 34703  | `academic_year=2019,academic_subject=Text Study,#3`                  | yes        |
| 34569  | `academic_year=2017,academic_subject=Writing,#2`                     | yes        |
| 33936  | `academic_year=2020,academic_subject=Reading`                        | yes        |
| 32284  | `academic_year=2023,academic_subject=Reading,#2`                     | yes        |
| 31889  | `academic_year=2016,academic_subject=Mathematics,#2`                 | yes        |
| 31112  | `academic_year=2024,academic_subject=English 100,#4`                 | yes        |
| 30807  | `academic_year=2024,academic_subject=US History AfricanAmerican,#4`  | yes        |
| 30438  | `academic_year=2020,academic_subject=Mathematics,#2`                 | yes        |
| 30338  | `academic_year=2017,academic_subject=Algebra I,#4`                   | yes        |
| 29563  | `academic_year=2022,academic_subject=Social Studies,#4`              | yes        |
| 29071  | `academic_year=2024,academic_subject=Algebra I,#4`                   | yes        |
| 28850  | `academic_year=2015,academic_subject=Mathematics,#4`                 | yes        |
| 27680  | `academic_year=2025,academic_subject=Math,#2`                        | yes        |
| 27549  | `academic_year=2020,academic_subject=Text Study,#3`                  | yes        |
| 27173  | `academic_year=2020,academic_subject=Science,#4`                     | yes        |
| 27002  | `academic_year=2023,academic_subject=English 100,#4`                 | yes        |
| 25659  | `academic_year=2019,academic_subject=Mathematics`                    | yes        |
| 25355  | `academic_year=2024,academic_subject=Math,#2`                        | yes        |
| 25078  | `academic_year=2024,academic_subject=English 200,#4`                 | yes        |
| 25000  | `academic_year=2016,academic_subject=Social Studies,#4`              | yes        |
| 24997  | `academic_year=2020,academic_subject=Social Studies`                 | yes        |
| 24922  | `academic_year=2018,academic_subject=Writing,#3`                     | yes        |
| 24915  | `academic_year=2023,academic_subject=Math,#2`                        | yes        |
| 24628  | `academic_year=2022,academic_subject=Social Studies`                 | yes        |
| 24570  | `academic_year=2023,academic_subject=English 200,#4`                 | yes        |
| 23979  | `academic_year=2018,academic_subject=Mathematics,#2`                 | yes        |
| 23803  | `academic_year=2015,academic_subject=Mathematics`                    | yes        |
| 23426  | `academic_year=2015,academic_subject=Mathematics,#2`                 | yes        |
| 22999  | `academic_year=2022,academic_subject=English 200,#4`                 | yes        |
| 22937  | `academic_year=2022,academic_subject=Math,#2`                        | yes        |
| 22138  | `academic_year=2017,academic_subject=Mathematics,#2`                 | yes        |
| 21605  | `academic_year=2016,academic_subject=Social Studies,#2`              | yes        |
| 21269  | `academic_year=2021,academic_subject=Writing,#4`                     | yes        |
| 21182  | `academic_year=2021,academic_subject=Math,#2`                        | yes        |
| 21152  | `academic_year=2024,academic_subject=Mathematics,#2`                 | yes        |
| 21019  | `academic_year=2018,academic_subject=Geometry,#4`                    | yes        |
| 21008  | `academic_year=2016,academic_subject=Science,#4`                     | yes        |
| 20112  | `academic_year=2018,academic_subject=Algebra I,#4`                   | yes        |
| 19941  | `academic_year=2024,academic_subject=Science,#2`                     | yes        |
| 19607  | `academic_year=2017,academic_subject=Geometry,#4`                    | yes        |
| 19471  | `academic_year=2015,academic_subject=Text Study`                     | yes        |
| 19171  | `academic_year=2024,academic_subject=English 400,#4`                 | yes        |
| 18504  | `academic_year=2026,academic_subject=Reading,#2`                     | yes        |
| 18085  | `academic_year=2022,academic_subject=English 100,#4`                 | yes        |
| 17693  | `academic_year=2020,academic_subject=Math,#2`                        | yes        |
| 17355  | `academic_year=2024,academic_subject=Text Study,#2`                  | yes        |
| 16999  | `academic_year=2024,academic_subject=Chemistry,#3`                   | yes        |
| 16959  | `academic_year=2017,academic_subject=Science,#3`                     | yes        |
| 16784  | `academic_year=2015,academic_subject=Text Study,#2`                  | yes        |
| 16376  | `academic_year=2024,academic_subject=English 300,#3`                 | yes        |
| 16238  | `academic_year=2017,academic_subject=Mathematics`                    | yes        |
| 16225  | `academic_year=2022,academic_subject=Social Studies,#2`              | yes        |
| 16002  | `academic_year=2023,academic_subject=Geometry,#3`                    | yes        |
| 15761  | `academic_year=2024,academic_subject=Biology,#3`                     | yes        |
| 15654  | `academic_year=2021,academic_subject=Social Studies,#2`              | yes        |
| 15566  | `academic_year=2017,academic_subject=Social Studies,#2`              | yes        |
| 15564  | `academic_year=2022,academic_subject=Science,#3`                     | yes        |
| 15395  | `academic_year=2021,academic_subject=Social Studies,#4`              | yes        |
| 15306  | `academic_year=2016,academic_subject=Science,#2`                     | yes        |
| 14755  | `academic_year=2023,academic_subject=Science,#3`                     | yes        |
| 14739  | `academic_year=2022,academic_subject=Reading,#2`                     | yes        |
| 14250  | `academic_year=2023,academic_subject=English 300,#4`                 | yes        |
| 14054  | `academic_year=2021,academic_subject=Science,#4`                     | yes        |
| 13897  | `academic_year=2022,academic_subject=Geometry,#4`                    | yes        |
| 13831  | `academic_year=2021,academic_subject=Science,#3`                     | yes        |
| 13669  | `academic_year=2024,academic_subject=World History,#4`               | yes        |
| 13626  | `academic_year=2024,academic_subject=Algebra II,#4`                  | yes        |
| 13619  | `academic_year=2023,academic_subject=Social Studies,#3`              | yes        |
| 13437  | `academic_year=2023,academic_subject=Algebra I,#3`                   | yes        |
| 13437  | `academic_year=2016,academic_subject=Social Studies`                 | yes        |
| 13410  | `academic_year=2024,academic_subject=Social Studies,#2`              | yes        |
| 13244  | `academic_year=2017,academic_subject=Social Studies,#4`              | yes        |
| 12970  | `academic_year=2017,academic_subject=Social Studies`                 | yes        |
| 12758  | `academic_year=2024,academic_subject=Geometry,#3`                    | yes        |
| 12734  | `academic_year=2019,academic_subject=Writing,#3`                     | yes        |
| 12312  | `academic_year=2022,academic_subject=Algebra II,#4`                  | yes        |
| 12148  | `academic_year=2024,academic_subject=Physics,#3`                     | yes        |
| 11685  | `academic_year=2021,academic_subject=Geometry,#3`                    | yes        |
| 11599  | `academic_year=2023,academic_subject=US History AfricanAmerican,#4`  | yes        |
| 11277  | `academic_year=2021,academic_subject=Reading,#2`                     | yes        |
| 11177  | `academic_year=2024,academic_subject=US History,#4`                  | yes        |
| 11174  | `academic_year=2023,academic_subject=Algebra II,#3`                  | yes        |
| 11108  | `academic_year=2021,academic_subject=Text Study,#2`                  | yes        |
| 10579  | `academic_year=2021,academic_subject=Social Studies,#3`              | yes        |
| 10499  | `academic_year=2018,academic_subject=Algebra II,#4`                  | yes        |
| 10415  | `academic_year=2017,academic_subject=English 100,#4`                 | yes        |
| 10399  | `academic_year=2019,academic_subject=Text Study,#2`                  | yes        |
| 10318  | `academic_year=2016,academic_subject=Mathematics`                    | yes        |
| 10275  | `academic_year=2020,academic_subject=Text Study,#2`                  | yes        |
| 10256  | `academic_year=2022,academic_subject=Algebra I,#4`                   | yes        |
| 10142  | `academic_year=2018,academic_subject=English 100,#4`                 | yes        |
| 9972   | `academic_year=2021,academic_subject=Algebra I,#3`                   | yes        |
| 9934   | `academic_year=2022,academic_subject=Writing,#3`                     | yes        |
| 9934   | `academic_year=2022,academic_subject=Writing`                        | yes        |
| 9911   | `academic_year=2022,academic_subject=English 300,#4`                 | yes        |
| 9879   | `academic_year=2017,academic_subject=Mathematics,#3`                 | yes        |
| 9806   | `academic_year=2022,academic_subject=English 200`                    | yes        |
| 9791   | `academic_year=2026,academic_subject=Math,#2`                        | yes        |
| 9748   | `academic_year=2018,academic_subject=Social Studies`                 | yes        |
| 9512   | `academic_year=2018,academic_subject=English 200,#4`                 | yes        |
| 9419   | `academic_year=2020,academic_subject=Science,#3`                     | yes        |
| 9300   | `academic_year=2016,academic_subject=Text Study,#2`                  | yes        |
| 9251   | `academic_year=2022,academic_subject=Social Studies,#3`              | yes        |
| 9195   | `academic_year=2023,academic_subject=Chemistry,#3`                   | yes        |
| 9112   | `academic_year=2019,academic_subject=Social Studies`                 | yes        |
| 9090   | `academic_year=2019,academic_subject=Social Studies,#4`              | yes        |
| 9055   | `academic_year=2016,academic_subject=Text Study,#3`                  | yes        |
| 9009   | `academic_year=2016,academic_subject=Mathematics,#3`                 | yes        |
| 8898   | `academic_year=2017,academic_subject=Science`                        | yes        |
| 8780   | `academic_year=2022,academic_subject=Science,#2`                     | yes        |
| 8494   | `academic_year=2022,academic_subject=Writing,#2`                     | yes        |
| 8416   | `academic_year=2023,academic_subject=English 400,#4`                 | yes        |
| 8408   | `academic_year=2025,academic_subject=English Language Arts`          | yes        |
| 8334   | `academic_year=2022,academic_subject=English 400,#4`                 | yes        |
| 8209   | `academic_year=2017,academic_subject=English 200,#3`                 | yes        |
| 8179   | `academic_year=2024,academic_subject=English Language Arts`          | yes        |
| 7957   | `academic_year=2015,academic_subject=Writing,#2`                     | yes        |
| 7940   | `academic_year=2017,academic_subject=Science,#2`                     | yes        |
| 7890   | `academic_year=2023,academic_subject=Physics,#3`                     | yes        |
| 7889   | `academic_year=2023,academic_subject=US History,#4`                  | yes        |
| 7758   | `academic_year=2025,academic_subject=Mathematics,#3`                 | yes        |
| 7740   | `academic_year=2024,academic_subject=AP World History,#4`            | yes        |
| 7573   | `academic_year=2023,academic_subject=English Language Arts`          | yes        |
| 7455   | `academic_year=2022,academic_subject=English 100`                    | yes        |
| 7400   | `academic_year=2021,academic_subject=Science,#2`                     | yes        |
| 7363   | `academic_year=2021,academic_subject=Algebra II,#4`                  | yes        |
| 7349   | `academic_year=2023,academic_subject=English 200`                    | yes        |
| 7166   | `academic_year=2015,academic_subject=Text Study,#3`                  | yes        |
| 7149   | `academic_year=2023,academic_subject=Social Studies,#2`              | yes        |
| 7115   | `academic_year=2024,academic_subject=Mathematics`                    | yes        |
| 7072   | `academic_year=2024,academic_subject=AP US History,#4`               | yes        |
| 6836   | `academic_year=2023,academic_subject=Biology,#3`                     | yes        |
| 6670   | `academic_year=2023,academic_subject=Writing,#3`                     | yes        |
| 6670   | `academic_year=2023,academic_subject=Writing`                        | yes        |
| 6630   | `academic_year=2017,academic_subject=English 300,#3`                 | yes        |
| 6621   | `academic_year=2022,academic_subject=English Language Arts`          | yes        |
| 6607   | `academic_year=2024,academic_subject=US History AfricanAmerican,#3`  | yes        |
| 6594   | `academic_year=2020,academic_subject=Social Studies,#2`              | yes        |
| 6524   | `academic_year=2020,academic_subject=Social Studies,#3`              | yes        |
| 6421   | `academic_year=2018,academic_subject=Social Studies,#4`              | yes        |
| 6416   | `academic_year=2023,academic_subject=English 100`                    | yes        |
| 6182   | `academic_year=2018,academic_subject=Text Study,#2`                  | yes        |
| 5742   | `academic_year=2023,academic_subject=World History,#3`               | yes        |
| 5656   | `academic_year=2020,academic_subject=Reading,#2`                     | yes        |
| 5510   | `academic_year=2019,academic_subject=Social Studies,#2`              | yes        |
| 5497   | `academic_year=2018,academic_subject=English 300,#4`                 | yes        |
| 5477   | `academic_year=2024,academic_subject=Algebra I,#3`                   | yes        |
| 5434   | `academic_year=2020,academic_subject=Science,#2`                     | yes        |
| 5424   | `academic_year=2017,academic_subject=Text Study,#3`                  | yes        |
| 5167   | `academic_year=2016,academic_subject=Science,#3`                     | yes        |
| 5155   | `academic_year=2022,academic_subject=English 300`                    | yes        |
| 5019   | `academic_year=2024,academic_subject=English 100,#3`                 | yes        |
| 4874   | `academic_year=2018,academic_subject=Social Studies,#3`              | yes        |
| 4771   | `academic_year=2023,academic_subject=Writing,#2`                     | yes        |
| 4755   | `academic_year=2023,academic_subject=AP World History,#4`            | yes        |
| 4593   | `academic_year=2017,academic_subject=Text Study,#2`                  | yes        |
| 4556   | `academic_year=2019,academic_subject=Social Studies,#3`              | yes        |
| 4536   | `academic_year=2021,academic_subject=English 200,#4`                 | yes        |
| 4410   | `academic_year=2021,academic_subject=English Language Arts`          | yes        |
| 4406   | `academic_year=2023,academic_subject=Science,#2`                     | yes        |
| 4355   | `academic_year=2024,academic_subject=English 200,#3`                 | yes        |
| 4300   | `academic_year=2016,academic_subject=Social Studies,#3`              | yes        |
| 4283   | `academic_year=2024,academic_subject=Algebra I MS,#3`                | yes        |
| 4230   | `academic_year=2018,academic_subject=Pre-Calculus,#4`                | yes        |
| 4083   | `academic_year=2019,academic_subject=AP Language`                    | yes        |
| 4037   | `academic_year=2023,academic_subject=AP US History,#4`               | yes        |
| 4024   | `academic_year=2023,academic_subject=English 300`                    | yes        |
| 3944   | `academic_year=2015,academic_subject=Mathematics,#3`                 | yes        |
| 3873   | `academic_year=2024,academic_subject=Algebra I`                      | yes        |
| 3768   | `academic_year=2021,academic_subject=Algebra I`                      | yes        |
| 3730   | `academic_year=2024,academic_subject=World History,#3`               | yes        |
| 3677   | `academic_year=2023,academic_subject=Algebra I,#2`                   | yes        |
| 3643   | `academic_year=2022,academic_subject=English 400`                    | yes        |
| 3609   | `academic_year=2018,academic_subject=Social Studies,#2`              | yes        |
| 3581   | `academic_year=2021,academic_subject=Writing,#3`                     | yes        |
| 3581   | `academic_year=2021,academic_subject=Writing`                        | yes        |
| 3540   | `academic_year=2023,academic_subject=Geometry,#2`                    | yes        |
| 3470   | `academic_year=2018,academic_subject=Geometry`                       | yes        |
| 3442   | `academic_year=2024,academic_subject=Physics`                        | yes        |
| 3426   | `academic_year=2024,academic_subject=Chemistry,#2`                   | yes        |
| 3408   | `academic_year=2021,academic_subject=English 100,#4`                 | yes        |
| 3372   | `academic_year=2016,academic_subject=Writing`                        | yes        |
| 3195   | `academic_year=2021,academic_subject=Algebra I,#2`                   | yes        |
| 3107   | `academic_year=2018,academic_subject=Writing,#2`                     | yes        |
| 3090   | `academic_year=2024,academic_subject=Social Studies`                 | yes        |
| 3063   | `academic_year=2024,academic_subject=Geometry,#2`                    | yes        |
| 3035   | `academic_year=2022,academic_subject=Algebra I,#3`                   | yes        |
| 3021   | `academic_year=2024,academic_subject=English 400,#3`                 | yes        |
| 3021   | `academic_year=2021,academic_subject=Geometry`                       | yes        |
| 3018   | `academic_year=2024,academic_subject=US History AfricanAmerican`     | yes        |
| 2945   | `academic_year=2024,academic_subject=English 300,#2`                 | yes        |
| 2901   | `academic_year=2023,academic_subject=Chemistry,#2`                   | yes        |
| 2858   | `academic_year=2016,academic_subject=Science`                        | yes        |
| 2837   | `academic_year=2024,academic_subject=Algebra II,#3`                  | yes        |
| 2814   | `academic_year=2018,academic_subject=English 100`                    | yes        |
| 2798   | `academic_year=2022,academic_subject=Geometry,#3`                    | yes        |
| 2790   | `academic_year=2022,academic_subject=Pre-Calculus,#3`                | yes        |
| 2780   | `academic_year=2024,academic_subject=US History AfricanAmerican,#2`  | yes        |
| 2755   | `academic_year=2024,academic_subject=US History,#3`                  | yes        |
| 2744   | `academic_year=2023,academic_subject=English 100,#3`                 | yes        |
| 2707   | `academic_year=2023,academic_subject=Physics,#2`                     | yes        |
| 2700   | `academic_year=2024,academic_subject=Physics,#2`                     | yes        |
| 2695   | `academic_year=2023,academic_subject=US History AfricanAmerican,#3`  | yes        |
| 2665   | `academic_year=2018,academic_subject=Geometry,#3`                    | yes        |
| 2641   | `academic_year=2017,academic_subject=Algebra I`                      | yes        |
| 2608   | `academic_year=2022,academic_subject=Geometry`                       | yes        |
| 2593   | `academic_year=2023,academic_subject=English 200,#3`                 | yes        |
| 2559   | `academic_year=2019,academic_subject=Writing,#2`                     | yes        |
| 2558   | `academic_year=2018,academic_subject=Algebra I`                      | yes        |
| 2534   | `academic_year=2021,academic_subject=Writing,#2`                     | yes        |
| 2529   | `academic_year=2022,academic_subject=Algebra II,#3`                  | yes        |
| 2524   | `academic_year=2017,academic_subject=Algebra I,#3`                   | yes        |
| 2445   | `academic_year=2023,academic_subject=Algebra II,#2`                  | yes        |
| 2424   | `academic_year=2024,academic_subject=AP African American Studies,#4` | yes        |
| 2424   | `academic_year=2021,academic_subject=Geometry,#2`                    | yes        |
| 2412   | `academic_year=2018,academic_subject=English 200`                    | yes        |
| 2364   | `academic_year=2017,academic_subject=English 100`                    | yes        |
| 2349   | `academic_year=2022,academic_subject=Algebra II`                     | yes        |
| 2338   | `academic_year=2017,academic_subject=English 200`                    | yes        |
| 2313   | `academic_year=2023,academic_subject=US History,#3`                  | yes        |
| 2306   | `academic_year=2016,academic_subject=Writing,#2`                     | yes        |
| 2298   | `academic_year=2024,academic_subject=Biology,#2`                     | yes        |
| 2268   | `academic_year=2021,academic_subject=English 200`                    | yes        |
| 2264   | `academic_year=2023,academic_subject=US History`                     | yes        |
| 2239   | `academic_year=2022,academic_subject=Algebra I`                      | yes        |
| 2221   | `academic_year=2025,academic_subject=Science,#3`                     | yes        |
| 2153   | `academic_year=2023,academic_subject=English 400`                    | yes        |
| 2057   | `academic_year=2023,academic_subject=Algebra I`                      | yes        |
| 2057   | `academic_year=2018,academic_subject=Writing`                        | yes        |
| 2038   | `academic_year=2022,academic_subject=English 200,#3`                 | yes        |
| 2020   | `academic_year=2023,academic_subject=Physics`                        | yes        |
| 1991   | `academic_year=2021,academic_subject=English 100`                    | yes        |
| 1966   | `academic_year=2024,academic_subject=World History`                  | yes        |
| 1937   | `academic_year=2024,academic_subject=Chemistry`                      | yes        |
| 1926   | `academic_year=2024,academic_subject=Algebra I,#2`                   | yes        |
| 1863   | `academic_year=2024,academic_subject=AP US History,#3`               | yes        |
| 1767   | `academic_year=2018,academic_subject=Algebra I,#3`                   | yes        |
| 1760   | `academic_year=2023,academic_subject=US History AfricanAmerican`     | yes        |
| 1739   | `academic_year=2022,academic_subject=Algebra I,#2`                   | yes        |
| 1734   | `academic_year=2024,academic_subject=AP World History,#3`            | yes        |
| 1719   | `academic_year=2024,academic_subject=English 200,#2`                 | yes        |
| 1677   | `academic_year=2021,academic_subject=Algebra II,#3`                  | yes        |
| 1651   | `academic_year=2021,academic_subject=Pre-Calculus,#3`                | yes        |
| 1651   | `academic_year=2017,academic_subject=Geometry`                       | yes        |
| 1627   | `academic_year=2018,academic_subject=English 300`                    | yes        |
| 1625   | `academic_year=2023,academic_subject=US History,#2`                  | yes        |
| 1593   | `academic_year=2023,academic_subject=Biology,#2`                     | yes        |
| 1582   | `academic_year=2024,academic_subject=Geometry`                       | yes        |
| 1574   | `academic_year=2019,academic_subject=Writing`                        | yes        |
| 1566   | `academic_year=2023,academic_subject=Biology`                        | yes        |
| 1562   | `academic_year=2018,academic_subject=English 100,#3`                 | yes        |
| 1556   | `academic_year=2023,academic_subject=Geometry`                       | yes        |
| 1527   | `academic_year=2023,academic_subject=World History,#2`               | yes        |
| 1525   | `academic_year=2023,academic_subject=English 300,#3`                 | yes        |
| 1523   | `academic_year=2022,academic_subject=Algebra II,#2`                  | yes        |
| 1516   | `academic_year=2024,academic_subject=US History,#2`                  | yes        |
| 1503   | `academic_year=2021,academic_subject=AP Language`                    | yes        |
| 1491   | `academic_year=2022,academic_subject=English 100,#3`                 | yes        |
| 1481   | `academic_year=2017,academic_subject=English 300`                    | yes        |
| 1446   | `academic_year=2018,academic_subject=English 200,#3`                 | yes        |
| 1432   | `academic_year=2024,academic_subject=Algebra II,#2`                  | yes        |
| 1418   | `academic_year=2024,academic_subject=World History,#2`               | yes        |
| 1417   | `academic_year=2024,academic_subject=Biology`                        | yes        |
| 1368   | `academic_year=2018,academic_subject=Algebra II`                     | yes        |
| 1361   | `academic_year=2019,academic_subject=AP Language,#3`                 | yes        |
| 1340   | `academic_year=2015,academic_subject=Writing`                        | yes        |
| 1336   | `academic_year=2017,academic_subject=Algebra I,#2`                   | yes        |
| 1309   | `academic_year=2024,academic_subject=English 400,#2`                 | yes        |
| 1287   | `academic_year=2018,academic_subject=Science,#4`                     | yes        |
| 1287   | `academic_year=2018,academic_subject=Science`                        | yes        |
| 1258   | `academic_year=2023,academic_subject=Chemistry`                      | yes        |
| 1198   | `academic_year=2018,academic_subject=Algebra II,#3`                  | yes        |
| 1187   | `academic_year=2024,academic_subject=English 100,#2`                 | yes        |
| 1176   | `academic_year=2020,academic_subject=AP Language,#4`                 | yes        |
| 1172   | `academic_year=2023,academic_subject=English 100,#2`                 | yes        |
| 1125   | `academic_year=2017,academic_subject=Geometry,#3`                    | yes        |
| 1108   | `academic_year=2022,academic_subject=Geometry,#2`                    | yes        |
| 1084   | `academic_year=2023,academic_subject=Spanish`                        | yes        |
| 1060   | `academic_year=2022,academic_subject=Pre-Calculus`                   | yes        |
| 1031   | `academic_year=2022,academic_subject=English 300,#3`                 | yes        |
| 1025   | `academic_year=2017,academic_subject=Social Studies,#3`              | yes        |
| 1017   | `academic_year=2021,academic_subject=English 100,#2`                 | yes        |
| 964    | `academic_year=2024,academic_subject=English 100`                    | yes        |
| 943    | `academic_year=2024,academic_subject=AP World History`               | yes        |
| 914    | `academic_year=2026,academic_subject=English Language Arts`          | yes        |
| 877    | `academic_year=2018,academic_subject=English 300,#3`                 | yes        |
| 877    | `academic_year=2018,academic_subject=Algebra I,#2`                   | yes        |
| 869    | `academic_year=2022,academic_subject=English 400,#3`                 | yes        |
| 862    | `academic_year=2021,academic_subject=Pre-Calculus`                   | yes        |
| 860    | `academic_year=2023,academic_subject=AP World History,#3`            | yes        |
| 858    | `academic_year=2024,academic_subject=English 400`                    | yes        |
| 836    | `academic_year=2026,academic_subject=Mathematics,#2`                 | yes        |
| 824    | `academic_year=2022,academic_subject=Pre-Calculus,#2`                | yes        |
| 816    | `academic_year=2024,academic_subject=English 200`                    | yes        |
| 813    | `academic_year=2024,academic_subject=English 300`                    | yes        |
| 810    | `academic_year=2018,academic_subject=Geometry,#2`                    | yes        |
| 809    | `academic_year=2023,academic_subject=English 400,#3`                 | yes        |
| 784    | `academic_year=2024,academic_subject=Algebra I MS,#2`                | yes        |
| 775    | `academic_year=2023,academic_subject=Algebra II`                     | yes        |
| 767    | `academic_year=2017,academic_subject=English 100,#2`                 | yes        |
| 760    | `academic_year=2024,academic_subject=AP African American Studies,#3` | yes        |
| 756    | `academic_year=2021,academic_subject=English 200,#3`                 | yes        |
| 751    | `academic_year=2021,academic_subject=Biology`                        | yes        |
| 740    | `academic_year=2019,academic_subject=Composition 200`                | yes        |
| 737    | `academic_year=2021,academic_subject=English 200,#2`                 | yes        |
| 716    | `academic_year=2024,academic_subject=US History`                     | yes        |
| 716    | `academic_year=2023,academic_subject=Spanish,#2`                     | yes        |
| 699    | `academic_year=2019,academic_subject=AP Literature`                  | yes        |
| 697    | `academic_year=2023,academic_subject=US History AfricanAmerican,#2`  | yes        |
| 692    | `academic_year=2021,academic_subject=AP Language,#2`                 | yes        |
| 681    | `academic_year=2022,academic_subject=English 100,#2`                 | yes        |
| 651    | `academic_year=2021,academic_subject=Algebra II,#2`                  | yes        |
| 627    | `academic_year=2017,academic_subject=Writing`                        | yes        |
| 624    | `academic_year=2017,academic_subject=English 200,#2`                 | yes        |
| 610    | `academic_year=2017,academic_subject=English 300,#2`                 | yes        |
| 598    | `academic_year=2020,academic_subject=Geometry`                       | yes        |
| 573    | `academic_year=2023,academic_subject=World History`                  | yes        |
| 570    | `academic_year=2025,academic_subject=Algebra I,#2`                   | yes        |
| 570    | `academic_year=2024,academic_subject=AP US History`                  | yes        |
| 566    | `academic_year=2022,academic_subject=Physics`                        | yes        |
| 547    | `academic_year=2021,academic_subject=Pre-Calculus,#2`                | yes        |
| 544    | `academic_year=2020,academic_subject=AP US History`                  | yes        |
| 530    | `academic_year=2021,academic_subject=Algebra II`                     | yes        |
| 525    | `academic_year=2023,academic_subject=AP US History,#3`               | yes        |
| 505    | `academic_year=2024,academic_subject=Algebra II`                     | yes        |
| 504    | `academic_year=2020,academic_subject=AP Language`                    | yes        |
| 502    | `academic_year=2018,academic_subject=Algebra II,#2`                  | yes        |
| 500    | `academic_year=2021,academic_subject=English 100,#3`                 | yes        |
| 499    | `academic_year=2021,academic_subject=Chemistry`                      | yes        |
| 494    | `academic_year=2022,academic_subject=English 400,#2`                 | yes        |
| 481    | `academic_year=2021,academic_subject=English 300,#4`                 | yes        |
| 468    | `academic_year=2021,academic_subject=AP Language,#4`                 | yes        |
| 467    | `academic_year=2020,academic_subject=AP World History,#2`            | yes        |
| 461    | `academic_year=2018,academic_subject=Pre-Calculus,#3`                | yes        |
| 459    | `academic_year=2023,academic_subject=English 300,#2`                 | yes        |
| 459    | `academic_year=2023,academic_subject=AP African American Studies,#3` | yes        |
| 459    | `academic_year=2019,academic_subject=AP Language,#2`                 | yes        |
| 458    | `academic_year=2023,academic_subject=Early Literacy`                 | yes        |
| 429    | `academic_year=2018,academic_subject=Science,#3`                     | yes        |
| 421    | `academic_year=2022,academic_subject=English 200,#2`                 | yes        |
| 416    | `academic_year=2019,academic_subject=Composition 200,#2`             | yes        |
| 408    | `academic_year=2019,academic_subject=AP World History`               | yes        |
| 398    | `academic_year=2021,academic_subject=AP Language,#3`                 | yes        |
| 383    | `academic_year=2024,academic_subject=Early Literacy`                 | yes        |
| 370    | `academic_year=2019,academic_subject=Composition 200,#3`             | yes        |
| 366    | `academic_year=2025,academic_subject=Early Literacy`                 | yes        |
| 336    | `academic_year=2020,academic_subject=AP Language,#3`                 | yes        |
| 293    | `academic_year=2018,academic_subject=English 100,#2`                 | yes        |
| 283    | `academic_year=2022,academic_subject=Physics,#4`                     | yes        |
| 283    | `academic_year=2022,academic_subject=Physics,#3`                     | yes        |
| 281    | `academic_year=2022,academic_subject=English 300,#2`                 | yes        |
| 272    | `academic_year=2018,academic_subject=English 200,#2`                 | yes        |
| 259    | `academic_year=2019,academic_subject=Algebra I`                      | yes        |
| 258    | `academic_year=2021,academic_subject=English 300`                    | yes        |
| 257    | `academic_year=2023,academic_subject=English 200,#2`                 | yes        |
| 255    | `academic_year=2020,academic_subject=AP World History,#3`            | yes        |
| 247    | `academic_year=2023,academic_subject=AP World History,#2`            | yes        |
| 245    | `academic_year=2019,academic_subject=Chemistry`                      | yes        |
| 229    | `academic_year=2017,academic_subject=Geometry,#2`                    | yes        |
| 228    | `academic_year=2024,academic_subject=AP US History,#2`               | yes        |
| 212    | `academic_year=2024,academic_subject=AP African American Studies,#2` | yes        |
| 209    | `academic_year=2023,academic_subject=English 400,#2`                 | yes        |
| 190    | `academic_year=2023,academic_subject=AP US History,#2`               | yes        |
| 190    | `academic_year=2019,academic_subject=AP Literature,#3`               | yes        |
| 186    | `academic_year=2024,academic_subject=AP African American Studies`    | yes        |
| 181    | `academic_year=2019,academic_subject=Chemistry,#2`                   | yes        |
| 180    | `academic_year=2024,academic_subject=AP World History,#2`            | yes        |
| 180    | `academic_year=2020,academic_subject=AP World History`               | yes        |
| 178    | `academic_year=2017,academic_subject=English 100,#3`                 | yes        |
| 168    | `academic_year=2022,academic_subject=Physics,#2`                     | yes        |
| 167    | `academic_year=2019,academic_subject=AP World History,#2`            | yes        |
| 167    | `academic_year=2018,academic_subject=Pre-Calculus,#2`                | yes        |
| 161    | `academic_year=2023,academic_subject=Pre-Calculus,#2`                | yes        |
| 157    | `academic_year=2023,academic_subject=AP African American Studies,#2` | yes        |
| 152    | `academic_year=2021,academic_subject=AP World History,#2`            | yes        |
| 149    | `academic_year=2024,academic_subject=Civics`                         | yes        |
| 145    | `academic_year=2025,academic_subject=Civics`                         | yes        |
| 136    | `academic_year=2024,academic_subject=Algebra I MS`                   | yes        |
| 136    | `academic_year=2020,academic_subject=AP US History,#3`               | yes        |
| 134    | `academic_year=2019,academic_subject=AP Literature,#2`               | yes        |
| 126    | `academic_year=2021,academic_subject=AP Literature`                  | yes        |
| 125    | `academic_year=2021,academic_subject=Biology,#2`                     | yes        |
| 122    | `academic_year=2018,academic_subject=English 300,#2`                 | yes        |
| 118    | `academic_year=2018,academic_subject=Pre-Calculus`                   | yes        |
| 116    | `academic_year=2026,academic_subject=Early Literacy`                 | yes        |
| 104    | `academic_year=2023,academic_subject=Civics`                         | yes        |
| 102    | `academic_year=2023,academic_subject=AP African American Studies`    | yes        |
| 102    | `academic_year=2021,academic_subject=AP World History`               | yes        |
| 101    | `academic_year=2020,academic_subject=Social Studies,#4`              | yes        |
| 96     | `academic_year=2021,academic_subject=AP US Government & Politics`    | yes        |
| 88     | `academic_year=2021,academic_subject=English 300,#3`                 | yes        |
| 82     | `academic_year=2020,academic_subject=Geometry,#3`                    | yes        |
| 71     | `academic_year=2023,academic_subject=AP World History`               | yes        |
| 64     | `academic_year=2023,academic_subject=Pre-Calculus`                   | yes        |
| 53     | `academic_year=2020,academic_subject=AP US History,#2`               | yes        |
| 50     | `academic_year=2023,academic_subject=AP US History`                  | yes        |
| 47     | `academic_year=2021,academic_subject=English 300,#2`                 | yes        |
| 40     | `academic_year=2020,academic_subject=AP Language,#2`                 | yes        |
| 40     | `academic_year=2018,academic_subject=Science,#2`                     | yes        |
| 16     | `academic_year=2025,academic_subject=Geometry`                       | yes        |
| 15     | `academic_year=2020,academic_subject=Geometry,#2`                    | yes        |

## `avg_percent_correct__standards_over_time`, dashboard_only

| Rows   | Cell                                                                 | Trace lead |
| ------ | -------------------------------------------------------------------- | ---------- |
| 195187 | `academic_year=2025,academic_subject=,#4`                            | yes        |
| 155675 | `academic_year=2025,academic_subject=Science,#2`                     | yes        |
| 105918 | `academic_year=2025,academic_subject=Science,#5`                     | yes        |
| 76982  | `academic_year=2025,academic_subject=,#3`                            | yes        |
| 62552  | `academic_year=2025,academic_subject=Mathematics,#5`                 | yes        |
| 36809  | `academic_year=2025,academic_subject=Science,#4`                     | yes        |
| 22767  | `academic_year=2026,academic_subject=Science,#3`                     | yes        |
| 21098  | `academic_year=2026,academic_subject=Mathematics,#4`                 | yes        |
| 14900  | `academic_year=2025,academic_subject=Mathematics,#4`                 | yes        |
| 12662  | `academic_year=2026,academic_subject=Science`                        | yes        |
| 11750  | `academic_year=2025,academic_subject=,#2`                            | yes        |
| 9981   | `academic_year=2026,academic_subject=,#2`                            | yes        |
| 9231   | `academic_year=2026,academic_subject=`                               | yes        |
| 9117   | `academic_year=2026,academic_subject=Science,#2`                     | yes        |
| 8142   | `academic_year=2026,academic_subject=Mathematics`                    | yes        |
| 7812   | `academic_year=2026,academic_subject=,#3`                            | yes        |
| 5694   | `academic_year=2026,academic_subject=Mathematics,#3`                 | yes        |
| 5424   | `academic_year=2025,academic_subject=Physical Education`             | yes        |
| 4978   | `academic_year=2025,academic_subject=Social Excellence,#2`           | yes        |
| 4302   | `academic_year=2025,academic_subject=History,#2`                     | yes        |
| 4111   | `academic_year=2025,academic_subject=Dance`                          | yes        |
| 2444   | `academic_year=2025,academic_subject=Visual Arts`                    | yes        |
| 2392   | `academic_year=2025,academic_subject=World History,#2`               | yes        |
| 1998   | `academic_year=2025,academic_subject=Music`                          | yes        |
| 1722   | `academic_year=2026,academic_subject=Social Excellence`              | yes        |
| 1548   | `academic_year=2025,academic_subject=US History,#2`                  | yes        |
| 1444   | `academic_year=2025,academic_subject=Text Study,#4`                  | yes        |
| 1355   | `academic_year=2025,academic_subject=Performing Arts`                | yes        |
| 1353   | `academic_year=2025,academic_subject=Physical Education,#2`          | yes        |
| 1350   | `academic_year=2025,academic_subject=Computer Science`               | yes        |
| 1348   | `academic_year=2026,academic_subject=Visual Arts`                    | yes        |
| 1339   | `academic_year=2026,academic_subject=Physical Education`             | yes        |
| 1305   | `academic_year=2026,academic_subject=Dance`                          | yes        |
| 1004   | `academic_year=2026,academic_subject=Text Study,#3`                  | yes        |
| 896    | `academic_year=2026,academic_subject=Physical Education,#2`          | yes        |
| 892    | `academic_year=2025,academic_subject=Social Studies,#2`              | yes        |
| 813    | `academic_year=2026,academic_subject=US History,#2`                  | yes        |
| 753    | `academic_year=2025,academic_subject=Text Study,#3`                  | yes        |
| 686    | `academic_year=2025,academic_subject=Mathematics,#2`                 | yes        |
| 540    | `academic_year=2026,academic_subject=Performing Arts`                | yes        |
| 537    | `academic_year=2026,academic_subject=Music`                          | yes        |
| 478    | `academic_year=2025,academic_subject=World History`                  | yes        |
| 459    | `academic_year=2025,academic_subject=Social Excellence`              | yes        |
| 433    | `academic_year=2026,academic_subject=Computer Science`               | yes        |
| 359    | `academic_year=2026,academic_subject=Algebra I MS,#2`                | yes        |
| 339    | `academic_year=2026,academic_subject=Algebra I,#2`                   | yes        |
| 289    | `academic_year=2026,academic_subject=Economics and Civics,#2`        | yes        |
| 286    | `academic_year=2025,academic_subject=History`                        | yes        |
| 271    | `academic_year=2026,academic_subject=US History`                     | yes        |
| 263    | `academic_year=2025,academic_subject=Physics`                        | yes        |
| 258    | `academic_year=2025,academic_subject=US History`                     | yes        |
| 205    | `academic_year=2026,academic_subject=Text Study,#2`                  | yes        |
| 205    | `academic_year=2025,academic_subject=US History AfricanAmerican`     | yes        |
| 204    | `academic_year=2025,academic_subject=Pre-Calculus`                   | yes        |
| 154    | `academic_year=2025,academic_subject=AP African American Studies,#3` | yes        |
| 145    | `academic_year=2026,academic_subject=Economics and Civics`           | yes        |
| 118    | `#34`                                                                | yes        |
| 115    | `academic_year=2025,academic_subject=AP African American Studies,#2` | yes        |
| 108    | `#46`                                                                | yes        |
| 97     | `academic_year=2026,academic_subject=Text Study`                     | yes        |
| 97     | `academic_year=2025,academic_subject=Text Study,#2`                  | yes        |
| 90     | `academic_year=2026,academic_subject=Algebra I MS`                   | yes        |
| 84     | `academic_year=2025,academic_subject=Text Study`                     | yes        |
| 76     | `#51`                                                                | yes        |
| 72     | `academic_year=2025,academic_subject=Mathematics`                    | yes        |
| 50     | `academic_year=2026,academic_subject=US History AfricanAmerican`     | yes        |
| 50     | `#55`                                                                | yes        |
| 44     | `academic_year=2025,academic_subject=AP African American Studies`    | yes        |
| 42     | `academic_year=2025,academic_subject=Anatomy and Physiology`         | yes        |
| 30     | `academic_year=2026,academic_subject=Social Studies`                 | yes        |
| 25     | `academic_year=2026,academic_subject=World History`                  | yes        |
| 22     | `academic_year=2025,academic_subject=English`                        | yes        |
| 19     | `academic_year=2026,academic_subject=Algebra I`                      | yes        |
| 19     | `academic_year=2026,academic_subject=AP Calculus`                    | yes        |
| 18     | `academic_year=2025,academic_subject=Social Studies`                 | yes        |
| 18     | `#42`                                                                | yes        |
| 16     | `#54`                                                                | yes        |
| 15     | `#33`                                                                | yes        |
| 14     | `#32`                                                                | yes        |
| 13     | `academic_year=2025,academic_subject=Science`                        | yes        |
| 11     | `academic_year=2025,academic_subject=Algebra I`                      | yes        |
| 11     | `academic_year=2025,academic_subject=`                               | yes        |

## `avg_percent_correct__standards_over_time`, dims_differ

| Rows  | Cell                                                                      | Trace lead |
| ----- | ------------------------------------------------------------------------- | ---------- |
| 34373 | `academic_year=2026,academic_subject=Text Study,d:d:d:`                   | yes        |
| 27857 | `academic_year=2026,academic_subject=Mathematics,d:d:d:#2`                | yes        |
| 22981 | `academic_year=2025,academic_subject=Text Study,d:d:d:`                   | yes        |
| 22335 | `academic_year=2026,academic_subject=Science,d:d:d:`                      | yes        |
| 18471 | `academic_year=2025,academic_subject=Mathematics,d:d:d:`                  | yes        |
| 15302 | `academic_year=2025,academic_subject=Science,d:d:d:`                      | yes        |
| 9044  | `academic_year=2026,academic_subject=Biology,d:d:d:`                      | yes        |
| 7755  | `academic_year=2026,academic_subject=Social Studies,d:d:d:`               | yes        |
| 4776  | `academic_year=2025,academic_subject=Social Studies,d:d:d:`               | yes        |
| 2978  | `academic_year=2025,academic_subject=Geometry,d:d:d:`                     | yes        |
| 2946  | `academic_year=2025,academic_subject=Physics,d:d:d:`                      | yes        |
| 2771  | `academic_year=2025,academic_subject=US History AfricanAmerican,d:d:d:`   | yes        |
| 2607  | `academic_year=2025,academic_subject=Algebra I,d:d:d:`                    | yes        |
| 2508  | `academic_year=2025,academic_subject=Biology,d:d:d:`                      | yes        |
| 2300  | `academic_year=2026,academic_subject=English 100,d:d:d:`                  | yes        |
| 2103  | `academic_year=2026,academic_subject=Algebra I,d:d:d:`                    | yes        |
| 2046  | `academic_year=2026,academic_subject=Chemistry,d:d:d:`                    | yes        |
| 2041  | `academic_year=2026,academic_subject=English 200,d:d:d:`                  | yes        |
| 2029  | `academic_year=2025,academic_subject=English 100,d:d:d:`                  | yes        |
| 1674  | `academic_year=2025,academic_subject=Chemistry,d:d:d:`                    | yes        |
| 1579  | `academic_year=2026,academic_subject=CCR 4,d:d:d:`                        | yes        |
| 1565  | `academic_year=2026,academic_subject=Geometry,d:d:d:`                     | yes        |
| 1544  | `academic_year=2026,academic_subject=US History AfricanAmerican,d:d:d:`   | yes        |
| 1412  | `academic_year=2026,academic_subject=Algebra II,d:d:d:`                   | yes        |
| 1364  | `academic_year=2026,academic_subject=World History,d:d:d:`                | yes        |
| 1300  | `academic_year=2026,academic_subject=AP African American Studies,d:d:d:`  | yes        |
| 1287  | `academic_year=2026,academic_subject=CCR 3,d:d:d:`                        | yes        |
| 1164  | `academic_year=2026,academic_subject=Human Anatomy and Physiology,d:d:d:` | yes        |
| 1126  | `academic_year=2026,academic_subject=Mathematics,d:d:d:#4`                | yes        |
| 1120  | `academic_year=2025,academic_subject=World History,d:d:d:`                | yes        |
| 1095  | `academic_year=2026,academic_subject=English 300,d:d:d:`                  | yes        |
| 1064  | `academic_year=2026,academic_subject=English 400,d:d:d:`                  | yes        |
| 1003  | `academic_year=2025,academic_subject=Algebra II,d:d:d:`                   | yes        |
| 915   | `academic_year=2026,academic_subject=US History,d:d:d:`                   | yes        |
| 870   | `academic_year=2025,academic_subject=CCR 4,d:d:d:`                        | yes        |
| 804   | `academic_year=2025,academic_subject=US History,d:d:d:`                   | yes        |
| 783   | `academic_year=2025,academic_subject=CCR 3,d:d:d:`                        | yes        |
| 710   | `academic_year=2024,academic_subject=Mathematics,d:d:d:`                  | yes        |
| 685   | `academic_year=2025,academic_subject=English 300,d:d:d:`                  | yes        |
| 661   | `academic_year=2025,academic_subject=English 400,d:d:d:`                  | yes        |
| 638   | `academic_year=2025,academic_subject=CCR 1,d:d:d:`                        | yes        |
| 563   | `academic_year=2026,academic_subject=Mathematics,d:d:d:#3`                | yes        |
| 512   | `academic_year=2025,academic_subject=English 200,d:d:d:`                  | yes        |
| 499   | `academic_year=2024,academic_subject=Mathematics,d:d:d:#3`                | yes        |
| 492   | `academic_year=2026,academic_subject=Economics and Civics,d:d:d:`         | yes        |
| 466   | `academic_year=2026,academic_subject=Geometry Honors,d:d:d:`              | yes        |
| 268   | `academic_year=2026,academic_subject=AP US History,d:d:d:`                | yes        |
| 262   | `academic_year=2026,academic_subject=Algebra I MS,d:d:d:`                 | yes        |
| 248   | `academic_year=2026,academic_subject=AP World History,d:d:d:`             | yes        |
| 240   | `academic_year=2025,academic_subject=AP African American Studies,d:d:d:`  | yes        |
| 210   | `academic_year=2025,academic_subject=Economics and Civics,d:d:d:`         | yes        |
| 165   | `academic_year=2025,academic_subject=Algebra I MS,d:d:d:`                 | yes        |
| 164   | `academic_year=2026,academic_subject=AP Language,d:d:d:`                  | yes        |
| 144   | `academic_year=2025,academic_subject=Math 4,d:d:d:`                       | yes        |
| 127   | `academic_year=2025,academic_subject=AP World History,d:d:d:`             | yes        |
| 126   | `academic_year=2025,academic_subject=AP US History,d:d:d:`                | yes        |
| 101   | `academic_year=2024,academic_subject=Mathematics,d:d:d:#2`                | yes        |
| 74    | `academic_year=2026,academic_subject=AP Pre Calculus,d:d:d:`              | yes        |
| 46    | `academic_year=2026,academic_subject=Mathematics,d:d:d:`                  | yes        |
| 33    | `academic_year=2026,academic_subject=Algebra II Honors,d:d:d:`            | yes        |
| 24    | `academic_year=2025,academic_subject=African American Studies,d:d:d:`     | yes        |
| 17    | `academic_year=2025,academic_subject=AP Language,d:d:d:`                  | yes        |

## `count_assessments__standards_over_time`, cube_only

| Rows   | Cell                                                                 | Trace lead |
| ------ | -------------------------------------------------------------------- | ---------- |
| 669120 | `academic_year=2024,academic_subject=Mathematics,#4`                 | yes        |
| 635764 | `academic_year=2023,academic_subject=Mathematics,#4`                 | yes        |
| 509828 | `academic_year=2024,academic_subject=Text Study,#4`                  | yes        |
| 401667 | `academic_year=2023,academic_subject=Text Study,#4`                  | yes        |
| 371234 | `academic_year=2018,academic_subject=Mathematics,#4`                 | yes        |
| 358816 | `academic_year=2022,academic_subject=Mathematics,#4`                 | yes        |
| 283361 | `academic_year=2019,academic_subject=Mathematics,#4`                 | yes        |
| 270140 | `academic_year=2022,academic_subject=Text Study,#4`                  | yes        |
| 264425 | `academic_year=2019,academic_subject=Text Study`                     | yes        |
| 248390 | `academic_year=2021,academic_subject=Mathematics,#4`                 | yes        |
| 243966 | `academic_year=2025,academic_subject=Reading`                        | yes        |
| 234480 | `academic_year=2018,academic_subject=Text Study`                     | yes        |
| 227739 | `academic_year=2021,academic_subject=Text Study,#4`                  | yes        |
| 221230 | `academic_year=2024,academic_subject=Reading`                        | yes        |
| 188891 | `academic_year=2023,academic_subject=Reading`                        | yes        |
| 179291 | `academic_year=2019,academic_subject=Text Study,#4`                  | yes        |
| 177648 | `academic_year=2023,academic_subject=Science`                        | yes        |
| 174705 | `academic_year=2024,academic_subject=Science`                        | yes        |
| 173741 | `academic_year=2018,academic_subject=Text Study,#4`                  | yes        |
| 162830 | `academic_year=2020,academic_subject=Mathematics,#4`                 | yes        |
| 159147 | `academic_year=2017,academic_subject=Mathematics,#4`                 | yes        |
| 156490 | `academic_year=2024,academic_subject=Science,#4`                     | yes        |
| 155619 | `academic_year=2022,academic_subject=Text Study`                     | yes        |
| 129361 | `academic_year=2024,academic_subject=Mathematics,#3`                 | yes        |
| 125478 | `academic_year=2021,academic_subject=Text Study`                     | yes        |
| 121015 | `academic_year=2015,academic_subject=Writing,#3`                     | yes        |
| 119112 | `academic_year=2020,academic_subject=Text Study,#4`                  | yes        |
| 117135 | `academic_year=2023,academic_subject=Mathematics,#3`                 | yes        |
| 116939 | `academic_year=2023,academic_subject=Text Study`                     | yes        |
| 116227 | `academic_year=2022,academic_subject=Science`                        | yes        |
| 106941 | `academic_year=2017,academic_subject=Text Study,#4`                  | yes        |
| 106164 | `academic_year=2025,academic_subject=Math`                           | yes        |
| 104314 | `academic_year=2024,academic_subject=Text Study,#3`                  | yes        |
| 104171 | `academic_year=2023,academic_subject=Mathematics`                    | yes        |
| 96436  | `academic_year=2024,academic_subject=Math`                           | yes        |
| 95506  | `academic_year=2020,academic_subject=Text Study`                     | yes        |
| 94652  | `academic_year=2023,academic_subject=Math`                           | yes        |
| 92973  | `academic_year=2022,academic_subject=Mathematics,#2`                 | yes        |
| 92908  | `academic_year=2023,academic_subject=Science,#4`                     | yes        |
| 91748  | `academic_year=2022,academic_subject=Math`                           | yes        |
| 88842  | `academic_year=2022,academic_subject=Mathematics,#3`                 | yes        |
| 88434  | `academic_year=2022,academic_subject=Reading`                        | yes        |
| 87992  | `academic_year=2016,academic_subject=Text Study`                     | yes        |
| 87031  | `academic_year=2026,academic_subject=Reading`                        | yes        |
| 84728  | `academic_year=2021,academic_subject=Math`                           | yes        |
| 80540  | `academic_year=2023,academic_subject=Social Studies,#4`              | yes        |
| 76100  | `academic_year=2024,academic_subject=Social Studies,#3`              | yes        |
| 75105  | `academic_year=2022,academic_subject=Mathematics`                    | yes        |
| 72685  | `academic_year=2021,academic_subject=Mathematics`                    | yes        |
| 71745  | `academic_year=2021,academic_subject=Science`                        | yes        |
| 71443  | `academic_year=2015,academic_subject=Text Study,#4`                  | yes        |
| 71047  | `academic_year=2019,academic_subject=Writing,#4`                     | yes        |
| 70772  | `academic_year=2020,academic_subject=Math`                           | yes        |
| 69392  | `academic_year=2021,academic_subject=Social Studies`                 | yes        |
| 69184  | `academic_year=2023,academic_subject=Mathematics,#2`                 | yes        |
| 68798  | `academic_year=2022,academic_subject=Text Study,#2`                  | yes        |
| 67662  | `academic_year=2021,academic_subject=Reading`                        | yes        |
| 66269  | `academic_year=2023,academic_subject=Text Study,#3`                  | yes        |
| 64815  | `academic_year=2019,academic_subject=Mathematics,#2`                 | yes        |
| 63638  | `academic_year=2022,academic_subject=Writing,#4`                     | yes        |
| 63024  | `academic_year=2016,academic_subject=Mathematics,#4`                 | yes        |
| 61631  | `academic_year=2021,academic_subject=Mathematics,#3`                 | yes        |
| 57384  | `academic_year=2017,academic_subject=Text Study`                     | yes        |
| 56436  | `academic_year=2016,academic_subject=Text Study,#4`                  | yes        |
| 55482  | `academic_year=2019,academic_subject=Mathematics,#3`                 | yes        |
| 53054  | `academic_year=2018,academic_subject=Mathematics,#3`                 | yes        |
| 52460  | `academic_year=2022,academic_subject=Science,#4`                     | yes        |
| 52348  | `academic_year=2025,academic_subject=Reading,#2`                     | yes        |
| 52257  | `academic_year=2023,academic_subject=Text Study,#2`                  | yes        |
| 51525  | `academic_year=2024,academic_subject=Text Study`                     | yes        |
| 51076  | `academic_year=2023,academic_subject=Social Studies`                 | yes        |
| 50022  | `academic_year=2021,academic_subject=Mathematics,#2`                 | yes        |
| 47883  | `academic_year=2022,academic_subject=Text Study,#3`                  | yes        |
| 47476  | `academic_year=2024,academic_subject=Reading,#2`                     | yes        |
| 44434  | `academic_year=2016,academic_subject=Writing,#3`                     | yes        |
| 43780  | `academic_year=2018,academic_subject=Mathematics`                    | yes        |
| 43617  | `academic_year=2023,academic_subject=Writing,#4`                     | yes        |
| 43366  | `academic_year=2020,academic_subject=Mathematics`                    | yes        |
| 39747  | `academic_year=2020,academic_subject=Science`                        | yes        |
| 39661  | `academic_year=2021,academic_subject=Text Study,#3`                  | yes        |
| 38627  | `academic_year=2020,academic_subject=Mathematics,#3`                 | yes        |
| 37668  | `academic_year=2026,academic_subject=Math`                           | yes        |
| 37641  | `academic_year=2024,academic_subject=Science,#3`                     | yes        |
| 35153  | `academic_year=2018,academic_subject=Text Study,#3`                  | yes        |
| 34703  | `academic_year=2019,academic_subject=Text Study,#3`                  | yes        |
| 34569  | `academic_year=2017,academic_subject=Writing,#2`                     | yes        |
| 33936  | `academic_year=2020,academic_subject=Reading`                        | yes        |
| 32284  | `academic_year=2023,academic_subject=Reading,#2`                     | yes        |
| 31889  | `academic_year=2016,academic_subject=Mathematics,#2`                 | yes        |
| 31112  | `academic_year=2024,academic_subject=English 100,#4`                 | yes        |
| 30807  | `academic_year=2024,academic_subject=US History AfricanAmerican,#4`  | yes        |
| 30438  | `academic_year=2020,academic_subject=Mathematics,#2`                 | yes        |
| 30338  | `academic_year=2017,academic_subject=Algebra I,#4`                   | yes        |
| 29563  | `academic_year=2022,academic_subject=Social Studies,#4`              | yes        |
| 29071  | `academic_year=2024,academic_subject=Algebra I,#4`                   | yes        |
| 28850  | `academic_year=2015,academic_subject=Mathematics,#4`                 | yes        |
| 27680  | `academic_year=2025,academic_subject=Math,#2`                        | yes        |
| 27549  | `academic_year=2020,academic_subject=Text Study,#3`                  | yes        |
| 27173  | `academic_year=2020,academic_subject=Science,#4`                     | yes        |
| 27002  | `academic_year=2023,academic_subject=English 100,#4`                 | yes        |
| 25659  | `academic_year=2019,academic_subject=Mathematics`                    | yes        |
| 25355  | `academic_year=2024,academic_subject=Math,#2`                        | yes        |
| 25078  | `academic_year=2024,academic_subject=English 200,#4`                 | yes        |
| 25000  | `academic_year=2016,academic_subject=Social Studies,#4`              | yes        |
| 24997  | `academic_year=2020,academic_subject=Social Studies`                 | yes        |
| 24922  | `academic_year=2018,academic_subject=Writing,#3`                     | yes        |
| 24915  | `academic_year=2023,academic_subject=Math,#2`                        | yes        |
| 24628  | `academic_year=2022,academic_subject=Social Studies`                 | yes        |
| 24570  | `academic_year=2023,academic_subject=English 200,#4`                 | yes        |
| 23979  | `academic_year=2018,academic_subject=Mathematics,#2`                 | yes        |
| 23803  | `academic_year=2015,academic_subject=Mathematics`                    | yes        |
| 23426  | `academic_year=2015,academic_subject=Mathematics,#2`                 | yes        |
| 22999  | `academic_year=2022,academic_subject=English 200,#4`                 | yes        |
| 22937  | `academic_year=2022,academic_subject=Math,#2`                        | yes        |
| 22138  | `academic_year=2017,academic_subject=Mathematics,#2`                 | yes        |
| 21605  | `academic_year=2016,academic_subject=Social Studies,#2`              | yes        |
| 21269  | `academic_year=2021,academic_subject=Writing,#4`                     | yes        |
| 21182  | `academic_year=2021,academic_subject=Math,#2`                        | yes        |
| 21152  | `academic_year=2024,academic_subject=Mathematics,#2`                 | yes        |
| 21019  | `academic_year=2018,academic_subject=Geometry,#4`                    | yes        |
| 21008  | `academic_year=2016,academic_subject=Science,#4`                     | yes        |
| 20112  | `academic_year=2018,academic_subject=Algebra I,#4`                   | yes        |
| 19941  | `academic_year=2024,academic_subject=Science,#2`                     | yes        |
| 19607  | `academic_year=2017,academic_subject=Geometry,#4`                    | yes        |
| 19471  | `academic_year=2015,academic_subject=Text Study`                     | yes        |
| 19171  | `academic_year=2024,academic_subject=English 400,#4`                 | yes        |
| 18504  | `academic_year=2026,academic_subject=Reading,#2`                     | yes        |
| 18085  | `academic_year=2022,academic_subject=English 100,#4`                 | yes        |
| 17693  | `academic_year=2020,academic_subject=Math,#2`                        | yes        |
| 17355  | `academic_year=2024,academic_subject=Text Study,#2`                  | yes        |
| 16999  | `academic_year=2024,academic_subject=Chemistry,#3`                   | yes        |
| 16959  | `academic_year=2017,academic_subject=Science,#3`                     | yes        |
| 16784  | `academic_year=2015,academic_subject=Text Study,#2`                  | yes        |
| 16376  | `academic_year=2024,academic_subject=English 300,#3`                 | yes        |
| 16238  | `academic_year=2017,academic_subject=Mathematics`                    | yes        |
| 16225  | `academic_year=2022,academic_subject=Social Studies,#2`              | yes        |
| 16002  | `academic_year=2023,academic_subject=Geometry,#3`                    | yes        |
| 15761  | `academic_year=2024,academic_subject=Biology,#3`                     | yes        |
| 15654  | `academic_year=2021,academic_subject=Social Studies,#2`              | yes        |
| 15566  | `academic_year=2017,academic_subject=Social Studies,#2`              | yes        |
| 15564  | `academic_year=2022,academic_subject=Science,#3`                     | yes        |
| 15395  | `academic_year=2021,academic_subject=Social Studies,#4`              | yes        |
| 15306  | `academic_year=2016,academic_subject=Science,#2`                     | yes        |
| 14755  | `academic_year=2023,academic_subject=Science,#3`                     | yes        |
| 14739  | `academic_year=2022,academic_subject=Reading,#2`                     | yes        |
| 14250  | `academic_year=2023,academic_subject=English 300,#4`                 | yes        |
| 14054  | `academic_year=2021,academic_subject=Science,#4`                     | yes        |
| 13897  | `academic_year=2022,academic_subject=Geometry,#4`                    | yes        |
| 13831  | `academic_year=2021,academic_subject=Science,#3`                     | yes        |
| 13669  | `academic_year=2024,academic_subject=World History,#4`               | yes        |
| 13626  | `academic_year=2024,academic_subject=Algebra II,#4`                  | yes        |
| 13619  | `academic_year=2023,academic_subject=Social Studies,#3`              | yes        |
| 13437  | `academic_year=2023,academic_subject=Algebra I,#3`                   | yes        |
| 13437  | `academic_year=2016,academic_subject=Social Studies`                 | yes        |
| 13410  | `academic_year=2024,academic_subject=Social Studies,#2`              | yes        |
| 13244  | `academic_year=2017,academic_subject=Social Studies,#4`              | yes        |
| 12970  | `academic_year=2017,academic_subject=Social Studies`                 | yes        |
| 12758  | `academic_year=2024,academic_subject=Geometry,#3`                    | yes        |
| 12734  | `academic_year=2019,academic_subject=Writing,#3`                     | yes        |
| 12312  | `academic_year=2022,academic_subject=Algebra II,#4`                  | yes        |
| 12148  | `academic_year=2024,academic_subject=Physics,#3`                     | yes        |
| 11685  | `academic_year=2021,academic_subject=Geometry,#3`                    | yes        |
| 11599  | `academic_year=2023,academic_subject=US History AfricanAmerican,#4`  | yes        |
| 11277  | `academic_year=2021,academic_subject=Reading,#2`                     | yes        |
| 11177  | `academic_year=2024,academic_subject=US History,#4`                  | yes        |
| 11174  | `academic_year=2023,academic_subject=Algebra II,#3`                  | yes        |
| 11108  | `academic_year=2021,academic_subject=Text Study,#2`                  | yes        |
| 10579  | `academic_year=2021,academic_subject=Social Studies,#3`              | yes        |
| 10499  | `academic_year=2018,academic_subject=Algebra II,#4`                  | yes        |
| 10415  | `academic_year=2017,academic_subject=English 100,#4`                 | yes        |
| 10399  | `academic_year=2019,academic_subject=Text Study,#2`                  | yes        |
| 10318  | `academic_year=2016,academic_subject=Mathematics`                    | yes        |
| 10275  | `academic_year=2020,academic_subject=Text Study,#2`                  | yes        |
| 10256  | `academic_year=2022,academic_subject=Algebra I,#4`                   | yes        |
| 10142  | `academic_year=2018,academic_subject=English 100,#4`                 | yes        |
| 9972   | `academic_year=2021,academic_subject=Algebra I,#3`                   | yes        |
| 9934   | `academic_year=2022,academic_subject=Writing,#3`                     | yes        |
| 9934   | `academic_year=2022,academic_subject=Writing`                        | yes        |
| 9911   | `academic_year=2022,academic_subject=English 300,#4`                 | yes        |
| 9879   | `academic_year=2017,academic_subject=Mathematics,#3`                 | yes        |
| 9806   | `academic_year=2022,academic_subject=English 200`                    | yes        |
| 9791   | `academic_year=2026,academic_subject=Math,#2`                        | yes        |
| 9748   | `academic_year=2018,academic_subject=Social Studies`                 | yes        |
| 9512   | `academic_year=2018,academic_subject=English 200,#4`                 | yes        |
| 9419   | `academic_year=2020,academic_subject=Science,#3`                     | yes        |
| 9300   | `academic_year=2016,academic_subject=Text Study,#2`                  | yes        |
| 9251   | `academic_year=2022,academic_subject=Social Studies,#3`              | yes        |
| 9195   | `academic_year=2023,academic_subject=Chemistry,#3`                   | yes        |
| 9112   | `academic_year=2019,academic_subject=Social Studies`                 | yes        |
| 9090   | `academic_year=2019,academic_subject=Social Studies,#4`              | yes        |
| 9055   | `academic_year=2016,academic_subject=Text Study,#3`                  | yes        |
| 9009   | `academic_year=2016,academic_subject=Mathematics,#3`                 | yes        |
| 8898   | `academic_year=2017,academic_subject=Science`                        | yes        |
| 8780   | `academic_year=2022,academic_subject=Science,#2`                     | yes        |
| 8494   | `academic_year=2022,academic_subject=Writing,#2`                     | yes        |
| 8416   | `academic_year=2023,academic_subject=English 400,#4`                 | yes        |
| 8408   | `academic_year=2025,academic_subject=English Language Arts`          | yes        |
| 8334   | `academic_year=2022,academic_subject=English 400,#4`                 | yes        |
| 8209   | `academic_year=2017,academic_subject=English 200,#3`                 | yes        |
| 8179   | `academic_year=2024,academic_subject=English Language Arts`          | yes        |
| 7957   | `academic_year=2015,academic_subject=Writing,#2`                     | yes        |
| 7940   | `academic_year=2017,academic_subject=Science,#2`                     | yes        |
| 7890   | `academic_year=2023,academic_subject=Physics,#3`                     | yes        |
| 7889   | `academic_year=2023,academic_subject=US History,#4`                  | yes        |
| 7758   | `academic_year=2025,academic_subject=Mathematics,#3`                 | yes        |
| 7740   | `academic_year=2024,academic_subject=AP World History,#4`            | yes        |
| 7573   | `academic_year=2023,academic_subject=English Language Arts`          | yes        |
| 7455   | `academic_year=2022,academic_subject=English 100`                    | yes        |
| 7400   | `academic_year=2021,academic_subject=Science,#2`                     | yes        |
| 7363   | `academic_year=2021,academic_subject=Algebra II,#4`                  | yes        |
| 7349   | `academic_year=2023,academic_subject=English 200`                    | yes        |
| 7166   | `academic_year=2015,academic_subject=Text Study,#3`                  | yes        |
| 7149   | `academic_year=2023,academic_subject=Social Studies,#2`              | yes        |
| 7115   | `academic_year=2024,academic_subject=Mathematics`                    | yes        |
| 7072   | `academic_year=2024,academic_subject=AP US History,#4`               | yes        |
| 6836   | `academic_year=2023,academic_subject=Biology,#3`                     | yes        |
| 6670   | `academic_year=2023,academic_subject=Writing,#3`                     | yes        |
| 6670   | `academic_year=2023,academic_subject=Writing`                        | yes        |
| 6630   | `academic_year=2017,academic_subject=English 300,#3`                 | yes        |
| 6621   | `academic_year=2022,academic_subject=English Language Arts`          | yes        |
| 6607   | `academic_year=2024,academic_subject=US History AfricanAmerican,#3`  | yes        |
| 6594   | `academic_year=2020,academic_subject=Social Studies,#2`              | yes        |
| 6524   | `academic_year=2020,academic_subject=Social Studies,#3`              | yes        |
| 6421   | `academic_year=2018,academic_subject=Social Studies,#4`              | yes        |
| 6416   | `academic_year=2023,academic_subject=English 100`                    | yes        |
| 6182   | `academic_year=2018,academic_subject=Text Study,#2`                  | yes        |
| 5742   | `academic_year=2023,academic_subject=World History,#3`               | yes        |
| 5656   | `academic_year=2020,academic_subject=Reading,#2`                     | yes        |
| 5510   | `academic_year=2019,academic_subject=Social Studies,#2`              | yes        |
| 5497   | `academic_year=2018,academic_subject=English 300,#4`                 | yes        |
| 5477   | `academic_year=2024,academic_subject=Algebra I,#3`                   | yes        |
| 5434   | `academic_year=2020,academic_subject=Science,#2`                     | yes        |
| 5424   | `academic_year=2017,academic_subject=Text Study,#3`                  | yes        |
| 5167   | `academic_year=2016,academic_subject=Science,#3`                     | yes        |
| 5155   | `academic_year=2022,academic_subject=English 300`                    | yes        |
| 5019   | `academic_year=2024,academic_subject=English 100,#3`                 | yes        |
| 4874   | `academic_year=2018,academic_subject=Social Studies,#3`              | yes        |
| 4771   | `academic_year=2023,academic_subject=Writing,#2`                     | yes        |
| 4755   | `academic_year=2023,academic_subject=AP World History,#4`            | yes        |
| 4593   | `academic_year=2017,academic_subject=Text Study,#2`                  | yes        |
| 4556   | `academic_year=2019,academic_subject=Social Studies,#3`              | yes        |
| 4536   | `academic_year=2021,academic_subject=English 200,#4`                 | yes        |
| 4410   | `academic_year=2021,academic_subject=English Language Arts`          | yes        |
| 4406   | `academic_year=2023,academic_subject=Science,#2`                     | yes        |
| 4355   | `academic_year=2024,academic_subject=English 200,#3`                 | yes        |
| 4300   | `academic_year=2016,academic_subject=Social Studies,#3`              | yes        |
| 4283   | `academic_year=2024,academic_subject=Algebra I MS,#3`                | yes        |
| 4230   | `academic_year=2018,academic_subject=Pre-Calculus,#4`                | yes        |
| 4083   | `academic_year=2019,academic_subject=AP Language`                    | yes        |
| 4037   | `academic_year=2023,academic_subject=AP US History,#4`               | yes        |
| 4024   | `academic_year=2023,academic_subject=English 300`                    | yes        |
| 3944   | `academic_year=2015,academic_subject=Mathematics,#3`                 | yes        |
| 3873   | `academic_year=2024,academic_subject=Algebra I`                      | yes        |
| 3768   | `academic_year=2021,academic_subject=Algebra I`                      | yes        |
| 3730   | `academic_year=2024,academic_subject=World History,#3`               | yes        |
| 3677   | `academic_year=2023,academic_subject=Algebra I,#2`                   | yes        |
| 3643   | `academic_year=2022,academic_subject=English 400`                    | yes        |
| 3609   | `academic_year=2018,academic_subject=Social Studies,#2`              | yes        |
| 3581   | `academic_year=2021,academic_subject=Writing,#3`                     | yes        |
| 3581   | `academic_year=2021,academic_subject=Writing`                        | yes        |
| 3540   | `academic_year=2023,academic_subject=Geometry,#2`                    | yes        |
| 3470   | `academic_year=2018,academic_subject=Geometry`                       | yes        |
| 3442   | `academic_year=2024,academic_subject=Physics`                        | yes        |
| 3426   | `academic_year=2024,academic_subject=Chemistry,#2`                   | yes        |
| 3408   | `academic_year=2021,academic_subject=English 100,#4`                 | yes        |
| 3372   | `academic_year=2016,academic_subject=Writing`                        | yes        |
| 3195   | `academic_year=2021,academic_subject=Algebra I,#2`                   | yes        |
| 3107   | `academic_year=2018,academic_subject=Writing,#2`                     | yes        |
| 3090   | `academic_year=2024,academic_subject=Social Studies`                 | yes        |
| 3063   | `academic_year=2024,academic_subject=Geometry,#2`                    | yes        |
| 3035   | `academic_year=2022,academic_subject=Algebra I,#3`                   | yes        |
| 3021   | `academic_year=2024,academic_subject=English 400,#3`                 | yes        |
| 3021   | `academic_year=2021,academic_subject=Geometry`                       | yes        |
| 3018   | `academic_year=2024,academic_subject=US History AfricanAmerican`     | yes        |
| 2945   | `academic_year=2024,academic_subject=English 300,#2`                 | yes        |
| 2901   | `academic_year=2023,academic_subject=Chemistry,#2`                   | yes        |
| 2858   | `academic_year=2016,academic_subject=Science`                        | yes        |
| 2837   | `academic_year=2024,academic_subject=Algebra II,#3`                  | yes        |
| 2814   | `academic_year=2018,academic_subject=English 100`                    | yes        |
| 2798   | `academic_year=2022,academic_subject=Geometry,#3`                    | yes        |
| 2790   | `academic_year=2022,academic_subject=Pre-Calculus,#3`                | yes        |
| 2780   | `academic_year=2024,academic_subject=US History AfricanAmerican,#2`  | yes        |
| 2755   | `academic_year=2024,academic_subject=US History,#3`                  | yes        |
| 2744   | `academic_year=2023,academic_subject=English 100,#3`                 | yes        |
| 2707   | `academic_year=2023,academic_subject=Physics,#2`                     | yes        |
| 2700   | `academic_year=2024,academic_subject=Physics,#2`                     | yes        |
| 2695   | `academic_year=2023,academic_subject=US History AfricanAmerican,#3`  | yes        |
| 2665   | `academic_year=2018,academic_subject=Geometry,#3`                    | yes        |
| 2641   | `academic_year=2017,academic_subject=Algebra I`                      | yes        |
| 2608   | `academic_year=2022,academic_subject=Geometry`                       | yes        |
| 2593   | `academic_year=2023,academic_subject=English 200,#3`                 | yes        |
| 2559   | `academic_year=2019,academic_subject=Writing,#2`                     | yes        |
| 2558   | `academic_year=2018,academic_subject=Algebra I`                      | yes        |
| 2534   | `academic_year=2021,academic_subject=Writing,#2`                     | yes        |
| 2529   | `academic_year=2022,academic_subject=Algebra II,#3`                  | yes        |
| 2524   | `academic_year=2017,academic_subject=Algebra I,#3`                   | yes        |
| 2445   | `academic_year=2023,academic_subject=Algebra II,#2`                  | yes        |
| 2424   | `academic_year=2024,academic_subject=AP African American Studies,#4` | yes        |
| 2424   | `academic_year=2021,academic_subject=Geometry,#2`                    | yes        |
| 2412   | `academic_year=2018,academic_subject=English 200`                    | yes        |
| 2364   | `academic_year=2017,academic_subject=English 100`                    | yes        |
| 2349   | `academic_year=2022,academic_subject=Algebra II`                     | yes        |
| 2338   | `academic_year=2017,academic_subject=English 200`                    | yes        |
| 2313   | `academic_year=2023,academic_subject=US History,#3`                  | yes        |
| 2306   | `academic_year=2016,academic_subject=Writing,#2`                     | yes        |
| 2298   | `academic_year=2024,academic_subject=Biology,#2`                     | yes        |
| 2268   | `academic_year=2021,academic_subject=English 200`                    | yes        |
| 2264   | `academic_year=2023,academic_subject=US History`                     | yes        |
| 2239   | `academic_year=2022,academic_subject=Algebra I`                      | yes        |
| 2221   | `academic_year=2025,academic_subject=Science,#3`                     | yes        |
| 2153   | `academic_year=2023,academic_subject=English 400`                    | yes        |
| 2057   | `academic_year=2023,academic_subject=Algebra I`                      | yes        |
| 2057   | `academic_year=2018,academic_subject=Writing`                        | yes        |
| 2038   | `academic_year=2022,academic_subject=English 200,#3`                 | yes        |
| 2020   | `academic_year=2023,academic_subject=Physics`                        | yes        |
| 1991   | `academic_year=2021,academic_subject=English 100`                    | yes        |
| 1966   | `academic_year=2024,academic_subject=World History`                  | yes        |
| 1937   | `academic_year=2024,academic_subject=Chemistry`                      | yes        |
| 1926   | `academic_year=2024,academic_subject=Algebra I,#2`                   | yes        |
| 1863   | `academic_year=2024,academic_subject=AP US History,#3`               | yes        |
| 1767   | `academic_year=2018,academic_subject=Algebra I,#3`                   | yes        |
| 1760   | `academic_year=2023,academic_subject=US History AfricanAmerican`     | yes        |
| 1739   | `academic_year=2022,academic_subject=Algebra I,#2`                   | yes        |
| 1734   | `academic_year=2024,academic_subject=AP World History,#3`            | yes        |
| 1719   | `academic_year=2024,academic_subject=English 200,#2`                 | yes        |
| 1677   | `academic_year=2021,academic_subject=Algebra II,#3`                  | yes        |
| 1651   | `academic_year=2021,academic_subject=Pre-Calculus,#3`                | yes        |
| 1651   | `academic_year=2017,academic_subject=Geometry`                       | yes        |
| 1627   | `academic_year=2018,academic_subject=English 300`                    | yes        |
| 1625   | `academic_year=2023,academic_subject=US History,#2`                  | yes        |
| 1593   | `academic_year=2023,academic_subject=Biology,#2`                     | yes        |
| 1582   | `academic_year=2024,academic_subject=Geometry`                       | yes        |
| 1574   | `academic_year=2019,academic_subject=Writing`                        | yes        |
| 1566   | `academic_year=2023,academic_subject=Biology`                        | yes        |
| 1562   | `academic_year=2018,academic_subject=English 100,#3`                 | yes        |
| 1556   | `academic_year=2023,academic_subject=Geometry`                       | yes        |
| 1527   | `academic_year=2023,academic_subject=World History,#2`               | yes        |
| 1525   | `academic_year=2023,academic_subject=English 300,#3`                 | yes        |
| 1523   | `academic_year=2022,academic_subject=Algebra II,#2`                  | yes        |
| 1516   | `academic_year=2024,academic_subject=US History,#2`                  | yes        |
| 1503   | `academic_year=2021,academic_subject=AP Language`                    | yes        |
| 1491   | `academic_year=2022,academic_subject=English 100,#3`                 | yes        |
| 1481   | `academic_year=2017,academic_subject=English 300`                    | yes        |
| 1446   | `academic_year=2018,academic_subject=English 200,#3`                 | yes        |
| 1432   | `academic_year=2024,academic_subject=Algebra II,#2`                  | yes        |
| 1418   | `academic_year=2024,academic_subject=World History,#2`               | yes        |
| 1417   | `academic_year=2024,academic_subject=Biology`                        | yes        |
| 1368   | `academic_year=2018,academic_subject=Algebra II`                     | yes        |
| 1361   | `academic_year=2019,academic_subject=AP Language,#3`                 | yes        |
| 1340   | `academic_year=2015,academic_subject=Writing`                        | yes        |
| 1336   | `academic_year=2017,academic_subject=Algebra I,#2`                   | yes        |
| 1309   | `academic_year=2024,academic_subject=English 400,#2`                 | yes        |
| 1287   | `academic_year=2018,academic_subject=Science,#4`                     | yes        |
| 1287   | `academic_year=2018,academic_subject=Science`                        | yes        |
| 1258   | `academic_year=2023,academic_subject=Chemistry`                      | yes        |
| 1198   | `academic_year=2018,academic_subject=Algebra II,#3`                  | yes        |
| 1187   | `academic_year=2024,academic_subject=English 100,#2`                 | yes        |
| 1176   | `academic_year=2020,academic_subject=AP Language,#4`                 | yes        |
| 1172   | `academic_year=2023,academic_subject=English 100,#2`                 | yes        |
| 1125   | `academic_year=2017,academic_subject=Geometry,#3`                    | yes        |
| 1108   | `academic_year=2022,academic_subject=Geometry,#2`                    | yes        |
| 1084   | `academic_year=2023,academic_subject=Spanish`                        | yes        |
| 1060   | `academic_year=2022,academic_subject=Pre-Calculus`                   | yes        |
| 1031   | `academic_year=2022,academic_subject=English 300,#3`                 | yes        |
| 1025   | `academic_year=2017,academic_subject=Social Studies,#3`              | yes        |
| 1017   | `academic_year=2021,academic_subject=English 100,#2`                 | yes        |
| 964    | `academic_year=2024,academic_subject=English 100`                    | yes        |
| 943    | `academic_year=2024,academic_subject=AP World History`               | yes        |
| 914    | `academic_year=2026,academic_subject=English Language Arts`          | yes        |
| 877    | `academic_year=2018,academic_subject=English 300,#3`                 | yes        |
| 877    | `academic_year=2018,academic_subject=Algebra I,#2`                   | yes        |
| 869    | `academic_year=2022,academic_subject=English 400,#3`                 | yes        |
| 862    | `academic_year=2021,academic_subject=Pre-Calculus`                   | yes        |
| 860    | `academic_year=2023,academic_subject=AP World History,#3`            | yes        |
| 858    | `academic_year=2024,academic_subject=English 400`                    | yes        |
| 836    | `academic_year=2026,academic_subject=Mathematics,#2`                 | yes        |
| 824    | `academic_year=2022,academic_subject=Pre-Calculus,#2`                | yes        |
| 816    | `academic_year=2024,academic_subject=English 200`                    | yes        |
| 813    | `academic_year=2024,academic_subject=English 300`                    | yes        |
| 810    | `academic_year=2018,academic_subject=Geometry,#2`                    | yes        |
| 809    | `academic_year=2023,academic_subject=English 400,#3`                 | yes        |
| 784    | `academic_year=2024,academic_subject=Algebra I MS,#2`                | yes        |
| 775    | `academic_year=2023,academic_subject=Algebra II`                     | yes        |
| 767    | `academic_year=2017,academic_subject=English 100,#2`                 | yes        |
| 760    | `academic_year=2024,academic_subject=AP African American Studies,#3` | yes        |
| 756    | `academic_year=2021,academic_subject=English 200,#3`                 | yes        |
| 751    | `academic_year=2021,academic_subject=Biology`                        | yes        |
| 740    | `academic_year=2019,academic_subject=Composition 200`                | yes        |
| 737    | `academic_year=2021,academic_subject=English 200,#2`                 | yes        |
| 716    | `academic_year=2024,academic_subject=US History`                     | yes        |
| 716    | `academic_year=2023,academic_subject=Spanish,#2`                     | yes        |
| 699    | `academic_year=2019,academic_subject=AP Literature`                  | yes        |
| 697    | `academic_year=2023,academic_subject=US History AfricanAmerican,#2`  | yes        |
| 692    | `academic_year=2021,academic_subject=AP Language,#2`                 | yes        |
| 681    | `academic_year=2022,academic_subject=English 100,#2`                 | yes        |
| 651    | `academic_year=2021,academic_subject=Algebra II,#2`                  | yes        |
| 627    | `academic_year=2017,academic_subject=Writing`                        | yes        |
| 624    | `academic_year=2017,academic_subject=English 200,#2`                 | yes        |
| 610    | `academic_year=2017,academic_subject=English 300,#2`                 | yes        |
| 598    | `academic_year=2020,academic_subject=Geometry`                       | yes        |
| 573    | `academic_year=2023,academic_subject=World History`                  | yes        |
| 570    | `academic_year=2025,academic_subject=Algebra I,#2`                   | yes        |
| 570    | `academic_year=2024,academic_subject=AP US History`                  | yes        |
| 566    | `academic_year=2022,academic_subject=Physics`                        | yes        |
| 547    | `academic_year=2021,academic_subject=Pre-Calculus,#2`                | yes        |
| 544    | `academic_year=2020,academic_subject=AP US History`                  | yes        |
| 530    | `academic_year=2021,academic_subject=Algebra II`                     | yes        |
| 525    | `academic_year=2023,academic_subject=AP US History,#3`               | yes        |
| 505    | `academic_year=2024,academic_subject=Algebra II`                     | yes        |
| 504    | `academic_year=2020,academic_subject=AP Language`                    | yes        |
| 502    | `academic_year=2018,academic_subject=Algebra II,#2`                  | yes        |
| 500    | `academic_year=2021,academic_subject=English 100,#3`                 | yes        |
| 499    | `academic_year=2021,academic_subject=Chemistry`                      | yes        |
| 494    | `academic_year=2022,academic_subject=English 400,#2`                 | yes        |
| 481    | `academic_year=2021,academic_subject=English 300,#4`                 | yes        |
| 468    | `academic_year=2021,academic_subject=AP Language,#4`                 | yes        |
| 467    | `academic_year=2020,academic_subject=AP World History,#2`            | yes        |
| 461    | `academic_year=2018,academic_subject=Pre-Calculus,#3`                | yes        |
| 459    | `academic_year=2023,academic_subject=English 300,#2`                 | yes        |
| 459    | `academic_year=2023,academic_subject=AP African American Studies,#3` | yes        |
| 459    | `academic_year=2019,academic_subject=AP Language,#2`                 | yes        |
| 458    | `academic_year=2023,academic_subject=Early Literacy`                 | yes        |
| 429    | `academic_year=2018,academic_subject=Science,#3`                     | yes        |
| 421    | `academic_year=2022,academic_subject=English 200,#2`                 | yes        |
| 416    | `academic_year=2019,academic_subject=Composition 200,#2`             | yes        |
| 408    | `academic_year=2019,academic_subject=AP World History`               | yes        |
| 398    | `academic_year=2021,academic_subject=AP Language,#3`                 | yes        |
| 383    | `academic_year=2024,academic_subject=Early Literacy`                 | yes        |
| 370    | `academic_year=2019,academic_subject=Composition 200,#3`             | yes        |
| 366    | `academic_year=2025,academic_subject=Early Literacy`                 | yes        |
| 336    | `academic_year=2020,academic_subject=AP Language,#3`                 | yes        |
| 293    | `academic_year=2018,academic_subject=English 100,#2`                 | yes        |
| 283    | `academic_year=2022,academic_subject=Physics,#4`                     | yes        |
| 283    | `academic_year=2022,academic_subject=Physics,#3`                     | yes        |
| 281    | `academic_year=2022,academic_subject=English 300,#2`                 | yes        |
| 272    | `academic_year=2018,academic_subject=English 200,#2`                 | yes        |
| 259    | `academic_year=2019,academic_subject=Algebra I`                      | yes        |
| 258    | `academic_year=2021,academic_subject=English 300`                    | yes        |
| 257    | `academic_year=2023,academic_subject=English 200,#2`                 | yes        |
| 255    | `academic_year=2020,academic_subject=AP World History,#3`            | yes        |
| 247    | `academic_year=2023,academic_subject=AP World History,#2`            | yes        |
| 245    | `academic_year=2019,academic_subject=Chemistry`                      | yes        |
| 229    | `academic_year=2017,academic_subject=Geometry,#2`                    | yes        |
| 228    | `academic_year=2024,academic_subject=AP US History,#2`               | yes        |
| 212    | `academic_year=2024,academic_subject=AP African American Studies,#2` | yes        |
| 209    | `academic_year=2023,academic_subject=English 400,#2`                 | yes        |
| 190    | `academic_year=2023,academic_subject=AP US History,#2`               | yes        |
| 190    | `academic_year=2019,academic_subject=AP Literature,#3`               | yes        |
| 186    | `academic_year=2024,academic_subject=AP African American Studies`    | yes        |
| 181    | `academic_year=2019,academic_subject=Chemistry,#2`                   | yes        |
| 180    | `academic_year=2024,academic_subject=AP World History,#2`            | yes        |
| 180    | `academic_year=2020,academic_subject=AP World History`               | yes        |
| 178    | `academic_year=2017,academic_subject=English 100,#3`                 | yes        |
| 168    | `academic_year=2022,academic_subject=Physics,#2`                     | yes        |
| 167    | `academic_year=2019,academic_subject=AP World History,#2`            | yes        |
| 167    | `academic_year=2018,academic_subject=Pre-Calculus,#2`                | yes        |
| 161    | `academic_year=2023,academic_subject=Pre-Calculus,#2`                | yes        |
| 157    | `academic_year=2023,academic_subject=AP African American Studies,#2` | yes        |
| 152    | `academic_year=2021,academic_subject=AP World History,#2`            | yes        |
| 149    | `academic_year=2024,academic_subject=Civics`                         | yes        |
| 145    | `academic_year=2025,academic_subject=Civics`                         | yes        |
| 136    | `academic_year=2024,academic_subject=Algebra I MS`                   | yes        |
| 136    | `academic_year=2020,academic_subject=AP US History,#3`               | yes        |
| 134    | `academic_year=2019,academic_subject=AP Literature,#2`               | yes        |
| 126    | `academic_year=2021,academic_subject=AP Literature`                  | yes        |
| 125    | `academic_year=2021,academic_subject=Biology,#2`                     | yes        |
| 122    | `academic_year=2018,academic_subject=English 300,#2`                 | yes        |
| 118    | `academic_year=2018,academic_subject=Pre-Calculus`                   | yes        |
| 116    | `academic_year=2026,academic_subject=Early Literacy`                 | yes        |
| 104    | `academic_year=2023,academic_subject=Civics`                         | yes        |
| 102    | `academic_year=2023,academic_subject=AP African American Studies`    | yes        |
| 102    | `academic_year=2021,academic_subject=AP World History`               | yes        |
| 101    | `academic_year=2020,academic_subject=Social Studies,#4`              | yes        |
| 96     | `academic_year=2021,academic_subject=AP US Government & Politics`    | yes        |
| 88     | `academic_year=2021,academic_subject=English 300,#3`                 | yes        |
| 82     | `academic_year=2020,academic_subject=Geometry,#3`                    | yes        |
| 71     | `academic_year=2023,academic_subject=AP World History`               | yes        |
| 64     | `academic_year=2023,academic_subject=Pre-Calculus`                   | yes        |
| 53     | `academic_year=2020,academic_subject=AP US History,#2`               | yes        |
| 50     | `academic_year=2023,academic_subject=AP US History`                  | yes        |
| 47     | `academic_year=2021,academic_subject=English 300,#2`                 | yes        |
| 40     | `academic_year=2020,academic_subject=AP Language,#2`                 | yes        |
| 40     | `academic_year=2018,academic_subject=Science,#2`                     | yes        |
| 16     | `academic_year=2025,academic_subject=Geometry`                       | yes        |
| 15     | `academic_year=2020,academic_subject=Geometry,#2`                    | yes        |

## `count_assessments__standards_over_time`, dashboard_only

| Rows   | Cell                                                                 | Trace lead |
| ------ | -------------------------------------------------------------------- | ---------- |
| 195187 | `academic_year=2025,academic_subject=,#4`                            | yes        |
| 155675 | `academic_year=2025,academic_subject=Science,#2`                     | yes        |
| 105918 | `academic_year=2025,academic_subject=Science,#5`                     | yes        |
| 76982  | `academic_year=2025,academic_subject=,#3`                            | yes        |
| 62552  | `academic_year=2025,academic_subject=Mathematics,#5`                 | yes        |
| 36809  | `academic_year=2025,academic_subject=Science,#4`                     | yes        |
| 22767  | `academic_year=2026,academic_subject=Science,#3`                     | yes        |
| 21098  | `academic_year=2026,academic_subject=Mathematics,#4`                 | yes        |
| 14900  | `academic_year=2025,academic_subject=Mathematics,#4`                 | yes        |
| 12662  | `academic_year=2026,academic_subject=Science`                        | yes        |
| 11750  | `academic_year=2025,academic_subject=,#2`                            | yes        |
| 9981   | `academic_year=2026,academic_subject=,#2`                            | yes        |
| 9231   | `academic_year=2026,academic_subject=`                               | yes        |
| 9117   | `academic_year=2026,academic_subject=Science,#2`                     | yes        |
| 8142   | `academic_year=2026,academic_subject=Mathematics`                    | yes        |
| 7812   | `academic_year=2026,academic_subject=,#3`                            | yes        |
| 5694   | `academic_year=2026,academic_subject=Mathematics,#3`                 | yes        |
| 5424   | `academic_year=2025,academic_subject=Physical Education`             | yes        |
| 4978   | `academic_year=2025,academic_subject=Social Excellence,#2`           | yes        |
| 4302   | `academic_year=2025,academic_subject=History,#2`                     | yes        |
| 4111   | `academic_year=2025,academic_subject=Dance`                          | yes        |
| 2444   | `academic_year=2025,academic_subject=Visual Arts`                    | yes        |
| 2392   | `academic_year=2025,academic_subject=World History,#2`               | yes        |
| 1998   | `academic_year=2025,academic_subject=Music`                          | yes        |
| 1722   | `academic_year=2026,academic_subject=Social Excellence`              | yes        |
| 1548   | `academic_year=2025,academic_subject=US History,#2`                  | yes        |
| 1444   | `academic_year=2025,academic_subject=Text Study,#4`                  | yes        |
| 1355   | `academic_year=2025,academic_subject=Performing Arts`                | yes        |
| 1353   | `academic_year=2025,academic_subject=Physical Education,#2`          | yes        |
| 1350   | `academic_year=2025,academic_subject=Computer Science`               | yes        |
| 1348   | `academic_year=2026,academic_subject=Visual Arts`                    | yes        |
| 1339   | `academic_year=2026,academic_subject=Physical Education`             | yes        |
| 1305   | `academic_year=2026,academic_subject=Dance`                          | yes        |
| 1004   | `academic_year=2026,academic_subject=Text Study,#3`                  | yes        |
| 896    | `academic_year=2026,academic_subject=Physical Education,#2`          | yes        |
| 892    | `academic_year=2025,academic_subject=Social Studies,#2`              | yes        |
| 813    | `academic_year=2026,academic_subject=US History,#2`                  | yes        |
| 753    | `academic_year=2025,academic_subject=Text Study,#3`                  | yes        |
| 686    | `academic_year=2025,academic_subject=Mathematics,#2`                 | yes        |
| 540    | `academic_year=2026,academic_subject=Performing Arts`                | yes        |
| 537    | `academic_year=2026,academic_subject=Music`                          | yes        |
| 478    | `academic_year=2025,academic_subject=World History`                  | yes        |
| 459    | `academic_year=2025,academic_subject=Social Excellence`              | yes        |
| 433    | `academic_year=2026,academic_subject=Computer Science`               | yes        |
| 359    | `academic_year=2026,academic_subject=Algebra I MS,#2`                | yes        |
| 339    | `academic_year=2026,academic_subject=Algebra I,#2`                   | yes        |
| 289    | `academic_year=2026,academic_subject=Economics and Civics,#2`        | yes        |
| 286    | `academic_year=2025,academic_subject=History`                        | yes        |
| 271    | `academic_year=2026,academic_subject=US History`                     | yes        |
| 263    | `academic_year=2025,academic_subject=Physics`                        | yes        |
| 258    | `academic_year=2025,academic_subject=US History`                     | yes        |
| 205    | `academic_year=2026,academic_subject=Text Study,#2`                  | yes        |
| 205    | `academic_year=2025,academic_subject=US History AfricanAmerican`     | yes        |
| 204    | `academic_year=2025,academic_subject=Pre-Calculus`                   | yes        |
| 154    | `academic_year=2025,academic_subject=AP African American Studies,#3` | yes        |
| 145    | `academic_year=2026,academic_subject=Economics and Civics`           | yes        |
| 118    | `#34`                                                                | yes        |
| 115    | `academic_year=2025,academic_subject=AP African American Studies,#2` | yes        |
| 108    | `#46`                                                                | yes        |
| 97     | `academic_year=2026,academic_subject=Text Study`                     | yes        |
| 97     | `academic_year=2025,academic_subject=Text Study,#2`                  | yes        |
| 90     | `academic_year=2026,academic_subject=Algebra I MS`                   | yes        |
| 84     | `academic_year=2025,academic_subject=Text Study`                     | yes        |
| 76     | `#51`                                                                | yes        |
| 72     | `academic_year=2025,academic_subject=Mathematics`                    | yes        |
| 50     | `academic_year=2026,academic_subject=US History AfricanAmerican`     | yes        |
| 50     | `#55`                                                                | yes        |
| 44     | `academic_year=2025,academic_subject=AP African American Studies`    | yes        |
| 42     | `academic_year=2025,academic_subject=Anatomy and Physiology`         | yes        |
| 30     | `academic_year=2026,academic_subject=Social Studies`                 | yes        |
| 25     | `academic_year=2026,academic_subject=World History`                  | yes        |
| 22     | `academic_year=2025,academic_subject=English`                        | yes        |
| 19     | `academic_year=2026,academic_subject=Algebra I`                      | yes        |
| 19     | `academic_year=2026,academic_subject=AP Calculus`                    | yes        |
| 18     | `academic_year=2025,academic_subject=Social Studies`                 | yes        |
| 18     | `#42`                                                                | yes        |
| 16     | `#54`                                                                | yes        |
| 15     | `#33`                                                                | yes        |
| 14     | `#32`                                                                | yes        |
| 13     | `academic_year=2025,academic_subject=Science`                        | yes        |
| 11     | `academic_year=2025,academic_subject=Algebra I`                      | yes        |
| 11     | `academic_year=2025,academic_subject=`                               | yes        |

## `count_assessments__standards_over_time`, dims_differ

| Rows  | Cell                                                                      | Trace lead |
| ----- | ------------------------------------------------------------------------- | ---------- |
| 34373 | `academic_year=2026,academic_subject=Text Study,d:d:d:`                   | yes        |
| 27857 | `academic_year=2026,academic_subject=Mathematics,d:d:d:#2`                | yes        |
| 22981 | `academic_year=2025,academic_subject=Text Study,d:d:d:`                   | yes        |
| 22335 | `academic_year=2026,academic_subject=Science,d:d:d:`                      | yes        |
| 18471 | `academic_year=2025,academic_subject=Mathematics,d:d:d:`                  | yes        |
| 15302 | `academic_year=2025,academic_subject=Science,d:d:d:`                      | yes        |
| 9044  | `academic_year=2026,academic_subject=Biology,d:d:d:`                      | yes        |
| 7755  | `academic_year=2026,academic_subject=Social Studies,d:d:d:`               | yes        |
| 4776  | `academic_year=2025,academic_subject=Social Studies,d:d:d:`               | yes        |
| 2978  | `academic_year=2025,academic_subject=Geometry,d:d:d:`                     | yes        |
| 2946  | `academic_year=2025,academic_subject=Physics,d:d:d:`                      | yes        |
| 2771  | `academic_year=2025,academic_subject=US History AfricanAmerican,d:d:d:`   | yes        |
| 2607  | `academic_year=2025,academic_subject=Algebra I,d:d:d:`                    | yes        |
| 2508  | `academic_year=2025,academic_subject=Biology,d:d:d:`                      | yes        |
| 2300  | `academic_year=2026,academic_subject=English 100,d:d:d:`                  | yes        |
| 2103  | `academic_year=2026,academic_subject=Algebra I,d:d:d:`                    | yes        |
| 2046  | `academic_year=2026,academic_subject=Chemistry,d:d:d:`                    | yes        |
| 2041  | `academic_year=2026,academic_subject=English 200,d:d:d:`                  | yes        |
| 2029  | `academic_year=2025,academic_subject=English 100,d:d:d:`                  | yes        |
| 1674  | `academic_year=2025,academic_subject=Chemistry,d:d:d:`                    | yes        |
| 1579  | `academic_year=2026,academic_subject=CCR 4,d:d:d:`                        | yes        |
| 1565  | `academic_year=2026,academic_subject=Geometry,d:d:d:`                     | yes        |
| 1544  | `academic_year=2026,academic_subject=US History AfricanAmerican,d:d:d:`   | yes        |
| 1412  | `academic_year=2026,academic_subject=Algebra II,d:d:d:`                   | yes        |
| 1364  | `academic_year=2026,academic_subject=World History,d:d:d:`                | yes        |
| 1300  | `academic_year=2026,academic_subject=AP African American Studies,d:d:d:`  | yes        |
| 1287  | `academic_year=2026,academic_subject=CCR 3,d:d:d:`                        | yes        |
| 1164  | `academic_year=2026,academic_subject=Human Anatomy and Physiology,d:d:d:` | yes        |
| 1126  | `academic_year=2026,academic_subject=Mathematics,d:d:d:#4`                | yes        |
| 1120  | `academic_year=2025,academic_subject=World History,d:d:d:`                | yes        |
| 1095  | `academic_year=2026,academic_subject=English 300,d:d:d:`                  | yes        |
| 1064  | `academic_year=2026,academic_subject=English 400,d:d:d:`                  | yes        |
| 1003  | `academic_year=2025,academic_subject=Algebra II,d:d:d:`                   | yes        |
| 915   | `academic_year=2026,academic_subject=US History,d:d:d:`                   | yes        |
| 870   | `academic_year=2025,academic_subject=CCR 4,d:d:d:`                        | yes        |
| 804   | `academic_year=2025,academic_subject=US History,d:d:d:`                   | yes        |
| 783   | `academic_year=2025,academic_subject=CCR 3,d:d:d:`                        | yes        |
| 710   | `academic_year=2024,academic_subject=Mathematics,d:d:d:`                  | yes        |
| 685   | `academic_year=2025,academic_subject=English 300,d:d:d:`                  | yes        |
| 661   | `academic_year=2025,academic_subject=English 400,d:d:d:`                  | yes        |
| 638   | `academic_year=2025,academic_subject=CCR 1,d:d:d:`                        | yes        |
| 563   | `academic_year=2026,academic_subject=Mathematics,d:d:d:#3`                | yes        |
| 512   | `academic_year=2025,academic_subject=English 200,d:d:d:`                  | yes        |
| 499   | `academic_year=2024,academic_subject=Mathematics,d:d:d:#3`                | yes        |
| 492   | `academic_year=2026,academic_subject=Economics and Civics,d:d:d:`         | yes        |
| 466   | `academic_year=2026,academic_subject=Geometry Honors,d:d:d:`              | yes        |
| 268   | `academic_year=2026,academic_subject=AP US History,d:d:d:`                | yes        |
| 262   | `academic_year=2026,academic_subject=Algebra I MS,d:d:d:`                 | yes        |
| 248   | `academic_year=2026,academic_subject=AP World History,d:d:d:`             | yes        |
| 240   | `academic_year=2025,academic_subject=AP African American Studies,d:d:d:`  | yes        |
| 210   | `academic_year=2025,academic_subject=Economics and Civics,d:d:d:`         | yes        |
| 165   | `academic_year=2025,academic_subject=Algebra I MS,d:d:d:`                 | yes        |
| 164   | `academic_year=2026,academic_subject=AP Language,d:d:d:`                  | yes        |
| 144   | `academic_year=2025,academic_subject=Math 4,d:d:d:`                       | yes        |
| 127   | `academic_year=2025,academic_subject=AP World History,d:d:d:`             | yes        |
| 126   | `academic_year=2025,academic_subject=AP US History,d:d:d:`                | yes        |
| 101   | `academic_year=2024,academic_subject=Mathematics,d:d:d:#2`                | yes        |
| 74    | `academic_year=2026,academic_subject=AP Pre Calculus,d:d:d:`              | yes        |
| 46    | `academic_year=2026,academic_subject=Mathematics,d:d:d:`                  | yes        |
| 33    | `academic_year=2026,academic_subject=Algebra II Honors,d:d:d:`            | yes        |
| 24    | `academic_year=2025,academic_subject=African American Studies,d:d:d:`     | yes        |
| 17    | `academic_year=2025,academic_subject=AP Language,d:d:d:`                  | yes        |

## `count_students__score_distribution`, cube_only

| Rows   | Cell                    | Trace lead |
| ------ | ----------------------- | ---------- |
| 211135 | `academic_year=2023#19` | yes        |
| 206882 | `academic_year=2023#12` | yes        |
| 205881 | `academic_year=2023#13` | yes        |
| 200814 | `academic_year=2023#4`  | yes        |
| 190879 | `academic_year=2023#2`  | yes        |
| 179835 | `academic_year=2024#8`  | yes        |
| 179336 | `academic_year=2024#3`  | yes        |
| 178834 | `academic_year=2024#11` | yes        |
| 178619 | `academic_year=2023#15` | yes        |
| 176419 | `academic_year=2023#5`  | yes        |
| 175147 | `academic_year=2024#13` | yes        |
| 173056 | `academic_year=2024#19` | yes        |
| 172049 | `academic_year=2024#12` | yes        |
| 171923 | `academic_year=2024#15` | yes        |
| 159477 | `academic_year=2024#9`  | yes        |
| 156825 | `academic_year=2024#14` | yes        |
| 151792 | `academic_year=2024`    | yes        |
| 148608 | `academic_year=2023#11` | yes        |
| 146725 | `academic_year=2023#3`  | yes        |
| 141893 | `academic_year=2023#17` | yes        |
| 139776 | `academic_year=2024#2`  | yes        |
| 138983 | `academic_year=2023#16` | yes        |
| 137923 | `academic_year=2024#17` | yes        |
| 136055 | `academic_year=2024#4`  | yes        |
| 134210 | `academic_year=2024#16` | yes        |
| 130887 | `academic_year=2022#16` | yes        |
| 130778 | `academic_year=2022#22` | yes        |
| 130755 | `academic_year=2022#2`  | yes        |
| 130307 | `academic_year=2022`    | yes        |
| 128790 | `academic_year=2022#3`  | yes        |
| 123918 | `academic_year=2017#6`  | yes        |
| 121277 | `academic_year=2018#2`  | yes        |
| 120253 | `academic_year=2016#5`  | yes        |
| 119982 | `academic_year=2024#20` | yes        |
| 119333 | `academic_year=2016`    | yes        |
| 119184 | `academic_year=2023#18` | yes        |
| 118812 | `academic_year=2023#20` | yes        |
| 118425 | `academic_year=2022#18` | yes        |
| 114911 | `academic_year=2022#20` | yes        |
| 114069 | `academic_year=2022#4`  | yes        |
| 113272 | `academic_year=2018#8`  | yes        |
| 112773 | `academic_year=2018#9`  | yes        |
| 112344 | `academic_year=2018#10` | yes        |
| 112195 | `academic_year=2024#18` | yes        |
| 111330 | `academic_year=2017`    | yes        |
| 111072 | `academic_year=2024#10` | yes        |
| 109902 | `academic_year=2018#11` | yes        |
| 109338 | `academic_year=2018#7`  | yes        |
| 109172 | `academic_year=2023#14` | yes        |
| 108632 | `academic_year=2017#5`  | yes        |
| 107906 | `academic_year=2022#21` | yes        |
| 105340 | `academic_year=2022#19` | yes        |
| 105227 | `academic_year=2019#2`  | yes        |
| 104744 | `academic_year=2021#6`  | yes        |
| 104594 | `academic_year=2021#2`  | yes        |
| 103777 | `academic_year=2023#9`  | yes        |
| 102948 | `academic_year=2019#13` | yes        |
| 102468 | `academic_year=2019#11` | yes        |
| 101230 | `academic_year=2021#21` | yes        |
| 99708  | `academic_year=2021#15` | yes        |
| 99493  | `academic_year=2019#12` | yes        |
| 97555  | `academic_year=2021`    | yes        |
| 96612  | `academic_year=2019#14` | yes        |
| 93612  | `academic_year=2022#11` | yes        |
| 92176  | `academic_year=2019#9`  | yes        |
| 91906  | `academic_year=2024#5`  | yes        |
| 91249  | `academic_year=2019`    | yes        |
| 90870  | `academic_year=2021#18` | yes        |
| 90579  | `academic_year=2021#3`  | yes        |
| 89312  | `academic_year=2021#19` | yes        |
| 88498  | `academic_year=2018`    | yes        |
| 88276  | `academic_year=2019#15` | yes        |
| 88275  | `academic_year=2018#12` | yes        |
| 88262  | `academic_year=2018#6`  | yes        |
| 87281  | `academic_year=2022#23` | yes        |
| 86688  | `academic_year=2017#11` | yes        |
| 84119  | `academic_year=2021#17` | yes        |
| 82318  | `academic_year=2021#20` | yes        |
| 81610  | `academic_year=2019#3`  | yes        |
| 78925  | `academic_year=2021#4`  | yes        |
| 76394  | `academic_year=2017#3`  | yes        |
| 76229  | `academic_year=2019#4`  | yes        |
| 74437  | `academic_year=2023#8`  | yes        |
| 73868  | `academic_year=2023#10` | yes        |
| 72270  | `academic_year=2015`    | yes        |
| 70860  | `academic_year=2018#3`  | yes        |
| 70058  | `academic_year=2022#17` | yes        |
| 69138  | `academic_year=2020#2`  | yes        |
| 68957  | `academic_year=2024#6`  | yes        |
| 68289  | `academic_year=2023#6`  | yes        |
| 67876  | `academic_year=2020#15` | yes        |
| 66885  | `academic_year=2020#17` | yes        |
| 65714  | `academic_year=2020#13` | yes        |
| 65172  | `academic_year=2020#14` | yes        |
| 64371  | `academic_year=2015#4`  | yes        |
| 63937  | `academic_year=2022#7`  | yes        |
| 63760  | `academic_year=2020#16` | yes        |
| 63627  | `academic_year=2018#4`  | yes        |
| 63604  | `academic_year=2020`    | yes        |
| 63143  | `academic_year=2016#6`  | yes        |
| 62137  | `academic_year=2020#11` | yes        |
| 60665  | `academic_year=2020#3`  | yes        |
| 59350  | `academic_year=2016#3`  | yes        |
| 56716  | `academic_year=2022#14` | yes        |
| 52852  | `academic_year=2020#4`  | yes        |
| 52711  | `academic_year=2021#10` | yes        |
| 51416  | `academic_year=2020#6`  | yes        |
| 48322  | `academic_year=2023#7`  | yes        |
| 47892  | `academic_year=2022#12` | yes        |
| 47617  | `academic_year=2022#13` | yes        |
| 47477  | `academic_year=2022#15` | yes        |
| 46475  | `academic_year=2022#9`  | yes        |
| 45709  | `academic_year=2021#22` | yes        |
| 44451  | `academic_year=2017#4`  | yes        |
| 43610  | `academic_year=2019#5`  | yes        |
| 41896  | `academic_year=2022#5`  | yes        |
| 40151  | `academic_year=2025#19` | yes        |
| 38851  | `academic_year=2021#16` | yes        |
| 38632  | `academic_year=2015#6`  | yes        |
| 37470  | `academic_year=2022#10` | yes        |
| 36376  | `academic_year=2020#9`  | yes        |
| 35834  | `academic_year=2025#31` | yes        |
| 31922  | `academic_year=2025#35` | yes        |
| 31682  | `academic_year=2015#7`  | yes        |
| 31319  | `academic_year=2021#7`  | yes        |
| 31087  | `academic_year=2022#8`  | yes        |
| 30923  | `academic_year=2025#17` | yes        |
| 30680  | `academic_year=2025#33` | yes        |
| 30643  | `academic_year=2025#5`  | yes        |
| 29833  | `academic_year=2015#5`  | yes        |
| 29353  | `academic_year=2018#5`  | yes        |
| 28508  | `academic_year=2015#3`  | yes        |
| 27563  | `academic_year=2025#41` | yes        |
| 26413  | `academic_year=2021#9`  | yes        |
| 24781  | `academic_year=2025#37` | yes        |
| 24772  | `academic_year=2015#8`  | yes        |
| 24169  | `academic_year=2021#12` | yes        |
| 23705  | `academic_year=2019#6`  | yes        |
| 23378  | `academic_year=2021#14` | yes        |
| 23050  | `academic_year=2016#4`  | yes        |
| 22964  | `academic_year=2025#7`  | yes        |
| 22144  | `academic_year=2025#39` | yes        |
| 22076  | `academic_year=2025#3`  | yes        |
| 21787  | `academic_year=2025#27` | yes        |
| 21742  | `academic_year=2025#25` | yes        |
| 21379  | `academic_year=2025#23` | yes        |
| 21345  | `academic_year=2021#8`  | yes        |
| 21320  | `academic_year=2020#7`  | yes        |
| 20712  | `academic_year=2020#18` | yes        |
| 20251  | `academic_year=2021#13` | yes        |
| 19485  | `academic_year=2015#2`  | yes        |
| 18728  | `academic_year=2022#6`  | yes        |
| 18569  | `academic_year=2021#11` | yes        |
| 17147  | `academic_year=2025#13` | yes        |
| 16665  | `academic_year=2021#5`  | yes        |
| 15646  | `academic_year=2015#9`  | yes        |
| 15525  | `academic_year=2019#7`  | yes        |
| 14097  | `academic_year=2026#19` | yes        |
| 13845  | `academic_year=2019#16` | yes        |
| 13231  | `academic_year=2025#9`  | yes        |
| 12732  | `academic_year=2016#8`  | yes        |
| 12445  | `academic_year=2025#29` | yes        |
| 11624  | `academic_year=2016#7`  | yes        |
| 11052  | `academic_year=2026#34` | yes        |
| 10963  | `academic_year=2019#10` | yes        |
| 10380  | `academic_year=2026#38` | yes        |
| 10371  | `academic_year=2026#5`  | yes        |
| 9714   | `academic_year=2026#36` | yes        |
| 9693   | `academic_year=2026`    | yes        |
| 9606   | `academic_year=2016#9`  | yes        |
| 8824   | `academic_year=2016#2`  | yes        |
| 8763   | `academic_year=2026#44` | yes        |
| 8263   | `academic_year=2026#40` | yes        |
| 7901   | `academic_year=2016#10` | yes        |
| 7868   | `academic_year=2017#9`  | yes        |
| 7382   | `academic_year=2017#8`  | yes        |
| 7367   | `academic_year=2017#7`  | yes        |
| 7361   | `academic_year=2026#30` | yes        |
| 7305   | `academic_year=2026#7`  | yes        |
| 7302   | `academic_year=2025`    | yes        |
| 7274   | `academic_year=2025#21` | yes        |
| 7225   | `academic_year=2026#42` | yes        |
| 7107   | `academic_year=2026#3`  | yes        |
| 7062   | `academic_year=2026#28` | yes        |
| 6976   | `academic_year=2020#12` | yes        |
| 6968   | `academic_year=2026#26` | yes        |
| 6933   | `academic_year=2017#2`  | yes        |
| 6849   | `academic_year=2026#17` | yes        |
| 6099   | `academic_year=2026#13` | yes        |
| 5646   | `academic_year=2017#10` | yes        |
| 5263   | `academic_year=2025#11` | yes        |
| 5015   | `academic_year=2020#8`  | yes        |
| 4166   | `academic_year=2026#15` | yes        |
| 3448   | `academic_year=2026#9`  | yes        |
| 3287   | `academic_year=2026#22` | yes        |
| 2391   | `academic_year=2025#15` | yes        |
| 2285   | `academic_year=2026#32` | yes        |
| 1515   | `academic_year=2026#11` | yes        |
| 1315   | `academic_year=2026#24` | yes        |
| 536    | `academic_year=2026#23` | yes        |
| 470    | `academic_year=2020#10` | yes        |
| 300    | `academic_year=2024#7`  | yes        |
| 140    | `academic_year=2023`    | yes        |
| 93     | `academic_year=2019#8`  | yes        |
| 47     | `academic_year=2020#5`  | yes        |

## `count_students__score_distribution`, dashboard_only

| Rows  | Cell                    | Trace lead |
| ----- | ----------------------- | ---------- |
| 62222 | `academic_year=2025#24` | yes        |
| 62025 | `academic_year=2025#4`  | yes        |
| 61853 | `academic_year=2025#26` | yes        |
| 58476 | `academic_year=2025#8`  | yes        |
| 57559 | `academic_year=2025#40` | yes        |
| 57392 | `academic_year=2025#28` | yes        |
| 39014 | `academic_year=2025#36` | yes        |
| 38339 | `academic_year=2025#30` | yes        |
| 37948 | `academic_year=2025#38` | yes        |
| 37557 | `academic_year=2025#10` | yes        |
| 27574 | `academic_year=2025#22` | yes        |
| 26796 | `academic_year=2025#42` | yes        |
| 24381 | `academic_year=2025#32` | yes        |
| 22299 | `academic_year=2025#12` | yes        |
| 20306 | `academic_year=2025#16` | yes        |
| 18720 | `academic_year=2025#6`  | yes        |
| 16543 | `academic_year=2025#34` | yes        |
| 15439 | `academic_year=2026#33` | yes        |
| 14150 | `academic_year=2025#14` | yes        |
| 10838 | `academic_year=2026#43` | yes        |
| 10765 | `academic_year=2026#27` | yes        |
| 10436 | `academic_year=2026#31` | yes        |
| 10382 | `academic_year=2026#12` | yes        |
| 9082  | `academic_year=2026#29` | yes        |
| 8484  | `academic_year=2026#4`  | yes        |
| 8242  | `academic_year=2026#25` | yes        |
| 7074  | `academic_year=2026#8`  | yes        |
| 5964  | `academic_year=2026#16` | yes        |
| 5811  | `academic_year=2026#39` | yes        |
| 5647  | `academic_year=2025#2`  | yes        |
| 5555  | `academic_year=2025#18` | yes        |
| 4146  | `academic_year=2026#10` | yes        |
| 3296  | `academic_year=2025#20` | yes        |
| 3285  | `academic_year=2026#18` | yes        |
| 3000  | `academic_year=2026#2`  | yes        |
| 1885  | `academic_year=2026#41` | yes        |
| 1392  | `academic_year=2026#14` | yes        |
| 888   | `academic_year=2026#21` | yes        |
| 772   | `academic_year=2026#6`  | yes        |
| 316   | `academic_year=2026#35` | yes        |
| 251   | `academic_year=2026#37` | yes        |
| 199   | `academic_year=2026#45` | yes        |
| 101   | ``                      | yes        |
| 55    | `academic_year=2026#20` | yes        |
| 42    | `#3`                    | yes        |
| 42    | `#2`                    | yes        |
| 10    | `#4`                    | yes        |

## `count_students__score_distribution`, dims_differ

| Rows | Cell                        | Trace lead |
| ---- | --------------------------- | ---------- |
| 617  | `academic_year=2024,d:d:#4` | yes        |
| 309  | `academic_year=2026,d:d:#6` | yes        |
| 270  | `academic_year=2026,d:d:#4` | yes        |
| 253  | `academic_year=2026,d:d:#5` | yes        |
| 234  | `academic_year=2026,d:d:#2` | yes        |
| 209  | `d:d:#11`                   | yes        |
| 193  | `d:d:#14`                   | yes        |
| 181  | `academic_year=2026,d:d:`   | yes        |
| 177  | `academic_year=2026,d:d:#8` | yes        |
| 175  | `academic_year=2026,d:d:#7` | yes        |
| 148  | `d:d:#20`                   | yes        |
| 123  | `d:d:#26`                   | yes        |
| 113  | `d:d:#42`                   | yes        |
| 107  | `d:d:#19`                   | yes        |
| 107  | `academic_year=2024,d:d:#2` | yes        |
| 105  | `d:d:#27`                   | yes        |
| 105  | `academic_year=2026,d:d:#3` | yes        |
| 104  | `academic_year=2024,d:d:#6` | yes        |
| 104  | `academic_year=2024,d:d:`   | yes        |
| 103  | `academic_year=2024,d:d:#8` | yes        |
| 97   | `d:d:#37`                   | yes        |
| 95   | `academic_year=2024,d:d:#5` | yes        |
| 93   | `academic_year=2024,d:d:#7` | yes        |
| 74   | `d:d:#13`                   | yes        |
| 72   | `d:d:#46`                   | yes        |
| 67   | `academic_year=2024,d:d:#3` | yes        |
| 63   | `d:d:#34`                   | yes        |
| 62   | `d:d:#50`                   | yes        |
| 57   | `d:d:#55`                   | yes        |
| 57   | `d:d:#5`                    | yes        |
| 56   | `d:d:#10`                   | yes        |
| 55   | `d:d:#53`                   | yes        |
| 40   | `d:d:#30`                   | yes        |
| 40   | `d:d:#22`                   | yes        |
| 39   | `d:d:#21`                   | yes        |
| 34   | `d:d:#7`                    | yes        |
| 33   | `d:d:#38`                   | yes        |
| 32   | `d:d:#54`                   | yes        |
| 20   | `d:d:#2`                    | yes        |
| 19   | `d:d:#29`                   | yes        |
| 19   | `d:d:`                      | yes        |
| 16   | `d:d:#8`                    | yes        |
| 16   | `d:d:#33`                   | yes        |
| 14   | `d:d:#28`                   | yes        |
| 13   | `d:d:#39`                   | yes        |
| 13   | `d:d:#35`                   | yes        |

## `grade_goal_distance__grid_grade`, cube_only

| Rows | Cell                                        | Trace lead |
| ---- | ------------------------------------------- | ---------- |
| 676  | `grade_level=3,academic_subject=Text Study` | yes        |
| 137  | `grade_level=6,academic_subject=Science`    | yes        |
| 30   | `grade_level=5,academic_subject=`           | yes        |
| 25   | `grade_level=6,academic_subject=`           | yes        |

## `grade_goal_distance__grid_grade`, dashboard_only

| Rows | Cell                                        | Trace lead |
| ---- | ------------------------------------------- | ---------- |
| 20   | `grade_level=6,academic_subject=Text Study` | yes        |

## `pct_proficient__dki_grid`, cube_only

| Rows | Cell                                                                         | Trace lead |
| ---- | ---------------------------------------------------------------------------- | ---------- |
| 106  | `module_code=,abbreviation=Courage,grade_level=6,academic_subject=Science`   | yes        |
| 31   | `module_code=,abbreviation=Legacy MS,grade_level=6,academic_subject=Science` | yes        |
| 30   | `module_code=,abbreviation=Legacy ES,grade_level=5,academic_subject=`        | yes        |
| 25   | `module_code=,abbreviation=Legacy MS,grade_level=6,academic_subject=`        | yes        |

## `pct_proficient__dki_grid`, dashboard_only

| Rows | Cell                                                                             | Trace lead |
| ---- | -------------------------------------------------------------------------------- | ---------- |
| 139  | `module_code=ET1,abbreviation=Courage,grade_level=6,academic_subject=US History` | yes        |
| 19   | `module_code=ET1,abbreviation=Courage,grade_level=6,academic_subject=Text Study` | yes        |

## `pct_proficient__dki_standards_grid`, cube_only

| Rows | Cell                                     | Trace lead |
| ---- | ---------------------------------------- | ---------- |
| 106  | `module_code=,abbreviation=Courage,#8`   | yes        |
| 106  | `module_code=,abbreviation=Courage,#7`   | yes        |
| 106  | `module_code=,abbreviation=Courage,#6`   | yes        |
| 106  | `module_code=,abbreviation=Courage,#5`   | yes        |
| 106  | `module_code=,abbreviation=Courage,#4`   | yes        |
| 106  | `module_code=,abbreviation=Courage,#3`   | yes        |
| 106  | `module_code=,abbreviation=Courage,#2`   | yes        |
| 106  | `module_code=,abbreviation=Courage`      | yes        |
| 31   | `module_code=,abbreviation=Legacy MS,#8` | yes        |
| 31   | `module_code=,abbreviation=Legacy MS,#7` | yes        |
| 31   | `module_code=,abbreviation=Legacy MS,#6` | yes        |
| 31   | `module_code=,abbreviation=Legacy MS,#5` | yes        |
| 31   | `module_code=,abbreviation=Legacy MS,#4` | yes        |
| 31   | `module_code=,abbreviation=Legacy MS,#3` | yes        |
| 31   | `module_code=,abbreviation=Legacy MS,#2` | yes        |
| 31   | `module_code=,abbreviation=Legacy MS`    | yes        |

## `pct_proficient__dki_standards_grid`, dashboard_only

| Rows | Cell                                       | Trace lead |
| ---- | ------------------------------------------ | ---------- |
| 139  | `module_code=ET1,abbreviation=Courage,#31` | yes        |
| 139  | `module_code=ET1,abbreviation=Courage,#30` | yes        |
| 139  | `module_code=ET1,abbreviation=Courage,#29` | yes        |
| 19   | `module_code=ET1,abbreviation=Courage,#26` | yes        |
| 19   | `module_code=ET1,abbreviation=Courage,#25` | yes        |
| 19   | `module_code=ET1,abbreviation=Courage,#24` | yes        |
| 19   | `module_code=ET1,abbreviation=Courage,#23` | yes        |
| 19   | `module_code=ET1,abbreviation=Courage,#22` | yes        |
| 19   | `module_code=ET1,abbreviation=Courage,#21` | yes        |
| 19   | `module_code=ET1,abbreviation=Courage,#20` | yes        |
| 19   | `module_code=ET1,abbreviation=Courage,#19` | yes        |
| 19   | `module_code=ET1,abbreviation=Courage,#18` | yes        |
| 19   | `module_code=ET1,abbreviation=Courage,#17` | yes        |
| 19   | `module_code=ET1,abbreviation=Courage,#16` | yes        |

## `pct_students_at_level__dki_bars`, cube_only

| Rows | Cell                                                                         | Trace lead |
| ---- | ---------------------------------------------------------------------------- | ---------- |
| 106  | `abbreviation=Courage,module_code=,grade_level=6,academic_subject=Science`   | yes        |
| 31   | `abbreviation=Legacy MS,module_code=,grade_level=6,academic_subject=Science` | yes        |
| 30   | `abbreviation=Legacy ES,module_code=,grade_level=5,academic_subject=`        | yes        |
| 25   | `abbreviation=Legacy MS,module_code=,grade_level=6,academic_subject=`        | yes        |

## `pct_students_at_level__dki_bars`, dashboard_only

| Rows | Cell                                                                             | Trace lead |
| ---- | -------------------------------------------------------------------------------- | ---------- |
| 139  | `abbreviation=Courage,module_code=ET1,grade_level=6,academic_subject=US History` | yes        |
| 12   | `abbreviation=Courage,module_code=ET1,grade_level=6,academic_subject=Text Study` | yes        |

## `pct_students_at_level__dki_standards_bars`, cube_only

| Rows | Cell                                     | Trace lead |
| ---- | ---------------------------------------- | ---------- |
| 106  | `abbreviation=Courage,module_code=,#8`   | yes        |
| 106  | `abbreviation=Courage,module_code=,#7`   | yes        |
| 106  | `abbreviation=Courage,module_code=,#6`   | yes        |
| 106  | `abbreviation=Courage,module_code=,#5`   | yes        |
| 106  | `abbreviation=Courage,module_code=,#4`   | yes        |
| 106  | `abbreviation=Courage,module_code=,#3`   | yes        |
| 106  | `abbreviation=Courage,module_code=,#2`   | yes        |
| 106  | `abbreviation=Courage,module_code=`      | yes        |
| 31   | `abbreviation=Legacy MS,module_code=,#8` | yes        |
| 31   | `abbreviation=Legacy MS,module_code=,#7` | yes        |
| 31   | `abbreviation=Legacy MS,module_code=,#6` | yes        |
| 31   | `abbreviation=Legacy MS,module_code=,#5` | yes        |
| 31   | `abbreviation=Legacy MS,module_code=,#4` | yes        |
| 31   | `abbreviation=Legacy MS,module_code=,#3` | yes        |
| 31   | `abbreviation=Legacy MS,module_code=,#2` | yes        |
| 31   | `abbreviation=Legacy MS,module_code=`    | yes        |

## `pct_students_at_level__dki_standards_bars`, dashboard_only

| Rows | Cell                                       | Trace lead |
| ---- | ------------------------------------------ | ---------- |
| 139  | `abbreviation=Courage,module_code=ET1,#37` | yes        |
| 139  | `abbreviation=Courage,module_code=ET1,#36` | yes        |
| 139  | `abbreviation=Courage,module_code=ET1,#35` | yes        |
| 32   | `abbreviation=Courage,module_code=ET1,#21` | yes        |
| 24   | `abbreviation=Courage,module_code=ET1,#24` | yes        |
| 15   | `abbreviation=Courage,module_code=ET1,#2`  | yes        |
| 13   | `abbreviation=Courage,module_code=ET1,#6`  | yes        |
| 12   | `abbreviation=Courage,module_code=ET1,#4`  | yes        |
| 12   | `abbreviation=Courage,module_code=ET1`     | yes        |
| 11   | `abbreviation=Courage,module_code=ET1,#7`  | yes        |
| 11   | `abbreviation=Courage,module_code=ET1,#5`  | yes        |
| 10   | `abbreviation=Courage,module_code=ET1,#3`  | yes        |
| 10   | `abbreviation=Courage,module_code=ET1,#18` | yes        |

## `pct_taken__assessments_over_time`, cube_only

| Rows | Cell                             | Trace lead |
| ---- | -------------------------------- | ---------- |
| 1696 | `module_code=CRQ1,grade_level=1` | yes        |
| 40   | `module_code=CRQ1,grade_level=0` | yes        |

## `pct_taken__assessments_over_time`, dashboard_only

| Rows | Cell                             | Trace lead |
| ---- | -------------------------------- | ---------- |
| 994  | `module_code=ET2,grade_level=8`  | yes        |
| 807  | `module_code=ET1,grade_level=6`  | yes        |
| 472  | `module_code=ET1,grade_level=8`  | yes        |
| 395  | `module_code=BL1,grade_level=8`  | yes        |
| 315  | `module_code=ET1,grade_level=9`  | yes        |
| 112  | `module_code=QA1,grade_level=6`  | yes        |
| 78   | `#44`                            | yes        |
| 42   | `#54`                            | yes        |
| 39   | `#52`                            | yes        |
| 34   | `#43`                            | yes        |
| 25   | `#3`                             | yes        |
| 22   | `module_code=MQQ1,grade_level=6` | yes        |
| 13   | `#25`                            | yes        |
| 13   | `#17`                            | yes        |
| 12   | `#36`                            | yes        |
| 10   | `#31`                            | yes        |

## `pct_taken__assessments_over_time`, dims_differ

| Rows | Cell        | Trace lead |
| ---- | ----------- | ---------- |
| 11   | `d:d:d:#10` | yes        |

## `region_goal_distance__lines_all`, cube_only

| Rows | Cell                    | Trace lead |
| ---- | ----------------------- | ---------- |
| 1060 | `region_name=Newark#11` | yes        |
| 917  | `region_name=Newark#7`  | yes        |
| 326  | `region_name=Newark#4`  | yes        |
| 146  | `region_name=Miami#13`  | yes        |
| 87   | `region_name=Miami#10`  | yes        |

## `region_goal_distance__lines_all`, dashboard_only

| Rows | Cell                   | Trace lead |
| ---- | ---------------------- | ---------- |
| 80   | `region_name=Miami#3`  | yes        |
| 52   | `region_name=Newark#5` | yes        |
| 39   | `region_name=Miami#5`  | yes        |
| 12   | `region_name=Miami#7`  | yes        |
| 10   | `#4`                   | yes        |

## `school_goal_distance__lines_all`, cube_only

| Rows | Cell                       | Trace lead |
| ---- | -------------------------- | ---------- |
| 179  | `abbreviation=Life#6`      | yes        |
| 106  | `abbreviation=Courage#11`  | yes        |
| 33   | `abbreviation=SPARK#4`     | yes        |
| 33   | `abbreviation=Legacy MS#5` | yes        |
| 33   | `abbreviation=Legacy ES#6` | yes        |
| 27   | `abbreviation=THRIVE#4`    | yes        |
| 25   | `abbreviation=Legacy MS#4` | yes        |

## `school_goal_distance__lines_all`, dashboard_only

| Rows | Cell                     | Trace lead |
| ---- | ------------------------ | ---------- |
| 76   | `abbreviation=Courage#3` | yes        |
| 32   | `abbreviation=Courage#5` | yes        |

## Other lines

- `pct_proficient__dki_grid` in `student_assessment_scores_view`:
  `pct_proficient__dki_grid:cells` (cells), 1367 cells; a trace lead; ask the
  analyst
- `pct_proficient__dki_standards_grid` in `student_assessment_scores_view`:
  `pct_proficient__dki_standards_grid:cells` (cells), 695 cells; a trace lead;
  ask the analyst
- `grade_goal_distance__grid_grade` in `student_assessment_scores_view`:
  `grade_goal_distance__grid_grade:cells` (cells), 39 cells; a trace lead; ask
  the analyst
- `school_goal_distance__lines_all` in `student_assessment_scores_view`:
  `school_goal_distance__lines_all:cells` (cells), 102 cells; a trace lead; ask
  the analyst
- `region_goal_distance__lines_all` in `student_assessment_scores_view`:
  `region_goal_distance__lines_all:cells` (cells), 29 cells; a trace lead; ask
  the analyst
- `count_assessments__standards_over_time` in `student_assessment_scores_view`:
  `count_assessments__standards_over_time:cells` (cells), 661 cells; a trace
  lead; ask the analyst
- `avg_percent_correct__standards_over_time` in
  `student_assessment_scores_view`:
  `avg_percent_correct__standards_over_time:cells` (cells), 372 cells; a trace
  lead; ask the analyst
- `count_students__score_distribution` in `student_assessment_scores_view`:
  `count_students__score_distribution:cells` (cells), 200 cells; a trace lead;
  ask the analyst
- `pct_taken__assessments_over_time` in `student_assessment_scores_view`:
  `pct_taken__assessments_over_time:cells` (cells), 74 cells; a trace lead; ask
  the analyst
- `pct_students_at_level__dki_bars` in `student_assessment_scores_view`:
  `pct_students_at_level__dki_bars:cells` (cells), 791 cells; a trace lead; ask
  the analyst
- `pct_students_at_level__dki_standards_bars` in
  `student_assessment_scores_view`:
  `pct_students_at_level__dki_standards_bars:cells` (cells), 3186 cells; a trace
  lead; ask the analyst
- `grade_goal_distance__grid_grade` in `student_assessment_scores_view`:
  formulas not compared: the grain columns sit on more than one table; 39 cells
  closed by coverage only
- `pct_proficient__dki_grid` in `student_assessment_scores_view`: formulas not
  compared: the grain columns sit on more than one table; 1367 cells closed by
  coverage only
- `pct_proficient__dki_standards_grid` in `student_assessment_scores_view`:
  formulas not compared: the grain columns sit on more than one table; 695 cells
  closed by coverage only
- `pct_students_at_level__dki_bars` in `student_assessment_scores_view`:
  formulas not compared: the grain columns sit on more than one table; 791 cells
  closed by coverage only
- `pct_students_at_level__dki_standards_bars` in
  `student_assessment_scores_view`: formulas not compared: the grain columns sit
  on more than one table; 3186 cells closed by coverage only
- `pct_taken__assessments_over_time` in `student_assessment_scores_view`:
  formulas not compared: the grain columns sit on more than one table; 74 cells
  closed by coverage only
- `region_goal_distance__lines_all` in `student_assessment_scores_view`:
  formulas not compared: the grain columns sit on more than one table; 29 cells
  closed by coverage only
- `school_goal_distance__lines_all` in `student_assessment_scores_view`:
  formulas not compared: the grain columns sit on more than one table; 102 cells
  closed by coverage only
- `pct_taken__assessments_over_time` in `student_assessment_scores_view`: a
  formula difference: the dashboard gets fixed (`fix_dashboard`). Reason: Where
  rows match, the dashboard averages completion across school, subject and
  replacement groups, while Cube pools assessments taken over assigned. Which
  completion rate is the KPI? Owner: Cube is right: completion is pooled taken
  over assigned, not an average of school and subject groups with groups under
  75% hidden. Comment added on the existing Avg. % Completion subtask in Asana.
  Task: https://app.asana.com/0/0/1220348719767537
- `# Students Complete - Assessment ID`, `Administered At`, `C 504 Status`,
  `Cohort`, `Course Teacher Name`, `Dashboard View Filter`,
  `Dibels Most Recent Composite`, `Discipline`, `Exclude Future Assessments`,
  `Grade Level`, `Grade/Subject`, `Head Of School`, `IEP Status`,
  `Is Foundations`, `Is Mastery Int - Custom`, `Is Replacement`, `Lastfirst`,
  `Lep Status`, `Ml Status`, `Module Code`, `Module Type`, `NJ Tutoring`,
  `Region`, `Response Type`, `School`, `School Level`, `School Level (School)`,
  `Schoolid`, `Scope`, `Select Chart Type`, `Standard`, `Standard Domain`,
  `Student Tier`, `Subject Area`, `Subject Area (group)`, `Teacher Name`,
  `Team`, `Term`, `Territory`, `Title`, `View by - O3 Standards`,
  `Week Start Monday`, `Week of`, `dibels_most_recent_composite`,
  `gifted_and_talented`, `head_of_school`, `is_low_25_fl`, `is_sipps`,
  `nj_student_tier`, `state_test_proficiency` on
  `Standards Over Time - Overview`, `Module - Overall - Assessments Over Time`,
  `School - Mastery Grid Grade`, `School - Mastery Lines All`,
  `DKI - Assessment Mastery Grid`, `DKI - Standards Mastery Grid`,
  `Region - Mastery Lines All`, `DKI - Assessment Mastery Bars`,
  `DKI - Standards Mastery Bars`, `Score Distribution - Bar Chart` in
  `student_assessment_scores_view`: sheet filters Cube has no member for: an
  intended difference; later runs stay quiet on it (`deliberate`). Reason: The
  sheet's filter keeps every value, so it changes no number in the compared
  cells.
- `% Completion` on `Module - Overall - Assessments Over Time` in
  `student_assessment_scores_view`: a sheet filter Cube has no member for: the
  dashboard gets fixed (`fix_dashboard`). Reason: The completion sheet hides
  module groups under 75% completion; Cube shows every group. Which completion
  rate is the KPI? Owner: Cube is right: completion is pooled taken over
  assigned, not an average of school and subject groups with groups under 75%
  hidden. Comment added on the existing Avg. % Completion subtask in Asana.
  Task: https://app.asana.com/0/0/1220348719767537
- `grade_goal_distance__grid_grade` in `student_assessment_scores_view`.
  Dashboard: MAX of the workbook's Grade Goal (Differentiated) calc (the raw
  grade_goal plus hard-coded ET, K-2 QA/CRQ, Math CRQ and TP rules) minus
  AVG(is_mastery_int). Cube: The highest grade_goal_differentiated (the dbt goal
  rules) minus pct_proficient.
- `pct_proficient__dki_grid` in `student_assessment_scores_view`. Dashboard:
  AVG(is_mastery_int), 1 when is_mastery is true and 0 when false. Cube:
  Proficient scores over scores carrying a verdict (count_scored).
- `pct_proficient__dki_standards_grid` in `student_assessment_scores_view`.
  Dashboard: AVG(is_mastery_int) over standard rows. Cube: Proficient scores
  over scores carrying a verdict (count_scored), standard rows.
- `pct_students_at_level__dki_bars` in `student_assessment_scores_view`.
  Dashboard: Percent of distinct students in each of 3 levels, grouped from
  fixed band numbers (ES/MS 1-2 Below, 3 Approaching, 4-5 At/Above; HS 1 Below,
  2 Approaching, 3-5 At/Above). Cube: Percent of distinct students at each
  mastery_level, set relative to each band set's mastery band.
- `pct_students_at_level__dki_standards_bars` in
  `student_assessment_scores_view`. Dashboard: Percent of distinct students in
  each of 3 levels on standard rows, grouped from fixed band numbers (ES/MS 1-2
  Below, 3 Approaching, 4-5 At/Above; HS 1 Below, 2 Approaching, 3-5 At/Above).
  Cube: Percent of distinct students at each mastery_level on standard rows, set
  relative to each band set's mastery band.
- `region_goal_distance__lines_all` in `student_assessment_scores_view`.
  Dashboard: MAX of the workbook's Region Goal (Differentiated) calc (the raw
  region_goal plus hard-coded ET, K-2 QA/CRQ, Math CRQ and TP rules) minus
  AVG(is_mastery_int). Cube: The highest region_goal_differentiated (the dbt
  goal rules) minus pct_proficient.
- `school_goal_distance__lines_all` in `student_assessment_scores_view`.
  Dashboard: MAX of the workbook's School Goal (Differentiated) calc (the raw
  school_goal plus hard-coded ET, K-2 QA/CRQ, Math CRQ and TP rules) minus
  AVG(is_mastery_int). Cube: The highest school_goal_differentiated (the dbt
  goal rules) minus pct_proficient.
