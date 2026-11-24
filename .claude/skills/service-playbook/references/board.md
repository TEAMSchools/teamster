# Board card

Phase 2. Write one workstream's card to the capacity board. The board's link is
the `Capacity board` row in `ids.md`; its page source is
`.claude/skills/service-playbook/board/index.html`.

## The board's data

Three collections in the page's shared database:

| Collection    | Fields                                                                                                                                          |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `workstreams` | `id`, `name`, `hours_by_month` (12 numbers, July first), `hours_per_year`, `proposed` (bool), `playbook_url`, `source` (`playbook` or `manual`) |
| `analysts`    | `id`, `name`, `capacity_hours_per_month` (hours available for recurring workstreams)                                                            |
| `assignments` | `workstream_id`, `analyst_id`; a workstream with no record is unassigned                                                                        |

The skill writes `workstreams` only. People make `analysts` and `assignments` on
the board.

## Write the card

1. Build the record from the playbook: `id` is the workstream slug (`surveys`),
   `hours_by_month` and `hours_per_year` from the CAPACITY SUMMARY table,
   `proposed` true while any hour in the doc still carries `[proposed]`,
   `playbook_url` the doc link, `source: playbook`.
2. Show the record. After a yes, `ArtifactData` `set` on collection
   `workstreams`, doc id the slug. A `set` on an existing card replaces its
   hours and keeps its assignment, because the assignment is its own record.
3. Read the record back with `get` and check the hours match.

## Changing the page

Edit `board/index.html`, then publish it with the Artifact tool to the
`Capacity board` URL. A republish keeps the database.

## Stop message

The record as written and the board link.
