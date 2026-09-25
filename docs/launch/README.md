# Data launch page — tool catalog

This directory holds the source of truth for the data team's tool catalog — what
tools exist, what each is for, and who needs it.

**Where it gets served is settled.** The catalog renders into a single static
launch page published to GitHub Pages (see #4762). Follow-on work may render the
same source into Okta bookmark tiles or a discovery skill.

**Only `status: verified` entries publish.** An entry left at `needs-review` is
excluded from the build, so setting `verified` is not a quality note — it is
what puts the tool in front of staff. The page starts empty and fills up.

| File            | What it is                                                            |
| --------------- | --------------------------------------------------------------------- |
| `links.yml`     | Every tool: name, URL, description, who it is for                     |
| `groups.yml`    | Topical groups, tool families, promo cards, and the publish threshold |
| `build.py`      | Loads, validates, and renders the catalog into the page               |
| `template.html` | The page shell the catalog gets rendered into                         |
| `RUNBOOK.md`    | The task sequence — start there if you are picking up this work       |
| `PROJECT.md`    | Why this exists, where it stands, and what's still open               |
| `README.md`     | This file: what the directory is and what "reviewed" means            |

`build.py` loads `links.yml` and `groups.yml`, validates them, and renders
`template.html` into the published page. See PROJECT.md for how the pieces fit
together and what's left to decide.

## The field reference lives in the published guide

**[Adding a tool to the launch page](../guides/launch-page-guide.md)** is the
reference for every field: what is required, what the legal values are, the
Google Drive sharing check, how to preview the page locally, and what each
validation error means. It is published in the docs site nav, so it is reachable
without cloning the repository.

Keep it as the single home for those rules. This file covers what the directory
is and the state of this particular catalog; it deliberately does not restate
the field table.

`build.py` is the authority if the two ever disagree — `_tier_one` validates
every entry, `_tier_two` only the verified subset.

## Current state

`links.yml` was **scraped from the existing Google Site** and merged. It is a
starting point, not a finished catalog. Every entry started at
`status: needs-review`.

- **44 tools** — 34 Tableau, 7 Google Sheets, 3 AppSheet apps, 0 Zendesk
- **12 `TODO` lines** flagging specific things a human needs to resolve
- **7 tools** have a linked user guide; the rest may or may not have one
- **3 tools** have no `audiences` at all and need roles assigned

The scrape found several kinds of problem, which is a good sign — these are
exactly the failures that come from maintaining the same list on five separate
pages by hand.

## What "verified" means here

Review every entry and change its `status` to `verified`. An entry is verified
when all of these are true:

1. **The tool still exists** and the URL loads. You will need Tableau access for
   most of them; ask if you do not have it.
1. **The name matches what the tool actually calls itself** when you open it,
   not what the old site called it.
1. **The description is accurate and one sentence.** Say what the tool is for,
   not how it works. Many scraped descriptions are decent; some are stale.
1. **`audiences` is right.** Who actually needs this in their day-to-day? A tool
   can be in several. A tool in none still appears in the All view, so an empty
   list is a real answer — but it should be a decision, not an accident.
1. **`system` and `group` are right.** Legal values are in the guide.
1. **For anything Google-hosted, the sharing is group-based.** The procedure is
   in the guide. This one is not optional — see below for what we already know
   about the files in this catalog.

## What we already know about the Google-hosted entries

The guide explains how to run the sharing check. These are the findings specific
to the files already in this catalog, which are worth keeping as a record:

- **The three GPA Rosters** in `links.yml` were checked and are group-shared
  correctly. Anything you add is on you to check.
- **The four Student Contact Info Feeds** are the case in point for why the
  check has to happen in the Share dialog: automated reads show only an owner,
  but the data team confirmed each is shared to its region's group with CMO
  staff holding access to all four, and none is link-shared. They carry student
  and guardian contact information, so treat them as the most sensitive entries
  here and re-confirm rather than assume if anything about them changes.

If you find a file that is link-shared: **do not add it to this file.** Flag it
instead. That is a live exposure to fix at the source, not something to
document.

## What order to do it in, and which entries need a decision

See [RUNBOOK.md](RUNBOOK.md). That file owns the sequence, the entries that need
a judgment call rather than a lookup, and what to flag as you go.

## Out of scope

Do not worry about any of this — it is handled elsewhere:

- Zendesk configuration, permissions, or article IDs
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
