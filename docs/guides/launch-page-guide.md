# Adding a tool to the launch page

The launch page is the page staff open to find a dashboard. It is built from one
file in this repository: `docs/launch/links.yml`. Add an entry there, open a
pull request, and the tool appears on the page when the pull request merges.

This guide covers adding a tool, changing one, and taking one down.

**Who this is for.** Anyone on the data team with push access. You do not need
Zendesk editing rights, and you never edit the page's HTML — only the catalog
file.

## Before you start

You need three things:

- **A Codespace on this repository**, and push access to open a pull request.
- **Access to the tool itself**, so you can open it and confirm what it is
  called and what it does. Most entries are Tableau, at `tableau.kipp.org`.
- **For anything Google-hosted or AppSheet: the ability to open the file's Share
  dialog.** This is not optional. See [The sharing check](#the-sharing-check).

## Where the catalog lives

Everything is under `docs/launch/`:

| File            | What it is                                                      |
| --------------- | --------------------------------------------------------------- |
| `links.yml`     | **The catalog.** One entry per tool. This is the file you edit  |
| `groups.yml`    | The page's sections, region families, promo cards, publish gate |
| `build.py`      | Validates the catalog and renders the page                      |
| `template.html` | The page shell                                                  |

`build.py` runs during the docs site build and generates `launch/index.html`.
You never edit the HTML.

Two things to know about how this publishes:

- **Only `status: verified` entries appear on the page.** An entry left at
  `needs-review` is excluded from the build. Setting `verified` is what puts the
  tool in front of staff — it is a release switch, not a quality note.
- **This repository is public, and so is the catalog file.** Tool names,
  descriptions, and URLs are fine; they are already public today, and the
  destinations all require sign-in. Do not add phone numbers, email addresses,
  individual staff names, or anything about how to authenticate to a system.

## Step 1 — Decide it belongs

A catalog entry is a claim that a staff member might need to find this tool. Ask
two questions:

1. **Is this staff-facing?** Machine plumbing — a sheet a pipeline writes to
   that nobody opens — does not belong here, even though it is a real artifact
   with a real URL.

1. **Is it already here under a different name?** Search `links.yml` for the
   tool and for words in its name. The catalog was assembled from five separate
   pages that had drifted apart, so near-duplicates are a real risk.

If you find a duplicate, a dead tool, or a tool missing from the list entirely,
**open an issue** rather than fixing it inside an unrelated pull request.

## The sharing check

**Do this before you write the entry, not after.**

A Tableau link is safe to publish because Tableau requires sign-in — the URL is
useless to anyone outside the network.

**A Google Drive link is not automatically safe.** If a Sheet is shared "anyone
with the link," then the URL _is_ the access control, and publishing it in a
public repository hands it to the internet.

So for anything with a `google-*` system:

1. Open the file.
1. Click **Share**.
1. Confirm **General access is _not_ "Anyone with the link."** It must be
   restricted to named people or Workspace groups.

**If you find one that is link-shared, do not add it.** Flag it instead. That is
a live exposure to fix at the source, not something to document.

**AppSheet apps need this twice.** An AppSheet app has its own access setting,
_and_ it reads from a backing Google Sheet with separate sharing. Both have to
require sign-in. Open the app, then open the Sheet behind it, and check each.

**Check the Share dialog, not a script.** For a file you do not administer, the
Drive API returns only the owner — not the groups it is actually shared with. An
empty group list from a script is inconclusive, not evidence of a problem. The
Share dialog shows the real picture.

## Step 2 — Write the entry

Add a block to `links.yml`. Entries run roughly alphabetically by name; put
yours where it reads naturally.

```yaml
- id: attendance_dashboard
  name: Attendance Dashboard
  url: https://tableau.kipp.org/#/views/...
  description:
    Monitor ADA, chronic absenteeism, completion status of chronic absenteeism
    interventions, and daily attendance calls.
  audiences: [leaders, ops, region]
  system: tableau
  group: attendance
  status: verified
```

### Fields checked on every entry

Validated whether the entry publishes or not. A missing or wrong value fails the
build.

| Field    | Rule                                                                      |
| -------- | ------------------------------------------------------------------------- |
| `id`     | Lowercase letters, digits, and underscores only. Must be unique           |
| `name`   | Non-empty. Use what the tool calls itself when you open it                |
| `url`    | Must start with `https://`                                                |
| `system` | One of the nine values in [Systems](#systems)                             |
| `group`  | One of the seven ids in [Groups](#groups). Required — there is no default |
| `status` | `needs-review` or `verified`                                              |

For `id`, use the name in `snake_case`: `attendance_dashboard`,
`coaching_conversation_tool`, `gpa_roster_camden`.

### Fields required to publish

Checked only once `status: verified` — which is also the only time they matter,
because that is when the entry reaches staff.

| Field         | Rule                                                                |
| ------------- | ------------------------------------------------------------------- |
| `description` | Non-empty. **One sentence**: what the tool is for, not how it works |
| `audiences`   | Non-empty list from `teachers`, `leaders`, `ops`, `region`          |

`audiences` controls **relevance, not access.** Tagging a tool for one role does
not hide it from anyone — the All view always lists everything, and the
destination system enforces who can actually see the data. So the question is
"who needs this in their day-to-day," and a tool can be in several.

### Optional fields

| Field             | What it does                                                              |
| ----------------- | ------------------------------------------------------------------------- |
| `guide`           | URL of the Zendesk help article for this tool. Must be `https://`         |
| `access: limited` | Badge for tools most staff cannot open. `limited` is the only legal value |
| `regions`         | Geography: any of `newark`, `camden`, `miami`, `paterson`, or `[all]`     |

**`regions` is not `audiences`.** `regions` is geography — which regions a tool
covers. `audiences: [region]` is the _Regional & CMO role view_, an entirely
different thing. A tool can be `audiences: [region]` with no `regions:` at all,
or scoped to one region and used by teachers.

Use `regions` when a tool exists once per region, like the GPA Rosters or the
Student Contact Info Feeds.

### The one YAML rule that bites

**Quote a string only when YAML needs it.** A value containing `: ` (colon then
space) needs quotes. Most values do not, and adding them anyway fails the
linter.

```yaml
name: "GPA Roster: Camden" # quoted -- contains a colon-space
name: Attendance Dashboard # not quoted -- does not need it
```

## Step 3 — Check it before you push

From the repository root:

```sh
# Validate the catalog and render the page
uv run --group docs pytest tests/launch -v

# Build the whole site and look at the real page
uv run --group docs mkdocs build --site-dir site
# then open site/launch/index.html
```

The tests are the same check CI runs. If validation fails you get **every**
problem at once, not just the first, each naming the entry:

```text
3 problem(s) in the launch catalog:
  - Attendance Dashboard: `id` 'Attendance-Dashboard' must match ^[a-z0-9_]+$
  - Seat Tracker: unknown `group` 'enrollment'
  - Stipend App: needs a non-empty `audiences` list
```

Also run the linter, because the YAML rules fire at push time rather than at
commit time:

```sh
.trunk/tools/trunk check --force --no-fix docs/launch/links.yml
```

## Step 4 — Open a pull request

Branch off `main`, commit, push, and open a pull request. Branch naming follows
the convention in the root `CLAUDE.md`.

CI runs the `launch` job on any change under `docs/launch/`. It validates the
catalog, builds the site, and **attaches the rendered page as a downloadable
artifact named `launch-page-preview`** — so a reviewer can open the real page as
your change would publish it.

**Work in batches, and merge as you go.** A twenty-entry diff gets reviewed
badly. Two or three related tools per pull request is about right.

**A blocked entry never blocks its batch.** If one tool needs a decision, leave
it at `status: needs-review`, note the question, and ship the rest. It simply
does not appear on the page until someone resolves it.

## Other changes you might be making

### Updating a URL, name, or description

Edit the entry in place. Leave `status: verified`. Nothing else is needed.

### Taking a tool off the page

Change `status: verified` to `status: needs-review`. The entry stays in the file
with its history intact and drops off the page on the next build. Prefer this to
deleting the block — a deletion loses the record that the tool existed.

Delete the entry only when the tool is genuinely gone.

### Adding a help guide link

Add `guide:` with the Zendesk article URL. It must be `https://`.

### Adding a region-variant tool

Tools that exist once per region collapse into a single row on the page with
per-region sub-links. That grouping is a **family**, defined in the `families:`
block of `groups.yml`.

The row takes its label and description from the family, not from its members.
Here is the real `gpa_roster` family, with its description shortened:

```yaml
families:
  - id: gpa_roster
    name: GPA Roster
    description:
      Student GPA for the current year, one sheet per region — quarter GPAs,
      year-to-date, and cumulative.
    group: academics
    members:
      - "GPA Roster: Camden"
      - "GPA Roster: Miami"
      - "GPA Roster: Newark"
      - "GPA Roster: Paterson"
```

| Key           | What it is                                               |
| ------------- | -------------------------------------------------------- |
| `id`          | Lowercase letters, digits, and underscores               |
| `name`        | The single row label staff see on the page               |
| `description` | The row's description. Member descriptions are not shown |
| `group`       | One of the seven ids in [Groups](#groups)                |
| `members`     | The **`name`** of each `links.yml` entry in the family   |

To add a member to an existing family:

1. Add a normal entry to `links.yml` with **exactly one** value in `regions:` —
   one of `newark`, `camden`, `miami`, `paterson`. `[all]` is not legal for a
   family member.

   ```yaml
   - id: gpa_roster_miami
     name: "GPA Roster: Miami"
     url: https://docs.google.com/spreadsheets/d/...
     description: Term and Y1 GPA for students in the Miami region.
     audiences: [region, teachers]
     system: google-sheet
     group: academics
     regions: [miami]
     status: verified
   ```

1. Add that entry's **`name`** to the family's `members:` list, character for
   character:

   ```yaml
   members:
     - "GPA Roster: Camden"
     - "GPA Roster: Miami"
     - "GPA Roster: Newark"
     - "GPA Roster: Paterson"
   ```

   Both places need the quotes, because `GPA Roster: Miami` contains a
   colon-space.

**Families match on `name`, not on `id`.** A member name with no matching entry
fails the build:

```text
family 'gpa_roster' names missing tool 'GPA Roster: Trenton'
```

**A member whose entry is not `verified` stays in the list and simply does not
render.** The family row is built from the verified members only, so a family
can legitimately list more members than the page shows. Removing an unverified
member from `members:` is not necessary and loses the record that the variant
exists.

A new family, or a new `group`, is a `groups.yml` conversation with the catalog
owner — not something to add unilaterally.

## Two things that will surprise you

**The page can refuse to publish.** `groups.yml` carries `minimum_verified: 25`.
If fewer than that many entries are verified, **no page is generated at all**
and the URL returns a 404, rather than serving a near-empty page. The build
still passes. This is deliberate.

**A broken catalog on `main` freezes all documentation publishing**, not just
the launch page — the docs deploy runs the same code path. That is why the pull
request check exists. Do not merge a catalog change with a failing `launch` job.

## Reference

### Groups

The section of the page a tool sorts into. Required on every entry.

| Id            | Section on the page               |
| ------------- | --------------------------------- |
| `attendance`  | Attendance & behavior             |
| `academics`   | Academics & assessment            |
| `college`     | College readiness & pathways      |
| `performance` | Performance management & coaching |
| `staff`       | Staff, hiring & pay               |
| `operations`  | Enrollment & operations           |
| `surveys`     | Surveys                           |

Pick the one the tool most belongs under. If none fits, raise it — do not guess.

### Systems

| Value           | Display label |
| --------------- | ------------- |
| `tableau`       | Tableau       |
| `appsheet`      | AppSheet      |
| `zendesk`       | Zendesk       |
| `google-sheet`  | Google Sheet  |
| `google-slides` | Google Slides |
| `google-form`   | Google Form   |
| `google-doc`    | Google Doc    |
| `apps-script`   | Apps Script   |
| `other`         | Other         |

Anything `google-*` or `appsheet` triggers
[the sharing check](#the-sharing-check).

### Audiences

| Value      | Role view on the page |
| ---------- | --------------------- |
| `teachers` | Teachers              |
| `leaders`  | Leaders               |
| `ops`      | Operations            |
| `region`   | Regional & CMO        |

There is always an **All tools** view listing every published entry regardless
of audience.

### Validation errors and what they mean

| Error                                       | Fix                                                                       |
| ------------------------------------------- | ------------------------------------------------------------------------- |
| ``missing `id` ``                           | Add one, in `snake_case`                                                  |
| `` `id` ... must match ^[a-z0-9_]+$ ``      | Lowercase letters, digits, underscores only                               |
| ``duplicate `id` ``                         | Another entry already uses it — the tool may already be listed            |
| `` `url` must be https ``                   | Use the `https://` form                                                   |
| ``unknown `system` ``                       | Use a value from [Systems](#systems)                                      |
| ``missing `group` `` / ``unknown `group` `` | Use an id from [Groups](#groups)                                          |
| `` `status` must be one of ... ``           | `needs-review` or `verified`                                              |
| ``verified entries need a `description` ``  | Write one sentence, or drop back to `needs-review`                        |
| ``needs a non-empty `audiences` list ``     | Decide who this is for                                                    |
| `unknown audience `                         | Use a value from [Audiences](#audiences)                                  |
| `` `access` may only be 'limited' ``        | Remove the field or set it to `limited`                                   |
| `a family member needs exactly one region`  | One of the four regions in `regions:`, not `[all]`, not several           |
| `family ... names missing tool `            | The `members:` name in `groups.yml` must match the entry's `name` exactly |

### Where to ask

Every judgment call here is one somebody else can answer in two minutes.
Guessing costs more than asking.

- **Does this tool belong in the catalog?** Ask the catalog owner.
- **Which group does it go in?** Ask, if none of the seven obviously fits.
- **I found a link-shared Google Sheet.** Flag it immediately. Do not add it.
- **A new group or family.** Needs a `groups.yml` decision, not a guess.
