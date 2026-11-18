# Ids

The only file in this skill with an id in it. Every other file names the thing
and points here. A row marked `UNSET` blocks the phase that uses it.

| Name                    | Id                                             | Used in | Re-find                                                                                                                                                          |
| ----------------------- | ---------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PMO templates folder    | `1nvIQDmEo4YxNkAvpornEMLRPOa2krOfD`            | 2       | Drive folder "Project Management"; ask the PMO if it moves                                                                                                       |
| Templates doc           | `1g-NGEA0n6Z7n1gF7qntgIBJbH9hEub7HkC3dNlZMfiA` | 2, 3    | Drive `search_files` `parentId = '<folder>'`, title "Project Management Templates", the Google Doc (a sheet of the same name sits beside it)                     |
| Handbook doc            | `11SeAT6TBWaxPJImK8dhEA8Zu4ZuezihaJElP4lKQ-gE` | 2       | same folder, title "Project Management Handbook"                                                                                                                 |
| Network calendar sheet  | `1qITq1ulvAMdI-DdPN2A_85SlzWFdlAmpO606yACVXtM` | 3       | see the rollover rule below                                                                                                                                      |
| Calendar breaks tab     | `Important Dates/Federal Holidays`             | 3       | the tab whose breaks table has a Yes/No column per region                                                                                                        |
| Asana project template  | `1219984420282253`                             | 4       | Asana, new project, "from a template", the Data team's "Data team project (charter)"; made by hand, see below                                                    |
| Asana Data team         | `2525102809595`                                | 4       | Asana `get_teams`                                                                                                                                                |
| Custom field: Priority  | `1128133924564212`                             | 4       | on the template for later triage; the skill never sets it. Read `custom_fields` on any task in a Data team project; `get_project` does not return field settings |
| Custom field: Active    | `1206198787739164`                             | 4       | as above                                                                                                                                                         |
| Active option: `Active` | `1206198787739165`                             | 4       | as above, `enum_options`                                                                                                                                         |
| Custom field: Domain    | `858469791639273`                              | 4       | as above                                                                                                                                                         |

## Calendar rollover

The calendar sheet is republished every year under a new id. When the sheet's
title does not name the current school year (title form
`<YYYY>-<YYYY> Final Calendar - All Regions`), stop and ask the user for the new
link, replace the sheet row, and check the tab name still matches before reading
it. Never place dates from a sheet for another year.

## Asana project template

Made by hand in Asana by the user, and remade the same way if it is ever
deleted: a private project in the Data team, imported from
`references/asana-template.csv`, then the three custom fields above added, the
parking-lot placeholder task deleted, the two recurring tasks set to repeat, and
the project saved as a template (project menu, "Save as template"). It carries
three sections, `0 · Governance`, `Handoff` and
`Parking lot and outside the core set`, and eight standing tasks; the Data
team's product template is a different thing and is not this one. The gid in the
table is the template's, not the project it was saved from.
`create_project_from_template` does not inherit the template's team, so phase 4
passes the Data team gid.
