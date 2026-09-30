# Zendesk help articles from Zendesk state — design

Refs [#5628](https://github.com/TEAMSchools/teamster/issues/5628). Revises the
publish half of
[2026-09-29-zendesk-help-articles-skill-design.md](2026-09-29-zendesk-help-articles-skill-design.md).

## Problem

The `zendesk-help-articles` skill keeps each article under
`docs/help-center/<slug>/` and expects a PR per article. That is wrong for two
reasons.

- **Access control.** Every Help Center article is restricted to signed-in
  users, and some carry sensitive policy detail. This repo is public. A
  committed article body is published gated content.
- **Two sources of truth.** Zendesk versions article bodies, and Guide agents
  can edit them again as of 2026-09-29. The repo copy drifts on the first typo
  fix in Guide, and the overwrite guard then blocks until someone reconciles by
  hand.

The repo copy bought an overwrite guard and attachment reuse. Both can come from
Zendesk at publish time.

No article was ever committed: `docs/help-center/` does not exist on `main`, so
there is no history to purge.

## Goal

Zendesk is the only source of truth, and no article content lands in the
checkout. Acceptance, from the issue:

- Publishing a new article and re-publishing an existing one both succeed with
  no article content written inside the checkout. The throwaway pytest runner
  holds only a scratchpad path and flags, and is deleted after the run.
- A Guide-side edit between `pull` and publish is detected and refused.
- A re-publish with an unchanged body uploads zero attachments.

The current publisher's verified behavior stays: end-to-end publish against
`teamschools.zendesk.com`, and a field-only change (permission group) going
through the article `PUT` without touching the translation.

## Design

### Working folder

State for one article lives in
`<session scratchpad>/zendesk/<article_id or slug>/`:

```text
article.html   body only, no <html> shell
article.yml    title, section_id, author_id, labels, user_segment,
               permission_group, article_id, last_known_updated_at
images/        new screenshots only
preview.html   written by preview(), edits only
backups/       stored body before each overwrite
```

The `attachments` map and per-image SHA256 in `article.yml` are removed. The
scratchpad is per session; a later session starts again from `pull`.

### Publisher (`scripts/publish_article.py`)

Three entry points.

`pull(article_id, workdir, *, client=None)` seeds a working folder for an edit.
It GETs the article, its `en-us` translation, the user segments and the
permission groups, and writes:

- `article.html` from the translation body.
- `article.yml` with the translation title, the article's `section_id`,
  `author_id` and `label_names`, the segment and group mapped back to names (a
  null segment becomes `everyone`), `article_id`, and `last_known_updated_at`
  from the article's `updated_at` at this moment.

It refuses when `workdir/article.html` already exists, so it never overwrites
in-progress edits. It also refuses a workdir inside the checkout.

`preview(workdir)` wraps `article.html` in the `sample-article.html` shell from
`references/design-system/` and writes `workdir/preview.html`. No network.
Zendesk-hosted images in a pulled body render only if the browser sends a
signed-in Zendesk session from the preview's origin; that is not guaranteed.
Text and layout always render.

`publish(workdir, *, live, approved_images, backup_dir, unpublish, client)`,
with `approved_images` defaulting to empty, `backup_dir` to `workdir/backups`,
`unpublish` to `False`, and `client` to one built from the environment. Order:

1. **Refuse a workdir inside the git checkout.** The repo root is derived from
   the script's own location, not from the caller. This is what makes "article
   content in the repo" impossible, not a caveat to remember.
2. Load `article.yml` and `article.html`; `title`, `section_id` and `author_id`
   are required.
3. **Check local images before any network call.** A local `src` is one that is
   not `http(s)://`, `//`, `data:` or `/hc/`. Each must resolve to a file under
   the workdir, and each must be in `approved_images`. There is no "unchanged"
   exemption: an uploaded image stops being local (step 7), so a local image is
   always new.
4. Resolve visibility names to ids (unchanged).
5. **Create or guard.** With no `article_id`, create a draft, then write
   `article_id` and `last_known_updated_at` to `article.yml` at once so a later
   failure cannot duplicate the article. With an `article_id`, GET the article
   and compare `updated_at` to `last_known_updated_at`; a mismatch refuses with
   both timestamps. A set `article_id` with no timestamp refuses and says to run
   `pull`. The live-demotion refusal stays (`live=False` on a live article needs
   `unpublish=True`).
6. Back up the stored title and body to `backup_dir`.
7. **Upload each local image, then rewrite its `src` in `workdir/article.html`
   to the returned `content_url` before the next upload.** A failure midway
   leaves the already-uploaded images as Zendesk URLs on disk, so a re-run skips
   them. The draft-then-live second run finds no local images and uploads
   nothing. The 409 retry stays.
8. `PUT` article fields (`author_id`, `user_segment_id`, `permission_group_id`,
   `label_names`); save `last_known_updated_at`.
9. `PUT` the translation (`title`, `body`, `draft`); GET the article and save
   `last_known_updated_at` again, before read-back, so a read-back failure never
   leaves the guard blaming someone else's edit.
10. **Read back.** Title must match. The set of attachment ids in the sent body
    (`/hc/article_attachments/<id>`) must be a subset of those in the stored
    body.
11. **Report orphans** from `GET /help_center/articles/{id}/attachments.json`:
    every attachment id not referenced in the sent body. Reported, never
    deleted.

`PublishResult` keeps `article_id`, `html_url`, `draft`, `uploaded`,
`orphaned_ids` and `backup`. `reused` is dropped: reuse is no longer a per-image
decision.

Removed: `sha256_of`, the `Article.attachments` field, and every read or write
of the `attachments` key. `load_article` and `save_state` stay, reading and
writing the scratchpad folder.

### Skill (`SKILL.md`)

- Description: drop "publish docs/help-center/<slug>"; add editing or updating
  an existing article as a trigger.
- Non-negotiables gain two rules:
  - The working folder lives in the session scratchpad; the publisher refuses
    anything else.
  - Before the first Zendesk write in a session (publish, unpublish, archive,
    permission change), if auto mode is on: stop, name the exact command about
    to run, and ask the operator to switch to manual mode (Shift+Tab). Run it
    only after they confirm, then say they can switch back. Reads (`pull`,
    searches, dry runs) stay in auto. Auto mode's classifier judged an identical
    archive script differently minutes apart on 2026-09-29; manual mode replaces
    that with a prompt the operator approves.
- New article flow:
  1. Compose `article.html` and `article.yml` in `<scratchpad>/zendesk/<slug>/`.
  2. PII gate for each image (unchanged wording).
  3. Mode switch.
  4. `publish(live=False)`; the user opens the draft signed in. This is the
     preview: the draft shows the sanitizer's real output.
  5. `publish(live=True)`; the user confirms the page renders.
- Edit flow:
  1. `pull(article_id)`.
  2. Edit `article.html`.
  3. `preview()`, then serve the workdir with `uv run python -m http.server` in
     the background. The Codespace forwards the port privately; the user opens
     it in a browser or VS Code's Simple Browser. No preview extension is
     installed, so this is the zero-install route.
  4. PII gate for any new image.
  5. Mode switch.
  6. `publish(live=True)`; the user checks the page signed in.
- Runner: each call goes through a throwaway
  `tests/test_zz_zendesk_<id or slug>.py` that holds only the workdir path and
  flags, run with `uv run pytest <file> -s`, deleted afterward.
- Keep: the design-system snippets and README pointer, the sanitizer rules, the
  PII gate, the pytest credential path, `PublishError` messages shown verbatim.
- Titles in examples are plain sentences. No example uses a
  `PowerSchool Admin ::` prefix today, so nothing changes there.

### References and repo config

- `references/zendesk-api.md`: add rows for Pull (article, translation) and the
  attachment list; rewrite the `last_known_updated_at` trap for the scratchpad
  file; reword the verified-live note "reused the recorded attachment" to the
  body-rewrite mechanism.
- `.gitignore`: remove `docs/help-center/*/images/`.
- `mkdocs.yml`: remove `help-center/` from `exclude_docs`.
- `.trunk/trunk.yaml`: keep the design-system export ignore.
- The 2026-09-29 spec and plan under `docs/superpowers/` stay as written.

## Testing

### Unit (`tests/zendesk_help_articles/`)

Rewrite in place. `FakeSession` gains a route for
`GET /help_center/articles/{id}/attachments.json`. Cases:

- `pull` round trip, including a null segment becoming `everyone`.
- `pull` refuses an existing `article.html` and a workdir inside the checkout.
- `preview` writes the shell with the body inside.
- `publish` refuses a workdir inside the checkout before any network call.
- Every local image needs approval; a missing or out-of-folder image refuses
  before any network call.
- `src` is rewritten on disk after each upload, including after a failure on a
  later image.
- A body with only Zendesk URLs uploads nothing.
- Orphans come from the attachment list.
- Read-back passes on full and shortened attachment urls and fails on a missing
  id or a title mismatch.
- A set `article_id` with no timestamp refuses and names `pull`.

Carried over: client auth and endpoints, visibility resolution, the 409 retry,
request timeouts, the live-demotion refusal, `_iso_z` normalization.

### Live acceptance

One throwaway pytest file against a throwaway draft article, never a real one,
run in manual mode:

1. Create and publish the article as a draft with one image.
2. `pull` it into a fresh workdir and publish unchanged: zero uploads.
3. `pull` again, change the translation with a separate API call, then publish:
   the guard refuses.
4. `git status` in the checkout shows no new files but the throwaway test.
5. Archive the throwaway article, with the operator's approval.

## Out of scope

- Deleting the remote branch of closed PR #5627. That is the operator's step;
  the branch-delete push is blocked for Claude.
- Matching attachments by content hash. Zendesk's attachment list returns no
  hash, and the body-rewrite mechanism meets the zero-upload criterion without
  one.
