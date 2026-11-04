# Assessment Cube — Data-Usage Reference

The field facts for `student_assessment_scores_view` now live in Cube itself:
each member's description, and its `ai_context` where it has one, come back from
the `meta` tool. Read them there. The session protocol and the open decisions
are in `assessment-cube-orchestrator.md`.

This file holds one thing Cube does not carry yet: the performance band sets of
the 2 internal sources, Illuminate and Focus Assessments. #5573 adds band-set
members to Cube and deletes this file.

## Illuminate performance band sets (interim)

`performance_band_label_number` means something only inside the band set its
assessment points at; its Cube description covers how to compare band numbers.
This table describes the band scale for `overall` rows; `standard` and `group`
rows may use a different one.

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
  cuts at 4.7 to 44.9, and practice SAT and ACT sets carry 27 to 55 bands.
- The same cut points do not imply the same mastery band: CIAs for non-AP
  courses share KIPP Performance Levels' cut points and start mastery at band 5,
  not 4.

## Focus Assessments performance band sets (interim)

Focus Assessments (Focus's Apex module, `assessment_type` value `apex`) marks
mastery at the band labeled `Level 3` and above in each set. Each band runs from
its cut point up to the next one. Band numbers do not compare across sets:
`Level 3` is band 3 in a 5-band set and band 6 in an 8-band set.

| Band set                                | Cut points                           | Mastery starts |
| --------------------------------------- | ------------------------------------ | -------------- |
| K-12 Progress Monitors (PETs, MQQ, TPQ) | 0 / 50 / 70 / 80 / 90                | band 3         |
| EOCs                                    | 0 / 50 / 70 / 80 / 90                | band 3         |
| 6-12 FAST (QAs)                         | 0 / 30 / 40 / 50 / 60 / 70 / 80 / 85 | band 6         |
| K-4 FAST (QAs)                          | 0 / 30 / 40 / 50 / 60 / 70 / 80 / 85 | band 6         |

- Cut points are percent correct.
- A Focus Assessments test with no band set has no band and no mastery verdict,
  so it drops out of `pct_proficient`.
