# Launch page: build, validation, and CI gate

Design for productionizing the launch page generator and building the CI gate
that must exist before it can publish. Companion to the launch page design,
which settles what the page is; this settles how it gets built and what stops it
shipping broken.

That companion is **not on `main` yet** — it lives on PR #4762 at
`docs/superpowers/specs/2026-08-06-launch-page-design.md`. Every reference to it
below is by PR number rather than by relative link, because a relative link
would resolve to nothing for anyone reading from `main` until #4762 merges.

## Context

`src/launch/links.yml` holds 46 tool entries scraped from the Google Site and
merged in #4763. Verification is in progress on #4767. Only `status: verified`
entries publish, and **zero of 46 are verified on `main` today**.

That makes now the safest moment to stand up the pipeline: it cannot publish
anything wrong, because it has nothing to publish. When #4767 merges, nine
entries flip to verified at once, and that merge becomes the first live publish.
The MkDocs deploy workflow also fires on `docs/**`, so a catalog that fails
validation on `main` freezes **all** documentation publishing. The gate has to
exist before that merge, not after.

## What this delivers

- `src/launch/build.py` — a four-function module, unit-testable without git,
  temp files, or subprocesses
- Two-tier validation, so in-progress entries never block a commit but nothing
  reaches staff malformed
- A minimum-verified threshold below which no page is generated at all
- Generation through an MkDocs `on_files` hook
- `tests/launch/`, a `conftest.py` that makes the module importable, and a
  pytest PR workflow scoped to it
- A downloadable preview of the rendered page on every catalog PR

## Architecture

```text
  src/launch/links.yml      catalog, 46 entries, each with status:
  src/launch/groups.yml     group defs, families, promos, publish threshold
  src/launch/template.html  page shell, __CATALOG__ placeholder
            |
            v
  src/launch/build.py
      load()      read the three files from the working tree
      select()    keep only status: verified          -- partitions, never exits
      validate()  tier 1 over all entries, tier 2 over selected
                    |
                    +--> errors -> raise CatalogError, listing every problem
      render()    below minimum -> return None, log the count
                  otherwise     -> inject JSON, RETURN an HTML string
            |
            v
  docs/hooks.py :: on_files
      File.generated(config, "launch/index.html", content=html)
            |
            v
  site/launch/index.html -> gh-pages -> /teamster/launch/
```

One entry point, three callers: `mkdocs serve` locally, `mkdocs build` in the PR
gate, `mkdocs gh-deploy` on merge. There is no second code path to drift.

### Why `on_files` and not `on_pre_build`

The obvious design — write `docs/launch/index.html` during `on_pre_build` and
let MkDocs collect it — **causes an infinite rebuild loop under
`mkdocs serve`**. Measured on a minimal project: one edit to a source file
produced 61 builds in 30 seconds, roughly two per second, indefinitely.

`serve.py` watches `docs_dir` recursively, and livereload clears its
`_want_rebuild` flag _before_ running the build, so the hook's own write is
re-detected as a user change mid-build. Identical content does not help; writing
the file bumps its mtime.

`File.generated(config, src_uri, content=...)` — present in mkdocs 1.6.1, which
is what resolves here — registers a virtual file that never touches `docs_dir`.
Verified against a minimal project: the page lands at `site/launch/index.html`,
`docs_dir` stays clean, the file is absent from `sitemap.xml`, and a single edit
produces two builds rather than 61.

This also removes the need for a `.gitignore` entry and eliminates a class of
bug where a stale generated file lingers in a local checkout.

### `render()` returns a string

Nothing in `build.py` writes to the filesystem. The hook decides where output
goes. This is what makes every test run on in-memory data, and it is a
structural guarantee that the serve loop cannot return.

## Validation rules

Selection runs **before** validation, so tier 2 knows which entries it is
judging. Getting this backwards would force every rule into tier 1.

`select()` only partitions — it never short-circuits. **Validation always runs
in full, including below the publication threshold.** The threshold is checked
in `render()`, after every rule has been applied, so it suppresses output
without ever suppressing a check. Putting the short-circuit in `select()` would
mean the entire pre-threshold window — today, and for a long stretch after #4767
lands nine of 46 — ran with no structural validation on the build path at all.

### Tier 1 — every entry, regardless of status

| Rule                                                             | Why                                                            |
| ---------------------------------------------------------------- | -------------------------------------------------------------- |
| `links.yml` parses as a list of mappings                         | Everything else depends on it                                  |
| `id` present, unique, matching `^[a-z0-9_]+$`                    | Duplicates surface at the worst possible moment                |
| `name` present and non-empty                                     | Nothing can reference an unnamed entry                         |
| `url` present, scheme is `https`                                 | A staff-facing link must not be plaintext                      |
| `system` in the nine-value enum documented in `README.md`        | The prototype hard-codes four; the other five degrade silently |
| `status` in `{needs-review, verified}`                           | A typo would silently unpublish an entry                       |
| `access`, if present, is exactly `limited`                       | Prototype treats any truthy value as limited                   |
| `regions` values all in `{newark, camden, miami, paterson, all}` | Unknown regions render blank                                   |
| `groups.yml` parses, with `groups`, `families`, `promos` present | Same                                                           |
| Every family member in `groups.yml` names a real entry           | A rename silently drops a tool                                 |
| Every family names a real group id                               | An unknown group throws before anything renders                |
| Every promo card has a non-empty `url` that is not `#`           | Four of five point at `#` today and would render as dead links |

### Tier 2 — `status: verified` entries only

| Rule                                                  | Why                                                 |
| ----------------------------------------------------- | --------------------------------------------------- |
| `description` present and non-empty                   | An unlabelled tile is useless                       |
| `audiences` non-empty, all values known               | Four entries have none today                        |
| A family member carries exactly one region, not `all` | Three GPA Rosters render blank buttons without this |
| `guide`, if present, is `https`                       | Same reason as `url`                                |

A half-finished `needs-review` entry never fails CI. Flipping one to `verified`
while it is still missing a description does, and the error names the entry and
the field.

### Deferred

`group` present on every entry and resolving to a known group id. The launch
page design on #4762 records `group` as a required per-entry field with a logged
rationale ("role tags and topical domains are different axes"), and that is the
right shape — a side table in `groups.yml` has to stay exhaustive, which is
precisely the coupling that lets two individually-green PRs break `main`
together.

Adding it means touching all 46 entries while 37 are in flight on #4767.
Sequenced into a follow-up PR after that merges.

**What this PR renders in the meantime.** `render()` emits a flat, alphabetical
list of verified entries — families still collapse into one row with per-region
sub-links, since that is driven by `groups.yml` and not by `group`. The grouped
layout arrives with the field. Nothing is lost by waiting: the threshold below
means no page is generated at all until well after the follow-up lands, so the
flat layout is never what staff see. It exists so `render()` is complete and
testable now rather than half-written.

Accordingly `groups.yml` in this PR carries group definitions, families, promos
and the threshold — but no entry-to-group map. The prototype's `assignments`
block is dropped rather than re-keyed.

## Publication threshold

Below a configured number of verified entries the hook generates **no page at
all**, logs the count, and lets the docs build succeed. `/teamster/launch/`
returns 404 until the catalog is genuinely ready.

This exists because the zero-verified page is not merely empty — it is broken.
With no tools the template falls through to its search-miss branch and renders
"No tool matches that", above a masthead reading `0 tools` and a footer
disclaiming `0 of 0 entries are still being verified`. Four of the five promo
cards in `groups.yml` point at `#`. The first live version would be five cards,
four of them dead, under an error message.

Gating on a count is cheaper than designing an empty state that should never be
seen, and it makes a broken intermediate page impossible rather than merely
unlikely.

The threshold lives in `groups.yml`, not in code. Seeded at **25** — over half
the catalog. Changing it is a one-line edit and the number belongs to the
catalog owner, not this design.

`groups.yml` content has no `status` field and therefore no publish gate of its
own. Promo cards with an empty or `#` URL are rejected by tier 1 rather than
rendered.

## CI surfaces

### The PR gate

A new `.github/workflows/pytest.yaml`, triggered on pull requests touching:

```yaml
paths:
  - src/launch/**
  - tests/launch/**
  - docs/hooks.py
  - mkdocs.yml
  - .github/workflows/pytest.yaml
```

`docs/hooks.py` and `mkdocs.yml` are in that list because once generation lives
in the hook, either can break the page without `src/launch/` changing at all.

Two steps: `uv run pytest tests/launch`, then `uv run --group docs mkdocs build`
followed by an upload of `site/launch/index.html` as a workflow artifact. A
reviewer downloads it and opens the real page before approving. The template
inlines all CSS and JS, so a single file opens standalone.

Below the threshold no page is generated, so there is nothing to upload. The
upload step sets `if-no-files-found: ignore` — the default is `warn`, which
would print a confusing warning on every PR until the catalog crosses the
threshold. The build still runs and the validation still gates; only the preview
is absent, which is correct, because there is nothing to preview.

**No `--strict`.** `mkdocs build --strict` fails on `main` today with exactly 80
warnings, every one an unresolvable relative link inside `docs/superpowers/**`
pointing out of `docs/` into `src/`. The live deploy passes only because
`mkdocs-gh-deploy.yaml` does not pass `--strict`. Fixing those 80 warnings is
unrelated work, and `--strict` buys nothing here: `build.py` raises
`CatalogError` on a validation failure, which fails the build strict or not.

### The deploy workflow

`src/launch/**` joins the `paths` filter in `mkdocs-gh-deploy.yaml`. Today that
workflow watches `docs/**` and `mkdocs.yml` only, so **merging a catalog change
currently triggers no deploy at all** — the launch page design's claim that
"merging a catalog change publishes it" is false until this lands.

Position in the list does not matter. `src/launch/**` and `docs/superpowers/**`
are disjoint prefixes, so no path can match both and the existing negation is
unaffected wherever the new pattern goes.

A catalog merge will trigger a full docs deploy rather than a partial one. That
takes about a minute and is acceptable.

### Prerequisite outside this work

The new check has no force until an admin adds it to ruleset `816683`, which
currently requires only `dbt Cloud` and `Trunk Check Runner`.

`strict_required_status_checks_policy` is `false` on that ruleset, meaning
branches need not be current with `main` before merging. The catalog has
cross-file exhaustiveness rules, so two PRs each green in isolation can produce
a broken `main`. Worth enabling alongside, or adding a merge queue for
`src/launch/**`.

## Testing

Four files under `tests/launch/`: pure Python, no Dagster import, no secrets.

### Making `src/launch/build.py` importable

There is no path by which a test can import it today. `pyproject.toml` packages
only `src/teamster`; there is no `[tool.pytest.ini_options] pythonpath`, no
`pytest.ini`, and `tests/conftest.py` does no path manipulation. `tests/` has no
root `__init__.py`, so pytest inserts only `tests/launch/` itself.

`tests/cube/test_cube_schema.py` is not the precedent for this — it never
imports `src/cube` code, it only reads YAML through `pathlib.rglob`. The nearest
real precedent is `tests/cube/test_mcp_server.py`, which reaches
`src/cube/mcp/server.py` through `importlib.util.spec_from_file_location`
precisely because no import path exists.

This design uses a **`tests/launch/conftest.py` that inserts `src` on
`sys.path`**, anchored on `Path(__file__).resolve().parents[2]`. Verified
empirically: `src/launch` imports as a PEP 420 namespace package with no
`__init__.py`, and a test importing `launch.build` passes.

Chosen over the alternatives because it is scoped to this one directory and has
no effect on the other 749 collected tests.
`[tool.pytest.ini_options] pythonpath` is global config on a tree that already
fails to collect. Adding `src/launch` to the hatch `packages` list would ship it
in the `teamster` wheel, which it is not part of. `spec_from_file_location`
works but is a heavier idiom than a module we control needs.

It also matches what `docs/hooks.py` does, so there is one mechanism to
understand rather than two.

### The files

| File               | Covers                                                               |
| ------------------ | -------------------------------------------------------------------- |
| `test_validate.py` | One test per rule, both tiers, on constructed dicts                  |
| `test_select.py`   | Status filtering, and that validation still runs below threshold     |
| `test_render.py`   | Threshold suppression, script-tag escaping, families, `access` badge |
| `test_catalog.py`  | Runs the real `src/launch/*.yml` through tier 1                      |

`test_catalog.py` is the one that actually protects `main`. The others protect
the rules themselves.

The escaping regression is worth naming: `json.dumps` does not escape `<`, so a
catalog value containing a closing script tag terminates the block early and
blanks the page with an exit-zero build. The prototype escapes `<`, `>`, and `&`
at the Unicode level; the test pins that behaviour.

## Failure handling

| Failure                               | Detected by                       | Behaviour                                          |
| ------------------------------------- | --------------------------------- | -------------------------------------------------- |
| `links.yml` unparseable               | tier 1                            | `CatalogError`, docs build fails                   |
| Duplicate or malformed `id`           | tier 1                            | Same                                               |
| Unknown `system`, non-https `url`     | tier 1                            | Same                                               |
| Family names a missing entry          | tier 1                            | Same                                               |
| Verified entry missing a description  | tier 2                            | Same                                               |
| Fewer verified entries than threshold | `render()`, after full validation | No page emitted, docs build succeeds, count logged |
| Catalog valid, rendered page wrong    | **Not detected**                  | Known gap — the preview artifact is the mitigation |

Errors accumulate rather than short-circuit: one build reports every problem, so
a contributor fixes them in one pass instead of one per push.

## Fixes carried from the prototype

The prototype at `.claude/scratch/launch-prototype/` is the starting point. It
is gitignored and therefore **not checkable by a reviewer**, so the claims below
about its behaviour have to be taken on trust until the implementation PR brings
the code into the repo, where each becomes a diff.

Two of the data claims that motivate the rules do not depend on the prototype
and can be checked against `main` now: `links.yml` contains three GPA Roster
entries (`gpa_roster_camden`, `gpa_roster_miami`, `gpa_roster_newark`) and
exactly four `regions:` keys in the whole file, all four on the Contact Info
Feeds — so the three Rosters carry none. The promo-card claim is prototype-only,
since `groups.yml` does not exist in the repo yet. Carried across as-is: family
validation, the script-tag escaping, the region accent mapping. Fixed on the
way:

- Reads `git show origin/main:src/launch/links.yml`. Fails outright under a
  shallow CI checkout, and reads the wrong tree in any case.
- Shells out to `git log` for a "last updated" stamp. Under `actions/checkout`
  the path-filtered form returns empty. `GITHUB_SHA` is not a substitute — it is
  a commit id where a human-readable date belongs. Either set `fetch-depth: 0`
  or use the unfiltered tip-commit date, which does resolve at depth 1. This
  design takes the tip-commit date and omits the stamp when it cannot be
  resolved; a missing date is not worth failing a build over.
- `assignments` keyed on the display `name`, a string that changes when someone
  edits a title. Superseded by per-entry `group` in the follow-up PR.
- `"limited": bool(e.get("access"))` — truthy for any value, so `access: open`
  would render a "Limited access" badge. Tier 1 now constrains the value and the
  test is `== "limited"`.
- The description substring sniff for `limited access` goes away with it.
- Hard-coded four-value `SYSTEMS`; the README documents nine.
- `regions: [all]` is documented as legal but unhandled — yields a blank label
  on a normal entry and an error on a family member.
- Loads webfonts from `fonts.googleapis.com`. A staff-facing page should not
  reach a third party for a typeface; falls back to a system stack.

Two housekeeping items in the same change: declare `pyyaml` in the `docs`
dependency group — it currently resolves only transitively through mkdocs — and
add `exclude_docs: hooks.py` to `mkdocs.yml`, since `docs/hooks.py` is inside
`docs_dir` and is currently served at `/teamster/hooks.py`.

## Out of scope

Recorded so the omissions are deliberate rather than forgotten.

- Wiring the build into the deploy job beyond the `paths` filter
- The per-entry `group` field and grouped rendering — follow-up PR after #4767
- `tests/cube` remains unprotected by CI, as does the rest of `tests/`
- The 80 pre-existing `docs/superpowers` link warnings
- The `pythonpath` config that would let the full test tree collect. This is a
  separate, pre-existing problem:
  `tests/sensors/sftp/test_sensors_sftp_renlearn.py` does
  `from tests.utils import ...` and dies at collection, taking 749 tests with
  it. The `tests/launch/conftest.py` shim above does not touch it and is not
  blocked by it.
- The Drive sharing check and its admin identity
- Retiring the Google Site

## Open questions

- **The threshold number.** Seeded at 25; belongs to the catalog owner.
- **Whether to enable `strict_required_status_checks_policy`** on ruleset
  `816683`, or add a merge queue for `src/launch/**`.
- **Whether `views.yml` is retired.** It still exists on `main` with per-view
  titles and intro copy. The launch page design says that copy moves into the
  template, but the prototype template contains none of it.

## Decisions log

| Decision                                        | Rationale                                                                                       |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Generate at build, do not commit the page       | No generated artifact in git; the preview artifact covers reviewability                         |
| `on_files` with `File.generated`                | `on_pre_build` writing into `docs_dir` loops `mkdocs serve` at two builds per second            |
| `render()` returns a string                     | Makes the loop structurally impossible and every test in-memory                                 |
| Select before validate                          | Tier 2 cannot exist otherwise                                                                   |
| Threshold checked in `render()`, not `select()` | Validation must run in full below the threshold, or the pre-launch window has no gate at all    |
| `tests/launch/conftest.py` path shim            | Scoped to one directory; global pytest config would touch a tree that already fails to collect  |
| Two-tier validation                             | In-progress entries must not block commits; published entries must not be malformed             |
| Threshold gate instead of an empty state        | The zero-verified page renders an error message, not an empty page; gating makes it unreachable |
| pytest scoped to `tests/launch`                 | The full tree does not collect; a blanket job turns this into a test-infrastructure project     |
| No `--strict`                                   | Fails on `main` today for unrelated reasons, and buys nothing over `CatalogError`               |
| Defer per-entry `group`                         | 37 entries in flight on #4767; the field is right, the timing is not                            |

Refs #4818, #4761
