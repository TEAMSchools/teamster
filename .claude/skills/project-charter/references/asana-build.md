# Asana build

Phase 4. Precondition: the work plan in the charter doc is approved and the
`Asana project template` row in `ids.md` is not `UNSET`. The Asana conventions
file injects on the first Asana call and carries the tool gotchas; this file
carries the order and the values.

## Order

1. `create_project_from_template` with the template gid and the Data team gid
   from `ids.md`, `name` as the charter's Project Name, private. The job runs
   asynchronously; `get_project` with `include_sections` a moment later shows
   the result. The template brings the three custom fields, the sections
   `0 · Governance`, `Handoff` and `Parking lot and outside the core set`, an
   `Untitled section` Asana adds, and the eight standing tasks listed in
   `asana-template.csv`: three milestones, two recurring tasks, three handoff
   tasks. Read the standing tasks' gids with `get_tasks` on the project; step 4
   dates them.
2. One section per delivery workstream, in the charter's order, named
   `1 · <workstream>`, `2 · <workstream>`, through `update_project`
   `add_sections`. They land after the template's sections; the numbers carry
   the order. The plan's `Governance` workstream gets no section: its rows are
   the standing tasks in `0 · Governance` and `Handoff`.
3. Members: the MOCHA Manager, Owner and Helpers, plus the user. Consulted and
   Approver names are stakeholders; they get status updates, not membership of a
   private Data team project. Resolve each name with `search_objects`
   (`resource_type: user`, the name as typed); the workspace spans three email
   domains, so match on the name the result shows, and list every match in the
   review message for the user to confirm. No email comes from the staff roster
   query in `intake-brief.md`. `update_project` `add_members` is refused by the
   permission classifier, so the stop message lists the members for the user to
   add in Asana. A task assigned to someone who is not a member gives them
   access, so a plan row owned by a stakeholder is assigned to the Owner with
   the stakeholder named in the notes.
4. Tasks, shown in full before the consent step below:
   - The standing milestones first: `update_tasks` sets assignee and due date on
     Charter signed, Kickoff and Close and lessons learned from the plan's
     governance rows, and on the three Handoff tasks from the plan's handoff
     rows. The recurring tasks keep their template dates.
   - One task per plan milestone that is not a standing one, with
     `resource_subtype: milestone`, `project_id`, its workstream's `section_id`,
     assignee and due date, all in one `create_tasks` call.
   - One task per plan task, in the same call shape plus `parent` set to its
     milestone's gid. `create_tasks` takes `parent`, `project_id` and
     `section_id` together, and the subtask is a project member. A task that is
     already a GitHub issue is named `#NNNN | title`, so it can later be
     multi-homed into TEAMster without renaming.
   - `html_notes`: the charter doc link and the task's work-plan note, inside
     the allowed tags only (headings and lists; no paragraph or break tags).
5. `update_project`: `set_custom_field_values` with Domain from the charter's
   stakeholder group and Active to `Active` (field and option gids in `ids.md`;
   Domain's option gids come from any Data team task that carries the field,
   read with `get_task` and `custom_fields.enum_options`, since the custom-field
   search needs a paid plan), and `html_notes` with the charter doc link as the
   description.

## Consent

Before step 4's first `create_tasks`: show the full task list (name, section,
assignee, due date, parent) and ask for a yes. After the yes, restate the
consent in plain text in the same turn as the call: "Creating these N tasks in
<project> as listed above." The consent classifier (root CLAUDE.md, _Branches_)
reads only that sentence, never the answer to a question.

## Check

Count workstream sections (names starting `N ·` with N of 1 or more; the
template's three sections and the untitled default are not counted) against the
plan's delivery workstreams, and milestone tasks and tasks against the plan's
rows, with `get_project` (`include_sections`) and `get_tasks`. The six dated
standing tasks are plan rows and count; the two recurring tasks have no plan row
and are left out of the count. The stop message carries the project link, the
three counts against the plan's three, and the members for the user to add.
