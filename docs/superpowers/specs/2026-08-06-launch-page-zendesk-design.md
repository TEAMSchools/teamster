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
- **The site is anonymously readable.** All twelve pages were verified
  accessible without signing in. Some of what it publishes should be behind a
  sign-in; a review of the specifics is tracked separately (see _Tracked
  follow-ups_).

## Goals

1. Author the tool catalog in git, reviewed by PR, editable by a coding agent.
1. Serve the launch page from a surface every staff member can already reach
   with credentials they already hold.
1. Eliminate catalog duplication so drift is structurally impossible.
1. Retire the Google Site.

## Non-goals for phase 1

Okta bookmark tiles, the Claude discovery skill, and the metrics glossary
rebuild. Each is tracked separately. See _Out of scope_.

## The content split

This is the load-bearing decision, and it is deliberate rather than incidental.

`TEAMSchools/teamster` is a **public** repository, and `docs/` is additionally
rendered to a public website. Anything committed here is world-readable
permanently, in git history. Directory placement does not change that.

Therefore content is split by whether it is safe to be public:

| Content                                              | Lives in | Rationale                                                                                                                                                                            |
| ---------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Tool catalog** (`links.yml`, `views.yml`)          | git      | Dashboard names, one-line descriptions, and URLs that resolve only behind SSO. An outsider gets a list of nouns and links that do not work. Already public today on the Google Site. |
| **Prose** (Our Team, Support runbook, Topline, Blog) | Zendesk  | Names individuals, describes operational detail, and carries contact routing. Authored directly in Guide, behind sign-in. Guide keeps article revisions.                             |

The rule, stated for `src/launch/CLAUDE.md`: **if it is not safe to post to the
open internet, it does not go in `src/launch/`.**

Two consequences worth naming:

- The Okta gate on Zendesk is for **audience and discoverability**, not
  confidentiality, for anything generated from git. That is an accepted and
  deliberate position, not an oversight.
- Prose is not version-controlled in git. It is versioned by Guide's article
  revisions, and a coding agent can still edit it through the Zendesk API — just
  not through a pull request.

## Approach

Author the catalog in git, generate six articles, publish them to Zendesk on
merge. Prose articles already in `Data | Launch` are left where they are.

Zendesk Help Center is the serving surface because every staff member can
already sign in to it through Okta, viewer seats are unlimited, and search and
mobile are solved. The data team already owns six Help Center categories,
including `Data | Launch`.

### Rejected alternatives

| Option                           | Why not                                                                                             |
| -------------------------------- | --------------------------------------------------------------------------------------------------- |
| GitHub Pages with authentication | `TEAMSchools/teamster` is public; Pages on a public repo cannot be gated. Private Pages needs GHEC. |
| Cloud Run behind IAP             | Builds a second authenticated surface next to one that already exists and already has the audience. |
| Publish via a Dagster asset      | Couples content deploys to the orchestrator, for what is a static render.                           |
| Private repo for gated content   | Solved instead by the content split above: sensitive prose never enters git at all.                 |
| Keep the Google Site, mirror it  | Preserves the maintenance burden being escaped and creates a second source of truth.                |

Publishing runs in GitHub Actions rather than Dagster because it mirrors the
existing
[mkdocs-gh-deploy.yaml](../../../.github/workflows/mkdocs-gh-deploy.yaml)
pattern and publishes on merge.

Note on credential custody: this repo's two deploy workflows differ.
`dagster-cloud-deploy.yaml` uses an Actions secret; `deploy-cube-mcp.yaml` holds
**no** Actions secret at all, authenticating by keyless Workload Identity
Federation and reading its runtime secret from GCP Secret Manager. A long-lived
Zendesk token in Actions secrets on a public repo is therefore a step away from
the more recent pattern, not a continuation of it. See Open dependency 2.

## Source layout

```text
src/launch/
├── CLAUDE.md          # domain conventions, including the public-content rule
├── links.yml          # tool catalog, one entry per tool
├── views.yml          # presentation for the six catalog views
├── manifest.yml       # hand-authored: view -> Zendesk article id and settings
└── publish/           # render and push
    ├── render.py
    ├── zendesk.py
    └── __main__.py
```

`src/<domain>/` follows the precedent in [src/cube/](../../../src/cube/), which
already mixes content, config, and code.

Not under [docs/](../../../docs/) because that tree is built and published as a
website. This is a separation of concerns, **not** a confidentiality control —
see _The content split_.

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
order. Membership is derived from tags.

## Rendering

Six catalog articles are generated: `All` plus five role views.

- A role view lists every tool whose `audiences` contains that view's id.
- The `All` view renders every entry, unfiltered, always.
- **Every role view ends with a persistent link to `All`.** A mistagged entry
  costs a reader one extra click, never access.

## Publishing

Triggered on merge to `main`, path-filtered to `src/launch/**`. Never on
`pull_request_target`; fork pull requests do not receive secrets.

**The managed set is exactly six articles, and CI only ever updates them.**
Creation is a one-time, deliberate act performed by a human (or a setup script)
outside the publish pipeline, because creation is where the irreversible
decisions live. This removes the entire create path from CI.

For each of the six views:

1. Read its `article_id` and `locale` from `manifest.yml`. A missing or null id
   fails the run loudly; CI never creates.
1. `PUT /api/v2/help_center/articles/{article_id}/translations/{locale}` with
   the rendered `body` and `title`.
1. Assert the article's `user_segment_id` still matches what `manifest.yml`
   declares, and fail if it has drifted.

**Article bodies are translation properties, not article properties.** Zendesk's
Update Article endpoint updates metadata only; per Zendesk's documentation it
"does not update translation properties such as the article's title, body, or
draft." A `PUT` to the article endpoint carrying a `body` can return `200 OK`
and change nothing — a silent no-op. Body writes must go through the
translations endpoint. This must be confirmed empirically before the renderer is
built (see _Implementation sequencing_).

### `manifest.yml`

Hand-authored and declarative — CI reads it and never writes it. Repository
rulesets forbid any direct push to `main` (four active rulesets, all with no
bypass actors, one enforcing `pull_request`), so a CI write-back is not merely
inadvisable, it is impossible.

Per view it declares: `article_id`, `locale`, `section_id`,
`permission_group_id`, `user_segment_id`, `position`, and a `content_hash` of
the last published body. Validation fails a PR that adds a view without a
complete manifest entry.

`user_segment_id` is **required and never defaulted**. Omitting it on creation
produces an article visible to everyone — which is precisely the condition this
project exists to correct.

### Safety properties

- **Idempotent.** Zendesk already provides this: per its documentation, the
  translations `PUT` "does not update the translation's `updated_at` value if
  the data in the request body matches the data in the translation." The
  pipeline additionally compares against the `content_hash` in `manifest.yml`
  rather than against a fresh `GET`, because Guide normalizes submitted HTML and
  does not preserve block wrapper elements across `GET` and `PUT` — a naive
  round-trip comparison would report a spurious diff on every run.
- **Removal is unpublish, not archive.** A view retired from source has its
  translation set to `draft: true`. Archiving in Zendesk is
  `DELETE /api/v2/help_center/articles/{id}` and is restorable only through the
  Guide UI, so the pipeline does not archive and its credential should not need
  `DELETE`.
- **Update-only.** CI cannot create, so it cannot duplicate.

## Validation and content lint

Runs on every pull request.

Schema checks:

- Required fields present, enum values known
- `id` values unique
- Every value in `audiences` exists in `views.yml`
- Every view in `views.yml` has a complete `manifest.yml` entry
- URLs well-formed and HTTPS

Content lint — deliberately narrow, because the catalog is names, descriptions,
and links, and legitimately contains none of the following:

- No email addresses
- No phone-shaped strings
- No sign-in guidance (the catalog links to tools; it does not explain how to
  authenticate to them)

These are decidable and near-zero-false-positive **on this corpus
specifically**. They are not a general content-safety mechanism, and they are
not what keeps sensitive prose out of git — the content split does that.

### Google-hosted tools need a sharing check

_The content split_ argues the catalog is safe to publish because its URLs
require sign-in. **That reasoning holds for Tableau but not automatically for
Google Drive.** A Tableau URL is gated by SSO no matter who holds it. A Drive
URL is gated by that file's sharing setting — and if a file is shared "anyone
with the link," the URL _is_ the access control. Publishing it in a public
repository hands it out.

This is not hypothetical: the catalog includes three GPA Roster spreadsheets,
which carry student-level academic data.

So any entry whose `system` is `google-*` carries an additional invariant: **the
underlying file must have no `anyone`-type permission.**

**The obvious implementation of that check does not work.** Drive's
`permissions.list` returns the full permission set only to a caller that
administers the file. For any other caller it returns just the owner — so a
naive assertion reads "no groups, no `anyone`" and passes, on a file it in fact
knows nothing about. That is a check that fails open, which is worse than no
check. This was hit during design: all four Student Contact Info Feeds returned
owner-only, while the data team confirms each is region-group shared with CMO
access and none is link-shared.

The check is therefore only meaningful when run as an identity that administers
the files — a Workspace admin credential or domain-wide delegation — and it must
**fail loudly on an owner-only result** rather than treating it as a pass.
Provisioning that identity is a prerequisite, not an implementation detail.

The three GPA Rosters were verified during design and are group-shared with no
link sharing. Their permission lists returned in full, which is itself the
signal that the reading identity administered them.

Where this runs matters. A pull-request check cannot be relied on — fork pull
requests receive no credentials, the same constraint that limits the dry-run.
And the risk is not mainly "someone adds a link-shared file today," which review
catches; it is "someone flips a file's sharing eighteen months from now," which
nothing catches. So the sharing assertion belongs in the **scheduled link-health
job** alongside liveness checking, where it runs with credentials on a cadence
and alerts on drift. Merge-time coverage is the reviewer checklist in
`src/launch/README.md`, which is best-effort by design.

That scheduled job is the one piece of this design that genuinely fits Dagster
rather than Actions: it is periodic, it alerts, and its results are worth
landing in the warehouse.

Validation will not block merge until `launch-validate` is added to the
`required_status_checks` ruleset, which currently lists only `dbt Cloud` and
`Trunk Check Runner`. That requires repo-admin rights and has lead time.

## Testing

- **Unit tests on the render functions.** Pure, no network. Given a `links.yml`
  fixture, assert the rendered article bodies.
- **Unit tests on each lint rule**, with passing and failing fixtures.
- **Dry-run mode** on pull requests. Renders and schema-checks always; performs
  a live diff only when a **separate read-only** Zendesk credential is present,
  and reports which mode it ran in. Fork pull requests get render-only, since
  they receive no secrets. The write credential is never exposed to a pull
  request job.

## Failure handling and rollback

| Failure               | Behavior                                                                                                                             |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Validation fails      | Pull request blocked, once the check is required. Nothing published.                                                                 |
| Publish fails partway | Job fails loudly. Re-run is safe: every operation is an idempotent update against a known id.                                        |
| Bad content merged    | Revert the commit; the next run republishes the prior body. Note this does not remove it from git history or from any public mirror. |
| Manifest wrong        | Run fails loudly rather than creating a duplicate, because CI cannot create.                                                         |

Concurrency: the publish workflow sets a concurrency group with
`cancel-in-progress: false`. Cancelling mid-publish is the partial-state case
worth avoiding, unlike the docs and Cube deploys which cancel freely.

## Open dependencies

1. **Zendesk Guide plan tier.** Both user segments and article labels require
   Guide Professional or Enterprise. The gating story and any label-based
   tooling depend on this. Verify first — it is cheap and it can invalidate
   design choices.
1. **A Zendesk API credential, and its blast radius.** Zendesk API tokens are
   not scoped; permissions derive from the associated user's role, so a token
   minted against an admin can read and modify **tickets**, not just Guide
   articles. OAuth is where scopes exist. Three decisions: OAuth versus API
   token; which Zendesk user the credential acts as, and whether a dedicated
   low-privilege Guide user can be provisioned; and where it is custodied given
   the keyless precedent noted above. The credential available during design was
   read-limited and could not enumerate permission groups.
1. **Help Center visibility.** The Data categories are currently readable
   without signing in. Whether gating is applied per user segment or Help Center
   wide is undecided and involves other departments. The pipeline treats
   visibility as configuration, never as an architectural assumption.
1. **Section placement and initial creation.** `Data | Launch` has five existing
   sections. Which section the six generated articles land in, and their
   `position` within it, needs deciding before the one-time creation step.

## Implementation sequencing

Before any renderer work, a throwaway spike settles the API questions
empirically:

1. Create one article via
   `POST /api/v2/help_center/{locale}/sections/{section_id}/articles`, passing
   `user_segment_id`, `permission_group_id`, and `label_names` explicitly in the
   create payload.
1. Update its body via
   `PUT /api/v2/help_center/articles/{id}/translations/{locale}`.
1. `GET` it back and assert the body actually changed — not merely that the call
   returned `200`.
1. Delete it.

That spike falsifies or confirms the translations behavior, the create-payload
requirements, and the plan-tier questions in an afternoon, before any of the
pipeline exists.

## Out of scope for phase 1

| Item                   | Disposition                                                                                                                                                                                     |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Okta bookmark tiles    | Follow-on spec. Reuses `links.yml`. Introduces Terraform, which this repo has none of today.                                                                                                    |
| Claude discovery skill | Follow-on spec. Reuses `links.yml`. Distribution surface undecided.                                                                                                                             |
| Metrics glossary       | Becomes a catalog entry pointing at the existing Apps Script URL, which is reachable independently of the Google Site. The Site can therefore be retired without rebuilding the glossary first. |
| Prose migration        | Our Team, Support, Topline, and Blog are authored in Zendesk directly. Not rendered from git. See _The content split_.                                                                          |
| `PS - Demo` page       | Deleted. Empty page in the current nav.                                                                                                                                                         |
| Google Site retirement | Needs its own cutover plan: content freeze, redirects, a named owner for deletion, and an answer for existing bookmarks. Not covered here.                                                      |

## Tracked follow-ups

A review of the live site surfaced content remediation items spanning published
contact details, sign-in guidance that is both stale and inadvisable to publish,
and a team page needing rework. These are tracked in Asana, assigned, with
specifics recorded there rather than in this repository. Most land on prose that
under this design is authored in Zendesk, so they are remediated there rather
than through this pipeline.

## Decisions log

| Decision                                         | Rationale                                                                                                                                                               |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Catalog public, prose in Zendesk                 | The repo is public; splitting by sensitivity is simpler and more honest than a private repo or a lint gauntlet.                                                         |
| Tag once, generate views                         | Kills the five-way duplication that is the current maintenance burden.                                                                                                  |
| Every view links to the full manifest            | A tagging mistake costs a click, not access.                                                                                                                            |
| Zendesk before Okta tiles and Claude skill       | Reaches all staff. The other two reach subsets.                                                                                                                         |
| GitHub Actions over a Dagster asset              | Matches existing deploy patterns and publishes on merge.                                                                                                                |
| CI updates only, never creates                   | Removes the manifest write-back that repository rulesets forbid, and the create-payload defaults that would otherwise publish anonymously-readable articles unattended. |
| Body writes go through the translations endpoint | The Articles endpoint accepts a body and silently ignores it.                                                                                                           |
| Spike the API before building the renderer       | Three of the riskiest assumptions are settled in an afternoon rather than discovered late.                                                                              |
