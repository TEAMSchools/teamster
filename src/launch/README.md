# Data launch page — tool catalog

This directory holds the source of truth for the data team's tool catalog — what
tools exist, what each is for, and who needs it.

**Where it gets served is settled.** The catalog renders into a single static
launch page published to GitHub Pages (see #4762). Follow-on work may render the
same source into Okta bookmark tiles or a discovery skill.

**Only `status: verified` entries publish.** An entry left at `needs-review` is
excluded from the build, so setting `verified` is not a quality note — it is
what puts the tool in front of staff. The page starts empty and fills up.

| File         | What it is                                                      |
| ------------ | --------------------------------------------------------------- |
| `links.yml`  | Every tool: name, URL, description, who it is for               |
| `views.yml`  | The five views and their intro copy. Presentation only          |
| `RUNBOOK.md` | The task sequence — start there if you are picking up this work |
| `README.md`  | This file: what the directory is and what "reviewed" means      |

The renderer and publishing pipeline do not exist yet. This is the data they
will consume.

## Current state

`links.yml` was **scraped from the existing Google Site** and merged. It is a
starting point, not a finished catalog. Every entry started at
`status: needs-review`.

- **46 tools** — 35 Tableau, 7 Google Sheets, 3 AppSheet apps, 1 Zendesk
- **61 `TODO` lines** flagging specific things a human needs to resolve
- **9 tools** have a linked user guide; the rest may or may not have one
- **4 tools** have no `audiences` at all and need roles assigned

The scrape found several kinds of problem, which is a good sign — these are
exactly the failures that come from maintaining the same list on five separate
pages by hand.

## The work

Review every entry and change its `status` to `verified`. An entry is verified
when all five of these are true:

1. **The tool still exists** and the URL loads. You will need Tableau access for
   most of them; ask if you do not have it.
1. **The name matches what the tool actually calls itself** when you open it,
   not what the old site called it.
1. **The description is accurate and one sentence.** Say what the tool is for,
   not how it works. Many scraped descriptions are decent; some are stale.
1. **`audiences` is right.** Who actually needs this in their day-to-day? See
   `views.yml` for what each role means. A tool can be in several. A tool in
   none still appears in the All view, so an empty list is a real answer — but
   it should be a decision, not an accident.
1. **`system` is right** — `tableau`, `appsheet`, `zendesk`, `google-sheet`,
   `google-slides`, `google-form`, `google-doc`, `apps-script`, or `other`.
1. **For anything Google-hosted, the sharing is group-based.** See below. This
   one is not optional.

### The other fields

- **`guide:`** — optional. The Zendesk help article for this tool, if one
  exists.
- **`access: limited`** — optional badge for tools most staff cannot open.
- **`regions:`** — optional, and **not the same thing as `audiences`**. This is
  geography: which of `newark`, `camden`, `miami`, `paterson` a tool covers, or
  `[all]`. Use it when a tool exists once per region, like the Student Contact
  Info Feeds. `audiences: [region]` means something entirely different — it is
  the _Regional and CMO_ role view. A tool can be `audiences: [region]` with no
  `regions:` at all, or scoped to one region and used by teachers.

Add `guide:` with the Zendesk article URL if the tool has a help article and the
entry is missing it.

### Google-hosted tools need one extra check

A Tableau link is safe to publish because Tableau requires sign-in — the URL is
useless to anyone outside. **A Google Drive link is not automatically safe.** If
a Sheet is shared "anyone with the link," then the URL _is_ the access control,
and publishing it here — in a public repository — hands it to the internet.

So for every entry with a `google-*` system, open the file, click **Share**, and
confirm **General access is _not_** "Anyone with the link." It should be
restricted to named people or Workspace groups.

If you find one that is link-shared: **do not add it to this file.** Flag it
instead. That is a live exposure to fix at the source, not something to
document.

The three GPA Rosters currently in `links.yml` were checked and are group-shared
correctly. Anything you add is on you to check.

**A tooling caveat you will hit.** For a file you do not administer, the Drive
API returns only the owner — not the groups it is actually shared with. An empty
group list from a script is therefore inconclusive, not evidence of a problem.
Check the Share dialog in the UI, which shows the real picture.

The four Student Contact Info Feeds are the case in point: automated reads show
only an owner, but the data team confirmed each is shared to its region's group
with CMO staff holding access to all four, and none is link-shared. They carry
student and guardian contact information, so treat them as the most sensitive
entries here and re-confirm rather than assume if anything about them changes.

**AppSheet apps need this twice over.** An AppSheet app has its own access
setting, _and_ it reads from a backing Google Sheet with its own separate
sharing. Both have to require sign-in. There is no API shortcut here — open the
app, then open the Sheet behind it, and check each.

### What order to do it in, and which entries need a decision

See [RUNBOOK.md](RUNBOOK.md). That file owns the sequence, the entries that need
a judgment call rather than a lookup, and what to flag as you go. This file
stays the field reference so the two cannot drift apart.

## Out of scope

Do not worry about any of this — it is handled elsewhere:

- The rendering or publishing pipeline
- Zendesk configuration, permissions, or article IDs
- Rewriting the `views.yml` intro copy (it needs doing, but not by hand here)
- The Our Team page, the support runbook, or the blog — those live in Zendesk
  directly and are not part of this catalog

## Conventions

- **Everything in this directory is public.** The repository is public and so is
  this file. Tool names, descriptions, and URLs are fine — they are already
  public on the current site, and the URLs require sign-in to be useful. **Do
  not add** phone numbers, email addresses, individual staff names, or anything
  explaining how to authenticate to a system.
- `audiences` controls **relevance, not access**. Tagging a tool for one role
  does not hide it from anyone; the All view always lists everything, and the
  destination system enforces who can actually see the data.
- One sentence per description. If it needs two, the second one probably belongs
  in a help guide.
