# Lattice Extract

This feed (`rpt_lattice__users`) decides which employees get a Lattice account.
It draws from the staff roster (`int_people__staff_roster`) and applies the
rules below. **An employee must clear _every_ gate to be included.**

Keep this doc in sync with the model whenever the criteria change.

## Lattice User Extract — Who's Included

### High level summary

- **KTAF central and Paterson include everyone** — no role filter.
- **Newark and Camden are treated identically** — operations leaders and two
  departments (**Technology** or **Marketing, Comms, and Enrollment**) included.
- **Miami includes additional leader roles** — gated on a title keyword match
  plus one hardcoded location ("Room 11"), rather than an explicit title or
  department list.
- **Part-time permanent and temporary workers are excluded; full-time temporary
  staff are included.**

### Current inclusion criteria

Included = a current (or just-departed) employee, in an eligible business unit,
who is **not** an intern, a temp, or a part-timer.

#### 1. Not an intern, part-timer, or title-flagged temp

- Their job title is not "Intern."
- Their worker type is not a "Part Time" classification.
- Anyone whose **job title** contains "Temporary," "Part Time," or "Part-Time"
  is excluded — this catches temps regardless of their worker type.
- **Full-time temporary staff are included** — Managers confirmed they should be
  included, so the "Temporary" worker type is not used to exclude (the job title
  exclusion above still applies as a backstop).
- Employees with a **blank worker type are kept** — in practice these are
  legitimate full-time staff, so we don't drop them.

#### 2. They belong to an eligible group

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

#### 3. Currently employed, or very recently departed

Either one:

- Their assignment status is "Active" or "Leave," **or**
- They were terminated within the last 30 days. This is to deactivate terminated
  users in Lattice, after 30 days they are dropped from the extract entirely.

## Lattice Fields Extract - What's Included

The file is a CSV; each column header is the field name Lattice reads. **Gender
and ethnicity** are sent verbatim from ADP, so the field options set up in
Lattice must match the source values exactly (e.g. "Latinx/Hispanic/Chicana(o)",
"Cis Woman"). A value can be blank when the employee has none recorded.

- `external_user_id` — ADP employee number (the Lattice user ID)
- `status` — Active or Inactive
- `work_email`
- `manager_email`
- `first_name`
- `last_name`
- `job_title`
- `department`
- `location`
- `business_unit`
- `start_date`
- `gender` — self-reported gender identity from ADP, only visible to admins
- `ethnicity` — race/ethnicity reporting category from ADP, only visible to
  admins
- `birthdate` — employee date of birth from ADP, only visible to admins

Not included:

- `tenure` - is a calculated field in Lattice
- `pronouns` - not currently collected from staff, incomplete in ADP
