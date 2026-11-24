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
offset: anchor `open` when the date is nearer the open week, else `close`; the
offset is the number of weeks from that anchor week.

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

Build the doc as one HTML file in the scratchpad: one `<table>` per section,
title row bold and spanning the columns, `[proposed]` kept in the cell text.
Show the user the section 9 table and the `[proposed]` list, then create the doc
with Drive `create_file`: `title` as above, `parentId` the
`Playbook Drive folder`, `contentMimeType: text/html`, and `base64Content` as a
file reference, `sha256:<sha256sum of the file>:<absolute path>`, so the HTML is
not retyped into the call. Drive converts it to a Google Doc. Check the returned
title and that the file's `mimeType` is `application/vnd.google-apps.document`;
the reported `fileSize` of a converted doc is not its length, so read the doc
back with `read_file_content` and count the twelve section titles.

## Stop message

The doc link, section 9 as a table, the `[proposed]` lines to clear, and the
question: put it on the board as it stands, or after the markers are cleared?
