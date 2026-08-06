# Data Launch Page: git-sourced Zendesk pipeline

Design spec for phase 1 of migrating the data team launch page off Google Sites.

Refs #4761

## Problem

The launch page runs on a Google Site that is difficult to maintain.

- **The tool catalog is hand-duplicated across five role pages** (All, Teachers,
  Leaders, Operations, Regional/CMO) and has already drifted. The Operations
  page lists `Home Instruction Tracker` carrying the OKRTS description.
- **Nothing is version controlled.** There is no history, no review before
  content goes live, and no way for a coding agent to propose a change.
- **Link rot is silent.** A dashboard URL that dies stays on the page until a
  human notices.
- **The metrics glossary is a bespoke Apps Script web app** embedded in an
  iframe, backed by a Sheet. Custom code and content, both outside version
  control.
- **The site is fully public.** All twelve pages were verified anonymously
  readable during design. This was not a deliberate decision and is the reason
  authentication is a requirement rather than a nicety.

## Goals

1. Author content in git, reviewed by PR, editable by a coding agent.
2. Serve it from a surface every staff member can already reach with credentials
   they already hold.
3. Eliminate catalog duplication so drift is structurally impossible.
4. Turn content-review findings into CI checks so they cannot regress.
5. Retire the Google Site.

## Non-goals for phase 1

Okta bookmark tiles, the Claude discovery skill, the metrics glossary rebuild,
and blog go-live. Each is tracked separately. See _Out of scope_.

## Approach

**Author in git, serve from Zendesk, launch from Okta.** One source of truth,
multiple renderers. Phase 1 builds the source of truth and the Zendesk renderer
only.

Zendesk Help Center is the serving surface because every staff member can
already sign in to it through Okta, viewer seats are unlimited, and search and
mobile are solved. The data team already owns six Help Center categories there,
including one named `Data | Launch`.

### Rejected alternatives

| Option                           | Why not                                                                                             |
| -------------------------------- | --------------------------------------------------------------------------------------------------- |
| GitHub Pages with authentication | `TEAMSchools/teamster` is public; Pages on a public repo cannot be gated. Private Pages needs GHEC. |
| Cloud Run behind IAP             | Builds a second authenticated surface next to one that already exists and already has the audience. |
| Publish via a Dagster asset      | Couples content deploys to the orchestrator. Its one real edge, credential custody, is moot below.  |
| Keep the Google Site, mirror it  | Preserves the maintenance burden being escaped and creates a second source of truth.                |

Publishing runs in GitHub Actions rather than Dagster because it mirrors the
existing
[mkdocs-gh-deploy.yaml](../../../.github/workflows/mkdocs-gh-deploy.yaml)
pattern, publishes on merge, and introduces no new credential-custody category:
this repo already holds deploy credentials in Actions secrets for
`deploy-cube-mcp.yaml` and `dagster-cloud-deploy.yaml`.

## Source layout

```text
src/launch/
├── CLAUDE.md          # domain conventions
├── links.yml          # tool catalog, one entry per tool
├── views.yml          # presentation for the six catalog views
├── content/           # prose as markdown
│   ├── support.md
│   ├── our-team.md
│   ├── topline.md
│   └── blog/
├── manifest.yml       # source path -> Zendesk article id, CI maintained
└── publish/           # render and push
    ├── render.py
    ├── zendesk.py
    └── __main__.py
```

`src/<domain>/` follows the precedent in [src/cube/](../../../src/cube/), which
already mixes content, config, and code.

Deliberately **not** under [docs/](../../../docs/): that tree feeds the public
MkDocs site. Keeping gated content in a separate directory means the public
build cannot pick it up even if someone later edits nav configuration. Directory
isolation, not nav omission, is the leak guard.

## Catalog schema

```yaml
- id: attendance
  name: Attendance Dashboard
  url: https://example.tableau.host/attendance
  description: >
    Monitor ADA, chronic absenteeism, suspension, and daily attendance calls.
  audiences: [teachers, leaders, ops, region]
  system: tableau
  access: limited # optional badge
  guide: https://teamschools.zendesk.com/hc/en-us/articles/000 # optional
  regions: [all] # optional
```

Required: `id`, `name`, `url`, `description`, `audiences`, `system`. Optional:
`access`, `guide`, `regions`.

**`audiences` controls relevance, never visibility.** It determines which
curated views a tool appears in. It is not an access-control mechanism;
authorization stays the responsibility of the destination system.

`views.yml` holds presentation only: each view's title, intro prose, and sort
order. Membership is derived from tags. Facts and curation are not split into
separate files, because a tool's audience is a fact about the tool.

## Rendering

Six catalog articles are generated: `All` plus five role views.

- A role view lists every tool whose `audiences` contains that view's id.
- The `All` view renders every entry, unfiltered, always.
- **Every role view ends with a persistent link to `All`.** A mistagged entry
  costs a reader one extra click, never access.

Prose markdown renders to HTML article bodies. Zendesk stores article bodies as
HTML, so markdown conversion happens at render time.

## Publishing

Triggered on merge to `main`, path-filtered to `src/launch/**`. Never on
`pull_request_target`; fork pull requests do not receive secrets.

For each rendered output:

1. Look up the source path in `manifest.yml`.
1. If an article id exists, `PUT` the updated body and title.
1. If not, `POST` to create, then write the new id back to `manifest.yml` and
   commit it.
1. Stamp the article with a `src:{path}` label.

### Article identity

`manifest.yml` is authoritative and gives a reviewable diff plus an obvious
rollback. The `src:` label is a recovery mechanism if the manifest is ever lost
or corrupted, since articles can be re-discovered by label query.

### Safety properties

- **Idempotent.** Rendered bodies are compared against the live article before
  writing. A no-op run performs no writes, so `updated_at` does not churn and
  "recently updated" ordering in Guide stays meaningful.
- **Never destructive.** A tool removed from source causes its article to be
  archived (unpublished) and reported. Nothing is deleted.
- **Adopts in place.** Existing `Data | Launch` articles are mapped to their new
  sources and have their bodies replaced. URLs and search history survive.
  Creating fresh articles would orphan every existing bookmark and inbound link.

## Validation and content lint

Runs on every pull request. A failure blocks the build.

Schema checks:

- Required fields present, enum values known
- `id` values unique
- Every value in `audiences` exists in `views.yml`
- URLs well-formed and HTTPS

Content lint, derived from the site review:

- **Sign-in guidance that asserts credential reuse across systems.** Flagged as
  a phishing-facilitation pattern regardless of accuracy.
- **Personal phone numbers.**
- **Individual staff contact details** in content intended for distribution.

These three rules exist so that review findings become conditions CI enforces
rather than things a person has to remember.

## Testing

- **Unit tests on the render functions.** Pure, no network. Given a `links.yml`
  fixture, assert the rendered article bodies.
- **Unit tests on each lint rule**, with passing and failing fixtures.
- **Dry-run mode**, exercised on every pull request. Renders, diffs against live
  Zendesk, and reports what would change: _"updates 3 articles, creates 1."_
  Reviewers see the effect before merging. This is the safety property the
  Google Site never had.

## Failure handling and rollback

| Failure               | Behavior                                                                                                          |
| --------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Validation fails      | Pull request blocked. Nothing published.                                                                          |
| Publish fails partway | Job fails loudly. Manifest records only articles that succeeded. Re-run is safe because publishing is idempotent. |
| Bad content merged    | Revert the commit. The next run republishes the prior body.                                                       |
| Manifest lost         | Rebuild by querying articles for their `src:` labels.                                                             |

## Open dependencies

These are unresolved. None of them block writing the implementation plan, but
the first blocks execution.

1. **A Zendesk Guide API credential with article create and update scope.**
   Unverified; the credential available during design was read-limited. This is
   the first task of the implementation plan, ahead of any renderer work.
1. **Help Center visibility.** The Data categories are currently readable
   without signing in. Whether gating is applied per user segment on the Data
   categories only, or Help Center wide, is undecided and involves other
   departments. The pipeline treats visibility as configuration, never as an
   architectural assumption, so either outcome is supported without redesign.
1. **Existing article mapping.** Whether the current `Data | Launch` articles
   map cleanly onto new sources requires a content pass.
1. **Content rewrite ownership.** The bulk of phase 1 effort is writing, not
   engineering, and has no named owner yet.

## Out of scope for phase 1

| Item                   | Disposition                                                                                                                                                                                                 |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Okta bookmark tiles    | Follow-on spec. Reuses `links.yml`. Introduces Terraform, which this repo has none of today.                                                                                                                |
| Claude discovery skill | Follow-on spec. Reuses `links.yml`. Distribution surface undecided.                                                                                                                                         |
| Metrics glossary       | Becomes a catalog entry pointing at the existing Apps Script URL, which is reachable independently of the Google Site. The Site can therefore be retired on schedule without rebuilding the glossary first. |
| Blog go-live           | Posts migrate into the repo in phase 1. Publishing stays gated on comms review.                                                                                                                             |
| `PS - Demo` page       | Deleted. Empty page in the current nav.                                                                                                                                                                     |

## Tracked follow-ups

A review of the live site surfaced content remediation items spanning published
contact details, sign-in guidance that is both stale and inadvisable to publish,
and a team page needing rework. The decision was to track these as follow-ups
rather than patch the Google Site in parallel; they will be addressed as content
moves, and the lint rules above prevent reintroduction.

**Specifics are deliberately not recorded in this repository, which is public.**
They need a durable internal home. Assigning one is itself a follow-up.

## Decisions log

| Decision                                     | Rationale                                                                          |
| -------------------------------------------- | ---------------------------------------------------------------------------------- |
| Content plus one surface first               | Proves the author-in-git, serve-elsewhere loop end to end before adding renderers. |
| Tag once, generate views                     | Kills the five-way duplication that is the current maintenance burden.             |
| Every view links to the full manifest        | A tagging mistake costs a click, not access.                                       |
| Zendesk before Okta and Claude skill         | Reaches all staff. The other two reach subsets.                                    |
| GitHub Actions over a Dagster asset          | Matches existing deploy patterns, publishes on merge, no new credential category.  |
| Adopt existing articles rather than recreate | Preserves URLs, bookmarks, inbound links, and search history.                      |
| Review findings become lint rules            | Makes remediation durable rather than a one-time cleanup.                          |
