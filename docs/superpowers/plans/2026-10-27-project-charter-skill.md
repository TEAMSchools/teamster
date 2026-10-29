# Project Charter Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `project-charter` skill that turns a stakeholder ask into an intake
brief, a filled Project Management Templates doc, a dated work plan, and an
Asana project, with a review stop after each.

**Architecture:** One skill under `.claude/skills/project-charter/`. `SKILL.md`
carries the size test, the four phases and their stop points. Five reference
files carry the per-phase procedure and the ids. One offline script places
work-plan dates; it is the only code and the only thing with unit tests. Live
tool behavior is verified once per phase on a real ask and recorded in the
reference files.

**Tech Stack:** Markdown skill files; Python 3 stdlib script (`csv`, `datetime`,
`argparse`, `dataclasses`); pytest; Drive, Docs, Sheets, Asana, Tableau, Cube,
GitHub and BigQuery MCP tools at run time.

**Spec:** `docs/superpowers/specs/2026-10-27-project-charter-skill-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-project-charter-skill`.
  Run every command from there; use `git -C <worktree>` for git.
- Always `uv run pytest` and `uv run python`. Offline suite:
  `uv run pytest tests/skills/test_project_charter_schedule.py`.
- Open skill, reference and rule files with Read, never `cat`;
  `.claude/rules/claude-md-editing.md` governs every line added to a skill: name
  the decision the line changes or cut it, no dated proof, no tombstones.
- Before each commit of a `.md` or `.py` file:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.
  Fix lint findings; formatting is the commit hook's.
- Commits carry `Refs #6154` and end with
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- No bare token `env` in any MCP tool string, commit message or issue text.
- Nothing from a transcript, thread or ticket is quoted into a file in the repo,
  a GitHub issue, or a PR. Reference files use invented examples.
- The charter lives in Drive only. No task writes a charter into the repo.
- Date rules, verbatim from the spec: due dates are Fridays; a week is blocked
  when any in-scope region has a closure of 3 or more consecutive weekdays in
  it; blocked weeks are skipped and do not count toward a duration; a single
  closed day does not block; Thanksgiving week is blocked whatever the tab says;
  a Friday closed for any in-scope region moves to Thursday; a date past the
  calendar's last row is marked `unverified: calendar not published`.
- Known ids (the builder verifies each by name; the user confirms every line of
  `ids.md` before any live test): PMO templates folder
  `1nvIQDmEo4YxNkAvpornEMLRPOa2krOfD`; calendar sheet
  `1qITq1ulvAMdI-DdPN2A_85SlzWFdlAmpO606yACVXtM`, tab
  `Important Dates/Federal Holidays`; Asana Data team `2525102809595`; custom
  fields Priority `1128133924564212`, Active `1206198787739164` (option `Active`
  = `1206198787739165`), Domain `858469791639273`.

## Review Focus

1. A closure that straddles a weekend, Thursday through Monday, has 2 weekdays
   in one week and 1 in the next; neither week blocks. Pinned by Task 2
   `test_straddling_closure_blocks_neither_week`.
2. A project start that falls mid-week counts that week as the first working
   week; a start on a Saturday or Sunday counts the following week. Pinned by
   Task 3 `test_start_midweek_counts_that_week` and
   `test_start_on_weekend_counts_next_week`.
3. An `after` that names no row, or names itself, must fail with the row names
   in the message rather than placing a date at the project start. Pinned by
   Task 3 `test_unknown_after_raises`.
4. A region column value other than exactly `Yes` (`yes`, `Y`, blank) must not
   count as a closure; the tab is hand-maintained. Pinned by Task 1
   `test_region_yes_is_case_sensitive`.
5. An override that lands a follower in a blocked week must still skip that week
   for the follower. Pinned by Task 3
   `test_override_shifts_follower_past_blocked_week`.

---

## File structure

```text
.claude/skills/project-charter/
  SKILL.md                      Task 8
  references/
    ids.md                      Task 4
    scheduling.md               Task 4
    intake-brief.md             Task 5
    charter.md                  Task 6
    asana-build.md              Task 7
  scripts/
    schedule_dates.py           Tasks 1-3
tests/skills/
  test_project_charter_schedule.py   Tasks 1-3
```

The spec names `tests/project_charter/`; the repo keeps skill-script tests in
`tests/skills/` with a `_load` helper (`test_model_support_scripts.py`), so the
test goes there. The script is loaded the same way; there is no package.

The script has three layers, each a task: parse the breaks table into closures;
derive blocked weeks and closed days; place rows. The CLI is part of Task 3.

---

### Task 1: Parse the breaks table

**Files:**

- Create: `.claude/skills/project-charter/scripts/schedule_dates.py`
- Create: `tests/skills/test_project_charter_schedule.py`

**Interfaces:**

- Produces:

  ```python
  @dataclass(frozen=True)
  class Closure:
      start: date
      end: date      # inclusive
      name: str

  REGIONS = ("Newark", "Camden", "Miami", "Paterson")

  def parse_breaks(
      rows: Iterable[Mapping[str, str]],
      school_year_start: int,
      regions: Sequence[str],
  ) -> list[Closure]: ...
  ```

  `rows` are `csv.DictReader` rows with the tab's headers: `Month`, `Date`,
  `Day`, `Holiday/Event`, and one column per region. A row is a closure when any
  column in `regions` is exactly `Yes`. `Month` is a month name or abbreviation;
  months July to December take `school_year_start`, January to June take
  `school_year_start + 1`. `Date` is `11` or a range `21 - 1`; a range whose end
  is a smaller day than its start crosses into the next month. A `Date` like
  `Dec 21 - Jan 1` (month names inside the cell) is parsed the same way, the
  cell's months winning over the `Month` column. Rows with an empty `Date` or an
  unparseable one raise `ValueError` naming the row.

- [ ] **Step 1: Write the failing tests**

  Copy the `_load` helper from `tests/skills/test_model_support_scripts.py` with
  `SKILL_SCRIPTS` pointing at `.claude/skills/project-charter/scripts`.

  ```python
  def rows(*r):  # helper: (Month, Date, Newark, Camden, Miami, Paterson)
      return [
          {"Month": m, "Date": d, "Day": "", "Holiday/Event": "x",
           "Newark": n, "Camden": c, "Miami": mi, "Paterson": p}
          for m, d, n, c, mi, p in r
      ]

  def test_single_day_closure():
      [c] = sd.parse_breaks(rows(("November", "11", "Yes", "Yes", "No", "Yes")),
                            2026, ["Newark"])
      assert (c.start, c.end) == (date(2026, 11, 11), date(2026, 11, 11))

  def test_range_within_month():
      [c] = sd.parse_breaks(rows(("November", "25 - 27", "Yes", "Yes", "Yes", "Yes")),
                            2026, sd.REGIONS)
      assert (c.start, c.end) == (date(2026, 11, 25), date(2026, 11, 27))

  def test_range_crossing_year():
      [c] = sd.parse_breaks(rows(("December", "Dec 21 - Jan 1", "Yes", "Yes", "Yes", "Yes")),
                            2026, sd.REGIONS)
      assert (c.start, c.end) == (date(2026, 12, 21), date(2027, 1, 1))

  def test_spring_month_takes_next_year():
      [c] = sd.parse_breaks(rows(("April", "3", "Yes", "No", "No", "No")), 2026, ["Newark"])
      assert c.start == date(2027, 4, 3)

  def test_out_of_scope_region_ignored():
      assert sd.parse_breaks(rows(("November", "11", "No", "Yes", "No", "No")),
                             2026, ["Newark"]) == []

  def test_region_yes_is_case_sensitive():
      assert sd.parse_breaks(rows(("November", "11", "yes", "Y", "", "YES")),
                             2026, sd.REGIONS) == []

  def test_unparseable_date_names_row():
      with pytest.raises(ValueError, match="Holiday/Event=x"):
          sd.parse_breaks(rows(("November", "TBD", "Yes", "No", "No", "No")),
                          2026, ["Newark"])
  ```

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `uv run pytest tests/skills/test_project_charter_schedule.py -v`
  Expected: FAIL, file `schedule_dates.py` not found.

- [ ] **Step 3: Implement `Closure`, `REGIONS` and `parse_breaks` in
      `schedule_dates.py`**

  Module docstring: what the script places and the rule list, pointing at
  `references/scheduling.md` for the tab's shape. Month lookup through
  `calendar.month_name` and `calendar.month_abbr`, case-insensitive.

- [ ] **Step 4: Run the tests to verify they pass**

  Run: `uv run pytest tests/skills/test_project_charter_schedule.py -v`
  Expected: 7 passed.

- [ ] **Step 5: Lint and commit**

  ```bash
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/project-charter/scripts/schedule_dates.py tests/skills/test_project_charter_schedule.py </dev/null
  git add .claude/skills/project-charter/scripts/schedule_dates.py tests/skills/test_project_charter_schedule.py
  git commit -m "feat(claude): parse the network calendar breaks tab into closures"
  ```

---

### Task 2: Blocked weeks and closed days

**Files:**

- Modify: `.claude/skills/project-charter/scripts/schedule_dates.py`
- Modify: `tests/skills/test_project_charter_schedule.py`

**Interfaces:**

- Consumes: `Closure` from Task 1.
- Produces:

  ```python
  def thanksgiving(year: int) -> date: ...   # fourth Thursday of November

  def closed_days(closures: Iterable[Closure]) -> frozenset[date]: ...
  # every weekday inside any closure

  def blocked_weeks(closures: Iterable[Closure], years: Iterable[int]) -> frozenset[date]: ...
  # the Monday of each blocked week: a week with 3+ consecutive weekdays
  # closed by one closure, plus Thanksgiving week for every year in `years`
  ```

- [ ] **Step 1: Write the failing tests**

  ```python
  def test_thanksgiving_2026():
      assert sd.thanksgiving(2026) == date(2026, 11, 26)

  def test_three_day_closure_blocks_week():
      c = sd.Closure(date(2026, 12, 23), date(2026, 12, 25), "x")   # Wed-Fri
      assert date(2026, 12, 21) in sd.blocked_weeks([c], [2026])

  def test_two_day_closure_does_not_block():
      c = sd.Closure(date(2026, 12, 24), date(2026, 12, 25), "x")
      assert sd.blocked_weeks([c], [2026]) == frozenset({date(2026, 11, 23)})

  def test_straddling_closure_blocks_neither_week():
      c = sd.Closure(date(2027, 2, 11), date(2027, 2, 15), "x")   # Thu-Mon
      assert sd.blocked_weeks([c], [2026]) == frozenset({date(2026, 11, 23)})

  def test_thanksgiving_week_blocked_without_a_row():
      assert sd.blocked_weeks([], [2026, 2027]) == frozenset(
          {date(2026, 11, 23), date(2027, 11, 22)}
      )

  def test_closed_days_skip_weekends():
      c = sd.Closure(date(2026, 12, 18), date(2026, 12, 21), "x")   # Fri-Mon
      assert sd.closed_days([c]) == frozenset({date(2026, 12, 18), date(2026, 12, 21)})
  ```

- [ ] **Step 2: Run the tests to verify they fail**

  Run:
  `uv run pytest tests/skills/test_project_charter_schedule.py -v -k "thanksgiving or block or closed"`
  Expected: FAIL, attribute errors.

- [ ] **Step 3: Implement the three functions**

  A week blocks when one closure covers 3 or more weekdays of that Monday to
  Friday; two closures do not add up. The 2-week winter break blocks both weeks
  because each has 5.

- [ ] **Step 4: Run the tests to verify they pass**

  Run: `uv run pytest tests/skills/test_project_charter_schedule.py -v`
  Expected: 13 passed.

- [ ] **Step 5: Lint and commit**

  ```bash
  git add .claude/skills/project-charter/scripts/schedule_dates.py tests/skills/test_project_charter_schedule.py
  git commit -m "feat(claude): derive blocked weeks and closed days from closures"
  ```

---

### Task 3: Place rows and the CLI

**Files:**

- Modify: `.claude/skills/project-charter/scripts/schedule_dates.py`
- Modify: `tests/skills/test_project_charter_schedule.py`

**Interfaces:**

- Consumes: `parse_breaks`, `closed_days`, `blocked_weeks` from Tasks 1-2.
- Produces:

  ```python
  @dataclass(frozen=True)
  class PlanRow:
      workstream: str
      name: str
      kind: str                 # "milestone" or "task"
      duration_weeks: int       # >= 1
      after: str | None = None  # another row's name
      override: date | None = None

  @dataclass(frozen=True)
  class Placed:
      row: PlanRow
      due: date
      rule: str                 # which rule placed the date
      note: str                 # "", "override", or "unverified: calendar not published"

  def place(
      rows: Sequence[PlanRow],
      start: date,
      closures: Iterable[Closure],
      calendar_end: date,
  ) -> list[Placed]: ...

  def read_plan(path: Path) -> list[PlanRow]: ...
  # CSV headers: workstream,name,kind,duration_weeks,after,override

  def main(argv: list[str] | None = None) -> int: ...
  ```

  Placement: a row's first working week is the week of its start, where its
  start is the project start (no `after`) or the Monday after its predecessor's
  due date. A start on a Saturday or Sunday begins the next week. Count
  `duration_weeks` working weeks forward, skipping blocked weeks; due is that
  week's Friday, `rule = "friday"`. If that Friday is a closed day, due is the
  Thursday, `rule = "closed friday -> thursday"`. An `override` replaces the due
  date, `rule = "override"`, `note = "override"`; followers start from it. A due
  date after `calendar_end` gets `note = "unverified: calendar not published"`.
  Rows are placed in dependency order; an `after` naming no row or its own row
  raises `ValueError` listing the row names.

  CLI:

  ```text
  uv run python .claude/skills/project-charter/scripts/schedule_dates.py \
    --breaks breaks.csv --school-year 2026 --regions Newark,Camden \
    --start 2027-01-11 --plan plan.csv [--end 2027-06-18]
  ```

  Prints a markdown table: workstream, name, kind, due, rule, note. With
  `--end`, a final line lists rows due after it (the spec's close-before-end
  check). Exit 2 on a `ValueError`, message on stderr.

- [ ] **Step 1: Write the failing tests**

  Use a fixture `closures` of one 3-day closure Wed 2027-02-17 to Fri 2027-02-19
  for every region, and `calendar_end = date(2027, 6, 18)`.

  ```python
  def test_one_week_row_lands_first_friday(closures):
      [p] = sd.place([sd.PlanRow("a", "m1", "milestone", 1)], date(2027, 1, 11),
                     closures, END)
      assert (p.due, p.rule, p.note) == (date(2027, 1, 15), "friday", "")

  def test_start_midweek_counts_that_week(closures):
      [p] = sd.place([sd.PlanRow("a", "m1", "milestone", 1)], date(2027, 1, 13),
                     closures, END)
      assert p.due == date(2027, 1, 15)

  def test_start_on_weekend_counts_next_week(closures):
      [p] = sd.place([sd.PlanRow("a", "m1", "milestone", 1)], date(2027, 1, 16),
                     closures, END)
      assert p.due == date(2027, 1, 22)

  def test_blocked_week_is_skipped(closures):
      [p] = sd.place([sd.PlanRow("a", "m1", "milestone", 2)], date(2027, 2, 8),
                     closures, END)
      assert p.due == date(2027, 2, 26)   # week of 2/15 skipped

  def test_closed_friday_moves_to_thursday():
      c = [sd.Closure(date(2027, 1, 15), date(2027, 1, 15), "x")]
      [p] = sd.place([sd.PlanRow("a", "m1", "milestone", 1)], date(2027, 1, 11), c, END)
      assert (p.due, p.rule) == (date(2027, 1, 14), "closed friday -> thursday")

  def test_after_starts_monday_after_predecessor(closures):
      out = sd.place([sd.PlanRow("a", "m1", "milestone", 1),
                      sd.PlanRow("b", "t1", "task", 1, after="m1")],
                     date(2027, 1, 11), closures, END)
      assert out[1].due == date(2027, 1, 22)

  def test_parallel_workstreams_start_together(closures):
      out = sd.place([sd.PlanRow("a", "m1", "milestone", 1),
                      sd.PlanRow("b", "m2", "milestone", 1)],
                     date(2027, 1, 11), closures, END)
      assert out[0].due == out[1].due

  def test_override_shifts_follower_past_blocked_week(closures):
      out = sd.place([sd.PlanRow("a", "m1", "milestone", 1, override=date(2027, 2, 12)),
                      sd.PlanRow("a", "t1", "task", 1, after="m1")],
                     date(2027, 1, 11), closures, END)
      assert (out[0].note, out[1].due) == ("override", date(2027, 2, 26))

  def test_past_calendar_is_unverified(closures):
      [p] = sd.place([sd.PlanRow("a", "m1", "milestone", 1)], date(2027, 6, 21),
                     closures, END)
      assert p.note == "unverified: calendar not published"

  def test_unknown_after_raises(closures):
      with pytest.raises(ValueError, match="m1"):
          sd.place([sd.PlanRow("a", "t1", "task", 1, after="nope")],
                   date(2027, 1, 11), closures, END)

  def test_cli_prints_table_and_end_warning(tmp_path, capsys):
      # write breaks.csv with the tab's headers and one Yes row; plan.csv with
      # two rows, one 30 weeks long; run main([...,"--end","2027-06-18"]);
      # assert "| due |" header, both row names, and "after 2027-06-18" in stdout
  ```

- [ ] **Step 2: Run the tests to verify they fail**

  Run:
  `uv run pytest tests/skills/test_project_charter_schedule.py -v -k "place or cli or after or override or unverified"`
  Expected: FAIL, attribute errors.

- [ ] **Step 3: Implement `PlanRow`, `Placed`, `place`, `read_plan`, `main`**

  Dependency order: repeat passes over unplaced rows whose `after` is placed or
  empty; a pass that places nothing with rows left means a cycle, raise. `main`
  builds `closures` with `parse_breaks(csv.DictReader(...))`, `calendar_end` as
  the latest `Closure.end`, and prints with no third-party table library.

- [ ] **Step 4: Run the whole file**

  Run: `uv run pytest tests/skills/test_project_charter_schedule.py -v`
  Expected: 24 passed.

- [ ] **Step 5: Run the CLI by hand on the real tab**

  Export the `Important Dates/Federal Holidays` tab to CSV in the session
  scratchpad (Sheets `get_values` on the tab's range, one call), write a 3-row
  plan, run the command above with `--regions Newark,Camden,Miami,Paterson`.
  Expected: every due date is a Friday or a Thursday after a closed Friday; the
  week of 2026-11-23 and the winter break weeks appear in no due date. Keep the
  CSV: Task 4 describes its shape from it.

- [ ] **Step 6: Lint and commit**

  ```bash
  git add .claude/skills/project-charter/scripts/schedule_dates.py tests/skills/test_project_charter_schedule.py
  git commit -m "feat(claude): place work plan dates and add the schedule_dates CLI"
  ```

---

### Task 4: `ids.md` and `scheduling.md`

**Files:**

- Create: `.claude/skills/project-charter/references/ids.md`
- Create: `.claude/skills/project-charter/references/scheduling.md`

**Interfaces:**

- Consumes: the CLI from Task 3; the CSV from Task 3 step 5.
- Produces: `ids.md`, the only file in the skill with an id in it, read by every
  phase; `scheduling.md`, read by phase 3.

- [ ] **Step 1: Look up every id by name**

  Drive `search_files` in folder `1nvIQDmEo4YxNkAvpornEMLRPOa2krOfD` for the
  "Project Management Templates" doc and the "Project Management Handbook" doc;
  record each id and exact title. Asana `get_project` on `1213735218595734` to
  confirm the team gid and the three custom field gids and the `Active` option
  gid listed in Global Constraints.

- [ ] **Step 2: Write `ids.md`**

  One table: name, id, where it is used (phase), how to re-find it (the Drive
  folder or Asana project to search by name). Rows: templates doc, handbook doc,
  PMO folder, calendar sheet, calendar tab name, Asana project template (value
  `UNSET`, with the one-paragraph procedure the user follows to make it by hand:
  a Data team project with the three custom fields and the sections
  `0 · Governance` and `Parking lot and outside the core set`, saved as a
  template), Data team, Priority, Active and its option, Domain. Under the
  table, the calendar rollover rule: when the sheet title's school year is not
  the current one, ask the user for the new link and replace the row. No dated
  "verified" notes.

- [ ] **Step 3: Write `scheduling.md`**

  Sections: the tab's shape (headers, the `Date` cell forms seen in the real
  export: single day, `25 - 27`, `Dec 21 - Jan 1`), how to read it (one Sheets
  `get_values` call on the whole tab, written to the session scratchpad as CSV
  with the headers unchanged, spaced from any other Sheets call), the plan CSV
  headers and the `after` convention, the command line, how to read the `rule`
  and `note` columns, how an override is entered (the `override` column, and
  that the note travels into the work plan's note column), and what to do with
  `unverified` rows. Then the write-back: the placed rows go into the doc's
  Template 2 table (milestone or task, owner, due date, status), the plan CSV
  goes in as a `Schedule inputs` table after it, and the Template 1 milestone
  table gets the exact dates. The date rules themselves are stated once, in the
  script's docstring; this file points at it.

- [ ] **Step 4: Have the user confirm `ids.md`**

  Show the table and stop. Every row needs a yes before any live test in later
  tasks. Record the Asana template gid when the user has made it.

- [ ] **Step 5: Lint and commit**

  ```bash
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/project-charter/references/ids.md .claude/skills/project-charter/references/scheduling.md </dev/null
  git add .claude/skills/project-charter/references/
  git commit -m "docs(claude): add project-charter ids and scheduling references"
  ```

---

### Task 5: `intake-brief.md`

**Files:**

- Create: `.claude/skills/project-charter/references/intake-brief.md`

**Interfaces:**

- Consumes: `.claude/skills/model-support/references/intake-and-inventory.md`
  sections "Find the consumers" and "Propose the boundary" (pointed at, not
  copied); the `zendesk-tickets` skill.
- Produces: the phase 1 procedure and the brief format that phase 2 reads.

- [ ] **Step 1: Write the source-tool table**

  One row per material type: transcript (Granola `search_meetings` then
  `get_meetings`; Wispr Flow `search_meetings` then `get_meeting`), email
  (Microsoft 365 `outlook_email_search`; Gmail when connected), Slack thread
  (`slack_read_thread` from a permalink), Drive doc or mockup
  (`read_file_content`; a Sheet through Sheets `get_values`), Zendesk ticket
  (invoke `zendesk-tickets`), pasted text, scratchpad file. Each row: the tool,
  what to pass, and the one thing to pull from it. Verify each tool name exists
  with ToolSearch before writing the row.

- [ ] **Step 2: Write the extraction prompt and the inventory order**

  Extraction: the five questions from the spec, answered in the stakeholder's
  terms, each line tagged `heard`. Inventory: the five numbered steps from the
  spec with the exact tool and query shape per step, each result line tagged
  `found` with the asset and how it was found; GitHub and Asana results marked
  leads. Support history: a BigQuery query shape against
  `kipptaf_marts.fct_support_tickets` grouped by category, themes only.

- [ ] **Step 3: Write the brief format**

  The five sections and the one-line size call; the sources list at the top with
  title and date; the PII rule (staff by name and title, nothing about a student
  or family, source material never quoted); where the brief is saved (session
  scratchpad) and the Google Doc offer, made once and not acted on unasked.

- [ ] **Step 4: Live check**

  Run phase 1 on the real ask the user supplies, from the reference alone. Fix
  any tool name or argument the run disproves. The brief stays in the
  scratchpad.

- [ ] **Step 5: Lint and commit**

  ```bash
  git add .claude/skills/project-charter/references/intake-brief.md
  git commit -m "docs(claude): add the project-charter intake reference"
  ```

---

### Task 6: `charter.md`

**Files:**

- Create: `.claude/skills/project-charter/references/charter.md`

**Interfaces:**

- Consumes: `ids.md` (templates doc, handbook, PMO folder); the brief format
  from Task 5.
- Produces: the phase 2 procedure; the doc's section names that Tasks 7 and 8
  refer to (`Template 1` to `Template 4`, the `Schedule inputs` table, the RAPID
  row `changes after signing`).

- [ ] **Step 1: Read the templates doc and handbook once**

  Docs `read_doc` on each (large results spill to a file; read with `jq` per the
  hooks CLAUDE.md). Record the exact heading text of Templates 1 to 6 and of
  handbook Parts II and IV, and the six Part IV failure-mode names.

- [ ] **Step 2: Write the copy-and-fill procedure**

  Drive `copy_file` into the project folder, name
  `<Project> - Charter and Plan`; load `anthropic-skills:google-workspace`
  before the first write; which Docs `update_doc` operation fills a table row
  versus a paragraph (verify in step 4). Fill order: Template 1 (charter,
  stakeholder map, MOCHA, RAPID log with the standing row
  `changes after signing` and its default text: Owner for dates, Manager for
  scope and MOCHA, any member for their own Asana tasks), Template 3, Template
  4; Templates 5 and 6 left blank. Names resolve to name and title only.

- [ ] **Step 3: Write the marking and check rules**

  `[proposed]` prefix on every sentence not tagged `heard` or `found` in the
  brief; cleared by the user on approval. The six Part IV checks, one line each:
  the failure mode, what in the draft fails it, the fix. The review message
  order: findings, doc link, the `[proposed]` list.

- [ ] **Step 4: Live check**

  Run phase 2 on the Task 5 brief into a test folder the user names. Verify the
  copy, the table writes and the `[proposed]` marks render. Fix the reference
  where a tool behaves differently.

- [ ] **Step 5: Lint and commit**

  ```bash
  git add .claude/skills/project-charter/references/charter.md
  git commit -m "docs(claude): add the project-charter charter reference"
  ```

---

### Task 7: `asana-build.md`

**Files:**

- Create: `.claude/skills/project-charter/references/asana-build.md`

**Interfaces:**

- Consumes: `ids.md` (template gid, team, custom fields); the work plan rows
  from phase 3 (`Placed` table written into the doc);
  `.claude/context/claude_ai_Asana.md`.
- Produces: the phase 4 procedure.

- [ ] **Step 1: Write the build order**

  The five spec steps with exact tool and argument shape:
  `create_project_from_template` (template gid, team gid, name, private),
  section creation per workstream `N · <workstream>`, member resolution by
  `search_objects` with `resource_type: user` (confirm each match in the review
  message; no roster emails), milestone tasks with
  `resource_subtype: milestone`, tasks with `parent` set to their milestone,
  `#NNNN | title` for tasks that are GitHub issues, Domain and Active values,
  the charter link into the project description.

- [ ] **Step 2: Write the consent block**

  Before `create_tasks`: show the full task list, ask for a yes, restate the
  consent in plain text in the same turn. `html_notes` tag allowlist pointer to
  the Asana context file. The count check at the end: sections, milestones and
  tasks created versus the work plan.

- [ ] **Step 3: Live check**

  With the user's Asana template gid in `ids.md`, run phase 4 from the Task 6
  doc into a project named `TEST · <name>`. Resolve the builder question (parent
  in `create_tasks` or a second `update_tasks` pass) against the real tool and
  write the answer into the reference. The user archives the project by hand.

- [ ] **Step 4: Lint and commit**

  ```bash
  git add .claude/skills/project-charter/references/asana-build.md
  git commit -m "docs(claude): add the project-charter Asana build reference"
  ```

---

### Task 8: `SKILL.md`, fresh-session run, PR

**Files:**

- Create: `.claude/skills/project-charter/SKILL.md`

**Interfaces:**

- Consumes: every reference file; the CLI.
- Produces: the skill.

- [ ] **Step 1: Write `SKILL.md`**

  Frontmatter `name: project-charter` and the description from the spec's
  trigger list, phrased like `zendesk-tickets`: the ask forms it triggers on and
  the single-task case it does not. Body, in order: the size test paragraph
  (phase 0); non-negotiables (PII rule, no quoting source material into git or
  GitHub, `ids.md` confirmed before any write, every phase ends with its output
  shown and a stop, `env` token rule); the four phases, each as the
  precondition, the reference file to read, the stop and what the user must say
  to continue; starting mid-way (ask for the doc link). Under 120 lines;
  procedure lives in the references.

- [ ] **Step 2: Lint the skill folder**

  ```bash
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/project-charter </dev/null
  ```

  Expected: no findings beyond formatting.

- [ ] **Step 3: Commit**

  ```bash
  git add .claude/skills/project-charter/SKILL.md
  git commit -m "feat(claude): add the project-charter skill"
  ```

- [ ] **Step 4: Fresh-session run**

  The user starts a new session, invokes the skill on the same real ask, and
  runs all four phases with a `TEST ·` Asana project. Fix what the run finds,
  one commit per fix, and the user archives the project.

- [ ] **Step 5: Open the PR**

  Push the branch; `mcp__github__create_pull_request` as a draft with the body
  from `.github/pull_request_template.md`, `Closes #6154`, no source-material
  text, ending with the generated-with line. Then invoke `pr-ci-review`.
