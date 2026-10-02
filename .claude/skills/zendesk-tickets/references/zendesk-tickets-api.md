# Zendesk Ticketing API, as this skill uses it

Base: `https://<subdomain>.zendesk.com/api/v2`. Basic auth, username
`<email>/token`, password the API token. The token is an admin's with no scope.
The client sends only GET requests, so the skill reads production and changes
nothing. Rate limit 700 requests per minute.

## Calls per operation

| Operation       | Call                                              | Notes                                                                                                                    |
| --------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| research, draft | `GET /tickets/{id}.json?include=users,groups`     | side-loads `users[]` (requester, assignee) and `groups[]`                                                                |
| research        | `GET /tickets/{id}/comments.json?include=users`   | cursor pages; `comments[].{author_id,public,plain_body,attachments}`                                                     |
| research        | `GET /users/{id}.json`, `GET /organizations/{id}` | requester and their organization                                                                                         |
| research, queue | `GET /search.json?query=...&sort_by=&sort_order=` | `results[]` mixed types; filter `result_type == "ticket"`; offset pages of 100, followed to `max_results` (default 1000) |
| resolve         | `GET /ticket_fields/20721852.json`                | `custom_field_options[].{name,value}`; name `A::B`, value a tag                                                          |
| resolve         | `GET /groups.json`                                | skip `deleted: true`                                                                                                     |
| resolve         | `GET /groups/{id}/memberships.json`               | `group_memberships[].user_id`                                                                                            |
| resolve, queue  | `GET /users/show_many.json?ids=1,2`               | names for ids                                                                                                            |
| resolve         | `GET /macros.json?active=true`                    | cursor pages                                                                                                             |
| draft_macro     | `GET /tickets/{id}/macros/{macro_id}/apply.json`  | `result.ticket` is the rendered change set; nothing is committed                                                         |

## Search syntax used

- `type:ticket` always first.
- `group_id:<id>` per group; repeated terms widen the match.
- `status<solved` for new, open, pending, hold.
- `requester:<user_id> created><YYYY-MM-DD>` for requester history.
- `custom_field_20721852:<tag>` for same-category tickets.
- Bare words search subject and body, ANDed. `research` uses the first 3 subject
  keywords: on 2026-09-30, all 4-6 words of eight recent Data subjects matched
  1-9 tickets (often only the ticket itself) while 3 words matched 1-161.

## Traps

- Cursor pagination: `meta.has_more` and `meta.after_cursor`, request param
  `page[after]`. Search uses offset pagination (`page=N`, `next_page` url); the
  client follows it to `max_results`, 1000 by default and Zendesk's own ceiling.
  `research` passes 11 for each similarity search, `queue` uses the default.
- The ticket's `custom_fields[]` carries tag values, not option names. Map
  through the field's `custom_field_options`.
- A comment's `public: false` is an internal note. The requester never sees it.
- The macro preview returns the whole ticket with the macro's changes applied.
  Only `status`, `priority`, `type`, `assignee_id`, `group_id`, `tags`,
  `custom_fields`, `comment`, and `email_ccs` count as changes (`CHANGE_KEYS`).

## Guards on drafts

- `public` on `draft_comment` must be the bool `True` or `False`. The draft's
  PUBLIC or INTERNAL label tells the user where to paste, so it comes only from
  their answer, never from `None`, `0`, or a string.
- A macro draft keeps only the keys the preview changed, and an `Assign to`
  macro whose preview sets status to solved or closed is refused whatever its
  title says.

## Verified live

2026-09-30, against `teamschools.zendesk.com`, ticket 483526 (Data group):

- `research` printed the header, one public comment, 39 requester-history rows,
  no same-category rows (the ticket had no Category), and 3 keyword rows.
  Comment keys observed: `attachments`, `audit_id`, `author_id`, `body`,
  `created_at`, `html_body`, `id`, `metadata`, `plain_body`, `public`, `type`,
  `via`. The ticket had no attachments, so the attachment shape is unverified.
- Repeated `group_id:` terms widen: `/search/count.json` gave 279 for Data, 123
  for Teaching & Learning, 402 for both in one query.
- `custom_field_20721852:<tag>` matches: 4606 tickets for one tag.
- Search returns `count`, `next_page`, `previous_page`, `facets`, `results`. The
  first `queue` run stopped at 100 rows with the newest tickets cut off;
  `search` now follows `next_page` up to 1000 results. The full queue was 402
  rows and took about 30 seconds.
- `users/show_many` silently drops ids past the first 100. `queue` on 402 rows
  showed raw ids until the client chunked the call.
- The macro preview returned `assignee_id`, `comment`, `custom_fields`,
  `group_id`, `priority`, `status`, `tags`, `type`: the ticket's current values
  plus the macro's changes, not a diff. Placeholders were rendered
  (`Hi <first name>`). `comment.body` came back as HTML with `<p>` tags and
  `comment.public: true`, so the draft display strips the tags to text.
