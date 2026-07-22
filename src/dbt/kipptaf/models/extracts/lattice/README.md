# Lattice User Extract — Who's Included

This feed (`rpt_lattice__users`) decides which employees get a Lattice account.
It draws from the staff roster (`int_people__staff_roster`) and applies the
rules below. **An employee must clear _every_ gate to be included.**

Keep this doc in sync with the model whenever the criteria change.

## High level summary

- **KTAF central and Paterson include everyone** — no role filter.
- **Newark and Camden are treated identically** — the same operations-title list
  and the same two departments apply to both. They are the only regions with
  role or department restrictions of that kind.
- **Miami is the exception** — it is gated on a title keyword match plus one
  hardcoded location ("Room 11"), rather than an explicit title or department
  list.
- **Part-timers and temporary workers are excluded** - part-timers are excluded
  on ADP worker type; temps are excluded by job title. We intentionally do not
  exclude on the "Temporary" worker type right now, because full-time-temporary
  might be mislabels in ADP — so a temp is dropped only if their title says so.

## Current inclusion criteria

Included = a current (or just-departed) employee, in an eligible business unit,
who is **not** an intern, a temp, or a part-timer.

### 1. Not an intern, part-timer, or title-flagged temp

- Their job title is not "Intern."
- Their worker type is not a "Part Time" classification.
- Anyone whose **job title** contains "Temporary," "Part Time," or "Part-Time"
  is excluded — this catches temps regardless of their worker type.
- **Full-time temporary staff are currently kept**, pending a review of their
  ADP records — that worker type might be a mislabel, so we don't auto-remove
  them.
- Employees with a **blank worker type are kept** — in practice these are
  legitimate full-time staff, so we don't drop them.

### 2. They belong to an eligible group

Any one of these qualifies:

- **KTAF central (KIPP TEAM and Family Schools Inc.)** — everyone.
- **KIPP Paterson** — everyone.
- **KIPP Miami** — only school/team leaders: job title contains "Director,"
  "Head," "Leader," or "Dean," **or** their work location is "Room 11."
- **Newark (TEAM Academy Charter School) or Camden (KIPP Cooper Norcross
  Academy)** — only these operations roles:
  - Director School Operations
  - Director Campus Operations
  - Managing Director of School Operations
  - Managing Director of Operations
- **Newark or Camden** — anyone in the **Technology** or **Marketing, Comms, and
  Enrollment** department.

### 3. Currently employed, or very recently departed

Either one:

- Their assignment status is "Active" or "Leave," **or**
- They were terminated within the last 30 days.

## Lattice Fields Extract - What's Included

The file is a CSV; each column header is the field name Lattice reads.

- `external_user_id` — ADP employee number (the Lattice user ID)
- `status` — Active or Inactive
- `work_email`, `manager_email`
- `first_name`, `last_name`
- `job_title`, `department`, `location`, `business_unit`
- `start_date`
- `gender` — self-reported gender identity from ADP
- `ethnicity` — race/ethnicity reporting category from ADP
- `birthdate` — employee date of birth from ADP

**Gender and ethnicity** are sent verbatim from ADP, so the field options set up
in Lattice must match the source values exactly (e.g.
"Latinx/Hispanic/Chicana(o)", "Cis Woman"). A value can be blank when the
employee has none recorded.
