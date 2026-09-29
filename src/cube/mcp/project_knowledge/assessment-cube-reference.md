# Assessment Cube — Data-Usage Reference

The field facts for `student_assessment_scores_view` now live in Cube itself:
each member's description, and its `ai_context` where it has one, come back from
the `meta` tool. Read them there. The session protocol and the open decisions
are in `assessment-cube-orchestrator.md`.

This file holds one thing Cube does not carry yet: the Illuminate performance
band sets. #5573 adds band-set members to Cube and deletes this file.

## Illuminate performance band sets (interim)

`performance_band_label_number` means something only inside the band set its
assessment points at. Band sets differ in cut points, in band count, and in
which band starts mastery, so never compare or pool band numbers across
assessments. This table describes the band scale for `overall` rows; `standard`
and `group` rows may use a different one.

The most-used configurations:

| Band set                                                 | Cut points                 | Mastery starts |
| -------------------------------------------------------- | -------------------------- | -------------- |
| KIPP Performance Levels (every year and "Imported" copy) | 0 / 21 / 41 / 61 / 81      | band 4         |
| District Default                                         | 0 / 60 / 70 / 80 / 90      | band 4         |
| SY26-27 KIPP Math Performance Levels                     | 0 / 30 / 50 / 60 / 70 / 80 | band 5         |
| KIPP T&F 2021-22 MS PB                                   | 0 / 25 / 45 / 65 / 85      | band 4         |
| HS Summative Assessment (non-AP), and its KIPP NJ copy   | 0 / 40 / 60 / 75 / 88      | band 3         |
| KIPP T&F 2021-22 ES PB                                   | 0 / 30 / 50 / 70 / 85      | band 4         |
| KIPP T&F 2026-27 K-2 PB                                  | 0 / 50 / 65 / 80 / 90      | band 4         |
| CKLA (80%+ Mastery)                                      | 0 / 20 / 40 / 60 / 80      | band 5         |
| CIAs for non-AP Courses                                  | 0 / 21 / 41 / 61 / 81      | band 5         |
| FAST Performance Bands 3-4                               | 8 bands, 0 / 55 / 60 … 85  | band 6         |
| AP4A/CCRS General                                        | 0 / 21 / 41 / 61 / 81      | every band     |

- Cut points are percent correct for most sets, but not all: a CKLA fluency set
  cuts at 4.7 to 44.9, and practice SAT and ACT sets carry 27 to 53 bands.
- The same cut points do not imply the same mastery band: CIAs for non-AP
  courses share KIPP Performance Levels' cut points and start mastery at band 5,
  not 4.
- An Illuminate `pct_proficient` therefore mixes different bars. Say which
  assessments a rate covers.
