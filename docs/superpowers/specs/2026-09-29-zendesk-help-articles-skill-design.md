# Zendesk help articles skill — design

Refs [#5614](https://github.com/TEAMSchools/teamster/issues/5614). Supersedes
the plan on [#4843](https://github.com/TEAMSchools/teamster/issues/4843); the
dashboard-drafting half of that issue continues as
[#5615](https://github.com/TEAMSchools/teamster/issues/5615).

## Problem

Publishing a help article to the KTAF Zendesk Help Center by API works. The "How
to access Tableau" article went live that way on 2026-09-29, through the admin
API token pair and the Help Center REST API. But the procedure exists only as
one person's memory plus a write-up, and it has traps that cost a session each
time they are rediscovered:

- Title and body live on the translation endpoint. A body sent to the article
  endpoint is accepted and does not replace the live text.
- The author defaults to whoever owns the token. It must be set explicitly.
- Zendesk rewrites attachment URLs on save and clones attachments referenced
  from another article, so a stored body never matches the body that was sent.
- The sanitizer runs at render time. Reading the body back proves it was stored,
  not how it looks.

Neither existing route avoids the API. No Zendesk MCP is connected in Claude
Code. The Dagster `ZendeskResource` requests OAuth scope `read users:write`,
which has no Help Center write access.

The KIPP NJ | Miami design system now ships a `zendesk-help-articles` subsystem:
a sanitizer-aware README, 15 paste-ready snippets, a sample article, and an
optional Guide theme stylesheet. It covers authoring completely and publishing
not at all.

## Approach

3 shapes were considered.

- **A — one skill, 2 phases.** Author from the vendored design export, then
  publish through a script. One trigger covers "write me a help article for X"
  end to end, and the publish phase can be entered alone with finished HTML.
- **B — 2 skills.** The export vendored as its own skill nearly untouched, and
  publishing as a second skill. Cleanest provenance, but the 2 always run
  together and the export's own `SKILL.md` would need a hand-off line anyway.
- **C — publish only.** Authoring rules stay in Claude Design and a personal
  skills folder, with no review or version history, and the image-path contract
  between author and publisher is lost.

**Selected: A.** Its one cost is a vendored copy that can drift from Claude
Design. A provenance file with the export date and a folder-replace refresh
procedure handles that.

## Skill layout

```text
.claude/skills/zendesk-help-articles/
  SKILL.md                     triggers, the 2 phases, the PII gate, non-negotiables
  references/
    design-system/             the export, verbatim: README.md, snippets/,
                               sample-article.html, snippet-library.html,
                               kipp-help-center-theme.css
    PROVENANCE.md              project id, export date, "replace the folder, do not edit"
    zendesk-api.md             the API calls in order, the traps above, the
                               attachment call shape once verified
  scripts/
    publish_article.py         the publisher
```

2 files from the export are dropped when vendoring. `preview/` holds only the
CSS for the export's 2 preview pages and is not needed for article HTML. The
export's own `SKILL.md` is replaced by ours; 2 skill files in one tree would
confuse the loader.

### Verbatim vendoring needs a lint exclusion

The `trunk fmt` pre-commit hook reformatted the August snapshot on the #4843
branch: it exploded minified inline styles across lines and entity-escaped font
names inside `style` attributes, so its provenance note warns not to copy
snippets from it. The snippets are the paste-ready artifact, so this export must
stay byte-for-byte. That requires this entry in `.trunk/trunk.yaml`, which the
user adds by hand because the file is edit-denied for Claude:

```yaml
lint:
  ignore:
    - linters: [ALL]
      paths:
        - .claude/skills/zendesk-help-articles/references/design-system/**
```

The export's README has 2 known defects that stay as-is because the folder is
verbatim: the ordered list under _The rules we author by_ numbers its items
`1,2,3,4,3,5,6,7,8`, and _Two gotchas that bite_ lists 3. `PROVENANCE.md` names
both so the next export can carry the upstream fix.

## Where an article lives

Each article is a folder in the repo, so a re-publish updates rather than
duplicates, and the overwrite guard has a last-known state to compare against.

```text
docs/help-center/<slug>/
  article.html     body only, no <html> shell, composed from the snippets
  article.yml      metadata and publish state, schema below
  images/          screenshots, referenced from article.html by relative path
```

`docs/help-center/` is not in the MkDocs nav, following the `docs/superpowers/`
precedent for Markdown under `docs/` that is not a published page.

`images/` is gitignored. Dashboard screenshots are the likeliest place PII
enters git history, and history is permanent. The cost is that a fresh Codespace
cannot re-upload an image it does not have. It does not need to: once uploaded,
the attachment URL is in the stored body, and `article.yml` records the id.

### `article.yml`

```yaml
title: How to access Tableau
section_id: 123
author_id: 456 # required; the publisher refuses to run without it
user_segment: Signed-in users # default; resolved by name at run time
permission_group: Agents and admins # default; resolved by name at run time
labels: [tableau, access]
article_id: 789 # set by the publisher on first create
last_known_updated_at: 2026-09-29T14:02:11Z # set by the publisher after every write
attachments:
  images/01-home.png:
    id: 111
    url: https://<subdomain>.zendesk.com/hc/article_attachments/111
    sha256: ab12…
```

`user_segment` and `permission_group` are names, not ids, and the defaults are
the "Signed-in users" segment and the all-agents permission group. The publisher
resolves both through the user segments and permission groups endpoints on each
run. An article that needs different visibility overrides the name in its file.
The publisher refuses to publish to the "everyone" segment unless the file names
it explicitly.

## Author phase

Entered by "write a help article for X" or "draft the Zendesk article". Steps:

1. Read `references/design-system/README.md`. It is the source of truth for what
   the sanitizer strips and the rules that follow.
2. Compose `article.html` from `snippets/` in the article order the README sets:
   summary panel, in-this-article, `<h2>` sections with numbered steps and
   callouts, screenshots, related articles. No `<h1>`; Zendesk renders the
   title.
3. Every screenshot is an `<img src="images/<name>.png">` with a relative path,
   inside the screenshot snippet's `div` + `img` + caption `div` pattern.
4. Write a starter `article.yml` with `title`, `labels`, and the ids left blank
   for the user to fill.
5. Stop and ask the user to preview `article.html` in a browser, wrapped in the
   export's `sample-article.html` shell, before anything touches Zendesk.

## Publish phase

Entered by "publish `docs/help-center/<slug>`" or a re-publish after an edit.

### Credentials

The admin API token pair that the Dagster `ZendeskResource` already uses. The
session-scoped autouse fixture in `tests/conftest.py` loads it from 1Password,
so the publisher runs through a throwaway `tests/test_zz_publish_<slug>.py`
under `uv run pytest <path> -s`, and the file is deleted afterward. The
publisher is never run bare; a plain `uv run python` gets no secrets.

### `scripts/publish_article.py`

A plain module: one function per API step and one orchestrator,
`publish(article_dir, *, live: bool)`. Basic auth username is `{email}/token`.

Flow, in order:

1. **Resolve names.** `GET /api/v2/help_center/user_segments.json` and
   `GET /api/v2/guide/permission_groups.json`; map the `user_segment` and
   `permission_group` names in `article.yml` to ids. Refuse if either name is
   missing from Zendesk, or if `author_id` is absent from the file.
2. **Create or fetch.** No `article_id`:
   `POST /api/v2/help_center/sections/{section_id}/articles.json` with a
   placeholder body, `draft: true`, the resolved ids,
   `notify_subscribers: false`. Record the new `article_id`. Existing
   `article_id`: `GET` the article.
3. **Overwrite guard.** Existing article only. Compare the fetched `updated_at`
   to `last_known_updated_at`. On mismatch, print both and abort: someone edited
   in the Zendesk editor since the last publish.
4. **Backup.** Write the fetched title and body to the session scratchpad. Never
   to the repo; a stored body can contain PII.
5. **Images.** For each relative `<img src>` in `article.html`, look up its
   entry under `attachments`. Missing entry or changed `sha256`: run the PII
   gate below, then upload as an inline attachment on this article and record
   id, url, and hash. Unchanged: reuse. Replaced images leave the old attachment
   behind; the publisher reports its id and does not delete it.
6. **Rewrite in memory.** Substitute each relative `src` with its recorded url.
   `article.html` on disk keeps the relative paths.
7. **Article fields.** `PUT /api/v2/help_center/articles/{id}.json` with
   `author_id`, `user_segment_id`, `permission_group_id`, `label_names`.
8. **Translation.**
   `PUT /api/v2/help_center/articles/{id}/translations/en-us.json` with `title`,
   `body`, and `draft: not live`.
9. **Read back.** `GET` the translation. Confirm the title matches and every
   recorded attachment id appears in the stored body, matched by id because
   Zendesk shortens the url. Write the new `updated_at` to `article.yml`.
10. **Report.** Print the article url and, when `live` is false, the draft url.
    The skill shows the draft to the user and asks before calling again with
    `live=True`.

### Image handling

Inline attachments behave differently from ordinary image hosting, and the flow
above is shaped by 4 facts:

- An inline attachment belongs to one article and inherits its user segment. A
  signed-in-users article serves its screenshots only to signed-in users. This
  is the access control for anything on a dashboard screenshot, and why the
  skill never hotlinks a Drive or GCS image.
- Zendesk shortens the stored `content_url` to `/hc/article_attachments/<id>`.
  Verification compares ids, not url strings.
- A body that references another article's attachment gets a cloned attachment
  on save, with a new id. Each article uploads its own images; none are shared.
- Deleting the article deletes its attachments. A re-publish that recreated the
  article would orphan every image link, which is why `article_id` is persisted.

The attachment call is `POST /api/v2/help_center/articles/{id}/attachments` with
multipart `file` and `inline=true`, 20 MB per file. Zendesk's current docs also
list a required `guide_media_id`, which suggests the Guide media library now
sits in front of attachments. **Which shape the live API accepts is unverified
and is the first build task.** The publisher gets whichever works, and
`references/zendesk-api.md` records the answer.

### PII gate

Before any upload, Claude opens the image and states in plain words what is
visible: school, grade band, any names, any count small enough to identify a
student. It then waits for the user's yes. No image reaches Zendesk without that
confirmation. "Aggregate-safe" means no rendered mark, label, tooltip, or table
row corresponds to one student, checked against the underlying counts and not
just the visual form. Redaction is the human's job; the skill does not claim it
can redact.

### Human verification

After read-back, the user opens the published page signed in and looks. The
sanitizer acts at render, so the stored body proves storage, not appearance. The
skill says this every time and does not mark an article done until the user
confirms.

## `SKILL.md`

Description names both entry points and the failure symptoms from the write-up:
a body sent to the article endpoint not replacing the live text, the wrong
author displayed, images not rendering, the Dagster resource lacking Help Center
scope. Body states the non-negotiables from the export's README, the 2 phases,
the credential harness, the guardrails in the order they fire, and the PII gate.
It tells the reader to open `references/design-system/README.md` before writing
any HTML and `references/zendesk-api.md` before any publish.

## Testing

- Unit tests with a mocked `requests` session: the overwrite guard aborts on a
  timestamp mismatch; missing `author_id` and an unlisted segment name refuse;
  relative `src` values rewrite to recorded urls and absolute ones are left
  alone; an unchanged hash reuses an attachment and a changed hash uploads.
- One live run, by hand, under the pytest harness: publish a draft with 1 image
  to a test section, verify on the rendered page signed in, delete the article.
  The `guide_media_id` question is answered in that run.
- Skill trigger check: a fresh session asked to "write a help article" or
  "publish the article" loads the skill.

## Carried from #4843

Ideas, not artifacts, credited to that issue's spec:

- The template order for dashboard guides: finding your school's numbers, the
  tabs, what each number means, reading it correctly, when it updates.
- The verbatim-label rule: every UI label copied character for character from
  the workbook, never paraphrased.
- The aggregate-safe screenshot definition above.
- The voice supplement's word swaps (grain to "one row per student per day",
  null to blank, records to students) and "do not explain the pipeline."
- The gradebook audit dashboard as the pilot article.

## Follow-ups

- [#5615](https://github.com/TEAMSchools/teamster/issues/5615): compare a
  published article against its production dashboard's workbook XML and dbt
  docs, and propose additions, deletions, and edits as a diff to `article.html`.
  Also drafts a first article for a dashboard that has none.
- Install `kipp-help-center-theme.css` in the Guide theme. Then article HTML can
  use `.kipp-*` classes instead of about 300 characters of inline style per
  block. The inline snippets keep working either way.
- Delete orphaned attachments after a confirmed re-publish.

## Out of scope

- Publish on merge from CI, and Dagster-based staleness detection. Both were
  deferred by #4843 and stay deferred; article volume does not justify them.
- A Zendesk MCP server. The REST API through the existing token is sufficient.
- Any change to the Dagster `ZendeskResource` OAuth scope.
