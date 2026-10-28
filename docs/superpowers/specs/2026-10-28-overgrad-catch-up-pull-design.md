# Overgrad catch-up pull: design

Fixes [#5852](https://github.com/TEAMSchools/teamster/issues/5852).

## Intent

A full Overgrad pull pages through each list endpoint with no sort order. A
record edited mid-pull can move pages, so the pull can return it twice or skip
it. Duplicates break dbt uniqueness tests; skips leave a record missing until
the next pull, about 12 hours later, with no alert.

Fixed means each `id` lands exactly once, and every record edited during the run
is in the landed file.

## Approaches

- **Catch-up pull plus merge in the asset (chosen).** After the full pull, pull
  again with `updated_after` set to the pull's start time, and merge by `id`. It
  fixes both failures at the source, for every endpoint, in about 20 lines.
- **Accept the 12-hour gap.** Rejected: the fix is small, and `followings`
  staging has no dedupe to absorb duplicates.
- **Incremental sync
  ([#5818](https://github.com/TEAMSchools/teamster/issues/5818)).** Would also
  close the gap, but is back on the backlog: deleted records have no cheap
  signal.

## Design

- `students`, `admissions`, `followings` (the endpoints that support
  `updated_after`): record `start = datetime.now(UTC)` before the full pull.
  After it, pull with `updated_after = start - 1 second`, formatted as UTC ISO
  8601 with milliseconds and `Z`.
- Merge the two pulls by `id`; the newer `updated_at` wins. Parse `updated_at`
  with `datetime.fromisoformat` rather than comparing strings.
- `schools`, `custom_fields`, and the partitioned `universities` asset are
  unchanged.
- `OvergradResource.list()` merges caller `params` with `limit` and `page`
  instead of replacing them.
- No dbt changes. Existing staging dedupes stay.

## Constraints the design rests on

Checked live against the Newark API:

- `updated_after` accepts a full timestamp, compares at millisecond precision,
  and includes the boundary value.
- It reads times as UTC and ignores a UTC offset, so the value is always sent
  with `Z`.
- `updated_at` arrives as a string, always `YYYY-MM-DDTHH:MM:SS.mmmZ`.

The 1 second absorbs clock difference between the run pod and Overgrad.

## Known limit

A record edited during the catch-up pull itself (a few seconds) can still be
missed; the next scheduled run picks it up. This gets a `shortcut:` comment.

## Tests

Offline unit tests in `tests/resources/test_resource_overgrad.py` (resource
`params` pass-through) and a new test for the merge: a duplicate `id` keeps the
newer `updated_at`, and a record only in the catch-up pull is added.

## Left to the builder

Where the merge helper lives (resource or asset module) and its name.

## Revision 2026-10-28: cursor paging replaces the catch-up pull

Review on PR #6180 found that the catch-up pull does not fix the skip. A live
check showed list results are sorted by `updated_at` ascending, are stable
between pulls, and ignore sort parameters. So an edit to a record on a page the
pull already read moves that record to the end. Every record after it shifts up
one place, and the record at the next page boundary slides onto a page already
read and is skipped. That skipped record was not edited, so `updated_after`
never returns it. A delete mid-pull skips a record the same way.

The design is now:

- `students`, `admissions`, `followings` page with a cursor: each request sends
  `updated_after` set to the last `updated_at` seen, at page 1, until a page
  comes back short. Edits and deletes cannot shift records onto a page already
  read. An edited record shows up again at the end.
- When a full page shares one `updated_at`, the next request keeps the same
  cursor and steps to the next page.
- The boundary is inclusive, so the pull repeats records. `merge_by_id` reduces
  them to one per `id`, newer `updated_at` winning.
- The start-time math, the second pull, and the known limit above no longer
  apply.
