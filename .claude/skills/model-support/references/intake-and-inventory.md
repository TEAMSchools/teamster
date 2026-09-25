# Intake and inventory

Document mode steps 1-2. Stop when the user has confirmed the family boundary.
Also the first step of QA mode when the family has no reference doc.

## Intake

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
3. Who owns the family now, and who inherits it.

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

For a Google Sheet consumer, check the data team's two-tier convention: the
Connected Sheets extraction lives in the shared drive's IMPORTRANGE Sources
folder, named exactly after the model, and users get a friendly-named sheet in
Reports that pulls from it with IMPORTRANGE. The exposure `url` points at the
source sheet. Check with the Drive tools: `get_file_metadata` on the exposure's
sheet ID gives its parent folder (then `get_file_metadata` on that folder for
its name), and `search_files` with `fullText contains '<sheet id>'` finds a
Reports sheet that imports it. A source sheet sitting in Reports, or no Reports
copy, goes under "Known issues, need to fix". The convention is written up in
`docs/guides/google-sheets.md` once PR #5525 merges.

## Propose the boundary

Walk parents from each exposed model:

```bash
rg -o 'ref\("[^"]+"\)' <model>.sql | sort -u   # parents
find src/dbt -name '<parent>.sql'              # locate; read the current project's copy
rg -l 'ref\("<model>"\)' src/dbt --glob '*.sql' # children
```

Default rule: a model is in the family when every child it has is in the family.
Shared hubs (`int_extracts__student_enrollments`,
`base_powerschool__final_grades`) stay out; the doc gets one line per hub:
"reads X for Y, joined on Z".

A model with children outside the family is still proposed as in-family when its
logic exists for this family (its name, or the columns the family's consumers
read). List the outside children as "also read by" in the doc, because a change
to the model moves them too. Example: `int_students__athletic_eligibility` also
feeds `rpt_deanslist__promo_status`.

Present a table (model, layer, in or out, why, outside children) and wait for
the user to confirm or edit it.

## Measure what exists

- Reference doc: `docs/models/*.md`. Family skill: `.claude/skills/<name>/`.
- Line counts per heading:

  ```bash
  awk '/^#{2,4} /{if(h)print n"\t"h; h=$0; n=0} {n++} END{print n"\t"h}' <file>
  ```

- Cut candidates: one-time checks, change logs, "Resolved —" notes, counts that
  go stale.
- Note every dashboard view or process step the doc does not explain.
- Open issues about the family: `mcp__github__search_issues` with each model
  name. Check each issue's claims against the current SQL before citing it;
  issue bodies drift (on athletic eligibility, an open question said two regions
  were excluded after the code had already brought one back). A resolved one is
  a candidate to comment on and close, with the user's go-ahead.
