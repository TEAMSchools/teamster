# Zendesk Help Center API, as this skill uses it

Base: `https://<subdomain>.zendesk.com/api/v2`. Basic auth, username
`<email>/token`, password the API token. The token is an admin's, so every write
is production.

## Calls in publish order

| Step      | Call                                                     | Notes                                                                 |
| --------- | -------------------------------------------------------- | --------------------------------------------------------------------- |
| Resolve   | `GET /help_center/user_segments.json`                    | `user_segments[].{id,name}`; everyone is `user_segment_id: null`      |
| Resolve   | `GET /guide/permission_groups.json`                      | `permission_groups[].{id,name}`; note the `/guide/` prefix            |
| Create    | `POST /help_center/sections/{section_id}/articles.json`  | body `{"article": {...}, "notify_subscribers": false}`, `draft: true` |
| Fetch     | `GET /help_center/articles/{id}.json`                    | `updated_at` drives the overwrite guard                               |
| Back up   | `GET /help_center/articles/{id}/translations/en-us.json` | the stored `title` and `body`                                         |
| Images    | `POST /help_center/articles/{id}/attachments.json`       | see _Attachments_                                                     |
| Fields    | `PUT /help_center/articles/{id}.json`                    | `author_id`, `user_segment_id`, `permission_group_id`, `label_names`  |
| Publish   | `PUT /help_center/articles/{id}/translations/en-us.json` | `title`, `body`, `draft`                                              |
| Read back | `GET /help_center/articles/{id}/translations/en-us.json` | compare attachment ids, not urls                                      |

## Traps

- Title and body live on the translation. A body sent to the article endpoint is
  accepted and does not replace the live text.
- `author_id` defaults to the token owner. Set it on create and on every update.
  An end-user account works as author but displays its email address.
- Zendesk stores the body as sent except attachment urls, which it shortens to
  `/hc/article_attachments/<id>`. A body that references another article's
  attachment gets a cloned attachment with a new id.
- Reading the body back proves it was stored, not how it renders. The sanitizer
  runs on the published page. Someone signed in has to open it.
- The translation `PUT` changes the article's `updated_at` after the article
  `PUT` returned. Fetch the article again before saving `last_known_updated_at`.

## Attachments

Inline attachments belong to one article and inherit its user segment. 20 MB
each. `content_url` is read-only and assigned at creation.

Call shape as implemented: multipart `file` plus form field `inline=true` on
`POST /help_center/articles/{id}/attachments.json`, response
`article_attachment.{id, content_url, file_name}`.

Zendesk's current docs also list a `guide_media_id` on this endpoint, which
suggests a Guide media object may be required first. The live verification in
the implementation plan settles this; the outcome is recorded below.

### Verified live

2026-09-29, against `teamschools.zendesk.com`, article 43853618074263 (a
throwaway draft, deleted afterward):

- The direct multipart shape works.
  `POST /help_center/articles/{id}/attachments.json` with
  `files={"file": (name, handle, "image/png")}` and `data={"inline": "true"}`
  returned 201. No Guide media object and no `guide_media_id` were needed.
- Response fields observed: `id`, `url` (the API resource), `content_url`
  (`https://<subdomain>.zendesk.com/hc/article_attachments/<id>`),
  `relative_path` (`/hc/article_attachments/<id>`), `file_name`,
  `display_file_name`, `content_type`, `size`, `inline`, `locale` (null),
  `article_id`.
- The upload answered 409 with an empty body when it ran immediately after the
  article was created. The identical call succeeded seconds later. The publisher
  retries 409 up to 5 times with a growing delay and surfaces every other status
  at once.
- After the translation PUT, `GET` on the translation returned the `<img src>`
  as the full `content_url`
  (`https://teamschools.zendesk.com/hc/article_attachments/<id>`) for this
  article's own attachment. The shortened `/hc/article_attachments/<id>` form
  was seen earlier on the "How to access Tableau" article. Read-back matches on
  id so both forms pass.
- A re-run with no changes uploaded nothing and reused the recorded attachment.
  A stale `last_known_updated_at` aborted before any write with the overwrite
  guard message.
