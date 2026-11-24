# Playbook doc

Phase 1. Read the Asana project and the calendar, place the steps in weeks,
compute the hours, and write one Google Doc in the table style of
`project-charter`'s charter. Ids are in `ids.md`.

## The doc

Named `<Workstream> - Service Playbook`, in the `Playbook Drive folder`. Twelve
sections, each a table with a bold title row spanning the table, in this order:

| #   | Title               | Columns or rows                                                                                                         |
| --- | ------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| 1   | SERVICE SUMMARY     | label/value rows: Service name, Owner, Backup, Partner team, Asana project, Date source, Hours per year, Busiest months |
| 2   | WHAT AND WHY        | label/value rows: What the service delivers; Why it matters                                                             |
| 3   | SCOPE               | label/value rows: Data team supports; Partner team owns                                                                 |
| 4   | STAKEHOLDER MAP     | Stakeholder, Power (H/M/L), Interest (H/M/L), Current Position, Key Concerns, Engagement Level                          |
| 5   | ROLES & OWNERSHIP   | label/value rows: M — Manager, O — Owner, C — Consulted, H — Helper, A — Approver                                       |
| 6   | ROUND CALENDAR      | Round, Includes, Open week, Close week (current school year)                                                            |
| 7   | ROUND CHECKLIST     | Step, Anchor, Offset weeks, Duration weeks, Hours per week, Role, Rounds                                                |
| 8   | STANDING WORK       | Work, Hours per week, Weeks (`school_year` or `all`)                                                                    |
| 9   | CAPACITY SUMMARY    | one row per month, July to June, then Total; the hours come from `capacity.py`, never typed                             |
| 10  | SYSTEMS             | System, What it does in this service, Link                                                                              |
| 11  | RAPID DECISION LOG  | Decision, R — Recommend, A — Agree, P — Perform, I — Input, D — Decide                                                  |
| 12  | KNOWN FAILURE MODES | Failure, What it looks like, Fix                                                                                        |

Busiest months in section 1 are the three months with the most hours in
section 9.

## Read

1. Asana `get_project` with `include_sections` and `notes`: the systems list and
   which section holds the rounds.
2. Asana `get_tasks` on the round section with
   `name,due_on,subtasks.name,subtasks.due_on,subtasks.assignee.name`, with
   `modified_since` about six months back so last year's completed rounds come
   too. Model the steps on the current school year's round tasks, and use last
   year's to fill steps a current round has not listed yet. Each round task
   becomes a row in section 6; its subtasks become steps in section 7. A subtask
   that repeats across rounds under the same name is one step; one that appears
   in only some rounds gets those round keys in `rounds`.
3. Asana `get_tasks` on the `Tickets + Breakfix` section: section 12. Rewrite
   each task as the failure it shows; drop every name.
4. The calendar. The date source is per workstream:
   - PM calendar (Surveys, teacher performance management): the network calendar
     sheet in `project-charter`'s `ids.md`, read with the Sheets API under ADC
     by tab name
     (`uv run --with google-api-python-client --with google-auth python -I <script>`
     with the script in the scratchpad). The sheet keeps old and revised
     `Performance Management` tabs side by side; list them and ask which is
     current. Read the playbook's column (Surveys: `SURVEY`). The tab is a
     free-text weekly grid with merged cells, so propose each round's open and
     close weeks as a table and wait for the user to confirm before using them.
   - Reporting Terms (microgoals `MG`, O3s `O3`, walkthroughs `WT`): one round
     per row of that `Type` for the school year, per region.
5. The breaks tab, exported as `project-charter`'s `references/scheduling.md`
   _Read the breaks tab_ says, to `<scratchpad>/breaks-<year>.csv`.

Subtask due dates against the confirmed windows give each step's anchor and
offset: anchor `open` when the date is nearer the open week, else `close`. The
offset counts unblocked weeks only, as the script places them: compute it with
`offset_between(anchor_week, due, blocked)` in `capacity.py`, where `blocked` is
`network_blocked` on the exported breaks. Counting calendar weeks instead moves
a step past a break and its hours into the wrong month.

## Place and compute

Write `<scratchpad>/playbook-<slug>.json`:

```json
{
  "windows": [
    { "round_key": "r1", "open_week": "2026-10-19", "close_week": "2026-11-02" }
  ],
  "steps": [
    {
      "name": "Reminders on",
      "anchor": "open",
      "offset_weeks": 0,
      "duration_weeks": 1,
      "hours_per_week": 1,
      "role": "owner",
      "rounds": null
    }
  ],
  "standing": [
    {
      "name": "Tickets and breakfix",
      "hours_per_week": 1,
      "weeks": "school_year"
    }
  ]
}
```

Run:

```bash
uv run python .claude/skills/service-playbook/scripts/capacity.py \
  --spec <scratchpad>/playbook-<slug>.json --breaks <scratchpad>/breaks-<year>.csv \
  --school-year <YYYY> --first-week <first day of school> --last-week <last day of school>
```

Redirect stdout only (`> <scratchpad>/capacity-<slug>.json`): `uv` can print a
warning on stderr, and `2>&1` puts it in front of the JSON.

The placement rules are in the script's docstring. The output is JSON: `steps`
(round, step, weeks), `hours_by_month` (12 values, July first) and
`hours_per_year`. Exit code 2 with a message on stderr names a step or round
that is wrong; fix the JSON and re-run.

## Hours

Asana carries no hours. Propose `hours_per_week` for every step and standing
item, each marked `[proposed]`, in one table, and ask the user to correct them
in one pass. Re-run the script after any change. Accepted hours lose their
marker; the rest keep it.

## Write

Write the prose sections to `<scratchpad>/content-<slug>.json`:

```json
{
  "slug": "surveys",
  "workstream": "Surveys",
  "owner": "<name>",
  "backup": "[proposed] ...",
  "partner_team": "...",
  "asana_url": "https://app.asana.com/...",
  "date_source": "...",
  "rounds": [
    {
      "key": "r1",
      "name": "Round 1",
      "includes": "...",
      "open_week": "2026-10-19",
      "close_week": "2026-11-02"
    }
  ],
  "what": "...",
  "why": "...",
  "supports": "...",
  "partner_owns": "...",
  "stakeholders": [["group", "H", "H", "Supportive", "concerns", "Decide"]],
  "roles": { "M": "...", "O": "...", "C": "...", "H": "...", "A": "..." },
  "systems": [["name", "what it does", "https://..."]],
  "rapid": [["decision", "R", "A", "P", "I", "D"]],
  "failure_modes": [["failure", "what it looks like", "fix"]],
  "questions": []
}
```

Round `key`s match the `round_key`s in the playbook JSON. Then build the HTML:

```bash
uv run python .claude/skills/service-playbook/scripts/render_doc.py \
  --content <scratchpad>/content-<slug>.json --playbook <scratchpad>/playbook-<slug>.json \
  --capacity <scratchpad>/capacity-<slug>.json --out <scratchpad>/playbook-<slug>.html
```

Show the user the section 9 table and the `[proposed]` list, then add the
playbook as a new tab of the `Service Playbooks doc` (`ids.md`), titled with the
workstream name. Drive's HTML import cannot make a tab, so build it with the
Google Docs connector and `scripts/doc_tabs.py`:

1. `update_doc` with
   `[{"addDocumentTab":{"tabProperties":{"title":"<workstream>"}}}]`; the reply
   carries the new `tabId`.
2. `doc_tabs.py skeleton --html <playbook html> --tab-id <tabId>`, and send its
   output as `requests`.
3. `read_doc`. Its result spills to a file; `jq '.content'` it into
   `<scratchpad>/doc.json`.
4. `doc_tabs.py fill --html <playbook html> --doc <scratchpad>/doc.json --tab-id <tabId>`,
   and send its output in chunks of 80 requests, in order, without reading the
   doc between chunks.

A fill runs to tens of kilobytes, so hand steps 2 to 4 to a subagent with the
exact commands rather than pasting the requests through the main conversation.
Check the tab afterwards: its tables count and its first cell reads
`SERVICE SUMMARY`. The doc's own service account cannot do this, because the
Google Docs API is turned off in the Data team's Cloud project.

## Stop message

The doc link, section 9 as a table, the `[proposed]` lines to clear, and the
question: put it on the board as it stands, or after the markers are cleared?
