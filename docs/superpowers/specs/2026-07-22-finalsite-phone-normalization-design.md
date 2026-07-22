# Finalsite Contact Phone Normalization — Design

Issue: [#4498](https://github.com/TEAMSchools/teamster/issues/4498) (follow-up
to [#4495](https://github.com/TEAMSchools/teamster/pull/4495))

## Problem

Finalsite emergency-contact phone values carry junk that flows through to the
DeansList `contacts.txt` feed:

- **Invisible Unicode control/formatting characters** — `U+202A`/`U+202C` bidi
  wrappers, `U+00A0` non-breaking space, `U+2011` non-breaking hyphen (render as
  `‚Ä™`/`¬†`/`‚Ä¨` mojibake). From parents pasting numbers out of a phone's
  contacts app.
- **Free-text** — labels ("Guardian Emergency Pickup"), the word "Mobile",
  partials ("52771", "-4069").

These live in the free-text emergency phone custom attributes
(`emrg_N_phone_*`), so they affect only emergency slots — `contact_1` (from
Finalsite's typed phone fields) is clean. The pattern is present across all four
Finalsite instances, roughly proportional to volume: ~40 control-char and ~95
free-text emergency mobiles network-wide.

## Design

### `clean_phone()` macro

New macro in the finalsite package (`src/dbt/finalsite/macros/`). Normalizes a
raw phone string to a canonical **10-digit US** string, or NULL when the value
is not a usable phone:

- Strip to digits (`regexp_replace(<col>, r'\D', '')`) — removes control chars,
  formatting punctuation, and free-text labels.
- If the result is 11 digits leading `1`, drop the `1`; if 10 digits, keep it;
  otherwise NULL.

Reasoning (from prod profiling of all phone values): ~94.8% are already 10
digits, 1,778 are 11-digit-leading-`1`, and only ~61 network-wide are too-short
/ 12+ / typos (NULLed — unusable). No meaningful international population to
preserve.

**No display formatting** (no parens/dashes) at this layer — a clean digit
string is the most flexible canonical form; each extract formats for its own
target. DeansList already ingests formatted numbers, so digits satisfy its "Only
numbers or x" rule without locking in a presentation.

Implementation note: to respect the repo's max-one-level-of-nesting /
no-repeated-expression convention, stage `regexp_replace(<col>, r'\D', '')` as a
named `*_digits` column in a CTE, then canonicalize that column — rather than
repeating the `regexp_replace` inside the macro. The plan will settle the exact
shape.

### Placement — `int_finalsite__student_contacts`

Apply `clean_phone()` to the four output phone columns (`phone_mobile`,
`phone_home`, `phone_work`, `phone_primary`) in the finalsite package
`int_finalsite__student_contacts` — the single point where the `contact_1` and
emergency branches converge. `phone_daytime` is always NULL and is skipped.

This is the earliest single chokepoint that catches every slot, and every
downstream consumer inherits clean phones (DeansList
`rpt_deanslist__family_contacts`, Focus `rpt_focus__*`, Clever
`rpt_clever__students`, the contacts dimension / bridge). A pure
`stg_finalsite__contacts` fix cannot reach the emergency phones — they live
inside its `custom_attributes` array, not as scalar columns.

## Rollout

Value-only change to a finalsite package model (no column added/renamed), so
kipptaf CI compiles unchanged and corrected values land after the next Dagster
prod rebuild of the district `int_finalsite__student_contacts` tables. Validate
locally via a consuming district build (e.g. `kippnewark`) with `--defer`.

## Validation

- Add a dbt unit test on `int_finalsite__student_contacts` (built via a district
  project) mocking garbled / free-text / invalid phone inputs and asserting the
  cleaned digit output (and NULL for unusable values).
- Build `int_finalsite__student_contacts` locally with `--defer`; confirm row
  counts are unchanged and spot-check known-garbled students before/after (PII
  stays local).
- Confirm downstream consumers still build (`rpt_focus__*`,
  `rpt_clever__students`, `int_students__contacts`,
  `rpt_deanslist__family_contacts`).

## Out of scope

- Formatting phones for display in any specific consumer (each extract owns its
  format).
- Fixing the data at the Finalsite source / data-entry side (this normalizes on
  read).
- Extension handling (`x1234`) and international numbers (negligible volume;
  NULLed if not 10/11-digit US).
