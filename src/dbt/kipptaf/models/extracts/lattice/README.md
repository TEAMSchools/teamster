# Lattice User Extract — Who's Included

This feed (`rpt_lattice__users`) decides which KTAF employees get a Lattice
account. It draws from the staff roster (`int_people__staff_roster`) and applies
the rules below. **An employee must clear _every_ gate to be included.**

Keep this doc in sync with the model whenever the criteria change.

## The short version

Included = a current (or just-departed) employee, in an eligible business unit,
who is **not** an intern, a temp, or a part-timer.

## The gates in plain language

### 1. Not an intern, temp, or part-timer

- Their job title is not "Intern."
- Their worker type is not a "Temporary" or "Part Time" classification.
- As a backstop for mislabeling, anyone whose **job title** contains
  "Temporary," "Part Time," or "Part-Time" is also excluded.
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

## Things worth remembering

- **Newark and Camden are treated identically** — the same operations-title list
  and the same two departments apply to both. They are the only regions with
  role or department restrictions of that kind.
- **Miami is the exception** — it is gated on a title keyword match plus one
  hardcoded location ("Room 11"), rather than an explicit title or department
  list.
- **KTAF central and Paterson are wide open** — no role filter, so those two
  always contribute the most people.
- **Worker type is the primary signal for temps and part-timers**, not job
  title. Most part-timers and temps have ordinary titles (Teacher, Counselor,
  Registered Nurse, Office Manager), so the title check alone would miss them —
  it is only a safety net.
