---
name: zendesk-help-articles
description:
  Use when writing or publishing a KTAF Zendesk Help Center article ("write a
  help article for X", "draft the Zendesk article", "publish
  docs/help-center/<slug>", a re-publish after an edit), when searching the Help
  Center for an existing article ("is there a help article on X"), when a
  published article shows the wrong author, its body did not change after an
  update, or its images do not render, or when asked whether the Dagster
  ZendeskResource or a Zendesk MCP can publish articles.
---

# Zendesk help articles

Two phases. Author composes `article.html` from the vendored design-system
snippets. Publish pushes an article folder through the Help Center REST API.
Enter either one.

## Non-negotiables

- Read `references/design-system/README.md` before writing any article HTML.
  Inline styles only; `margin` only on `<table>`; `<div>` not `<p>` inside a
  `<td>`; empty elements are deleted; the sanitizer runs at render, so the
  stored body proves storage, not appearance.
- Read `references/zendesk-api.md` before any publish.
- The publisher runs only under pytest, through a throwaway
  `tests/test_zz_publish_<slug>.py`, deleted afterward. A bare `uv run python`
  has no credentials. Neither the Dagster `ZendeskResource` (scope
  `read users:write`) nor any connected MCP can write to the Help Center.
- Draft first for a new article. Going live is a second call with `live=True`,
  after the user has seen the draft. An article that is already live is updated
  in place with `live=True`; the publisher refuses `live=False` on it unless
  `unpublish=True`, because Zendesk has no draft of a live article and the page
  would vanish for readers.
- No image uploads without the PII gate below.

## Article folder

```text
docs/help-center/<slug>/
  article.html   body only, no <html> shell
  article.yml    title, section_id, author_id, labels; optional user_segment,
                 permission_group; publisher-owned article_id,
                 last_known_updated_at, attachments
  images/        screenshots, gitignored, referenced by relative path
```

`author_id` is required. Visibility defaults to the "Signed-in users" segment
and the "Agents and admins" permission group; override by name in the file.
`user_segment: everyone` is the only way to publish to everyone. The publisher
rewrites `article.yml` on every run, so comments in it do not survive.

## Search

To find an existing article, write `tests/test_zz_search_articles.py`:

```python
import sys

sys.path.insert(0, ".claude/skills/zendesk-help-articles/scripts")
from publish_article import search_articles  # noqa: E402


def test_search():
    search_articles("<words from the question>")
```

Run `uv run pytest tests/test_zz_search_articles.py -s`, read the titles and
urls, delete the file. The `zendesk-tickets` skill calls this after `research`
when a ticket's answer is an article.

## Author

1. Read `references/design-system/README.md`.
2. Compose `article.html` from `references/design-system/snippets/` in the
   README's article order: summary panel, in-this-article, `<h2>` sections with
   numbered steps and callouts, screenshots, related articles. No `<h1>`.
3. Reference every screenshot as `<img src="images/<name>.png">` inside the
   screenshot snippet.
4. Write `article.yml` with `title` and `labels`; leave `section_id` and
   `author_id` for the user to fill.
5. Ask the user to preview `article.html` in a browser, wrapped in the export's
   `sample-article.html` shell. Stop until they have.

## Publish

1. Run the PII gate for every image under `images/` that is new or changed: open
   it with the Read tool, state in plain words what is visible (school, grade
   band, any names, any count small enough to identify a student), and wait for
   the user's yes. Collect the approved relative paths.
2. Write `tests/test_zz_publish_<slug>.py`:

   ```python
   import sys
   from pathlib import Path

   sys.path.insert(0, ".claude/skills/zendesk-help-articles/scripts")
   from publish_article import publish  # noqa: E402


   def test_publish():
       result = publish(
           Path("docs/help-center/<slug>"),
           live=False,
           approved_images=frozenset({"images/01-home.png"}),
           backup_dir=Path("<session scratchpad>/zendesk-backups"),
       )
       print(result)
   ```

3. `cd <checkout> && uv run pytest tests/test_zz_publish_<slug>.py -s`.
4. Show the user the draft url and the report: uploaded, reused, orphaned
   attachment ids. Orphans are reported, not deleted.
5. On the user's yes, change `live=False` to `live=True`, run again, then delete
   the test file. For an edit to an article that is already live, skip the draft
   step and run with `live=True` once.
6. Ask the user to open the published page signed in and check it renders. The
   article is done when they confirm, not before.

A `PublishError` message is written for the user. Show it verbatim. The
overwrite guard names both timestamps and how to proceed.
