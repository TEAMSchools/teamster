---
name: zendesk-help-articles
description:
  Use when writing, editing, or publishing a KTAF Zendesk Help Center article
  ("write a help article for X", "draft the Zendesk article", "update the help
  article on Y", a re-publish after an edit), including end-user help for a
  Focus SIS District Report or a Tableau dashboard, when searching the Help
  Center for an existing article ("is there a help article on X"), when a
  published article shows the wrong author, its body did not change after an
  update, or its images do not render, or when asked whether the Dagster
  ZendeskResource or a Zendesk MCP can publish articles.
---

# Zendesk help articles

Zendesk holds the only copy of an article. Work happens in a folder in the
session scratchpad: `pull` fills it for an edit, you compose it for a new
article, and `publish` writes it back.

## Non-negotiables

- Read `references/design-system/README.md` before writing any article HTML.
  Inline styles only; `margin` only on `<table>`; `<div>` not `<p>` inside a
  `<td>`; empty elements are deleted; the sanitizer runs at render, so the
  stored body proves storage, not appearance.
- Read `references/zendesk-api.md` before any publish.
- The working folder is `<session scratchpad>/zendesk/<article_id or slug>/`.
  `publish`, `pull` and `preview` refuse a folder inside the checkout: articles
  are restricted to signed-in users and this repo is public.
- Every publisher call runs under pytest, through a throwaway
  `tests/test_zz_zendesk_<id or slug>.py` that holds only the folder path and
  flags, deleted afterward. A bare `uv run python` has no credentials. Neither
  the Dagster `ZendeskResource` (scope `read users:write`) nor any connected MCP
  can write to the Help Center.
- Before the first Zendesk write in a session (publish, unpublish, archive,
  permission change), if auto mode is on: stop, show the exact command, and ask
  the user to switch to manual mode with Shift+Tab. Run it only after they
  confirm, then tell them they can switch back. Auto mode's classifier can
  refuse a write it allowed minutes earlier; reads (`pull`, `preview`, searches,
  dry runs) stay in auto.
- Draft first for a new article. Going live is a second call with `live=True`,
  after the user has seen the draft. An article that is already live is updated
  in place with `live=True`; the publisher refuses `live=False` on it unless
  `unpublish=True`, because Zendesk has no draft of a live article and the page
  would vanish for readers.
- No publish without the PII gate below, for body text and images.

## Working folder

```text
<session scratchpad>/zendesk/<article_id or slug>/
  article.html   body only, no <html> shell
  article.yml    title, section_id, author_id, labels; optional user_segment,
                 permission_group; publisher-owned article_id,
                 last_known_updated_at; draft (written by pull)
  images/        new screenshots, referenced by relative path
  preview.html   written by preview()
  backups/       the stored body before each overwrite
```

`author_id` is required. Visibility defaults to the "Signed-in users" segment
and the "Agents and admins" permission group; override by name in the file.
`user_segment: everyone` is the only way to publish to everyone.

`last_known_updated_at` is Zendesk's `updated_at` when the folder was pulled,
refreshed after each publish. If Zendesk's value differs at publish time,
someone edited in Guide and the publisher refuses. After each upload the
publisher rewrites that image's `src` in `article.html` to its Zendesk url, so
an image is never uploaded twice. The publisher rewrites `article.yml` on every
run, so comments in it do not survive.

The scratchpad ends with the session. To edit an article again later, pull it
again.

## Runner

```python
import sys
from pathlib import Path

sys.path.insert(0, ".claude/skills/zendesk-help-articles/scripts")
from publish_article import preview, publish, pull  # noqa: E402

WORKDIR = Path("<session scratchpad>/zendesk/<article_id or slug>")


def test_run():
    print(publish(WORKDIR, live=False, approved_images=frozenset({"images/01-home.png"})))
```

Swap the call in `test_run` for the step at hand, then
`cd <checkout> && uv run pytest tests/test_zz_zendesk_<id or slug>.py -s`.

## Search

To find an existing article, swap the call for
`search_articles("<words from the question>")`, imported from the same module.
It prints id, title, url, and updated date; a read, so it stays in auto mode.
The `zendesk-tickets` skill calls this after `research` when a ticket's answer
is an article.

## Content

- Every fact the reader acts on comes from the user: the navigation path, exact
  screen, report, filter and button names, school and category names as the
  system spells them, the help contact, and quirks readers will hit. Ask for any
  you do not have; a plausible guess reads as fact on the published page. A body
  still holding a `[placeholder]` is not ready to publish.
- Write in the reader's terms. When the source is SQL, a dbt model, or a
  dashboard spec, name what the reader sees on screen; table and column names
  stay in the source.
- Give navigation as a path, "Go to **Reports** → **District Reports**", rather
  than a menu's position on screen, which differs between users.
- Example data in the body follows the PII gate.

An article on running a report or dashboard (a Focus District Report, a Tableau
dashboard) has these `<h2>` sections after the summary panel and
in-this-article:

1. Where to find it: numbered steps to the exact folder and title.
2. Choosing your filters: a data table with one row per filter and what it does,
   plus a warning callout for each quirk (one filter's list ignoring another).
3. What the report shows: one `<h3>` per output table, what one row is, and a
   short example table.
4. Get help: the contact the user gave.

Related articles still close the article, per the README order.

## New article

1. Collect the facts under _Content_ from the user.
2. Read the design-system README. Compose `article.html` from
   `references/design-system/snippets/` in the README's article order: summary
   panel, in-this-article, `<h2>` sections with numbered steps and callouts,
   screenshots, related articles. No `<h1>`.
3. Reference each screenshot as `<img src="images/<name>.png">` inside the
   screenshot snippet.
4. Write `article.yml` with `title` (a plain sentence) and `labels`; ask the
   user for `section_id` and `author_id`.
5. PII gate for the body text and each image.
6. Auto-mode check, then `publish(WORKDIR, live=False, approved_images=...)`.
7. Show the draft url and the report. Ask the user to open the draft signed in.
   This is the preview: the draft shows what the sanitizer does. Stop until they
   approve.
8. `publish(WORKDIR, live=True)`. Nothing is uploaded this time; the images are
   Zendesk urls now.
9. Ask the user to confirm the live page renders. Delete the test file.

## Edit an existing article

1. `pull(<article_id>, WORKDIR)`.
2. Edit `article.html`. For a new or replaced screenshot, save it under
   `images/` and point the `src` at it.
3. `preview(WORKDIR)`, then serve the folder with
   `uv run python -m http.server 8765 --bind 127.0.0.1 --directory <WORKDIR>` as
   a background Bash job. The folder holds `backups/` of the gated body, so keep
   the loopback bind. VS Code forwards the port; ask the user to open
   `/preview.html` on it in a browser or VS Code's Simple Browser. Images
   already on Zendesk render only if the browser's Zendesk session reaches them;
   text and layout always render. Stop until they approve, then stop the server.
4. PII gate for changed body text and any new image.
5. Auto-mode check, then `publish(WORKDIR, live=True, approved_images=...)`. If
   `article.yml` says `draft: true`, the article was a draft when pulled: use
   `live=False` to keep it one. The publisher refuses `live=True` on it until
   the user asks to take it live and you delete that line.
6. Show the report. Ask the user to open the page signed in and confirm it
   renders. Delete the test file.

## PII gate

Example data in the body text is invented: names like "Alex R." and "Taylor B.",
with a muted caption under each example table reading _Names above are examples,
not real students._ Values from a query, a ticket, or a screenshot stay out of
the body. Before publishing, read the body for names, school-facing ids, and
counts small enough to identify a student, tell the user what you found, and
wait for their yes.

For every local image the body references: open it with the Read tool, state in
plain words what is visible (school, grade band, any names, any count small
enough to identify a student), and wait for the user's yes. Collect the approved
relative paths for `approved_images`; the publisher refuses any local image not
in it.

## Report

`publish` returns `uploaded` (local images uploaded this run), `orphaned_ids`
(inline images on the article the body no longer references; download
attachments are left out; reported, never deleted), `backup`, `html_url` and
`draft`. A `PublishError` message is written for the user. Show it verbatim. The
overwrite guard names both timestamps and how to proceed.
