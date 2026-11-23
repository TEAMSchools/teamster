# Dashboard build plans in Asana: design

## Intent

The Asana project "Data Marts + Semantic Layer" tracks what each Tableau
dashboard needs before it can run on Cube. Today the work hangs off table tasks
(`fct_*`, `dim_*`, `bridge_*`) in each domain section, and a dashboard reaches
its work only through blocked-by links. The analysts plan by dashboard and by
due date, so they read the plan in 2 places: the dashboard task for the date,
and the table tasks for the work.

The change makes each dashboard task hold its own dated build plan. A build that
serves several dashboards is planned under the dashboard that needs it first.
Every later dashboard gets a "Confirm" item, so reused work is checked instead
of overlooked. The end state has no open table tasks and no open `mart:`,
`cube:` or `view:` stage tasks; both are closed, not deleted, so their history
stays. Each dashboard task holds PR tasks, and each PR task holds rows named for
the Cube measures and dimensions it ships. The semantic layer build status page
reads those rows.

## Goals

- Each dashboard task lists its PRs and decisions as subtasks, each with an
  owner and a due date that fits the dashboard's own due date.
- A build shared by several dashboards appears once, under the earliest-due
  dashboard that needs it.
- Each later dashboard has a "Confirm `<build>` shipped with `<dashboard>`"
  subtask per reused build, blocked by that build.
- Each measure and dimension row sits under the PR task that ships it.
- The build status page keeps showing every dashboard's measure and dimension
  rows, with their status, through the whole migration.
- The cube-builder skill writes and keeps this shape for every dashboard it
  plans.

## Non-goals

- Changing the domain milestone tasks (`verified`, `Security review`,
  `Pilot run`, `launched`, the `M*` tasks), or how the page reads them.
- Changing the Zapier GitHub sync itself. The design works around its behavior.
- Planning dashboards outside this year's plan (the "2027-28" and "2026-27
  Stretch" sections).
- Moving the generator into teamster (#5794 tracks that).

## Anti-goals

- The status page loses rows, or shows a wrong status, at any point in the
  migration. A dashboard that drops off the page looks like it lost its work.
- A field's status lives in 2 places that can disagree.
- An analyst has to remember to move a synced PR task by hand.
- Student or staff data reaches Asana. Asana text carries field names, member
  names and counts only, the same rule the build issues follow.

## Current state

- **Dashboard tasks** are tagged `dashboard` and sit top-level in a domain
  section (`1 · Assessments`, and so on). Their notes say what the dashboard
  needs and point at the gap catalog.
- **Table tasks** (`fct_*`, `dim_*`, `bridge_*`) sit top-level in the same
  sections. Each has 1 subtask per missing field, plus `mart:`, `cube:` and
  `view:` stage subtasks. A row's `Used by:` line links every dashboard it
  serves. A table blocks each dashboard that a row on it names.
- **PR tasks** exist on some dashboards already. DDI Suite holds PR A to E, its
  hub issue (#6192), its validation issue and several synced GitHub tasks. STAT
  holds PR S1 to S4. Literacy holds L1 to PM4 (added 2026-11-23, see _Pilot_).
- **The generator** (`generate_dashboard.py` in
  `cristinabaldor/semantic-layer-dashboard`) reads the project every 4 hours and
  writes `data.js` for `docs/launch/semantic-layer/`. It reads measure rows
  (subtasks tagged `measure`) directly under a dashboard or under a table task,
  and dimension rows (other subtasks of a table task). Each row counts for every
  dashboard its `Used by:` line links. It reads table tasks at the top level or
  1 level under a top-level task, and nothing deeper.
- **The sync script** (`scripts/asana_sync.py`, only on the unmerged branch
  `cristinabaldor/feat/claude-asana-sync-done-when-live`) ticks a row done when
  every Cube member its notes name is on a public view on `main` and no blocker
  on the row is open. It tags open rows `needs-data` or `needs-cube` from the
  table's open stage subtasks, and tags every row `measure` or `dimension`.
- **The Zapier GitHub sync** creates a `#NNNN | <title>` task in the TEAMster
  project for each issue and PR, under Charlie Bini's account, about a minute
  after the issue or PR opens. It moves the task between TEAMster sections and
  completes it when the PR merges. It does not parent a PR task under the issue
  its body refs: #6280 says "Refs #6192" and arrived top-level. A task moved by
  hand keeps its new parent through later syncs.

## Approaches

### What sits directly under a dashboard

- **A. Planned PR tasks (picked).** Each PR or decision is a subtask with an
  owner and a due date. A dbt PR and the Cube PR that reads its columns get
  separate dates, so the order shows. This is the DDI Suite pattern, made the
  rule.
- B. Table tasks directly under the dashboard. Fewer layers, but a table built
  by a dbt PR and then a Cube PR gets 1 date, and a table that serves several
  dashboards still has to sit under 1 of them.
- C. Table tasks stay in the domain sections; dashboards hold only PR and
  Confirm tasks. Least disruptive, but it keeps the 2 places to look, which is
  the problem.

### Where the field rows of a shared table go

`fct_assessment_scores_enrollment_scoped` shows why this needs a rule: its 27
rows serve 4 dashboards, already planned as 4 PRs.

- **Option 1, each row moves to the PR that ships it (picked).** The row goes
  under the planned PR of the earliest-due dashboard that needs it. Its
  `Used by:` line keeps naming the later dashboards. A table task keeps only
  rows no plan has claimed, and it closes when it is empty.
- Option 2, the table stays whole. Each PR task links it with blocked-by and
  names its rows in notes. Less moving, but a row's status lives in 2 places.

### Synced PR tasks

- **Promote (picked).** When a PR opens, its synced task takes the planned PR
  task's place, and the placeholder closes. 1 line per PR, which Zapier
  completes at merge.
- Nest. The synced task moves under the placeholder. 2 lines per PR, and someone
  closes the placeholder by hand.

## Design

### Shape

```text
<Dashboard>                                  tag: dashboard (top-level, domain section)
├── #NNNN | <hub issue title>                synced hub task, moved here
├── <Decision>                                owner, due
├── PR <id> (<dbt|Cube>): <scope>            owner, due; blocked by the PRs it needs
│   ├── <row named for a measure>             tag: measure; notes: Use:, Used by:, member names
│   └── <row named for a dimension>           tag: dimension
├── Confirm <build> shipped with <dashboard>  due: that dashboard's due date; blocked by <build>
├── Already in Cube                          holds live rows no PR ships
├── Deferred                                  holds deferred rows
└── Validate <dashboard> in Cube             blocked by every PR and Confirm item
```

### Rules

- **Ownership.** A build belongs to the earliest-due dashboard that needs it.
  When due dates tie, it goes to the dashboard whose build issue opened first.
- **Confirm items.** 1 per reused build per later dashboard, named
  `Confirm <build> shipped with <dashboard>`, due on the owning dashboard's due
  date, blocked by the build's PR task. Its notes name the members the later
  dashboard reuses. The later dashboard's owner ticks it after checking those
  members cover the later dashboard's need. A gap becomes a new PR task under
  the later dashboard.
- **Due dates.** A PR's due date is on or before its dashboard's. A dbt PR is
  due before the Cube PR that reads its columns. When a dashboard's due date
  moves, the builder re-checks ownership of its builds and moves any build to
  the dashboard that is now earliest, swapping the PR task and the Confirm item.
- **Rows.** A row is named for the Cube member it ships, with the workbook field
  in its notes. Its notes keep the `Use:` line, the `Used by:` line, and the
  member names the sync script checks.
- **Row tags (builder's call).** Rows already carry `measure` or `dimension`
  tags, set by the sync script's earlier `--apply` runs. Under a PR task, the
  tag is the only thing that tells the 2 apart, so the builder keeps the tag
  when it moves a row and sets it when it creates one. The sync script checks
  every row under a dashboard has exactly 1 of the 2 and reports any that do
  not.
- **Which PR holds a row (builder's call).** A row sits under the PR that ships
  its Cube member, which is the Cube PR when a dbt PR comes first. The Cube PR
  is blocked by that dbt PR.
- **Row status (builder's call).** Done when its members are on a public view on
  `main`, as today. Otherwise the sync script reads the row's parent PR: if any
  open dbt PR blocks the parent, the row is `needs-data`; if not, it is
  `needs-cube`. A merged parent whose members are not on a public view yet stays
  `needs-cube`. The PR's name carries its type: `(dbt)` or `(Cube)`.
- **Rows no PR ships.** Each dashboard has 2 holder subtasks: "Already in Cube"
  and "Deferred". A row that is live with no PR to ship it, or that is deferred,
  goes under the holder on the earliest-due dashboard that uses it. Its
  `Used by:` line keeps counting it for the others. The measure rows that sit
  directly under dashboard tasks today move to a PR task or a holder the same
  way.
- **Stage subtasks (builder's call).** When a row moves to a PR task, the
  builder removes the row's blocked-by links to the table's `mart:`, `cube:` and
  `view:` stages, so status comes from the PR alone. The PR tasks take over both
  jobs the stages did: a dbt PR blocks the Cube PR that reads it, and the parent
  PR sets the row's status. A stage that is done closes with its table task. A
  stage with work left becomes a PR task under the earliest-due dashboard that
  needs it, and only closes once it is empty. A table task closes when it has no
  rows and no open stages.
- **Promotion.** After the builder opens a PR, it waits for the synced `#NNNN |`
  task (up to a few minutes). It moves that task under the dashboard, gives it
  the placeholder's due date and owner, moves the placeholder's rows under it,
  and moves every blocked-by link that pointed at the placeholder. Then it
  closes the placeholder with a comment linking the synced task.
- **Sweep.** Each builder run for a dashboard starts by finding open PRs that
  ref the dashboard's hub issue, then promotes any whose synced task is not
  under the dashboard yet. That covers PRs opened outside the builder.
- **The 30-link cap.** Asana caps a task at 30 dependencies plus dependents.
  Validate links PR tasks and Confirm items, never rows.

### Order of work

1. **Tools read the new shape.** Both changes ship before any row moves.
   - Generator: read `measure` and `dimension` rows under any subtask of a
     dashboard task (PR tasks and synced tasks), keep reading table tasks while
     any remain, and count a row for each dashboard its `Used by:` links, as
     today.
   - Sync script: merge it into `main`. Read rows under PR tasks and holders.
     Derive `needs-data` / `needs-cube` from the row's parent PR, as _Row
     status_ says, and keep the stage-subtask rule for rows still on table
     tasks. Find dashboards by the `dashboard` tag instead of a fixed list.
     Treat a missing validation file as no verdicts.
   - Schedule: the sync script runs every 4 hours, just before the generator,
     with an Asana token stored as a GitHub secret. Where both run is the
     builder's call; #5794 already tracks moving the generator into teamster.
   - Check: the page's row counts for every dashboard are unchanged after
     deploy.
2. **The cube-builder skill writes the shape.** Plan step 3 creates the PR
   tasks, decision tasks, Confirm items and Validate task under the dashboard,
   moves the hub's synced task there, and moves rows to their PR tasks. _Build_
   gains promotion, and each run starts with the sweep. The rule "Asana changes
   only for a miss" becomes "Asana mirrors the approved build plan".
3. **Pilot: Literacy, then STAT.** Move each row to its PR task, re-run the
   generator, and compare the page with the counts from before the move.
4. **Every other dashboard, by due date.** Each needs a cube-builder inventory
   first, since later dashboards' Confirm items depend on what earlier ones
   ship. A table task closes when no row is left on it.

### Pilot state (2026-11-23)

Literacy already holds its PR tasks, decision, Confirm items and Validate task
as plain subtasks (no tags), and the #6461 hub task. The generator skips
untagged subtasks, so the page is unchanged. Its rows are still on
`fct_dibels_progress_monitoring`, `fct_sight_words` and
`fct_assessment_scores_enrollment_scoped`. They move in step 3.

## Left to the builder

- How the generator and the sync script find a PR task's type, if a name without
  `(dbt)` or `(Cube)` turns up.
- How long promotion waits for a synced task, and what the builder reports when
  it never appears.
- The order of subtasks under a dashboard. The API appends; reordering is
  cosmetic.
- How to test both tools against a copy of the project before step 1 ships.
