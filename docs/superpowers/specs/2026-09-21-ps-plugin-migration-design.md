# Move the PowerSchool gradebook audit plugin into teamster

Design for #5433. Brainstormed 2026-09-21. Facts about `TEAMSchools/ps-plugins`
measured against its `main` on 2026-09-21; re-read the source repo before each
PR, because it stays writable until it is archived.

## Decision

One feature spans three homes today. `TEAMSchools/ps-plugins` holds the
PowerSchool plugin that writes `U_EXPECTATIONS`. `teamster` holds the dbt models
that read it. A Claude skill that turns Teaching & Learning's planning sheet
into upload CSVs lives in Claude Desktop, ahead of the stale copy committed to
`ps-plugins`. Nothing checks that the three agree, and one person holds the
whole picture.

Copy the `ps-plugins` working tree into `teamster` at a new top-level
`ps-plugins/` directory, leave the five PowerSchool reference PDFs behind in
Google Drive, and archive the source repo private. Fold plugin maintenance into
the existing `gradebook-audit` skill rather than adding a second data-team
skill. Keep the end-user skill a separate, self-contained artifact, but move its
source into `teamster` and build its zip in CI.

Copy the tree; do not `git subtree add`. Subtree imports the source repo's full
history, and that history contains the five PDFs. `teamster` is public, so a
history import publishes them permanently. The source repo is young enough that
its history is worth less than that guarantee, and archiving it privately keeps
the history readable.

The migration is a relocation, not a rewrite. Plugin behavior, the deployed v2.5
package, and the dbt models do not change. What changes is where the files live
and what CI asserts about them.

## What moves

| Source path (`ps-plugins`)            | Destination (`teamster`)                  |
| ------------------------------------- | ----------------------------------------- |
| `gradebook-audit/`                    | `ps-plugins/gradebook-audit/`             |
| `scripts/build_plugin.py`             | `ps-plugins/scripts/build_plugin.py`      |
| `.github/workflows/build-plugin.yaml` | `.github/workflows/build-plugin.yaml`     |
| `CLAUDE.md`                           | `ps-plugins/CLAUDE.md`                    |
| `README.md`                           | `ps-plugins/README.md`                    |
| `docs/reference/README.md`            | `ps-plugins/docs/reference/README.md`     |
| `docs/reference/*.pdf` (5 files)      | Google Drive; file IDs in the index       |
| `.claude/skills/...` (flat copy)      | discarded; superseded by the Desktop copy |
| `.github/workflows/claude*.yaml`      | discarded; `teamster` has better versions |

`gradebook-audit/` keeps its internal shape exactly: `plugin.xml`,
`permissions_root/`, `queries_root/`, `docs/deployment_guide.md`, and
`WEB_ROOT/admin/gradebookaudit/` with its five HTML pages. The `gradebookaudit/`
directory level is load-bearing. `plugin.xml` registers the left-nav link at
`/admin/gradebookaudit/gradebook_expectations.html` and all four entries in
`permission_mappings.xml` reference the same prefix. Flattening it makes the nav
link 404 and binds the permissions to nothing, both silently. That level was
lost once already, during the earlier migration out of a Claude Desktop project.

`ps-plugins/` sits at the top level rather than under `src/`. `src/` holds
`cube`, `dbt`, and the `teamster` Dagster package, all of which `teamster`'s own
pipelines build or deploy. A PowerSchool plugin is installed by hand on three
PowerSchool instances. Keeping it out of `src/` also keeps it out of the path
filters that select `src/**`.

## The reference PDFs

`docs/reference/` holds five PowerSchool developer PDFs totalling about 2.66 MB,
plus a `README.md` index describing what each one covers. PowerSchool does not
want the PDFs published. `teamster` is public and stays public, so the PDFs do
not move with the tree.

They were committed to `ps-plugins` because nothing in that repo could reach
Google Drive. `teamster` does not have that limitation: it authenticates to
Drive through `src/teamster/libraries/google/drive/resources.py`. Move the five
files to the shared Drive folder and record each Drive file ID in the committed
index, which is the pattern the index already uses for the PowerSchool Data
Dictionary.

Record in the index how a reader fetches a PDF, so a successor does not have to
work it out: either through the Google Drive connector, or through a throwaway
script run under pytest, which is how `tests/CLAUDE.md` says to run credentialed
one-offs.

## Skills

### `gradebook-audit` absorbs plugin maintenance

The existing `.claude/skills/gradebook-audit/SKILL.md` already references
`ps-plugins` in three places and already owns the rollover procedure. Plugin
maintenance belongs to the same domain, so it goes in the same skill. Two skills
that must cross-reference each other drift; one skill that owns the chain does
not.

That file is 649 lines today and is the only skill in `.claude/skills/` with no
subdirectory. Adding plugin maintenance and end-user-skill maintenance to a flat
file makes it unreadable and unreliable. Restructure it into a routing
`SKILL.md` plus `references/` and `playbooks/`, following
`tableau-workbook-xml`, which routes in 263 lines to seven reference files.

The skill then owns three responsibilities:

1. The dbt models and the Tableau dashboard, which it already covers.
2. The PowerSchool plugin: how it is built, versioned, packaged, and deployed to
   each instance.
3. Propagating a plugin change into the end-user skill, in plain language.

Responsibility 3 gets a named playbook, with the instruction to avoid technical
detail written into the playbook itself. Otherwise plain language depends on
whoever is driving remembering to ask for it.

### The end-user skill stays separate and shippable

Teaching & Learning will not have repository access, so the end-user skill has
to remain a zip they install in Claude Desktop. Its source moves to
`ps-plugins/skills/gradebook-expectations-upload/`, seeded from the Claude
Desktop copy.

Seed from Desktop, not from `ps-plugins`. The committed copy is a single flat
`SKILL.md` of 30,781 bytes, last changed in commit `76e2add` on 2026-09-14. The
Desktop copy is restructured into `SKILL.md` plus `playbooks/rollover.md`,
`playbooks/refresh.md`, `playbooks/troubleshoot.md`, and four files under
`references/`. Troubleshooting exists only in the Desktop copy.

The zip must be self-contained. A skill installed in Claude Desktop cannot
resolve a path outside its own folder, so the end-user skill never references
`teamster` files, dbt models, or the warehouse. It reads the two Google Sheets
and its own `references/`, and nothing else.

A workflow builds the zip on push and attaches it to a release, so the download
link is stable and always current. Stamp a version inside `SKILL.md` and have
the `gradebook-audit` skill know the current one, so a report of "the screen
does not match the instructions" can be resolved against a known build.

### Applying ICM selectively

The restructure follows the parts of ICM (Interpretable Context Methodology)
that fit this repo: a small routing entry file, load only what the step needs,
one home per fact, an explicit change-impact map, and the walk test as the
acceptance criterion.

It does not adopt numbered stage folders, a `CONTEXT.md` per folder, or the
factory and product split. Plugin and dbt paths are load-bearing, the Claude
Code loader requires `SKILL.md` at the skill root, and no skill here emits a
per-run product into the tree. Issue #5434 records the full assessment and the
method, for the other skills queued for the same treatment.

## Contracts and checks

Three facts are shared across artifacts that cannot currently see each other.
Two are machine-checkable and become build failures. The third is not, and
becomes a pull-request gate.

### Column set

`gradebook_audit.named_queries.xml` declares nine columns: `id`, `school_level`,
`quarter`, `week_number`, `cnt_w`, `cnt_h`, `cnt_f`, `cnt_s`, `notes`. Two dbt
models read the same table:
`src/dbt/powerschool/models/sis/staging/odbc/stg_powerschool__u_expectations.sql`
and
`src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__u_expectations.sql`.

A check parses the named-query columns and compares them to the columns those
models select. A column added on one side and not the other fails the build.

### CSV header

`gradebook_expectations.html` holds the accepted header in three places: the
displayed template note at line 150, the generated template file at line 407,
and the import validator at line 428, which reads
`var expected = ['school level','quarter','week number','w','h','f','s','notes']`.
The end-user skill documents the same header in `references/csv-format.md`.

A check compares the validator's array to the documented header. A mismatch here
is the failure that has already happened once: a file whose header does not
match is rejected outright with "Header row does not match template", and
nothing imports.

Both checks extend `scripts/build_plugin.py`, which already validates that every
page path in the plugin XML resolves to a real file in the staged package. It is
standard-library only and exists because a silent failure of exactly this class
reached production once. Extending it beats introducing a second pattern.

### The walkthrough has no automated check

`references/powerschool-navigation.md` describes the screens the plugin's
`WEB_ROOT` pages render. No test can tell you that prose describing a user
interface has gone stale. A pull request that changes
`ps-plugins/gradebook-audit/WEB_ROOT/**` without changing `ps-plugins/skills/**`
fails a check that asks the author to confirm the walkthrough still matches and
to rebuild the zip if it does not.

## Isolation from the rest of the repo

A top-level `ps-plugins/` directory matches no path filter in
`deploy-prod-kippcamden.yaml`, `deploy-prod-kippmiami.yaml`,
`deploy-prod-kippnewark.yaml`, `deploy-prod-kipppaterson.yaml`,
`deploy-prod-kipptaf.yaml`, `deploy-cube-mcp.yaml`, or `pytest.yaml`. dbt Cloud
CI selects `state:modified` dbt nodes, and plugin files are not dbt nodes. No
Dagster code location redeploys and no dbt model rebuilds when a plugin file
changes.

Two workflows need a change:

`trunk-check.yaml` runs on every pull request; its `paths-ignore` lists only
`requirements.txt`. Prettier is enabled in `.trunk/trunk.yaml`, which has no
`ignore:` block, so prettier will reformat the plugin's HTML pages. PowerSchool
PSHTML markup does not survive a generic HTML formatter. Add an ignore entry for
prettier on `ps-plugins/**/*.html`.

`claude-code-review.yaml` filters on `src/**`, `tests/**`, `scripts/**`, and
`.github/workflows/**`, so plugin pull requests get no automated review today.
Add `ps-plugins/**` to that filter.

`.github/CODEOWNERS` has `* @TEAMSchools/admins` as the default, so every plugin
pull request pings the admins team. Add an explicit `/ps-plugins/` line naming
the intended owners.

## Retiring the source repo

After the migration lands and the plugin builds from `teamster`, set
`TEAMSchools/ps-plugins` back to private and archive it. Replace its `README.md`
with a pointer to `teamster` and to this spec. The repo stays readable as the
historical record, including the PDF history that did not come across.

The repo was public briefly on 2026-09-21 to unblock this design work. Treat the
five PDFs as having been exposed; that risk is accepted and is not reopened
here.

## Acceptance

The work is done when all of the following hold, each proven rather than
asserted:

- `ps-plugins/` exists in `teamster` with the plugin source, the build script,
  and the reference index. No PDF is in the working tree, and
  `git log --all --diff-filter=A -- '*.pdf'` on `teamster` returns nothing new.
- `uv run python ps-plugins/scripts/build_plugin.py gradebook-audit` builds and
  validates, and the resulting zip matches the deployed v2.5 package contents.
- Each contract check fails when one side is changed alone. Demonstrate the
  failure for both checks before claiming either works.
- The end-user skill zip builds, attaches to a release, and carries a version
  stamp.
- `gradebook-audit/SKILL.md` routes rather than holds content, and passes a cold
  read: an agent with no memory orients and acts from the entry file plus at
  most two more reads.
- `TEAMSchools/ps-plugins` is private and archived, and its README points here.

## Open items

The Claude Desktop zip of the end-user skill is a required input and is not yet
in hand. The implementation plan can be written without it, but the skill cannot
be seeded until it arrives.

Two known defects are in scope to record, and optionally to fix:

The Desktop skill's `playbooks/rollover.md` carries an unresolved gap. Its
date-to-week-number method needs at least one existing row in `ps_plugin_data`
to anchor against, and a genuine rollover run before the school year starts has
none. Nobody has confirmed how PowerSchool assigns week numbers in that case.
The gap was found in dry-run testing and has never been exercised against a real
start-of-year load.

The plugin's generated template and its `validSL` check accept `ES` as a school
level, but the end-user skill only ever produces `MS` and `HS` rows. Either
record why `ES` is accepted or remove it.
