# Zendesk Partition Labeling Guide

Working guide for the two hand-labeling passes in the opening week of
[#4739](https://github.com/TEAMSchools/teamster/issues/4739). This is the rubric
of record — the base rate it produces is measured against a kill criterion that
was fixed in advance, so the rubric must not move once labeling starts.

Worksheets live in `.claude/scratch/zendesk/`. They contain student and staff
names. Do not copy rows into Slack, email, Asana, or any document outside that
folder. Counts and rates are fine to share; ticket text is not.

Every worksheet has a `url` column linking straight to the ticket in Zendesk.
The excerpt columns are truncated, so when a row is ambiguous, open the ticket
and read the real thread before deciding. That is faster and more reliable than
guessing from a 400-character excerpt.

## Why this exists

The Data team answers about 2,300 Zendesk tickets a year. The obvious response
is to write better canned replies. Before doing that, we want to know how many
of these tickets should never have been filed — because the platform the team
itself builds caused them. A ticket caused by our own design decision is a bug
report, not a support request, and writing a faster reply to it makes the
underlying problem cheaper to ignore.

So we sort tickets into "we caused this" and "this is real demand," and only the
second group gets the canned-reply treatment.

## Pass 1 — seasonality (about half a day)

**File:** `seasonality_worksheet.tsv` — 120 rows.

The probe found five week-of-year slots where ticket volume spiked in both
school years. Four of the five are DeansList in the weeks right around the first
day of school. The question is whether those tickets are _the same request_
recurring, or just unrelated problems that happen to cluster when school starts.

Fill the `same_ask_group` column:

- Read the `subject` of the rows in one `category` + `week_offset` group.
- Give a short lowercase label to each cluster of subjects that are asking for
  the same thing — `roster_missing_students`, `new_staff_cant_log_in`,
  `attendance_codes_wrong`. Invent labels as you go; consistency matters more
  than the wording.
- Leave the cell **blank** when a row does not resemble any other row in its
  group. Blanks are a real finding, not a failure.
- Use the same label across both academic years when the ask matches. That
  cross-year match is the entire point of the exercise.

**What we're looking for:** any single group with 10 or more rows sharing a
label in _both_ 2024 and 2025.

## Pass 2 — the partition (rest of the week)

**File:** `partition_sample_uncategorized.tsv` — 350 rows.

Every row is a ticket nobody categorized. Read `subject`, `request_excerpt`, and
`reply_excerpt`, then fill three columns.

### The `label` column

Exactly one of:

| Label                  | Meaning                                                                                                     |
| ---------------------- | ----------------------------------------------------------------------------------------------------------- |
| `self_inflicted`       | Something the Data team built, configured, or owns caused this ticket, and the team could stop it recurring |
| `genuine`              | A real request. A new question, a one-off analysis, or something only a human could answer                  |
| `vendor_or_user_error` | Caused outside the team — a vendor outage, or someone typing the wrong thing into a source system           |

### The two mandatory fields

**`self_inflicted` requires both `artifact_name` and `one_line_fix`.** A row
with a `self_inflicted` label and either field empty gets changed to `genuine`
before counting. This is not bureaucracy — it is the only thing keeping the
label honest. Without it, every ticket becomes "well, we should have built
something better," the bucket swallows everything, and the exercise proves
nothing.

- `artifact_name` — the specific thing that would be fixed. A dashboard name, a
  dbt model, a Tableau view, a Cube view, an integration, a permission group.
  "The DeansList sync" counts. "DeansList" does not; that is a whole vendor.
- `one_line_fix` — what someone would actually do. "Grant this view by role from
  the staff roster instead of per request." "Rename the measure so it stops
  reading as year-to-date."

### Worked examples

Paraphrased from real tickets, identifiers removed.

| Reply reads roughly                                                                                                  | Label                  | Why                                                                                                                                      |
| -------------------------------------------------------------------------------------------------------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| "You should now have access to all Google Classrooms at that school."                                                | `self_inflicted`       | A permission granted by hand. Artifact: the Classroom access group. Fix: derive access from the staff roster. Nobody should have to ask. |
| "That was a Clever outage that affected a number of districts."                                                      | `vendor_or_user_error` | Outside our control. Nothing to build.                                                                                                   |
| "Both of those students were originally enrolled at another school and transferred, so they show under the old one." | `genuine`              | A real question about how enrollment history works, answered by explaining it.                                                           |
| "Final ADA for that school is 93.08%."                                                                               | `genuine`              | A data pull. Someone wanted a number and got it.                                                                                         |
| "You're right, that dashboard was still showing last year's term. Fixed now."                                        | `self_inflicted`       | We shipped a stale default. Artifact: the dashboard. Fix: drive the term filter off the current academic year.                           |
| "We don't have capacity to support that right now."                                                                  | `genuine`              | A demand-versus-capacity answer, not a defect.                                                                                           |

### Misrouted mail

A small number of rows (roughly 3%) are not support tickets at all — vendor
invoices, statements of account, and sales outreach that landed in the Data
queue by accident. Label those `vendor_or_user_error` and move on. They are not
a defect and they are not demand; there are too few to matter to the result.

### When you are unsure

**Default to `genuine`.** We would much rather understate the self-inflicted
rate than overstate it. An inflated number would send the team off rebuilding
things that were fine, and it would read to them as blame rather than diagnosis.
If you find yourself constructing an argument for why something is our fault,
that is the signal to mark it `genuine` and move on.

Flag genuinely hard rows by putting `?` at the start of `one_line_fix` and keep
going. Do not spend more than about two minutes on any single row.

### Handoff

Deciding whether an artifact is something the Data team owns takes platform
knowledge you are not expected to have. So:

1. You do the full pass — label everything, fill `artifact_name` and
   `one_line_fix` wherever you propose `self_inflicted`.
2. Anthony reviews only the `self_inflicted` rows and the `?` rows, and confirms
   or demotes each one.
3. The confirmed count is what gets measured.

That split keeps the volume achievable inside the week while keeping the number
trustworthy.

## What happens with the result

The share of the 350 rows confirmed `self_inflicted` is compared against a 20%
threshold set before any labeling began.

- **20% or above** — the queue is substantially a defect backlog. The project
  pivots to fixing artifacts, and the confirmed `artifact_name` values become
  the starting backlog.
- **Below 20%** — the thesis was wrong, we say so plainly, and the project
  continues as originally planned with reply clustering across the whole corpus.

Both outcomes are useful. Nobody is trying to hit the number.
