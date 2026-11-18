# Intake and inventory

Document mode steps 1-2. Stop when the user has confirmed the family boundary.
Also the first step of QA mode when the family has no reference doc.

## Intake

If the family already has a reference doc or a family skill, read their source,
sheet-upkeep, and owner sections first. Put what they say into the message below
as answers to confirm, and ask only what they leave open. On DIBELS the family
skill already named five sources and six sheet procedures.

Ask in one message, before reading any SQL:

1. Material that explains the model: Google Docs, PDFs, meeting notes, a
   requester's email. Three ways to hand it over:
   - a file dropped in the session scratchpad (give the absolute path);
   - a public URL, read with WebFetch;
   - an org Google Drive link, read with the Google Drive tools. They run as the
     user, so no extra sharing is needed. Ask the user to share the file with
     `codespaces@teamster-332318.iam.gserviceaccount.com` only when you need
     specific tabs of a Sheet through the Sheets API (the Drive tools flatten
     every tab into one blob with no tab names).

   A Google Doc's tabs arrive as `#` headings: list them first and read every
   tab that turns the policy into rules (athletic eligibility's Reporting tab
   settled a blank status the policy tab left open). Record the source's title
   and last-modified date (`get_file_metadata`), and never put an internal doc
   link in the reference doc. If the model was designed through
   `superpowers:brainstorming`, its spec under `docs/superpowers/specs/` counts
   too. Granola and other claude.ai connectors may need authorizing in the
   user's claude.ai connector settings; when one is unavailable, ask for an
   export to scratch.

2. Google Sheet upkeep: does anyone maintain an input sheet for this family
   (examples: CARAT goal updates, season regeneration, College Board ID
   tagging)? Each one becomes a procedure in the family skill.
3. Who owns the family now, and who inherits it. When the user remembers only a
   first name, look it up in Cube's staff view, or in
   `kipptaf_people.int_people__staff_roster` selecting only `formatted_name`,
   `job_title` and `home_department_name`: the roster row also holds home
   address, birth date, pay and personal contacts. The doc gets name and title,
   never contact details.

Source material explains intent. The SQL decides what the doc claims.

## Find the consumers

Grep `src/dbt/*/models/exposures/*.yml` for every model name in the lineage.
Reading exposure YAML is local; do not open Tableau.

| Exposures found                      | Doc outline (`reference-doc.md`)                 |
| ------------------------------------ | ------------------------------------------------ |
| Tableau (`- tableau` under `kinds:`) | Dashboard: one section per view                  |
| Google Sheet, extract, or other      | Process: trigger, inputs, steps, outputs, owner  |
| Both                                 | Both middles, one section per consumer           |
| None                                 | Ask who consumes it; suggest adding the exposure |

Every external consumer needs an exposure (`src/dbt/kipptaf/CLAUDE.md` →
Exposures). A missing one is a finding, not a reason to guess the branch.

A periodic submission (a federal or funder report entered by hand on someone
else's site, such as CRDC or CSGF) uses the process outline even when a Tableau
exposure exists: the workbook is a worksheet for typing numbers in, not the
product. Its skill carries the cycle (kickoff doc and owner table, collection
sheet, entry, and the error flags the receiving site raises) plus a rollover
that maps the receiver's published element changes to the code. Read the last
cycle's folder first; on CRDC it held the owner table, deadlines, and the
reference dates the SQL encodes.

For a Google Sheet consumer, check the data team's two-tier convention: the
Connected Sheets extraction lives in the shared drive's IMPORTRANGE Sources
folder, named exactly after the model, and users get a friendly-named sheet in
Reports that pulls from it with IMPORTRANGE. The exposure `url` points at the
source sheet. Check with the Drive tools: `get_file_metadata` on the exposure's
sheet ID gives its parent folder (then `get_file_metadata` on that folder for
its name), and `search_files` with `fullText contains '<sheet id>'` finds a
Reports sheet that imports it. A source sheet sitting in Reports, or no Reports
copy, goes under "Known issues, need to fix".

Then check the two ways that layout loses data without an error:

- Row caps. Each Reports tab reads a fixed range, such as
  `IMPORTRANGE(<source>, "<tab>!A1:AD3000")`. Read every tab's formula and
  compare its cap with the source tab's row count; a cap below the count drops
  the rest. The Grad Plan NCA tracker read 3,000 of 9,379 rows until 2026-09-28.
  Formulas need the Sheets API: ask the user to share the Reports sheets with
  the codespaces service account. In a shared drive only managers can share, so
  confirm with `get_file_permissions` that the share landed before retrying
  a 403.
- Frozen extracts. A source sheet's Connected Sheets extract tabs are copies
  that change only when someone refreshes them. If `get_file_metadata` shows no
  change since the sheet was created, nobody refreshes them, and that refresh
  becomes a procedure in the family skill.

The convention is written up in `docs/guides/google-sheets.md`.

## Propose the boundary

Walk parents from each exposed model:

```bash
rg -o 'ref\("[^"]+"\)' <model>.sql | sort -u   # parents
find src/dbt -name '<parent>.sql'              # locate; read the current project's copy
rg -l 'ref\("<model>"\)' src/dbt --glob '*.sql' # children
```

First rule: a model whose logic exists for this family (its name, or the columns
the family's consumers read) is in the family, even with children outside it.
List the outside children as "also read by" in the doc, because a change to the
model moves them too. Example: `int_students__athletic_eligibility` also feeds
`rpt_deanslist__promo_status`.

Then the default rule for the rest: a model is in the family when every child it
has is in the family. Apply it second, because on its own it cascades: one
outside reader of a mid-chain model drops that model, then every parent whose
only child it was. On DIBELS a topline model reading the verdict model left the
default rule with 12 of 24 models, and without the model that computes the
verdicts. Shared hubs (`int_extracts__student_enrollments`,
`base_powerschool__final_grades`) stay out; the doc gets one line per hub:
"reads X for Y, joined on Z".

A model can belong to the family only while a condition holds: DIBELS carries
the NJDOE screener extract until a data-sharing agreement lets the data team
pull from the vendor directly. The doc records the condition. A family model
that already has its own reference doc (an open PR counts) keeps it; the family
doc links to it instead of copying it.

Present a table (model, layer, in or out, why, outside children) and wait for
the user to confirm or edit it.

## Measure what exists

- Reference doc: `docs/models/*.md`. Family skill: `.claude/skills/<name>/`.
- Line counts per heading:

  ```bash
  awk '/^#{2,4} /{if(h)print n"\t"h; h=$0; n=0} {n++} END{print n"\t"h}' <file>
  ```

- Every non-code file under the family skill (json, csv, tsv): a generic example
  or one cycle's data? Year-stamped names (`2026_27`, `sy26`, `fall`) are the
  tell. Cycle data is a cut candidate (`model-skill.md` → Shape).
- Cut candidates: one-time checks, change logs, "Resolved —" notes, counts that
  go stale.
- Note every dashboard view or process step the doc does not explain.
- Every model the doc and skill name exists in the checkout:

  ```bash
  cd <worktree> && for m in $(rg -oN --no-filename '\b(stg|int|rpt|dim|fct)_[a-z0-9_]+__[a-z0-9_]*[a-z0-9]' <doc> <skill dir> | sort -u); do
    [ -z "$(find src/dbt -name "$m.sql" -print -quit)" ] && echo "MISSING $m"; done
  ```

  A missing model that lives on an open PR is paused work, not a doc to
  maintain: move its design detail into that PR's and issue's bodies so the next
  owner can pick it up, and leave one line in the doc and skill (on hold, with
  the links). The DIBELS skill described a Bright Spots model that had sat on an
  unmerged PR for a month as if it were shipped.

- Open Asana tasks: `search_tasks` with `assignee_any` set to the owner,
  `completed=false`, once per family term (the family name, its measures or
  dashboard, its sheets). TEAMster tasks named `#NNNN | title` mirror GitHub:
  they follow their issue, so fix the issue and the task follows. Tasks with no
  number are known only to Asana: each one is done (complete it with a one-line
  comment), belongs in an issue body (move the detail, then complete it with a
  pointer), or needs a new owner. On DIBELS, a "send the preview" task held an
  open question the issue already carried. Propose the actions as a table and
  wait for the user before changing any task.
- Open PRs that edit family files: search PRs for each model name, then list
  each PR's files. Two PRs editing one model or skill file conflict for
  whichever merges second; tell the user which pair before starting (on DIBELS,
  a Miami PR edited the old single-file skill that another PR had split).
- Open issues about the family: `mcp__github__search_issues` with each model
  name. Check each issue's claims against the current SQL before citing it;
  issue bodies drift (on athletic eligibility, an open question said two regions
  were excluded after the code had already brought one back). A resolved one is
  a candidate to comment on and close, with the user's go-ahead.
- Support channels: search the ticket system's warehouse copy and the team's
  Slack channels for the family over the last six months — the themes become the
  skill's triage routes and the doc's support section. Ask the user for the
  names users actually type before searching: they share few words with the
  model names, so run a second pass with the surface terms the first pass
  uncovers (on DDI, users wrote "DKI" and "enrichment grades on report cards";
  no model-derived keyword matched either). In BigQuery the Airbyte
  `kipptaf_zendesk.tickets` copy is live; the dlt
  `dagster_kipptaf_dlt_zendesk_support` copy is frozen at 2025-02.
