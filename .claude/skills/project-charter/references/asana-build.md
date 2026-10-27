# Asana build

Phase 4. Precondition: the work plan in the charter doc is approved and the
`Asana project template` row in `ids.md` is not `UNSET`. The Asana conventions
file injects on the first Asana call and carries the tool gotchas; this file
carries the order and the values.

## Order

1. `create_project_from_template` with the template gid and the Data team gid
   from `ids.md`, `name` as the charter's Project Name, private. The template
   brings the three custom fields and the sections `0 · Governance` and
   `Parking lot and outside the core set`.
2. One section per workstream, in the charter's order, named `1 · <workstream>`,
   `2 · <workstream>`, so they sort after governance and before the parking lot.
3. Members: the MOCHA Manager, Owner and Helpers, plus the user. Consulted and
   Approver names are stakeholders; they get status updates, not membership of a
   private Data team project. Resolve each name with `search_objects`
   (`resource_type: user`, the name as typed); the workspace spans three email
   domains, so match on the name the result shows, and list every match in the
   review message for the user to confirm. No email comes from the staff roster.
4. Tasks, in two groups, each shown in full before the consent step below:
   - One task per milestone with `resource_subtype: milestone`, in its
     workstream's section, assignee from the work plan, due date from it.
   - One task per work-plan task, in its section, assignee and due date from the
     plan, `parent` set to its milestone task's gid. A task that is already a
     GitHub issue is named `#NNNN | title`, so it can later be multi-homed into
     TEAMster without renaming.
   - `html_notes`: the charter doc link and the task's work-plan note, inside
     the allowed tags only (headings and lists; no paragraph or break tags).
5. `update_project`: Domain from the charter's stakeholder group, Active to
   `Active`, with `custom_fields` as a JSON-encoded string of field gid to
   option gid; the charter doc link in the project description.

## Consent

Before step 4's first `create_tasks`: show the full task list (name, section,
assignee, due date, parent) and ask for a yes. After the yes, restate the
consent in plain text in the same turn as the call: "Creating these N tasks in
<project> as listed above." The bulk-launch rule in the root CLAUDE.md reads
only that sentence.

## Check

Count sections, milestone tasks and tasks in the created project with
`get_project` (`include_sections`) and `get_tasks`, and compare with the work
plan. The stop message carries the project link and the three counts against the
plan's three.
