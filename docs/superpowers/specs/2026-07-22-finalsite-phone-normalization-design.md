# Finalsite Contact Phone Normalization — Design

Issue: [#4498](https://github.com/TEAMSchools/teamster/issues/4498) (follow-up
to [#4495](https://github.com/TEAMSchools/teamster/pull/4495))

## Problem

Finalsite emergency-contact phone values carry junk that flows through to the
DeansList `contacts.txt` feed (and other contact consumers):

- **Invisible Unicode control/formatting characters** — `U+202A`/`U+202C` bidi
  wrappers, `U+00A0` non-breaking space, `U+2011` non-breaking hyphen (render as
  `‚Ä™`/`¬†`/`‚Ä¨` mojibake). From parents pasting numbers out of a phone's
  contacts app.
- **Free-text and malformed values** — labels ("Guardian Emergency Pickup"), the
  word "Mobile", extensions ("ext. 2606"), typo'd extra digits, placeholder junk
  ("00000000000"), and concatenated multiple numbers.

These live in the free-text emergency phone custom attributes
(`emrg_N_phone_*`), so they affect only emergency slots — `contact_1` (from
Finalsite's typed phone fields) is clean. The pattern is present across all four
Finalsite instances.

Goal: normalize phone values to a consistent standard for **all** contact
consumers (DeansList, Focus, Clever, the contacts dimension), not just
DeansList.

## Design

### `clean_phone()` macro

New macro in the finalsite package (`src/dbt/finalsite/macros/`). Normalizes a
raw phone to canonical **E.164** when it parses confidently, otherwise returns
the **de-garbled original** — it never returns NULL for a non-null input (a
malformed value passes through visibly so a downstream consumer can flag it).

E.164 is the international standard (`+` + 1-3 digit country code + national
number, max 15 digits), which handles US and international numbers uniformly.

Logic:

1. **De-garble** — strip non-printable / non-ASCII control characters and trim
   (`regexp_replace(p, r'[^\x20-\x7E]', '')`). This alone fixes the mojibake.
2. **Split an explicit extension** — if an `x` / `ext` / `extension` marker
   followed by digits is present, hold the trailing digits as the extension and
   parse the part before it as the number.
3. **Classify the number:**
   - **International** — leading `+` with a country code other than `1`, or an
     `011` international-dial prefix (→ `+<cc>`), with a plausible 8-15 digit
     length → emit `+<digits>` (E.164, preserved as entered — not NANP-forced).
   - **US / NANP** — resolves to 10 NANP-valid digits (`[2-9]XX[2-9]XXXXXX`),
     whether entered bare-10, `+1`-prefixed, or 11-digit leading `1` → emit
     `+1XXXXXXXXXX`. NANP validation (`[2-9]` area and exchange) naturally
     routes placeholders like `0000000000` to passthrough instead of a fake
     `+10…`.
   - **Otherwise** → passthrough the de-garbled original. This covers US numbers
     with a typo'd extra digit, unmarked international numbers (a non-US country
     code with no `+`), concatenated multiple numbers, and placeholder / junk
     values — all preserved visibly rather than dropped or mis-normalized.
4. On a confident parse, append `x<ext>` when an extension was split. The
   passthrough branch returns the de-garbled original unchanged.

Limitations (documented, acceptable):

- **No `libphonenumber` in BigQuery** — this is a best-effort regex normalizer,
  not a validating parser; it canonicalizes shape, it does not verify a country
  code/length is real.
- **Bare international without a `+`** is indistinguishable from US, so it falls
  to passthrough rather than being mis-tagged `+1`.

### Placement — `int_finalsite__student_contacts`

Apply `clean_phone()` to the four output phone columns (`phone_mobile`,
`phone_home`, `phone_work`, `phone_primary`) in the finalsite package
`int_finalsite__student_contacts` — the single point where the `contact_1` and
emergency branches converge. `phone_daytime` is always NULL and is skipped.

This is the earliest single chokepoint that catches every slot, and every
downstream consumer inherits normalized phones (DeansList
`rpt_deanslist__family_contacts`, Focus `rpt_focus__*`, Clever
`rpt_clever__students`, the contacts dimension / bridge). A pure
`stg_finalsite__contacts` fix cannot reach the emergency phones — they live
inside its `custom_attributes` array, not as scalar columns.

Consumers that need a different presentation format from this E.164 canonical at
their own extract layer (see DeansList below).

### DeansList extract formatting

`rpt_deanslist__family_contacts` applies a final transform to its `HomePhone`,
`WorkPhone`, and `CellPhone` columns: strip everything except digits and the
extension marker `x` (`regexp_replace(lower(phone), r'[^0-9x]', '')`),
satisfying the DeansList template's "Only numbers or x" rule. This keeps the US
country-code `1` (`+18623007240` → `18623007240`), keeps extensions (`…x216`),
and leaves international numbers as their country-code + national digits. It is
a thin per-consumer format step over the shared E.164 canonical, not a second
normalization.

## Data profile (rationale)

All phone values across the four instances (`phone_mobile` / `home` / `work` /
`primary`):

| signal                    | count  | disposition              |
| ------------------------- | ------ | ------------------------ |
| bare 10-digit             | 76,599 | US → `+1…`               |
| leading `+1`              | 3,378  | US → `+1…`               |
| bare 11-digit leading `1` | 347    | US → `+1…`               |
| leading `+` non-`1`       | 127    | international → `+<cc>…` |
| other                     | 162    | passthrough              |

The 162-value "other" tail profiled into: US numbers with a typo'd extra digit
(largest; recognizable US area codes), placeholder junk (all-zeros / all-nines /
blank), unmarked international (`+20` Egypt, `+84` Vietnam, `+60` Malaysia,
etc., entered without the `+`), concatenated multiple numbers, and explicit
extensions. Only the extensions are confidently normalizable; the rest pass
through by design.

## Rollout

The `int_finalsite__student_contacts` change is value-only (no column added /
renamed), so kipptaf CI compiles unchanged and normalized values land after the
next Dagster prod rebuild of the district tables; validate locally via a
consuming district build (e.g. `kippnewark`) with `--defer`. The
`rpt_deanslist__family_contacts` formatting change is a kipptaf model, so dbt
Cloud CI exercises it directly.

## Validation

- Add a dbt unit test on `int_finalsite__student_contacts` (built via a district
  project) covering representative inputs: a garbled US number (control chars →
  `+1…`), bare-10 and `+1` US, an international `+<cc>` number (preserved), an
  explicit extension (`+1…xNNN`), a placeholder (passthrough), and a typo'd
  extra-digit US number (passthrough).
- Build `int_finalsite__student_contacts` locally with `--defer`; confirm row
  counts are unchanged and spot-check known-garbled / international / extension
  students before/after (PII stays local).
- Confirm downstream consumers still build (`rpt_focus__*`,
  `rpt_clever__students`, `int_students__contacts`,
  `rpt_deanslist__family_contacts`).
- Confirm `rpt_deanslist__family_contacts` phone columns emit only digits and
  `x` (no `+`, parens, or spaces) — the DeansList "numbers or x" requirement.

## Out of scope

- Repairing malformed numbers (typo'd extra digits, concatenations) or adding a
  `+` to unmarked international numbers — passed through visibly for a consumer
  to flag.
- Reformatting phones for consumers other than DeansList (Focus, Clever, the
  contacts dimension read the E.164 canonical as-is; they can format at their
  own extract later if needed).
- Fixing the data at the Finalsite source / data-entry side.
