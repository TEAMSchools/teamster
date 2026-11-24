# Service Playbook Skill and Capacity Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `service-playbook` skill that writes a recurring workstream's
playbook as a Google Doc with computed monthly hours, plus a shared capacity
board where workstream cards are dragged onto analysts and totaled against
capacity.

**Architecture:** One small Python script computes step weeks and monthly hours,
reusing `project-charter`'s closure and blocked-week functions by import. The
skill's references tell Claude how to read Asana and the PM calendar, fill the
doc, and write the card. The board is a single HTML page published as a
claude.ai artifact with a shared database; its source lives in the skill folder.

**Tech Stack:** Python 3 (stdlib only), pytest, Claude Code skill Markdown,
claude.ai Artifact (HTML, `db` and `user` capabilities), Google Drive and Sheets
APIs, Asana MCP.

**Spec:** `docs/superpowers/specs/2026-11-24-service-playbook-skill-design.md`

**Worktree:**
`/workspaces/teamster/.claude/worktrees/cristinabaldor/feat/claude-service-playbook`
(branch `cristinabaldor/feat/claude-service-playbook`, issue #6497). Every
command runs with `git -C <worktree>` or from `cd <worktree>`; never the main
checkout path.

## Global Constraints

- Surveys only in v1; other workstreams appear on the board as hand-entered
  cards.
- Effort unit: `duration_weeks` plus `hours_per_week` per step; monthly hours
  run July to June, 12 values.
- Every value not from the user, Asana or the calendar starts with `[proposed]`;
  the skill never clears a marker.
- No student data anywhere; staff names only as owner, backup, analysts. Failure
  modes state the failure, never the person.
- Reuse `.claude/skills/project-charter/references/ids.md` for the calendar
  sheet; do not edit anything under `.claude/skills/project-charter/`.
- Network-wide workstream: a week is blocked only when all four regions
  (`Newark`, `Camden`, `Miami`, `Paterson`) block it.
- Board data: collections `workstreams`, `analysts`, `assignments` with the
  fields in the spec's _Data_ section; the skill never writes `assignments`.
- Lint every Markdown file with
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from the worktree; formatting is the commit hook's.
- Tests: `uv run pytest tests/skills/test_service_playbook_capacity.py`, never
  bare `uv run pytest`.

## Review Focus

1. A step whose offset lands outside the school year (before July 1 or after
   June 30): expect a `ValueError` naming the step and the round, not hours
   silently dropped. Test in Task 1.
2. A window `open_week` given as a mid-week date: expect it normalized to its
   Monday. Test in Task 1.
3. A step's `rounds` naming a round with no window: expect a `ValueError` naming
   the round. Test in Task 1.
4. A week where only Miami is on break, for a network workstream: expect it not
   blocked, so hours stay in that week. Test in Task 1.
5. On the board, an analyst whose capacity is 0 or unset: expect the total shown
   with no percentage and no division error; and a card whose hours change while
   assigned keeps its analyst. Checked in Task 3.

---

### Task 1: Week placement and monthly hours script

**Files:**

- Create: `.claude/skills/service-playbook/scripts/capacity.py`
- Test: `tests/skills/test_service_playbook_capacity.py`

**Interfaces:**

- Consumes: from `.claude/skills/project-charter/scripts/schedule_dates.py`
  (loaded by file path, as `tests/skills/test_project_charter_schedule.py`
  does): `REGIONS`, `Closure`, `parse_breaks(rows, school_year_start, regions)`,
  `blocked_weeks(closures, years) -> frozenset[date]`.
- Produces, in `capacity.py`:
  - `@dataclass(frozen=True) class Window: round_key: str; open_week: date; close_week: date`
    (both normalized to Mondays in `__post_init__`)
  - `@dataclass(frozen=True) class Step: name: str; anchor: Literal["open", "close"]; offset_weeks: int; duration_weeks: int; hours_per_week: float; role: str; rounds: tuple[str, ...] | None = None`
  - `@dataclass(frozen=True) class Standing: name: str; hours_per_week: float; weeks: Literal["school_year", "all"]`
  - `network_blocked(closures: Iterable[Closure], years: Iterable[int]) -> frozenset[date]`
    — the intersection over `REGIONS` of `blocked_weeks` run on each region's
    closures (a closure with empty `regions` counts for every region).
  - `step_weeks(step: Step, window: Window, blocked: frozenset[date]) -> list[date]`
    — Mondays the step occupies.
  - `monthly_hours(steps, windows, standing, blocked, school_year_start: int, first_week: date, last_week: date) -> list[float]`
    — 12 values, July first; a week counts in the month of its Monday.
  - CLI:
    `capacity.py --spec <playbook.json> --breaks <breaks.csv> --school-year <YYYY> --first-week <date> --last-week <date>`
    printing JSON
    `{"steps": [{"round": str, "step": str, "weeks": [iso dates]}], "hours_by_month": [12 floats], "hours_per_year": float}`.
    `playbook.json` keys: `windows` (list of
    `{round_key, open_week, close_week}`), `steps` (list of Step fields),
    `standing` (list of Standing fields).

Placement rule for `step_weeks`: start at the anchor week (`open_week` or
`close_week`). Offset 0 is the anchor week even when it is blocked (window weeks
are never moved). A nonzero offset moves that many unblocked weeks forward or
back, skipping blocked weeks without counting them. The week reached is the
step's first week; each further week, up to `duration_weeks`, is the next
unblocked week after the one before. `first_week` and `last_week` bound
`standing` weeks with `weeks: school_year`; `all` means every Monday from July 1
of `school_year_start` to June 30 of the next year.

- [ ] **Step 1: Write the failing tests**

```python
def test_network_blocked_ignores_one_region_break():
    # Miami-only spring break Mar 22-26 2027; all-region winter break Dec 21-25 2026
    closures = [
        cap.sd.Closure(date(2027, 3, 22), date(2027, 3, 26), "Spring", frozenset({"Miami"})),
        cap.sd.Closure(date(2026, 12, 21), date(2026, 12, 25), "Winter", frozenset(cap.sd.REGIONS)),
    ]
    blocked = cap.network_blocked(closures, [2026])
    assert date(2027, 3, 22) not in blocked
    assert date(2026, 12, 21) in blocked
    assert date(2026, 11, 23) in blocked  # Thanksgiving week, from blocked_weeks

def test_window_normalizes_to_monday():
    w = cap.Window("r2", date(2026, 12, 2), date(2026, 12, 11))
    assert (w.open_week, w.close_week) == (date(2026, 11, 30), date(2026, 12, 7))

def test_negative_offset_skips_thanksgiving():
    w = cap.Window("r2", date(2026, 11, 30), date(2026, 12, 7))
    s = cap.Step("Dashboard refresh", "open", -1, 1, 2.0, "owner")
    assert cap.step_weeks(s, w, frozenset({date(2026, 11, 23)})) == [date(2026, 11, 16)]

def test_offset_zero_stays_in_blocked_anchor_week():
    w = cap.Window("r3", date(2026, 12, 21), date(2027, 1, 11))
    s = cap.Step("Reminders on", "open", 0, 1, 1.0, "owner")
    assert cap.step_weeks(s, w, frozenset({date(2026, 12, 21)})) == [date(2026, 12, 21)]

def test_duration_skips_blocked_weeks():
    w = cap.Window("r3", date(2026, 12, 14), date(2027, 1, 11))
    s = cap.Step("Monitor", "open", 0, 3, 0.5, "owner")
    blocked = frozenset({date(2026, 12, 21), date(2026, 12, 28)})
    assert cap.step_weeks(s, w, blocked) == [date(2026, 12, 14), date(2027, 1, 4), date(2027, 1, 11)]

def test_monthly_hours_by_monday_month_and_rounds_filter():
    windows = [cap.Window("r1", date(2026, 10, 19), date(2026, 11, 2)),
               cap.Window("r2", date(2026, 11, 30), date(2026, 12, 7))]
    steps = [cap.Step("Reminders off", "close", 0, 1, 1.0, "owner"),
             cap.Step("Publish", "close", 1, 1, 3.0, "owner", rounds=("r1",))]
    hours = cap.monthly_hours(steps, windows, [], frozenset(), 2026,
                              date(2026, 8, 17), date(2027, 6, 14))
    assert len(hours) == 12
    assert hours[4] == 4.0   # November: r1 off (Nov 2) + publish (Nov 9)
    assert hours[5] == 1.0   # December: r2 off (Dec 7)
    assert sum(hours) == 5.0

def test_standing_school_year_skips_blocked():
    hours = cap.monthly_hours([], [], [cap.Standing("Tickets", 1.0, "school_year")],
                              frozenset({date(2026, 11, 23)}), 2026,
                              date(2026, 11, 2), date(2026, 11, 30))
    assert hours[4] == 4.0   # Nov 2, 9, 16, 30 (23 blocked)

def test_step_outside_school_year_raises():
    w = cap.Window("r1", date(2026, 7, 6), date(2026, 7, 13))
    s = cap.Step("Prep", "open", -2, 1, 1.0, "owner")
    with pytest.raises(ValueError, match="Prep.*r1"):
        cap.monthly_hours([s], [w], [], frozenset(), 2026, date(2026, 8, 17), date(2027, 6, 14))

def test_unknown_round_raises():
    s = cap.Step("Publish", "close", 1, 1, 3.0, "owner", rounds=("r9",))
    with pytest.raises(ValueError, match="r9"):
        cap.monthly_hours([s], [], [], frozenset(), 2026, date(2026, 8, 17), date(2027, 6, 14))
```

Load the modules at the top of the test file by file path, following
`tests/skills/test_project_charter_schedule.py`'s `_load` helper; expose the
charter module as `cap.sd` by having `capacity.py` load it the same way under
the name `sd`.

- [ ] **Step 2: Run the tests and confirm they fail**

Run:
`cd <worktree> && uv run pytest tests/skills/test_service_playbook_capacity.py -q 2>&1 | tail -n 15`
Expected: collection error or FAIL, because `capacity.py` does not exist.

- [ ] **Step 3: Implement `capacity.py` with the Interfaces above**

Stdlib only. The module docstring states the placement rule in the paragraph
above this task's steps, once; `references/playbook-doc.md` points at it rather
than restating it. The CLI reads the breaks CSV with `parse_breaks` for all four
regions and passes `years=[school_year_start]` to `network_blocked`.

- [ ] **Step 4: Run the tests and confirm they pass**

Run:
`cd <worktree> && uv run pytest tests/skills/test_service_playbook_capacity.py tests/skills/test_project_charter_schedule.py -q 2>&1 | tail -n 5`
Expected: all pass (the charter suite proves the import left it untouched).

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add .claude/skills/service-playbook/scripts/capacity.py tests/skills/test_service_playbook_capacity.py
git -C <worktree> commit -m "feat(claude): week placement and monthly hours for service playbooks"
```

### Task 2: Skill instructions

**Files:**

- Create: `.claude/skills/service-playbook/SKILL.md`
- Create: `.claude/skills/service-playbook/references/playbook-doc.md`
- Create: `.claude/skills/service-playbook/references/board.md`
- Create: `.claude/skills/service-playbook/references/ids.md`

**Interfaces:**

- Consumes: `capacity.py` CLI and JSON output from Task 1.
- Produces: `references/ids.md` rows `Playbook Drive folder` and
  `Capacity board`, both `UNSET` until Tasks 3 and 4 fill them; the
  `workstreams` record shape Task 3's page reads.

Read `.claude/rules/claude-md-editing.md` (loads on the first skill-file read)
and `.claude/skills/project-charter/SKILL.md` before writing; match its shape.

- [ ] **Step 1: Write `SKILL.md`**

Frontmatter `name: service-playbook`; `description` triggers on: "playbook for
<workstream>", "describe this recurring workstream", "time estimates for
<workstream>", "capacity board", "add <workstream> to the board", "how many
hours is <workstream>". Not for a project that starts and ends: point to
`project-charter`. Body: the non-negotiables (read `references/ids.md` and
`project-charter`'s `ids.md` first; no student data; `[proposed]` rule; every
Drive and board write after the user has seen it; no bare `env` token in tool
strings), then two phases, each ending with its output shown and a stop:

1. Playbook doc: read `references/playbook-doc.md`.
2. Board card: read `references/board.md`.

- [ ] **Step 2: Write `references/playbook-doc.md`**

Covers, in order: the 12 doc sections with their table columns, verbatim from
the spec's _Format_ list; the Asana reads (project notes and sections, round
tasks with `subtasks.name,subtasks.due_on,subtasks.assignee.name`,
`Tickets + Breakfix` tasks), noting failure modes drop names; reading the PM
calendar by tab name with the Sheets API under ADC
(`uv run --with google-api-python-client --with google-auth python -I <script>`),
asking which `Performance Management` tab is current, and proposing each round's
open and close weeks for the user to confirm; exporting the breaks tab per
`project-charter`'s `references/scheduling.md` _Read the breaks tab_; writing
`<scratchpad>/playbook-<slug>.json` and running `capacity.py`; proposing hours
per step marked `[proposed]` for one correction pass; creating the doc in the
`Playbook Drive folder` (ask for it when `UNSET`) named
`<Workstream> - Service Playbook`, through the Google Docs connector when it is
signed in, else Drive `create_file` from HTML tables, saying which was used.

- [ ] **Step 3: Write `references/board.md`**

Covers: the three collections and their fields, verbatim from the spec's _Data_
section; writing one `workstreams` record with `ArtifactData` `set`, doc id =
the playbook slug, `source: playbook`, `proposed: true` while any step hour is
still `[proposed]`; never writing `assignments` or `analysts`; showing the
record before the write; republishing the page from
`.claude/skills/service-playbook/board/index.html` to the `Capacity board` URL
in `ids.md` after a page change.

- [ ] **Step 4: Write `references/ids.md`**

Same table shape as `project-charter`'s (`Name`, `Id`, `Used in`, `Re-find`),
two rows, both `UNSET`.

- [ ] **Step 5: Lint and commit**

Run:
`cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/service-playbook/SKILL.md .claude/skills/service-playbook/references/*.md </dev/null 2>&1 | tail -n 15`
Expected: no lint issues (a `fmt` line alone is fine; the hook formats).

```bash
git -C <worktree> add .claude/skills/service-playbook/SKILL.md .claude/skills/service-playbook/references/
git -C <worktree> commit -m "feat(claude): service-playbook skill instructions"
```

### Task 3: Capacity board page

**Files:**

- Create: `.claude/skills/service-playbook/board/index.html`
- Modify: `.claude/skills/service-playbook/references/ids.md` (`Capacity board`
  row)

**Interfaces:**

- Consumes: the `workstreams`, `analysts`, `assignments` shapes from Task 2's
  `references/board.md`.
- Produces: the published board URL in `ids.md`.

Load the `artifact-capabilities` and `artifact-design` skills before writing.
Model the interactions on the Leader ITR Setup page
(`https://claude.ai/artifact/XkFtJLspz6peRe8EBVP6jS`, read it with the Artifact
tool's `read`): chips moved by click or drag between columns, live totals,
search, autosave status line, owner-only controls, a read-only class for other
viewers. Fonts Whitney, Calibri, Verdana; light and dark tokens.

- [ ] **Step 1: Write the page**

Columns: `Unassigned` plus one per `analysts` record. Chip: name, hours per
year, 12-bar month strip, `proposed` badge, playbook link. Column header: hours
per year against `capacity_hours_per_month × 12`, and a summed month strip with
any month over `capacity_hours_per_month` in the warning color. Capacity 0 or
unset shows the total with no percentage. Editors (the owner, plus names the
owner lists) can add an analyst, set capacity, add a `manual` card (name plus 12
monthly hours or one yearly figure spread evenly), and move cards; everyone else
gets the read-only view.

- [ ] **Step 2: Publish and record the URL**

Publish with the `db` and `user` capabilities, `icon: chart`. Write the URL into
`ids.md`'s `Capacity board` row.

- [ ] **Step 3: Verify in the browser**

Seed through `ArtifactData`: 2 analysts (one with capacity 0), 2 `manual` cards.
Then check, and report each result:

- Dragging a card to an analyst updates that column's yearly total and month
  strip, and the change shows after a reload.
- The capacity-0 analyst shows a total with no percentage.
- Rewriting a seeded card's `hours_by_month` with `ArtifactData` `set` leaves
  its assignment in place.
- A second viewer without edit rights cannot move cards. Delete the seed records
  afterwards.

- [ ] **Step 4: Commit**

```bash
git -C <worktree> add .claude/skills/service-playbook/board/index.html .claude/skills/service-playbook/references/ids.md
git -C <worktree> commit -m "feat(claude): capacity board for service playbook workstreams"
```

### Task 4: Surveys acceptance run

**Files:**

- Modify: `.claude/skills/service-playbook/references/ids.md`
  (`Playbook Drive folder` row)

**Interfaces:**

- Consumes: everything above.
- Produces: the Surveys playbook doc and the Surveys card on the board.

This task is interactive with the user: it runs the skill as written, and every
fix the run needs goes back into the skill files in this task.

- [ ] **Step 1: Run phase 1 on Asana project `1210036297132224`**

Follow `SKILL.md` as written, against the 2026-27 calendar sheet. Stop where the
skill stops: windows to confirm, then hours to correct, then the doc link.

- [ ] **Step 2: Check the doc against the spec's acceptance line**

All 12 sections present; every hour the user has not accepted carries
`[proposed]`; the capacity summary equals `capacity.py`'s `hours_by_month` for
the confirmed `playbook-surveys.json`; no staff names in the failure modes.

- [ ] **Step 3: Run phase 2**

Write the Surveys card. Confirm on the board that its month strip equals the
doc's capacity summary.

- [ ] **Step 4: Fold run fixes into the skill, lint, commit**

Record the Drive folder id in `ids.md`. Lint as in Task 2 Step 5.

```bash
git -C <worktree> add -u
git -C <worktree> commit -m "fix(claude): service-playbook fixes from the Surveys run"
```

### Task 5: Pull request

- [ ] **Step 1: Push and open the PR**

Body from `.github/pull_request_template.md`, plain-language sections per
`.github/PLAIN_LANGUAGE.md`, `Closes #6497`, links to the Surveys doc and the
board. Verify the returned title and body match.

- [ ] **Step 2: Offer CI watching and review response**

Per the root CLAUDE.md _Pull requests and CI_.
