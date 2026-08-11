# Data Launch Page: static site built from a versioned catalog

Design spec for phase 1 of migrating the data team launch page off Google Sites.

Refs #4761

## Problem

The launch page runs on a Google Site that is difficult to maintain.

- **The tool catalog is hand-duplicated across five role pages** (All, Teachers,
  Leaders, Operations, Regional/CMO) and has already drifted. The Operations
  page lists `Home Instruction Tracker` carrying the OKRTS description, and the
  same tool resolves to two different URLs depending on which page you arrive
  from.
- **Nothing is version controlled.** No history, no review before content goes
  live, no way for a coding agent to propose a change.
- **Link rot is silent.** A dashboard URL that dies stays on the page until a
  human notices.
- **The metrics glossary is a bespoke Apps Script web app** embedded in an
  iframe, backed by a Sheet. Custom code and content, both outside version
  control.

## Goals

1. Author the tool catalog in git, reviewed by PR, editable by a coding agent.
1. Eliminate catalog duplication so drift is structurally impossible.
1. Publish automatically on merge, with no manual step.
1. Retire the Google Site.

## Non-goals for phase 1

Okta bookmark tiles, the Claude discovery skill, and the metrics glossary
rebuild. Each is tracked separately. See _Out of scope_.

## The content split

The load-bearing decision, and deliberate rather than incidental.

`TEAMSchools/teamster` is a **public** repository, and `docs/` is rendered to a
public website. Anything committed here is world-readable permanently, in git
history. Directory placement does not change that.

So content splits by whether it is safe to be public:

| Content                                              | Lives in | Rationale                                                                                                                                                                                                     |
| ---------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Tool catalog** (`links.yml`, `groups.yml`)         | git      | Tool names, one-line descriptions, and URLs that resolve only behind SSO or Workspace group membership. An outsider gets a list of nouns and links that do not open. Already public today on the Google Site. |
| **Prose** (Our Team, Support runbook, Topline, Blog) | Zendesk  | Names individuals, describes operational detail, carries contact routing. Authored directly in Guide, behind Okta sign-in. Guide keeps article revisions.                                                     |

The rule for `src/launch/CLAUDE.md`: **if it is not safe to post to the open
internet, it does not go in `src/launch/`.**

Prose is not version-controlled in git. It is versioned by Guide's article
revisions, and a coding agent can still edit it through the Zendesk API — just
not through a pull request.

## Approach

**The landing page is a static page published to GitHub Pages. It carries no
authentication, because it carries nothing worth gating.** Every destination it
links to enforces its own access: Tableau by SSO, Google Sheets by Workspace
group, Zendesk help articles by Okta sign-in.

A build step renders `links.yml` plus `groups.yml` into a single self-contained
HTML page. The existing MkDocs deploy workflow publishes it alongside the docs
site. Merging a catalog change publishes it; there is no other step.

### Why not Zendesk articles, which an earlier draft specified

That draft generated five Guide articles from the catalog and published them
through the Zendesk API. It carried a Guide write credential, an article-id
manifest, create-versus-update semantics, a translations-endpoint trap where a
`PUT` to the wrong endpoint returns `200` and silently changes nothing, and a
Guide plan-tier dependency.

**All of that machinery existed to put a public list behind a sign-in that the
list does not need.** Once the content split established that the catalog is
safe to publish, the gating requirement disappeared and the pipeline built to
satisfy it became cost without benefit.

### Why the earlier rejection of GitHub Pages was stale

The previous draft's rejected-alternatives table read:

> GitHub Pages **with authentication** — `TEAMSchools/teamster` is public; Pages
> on a public repo cannot be gated. Private Pages needs GHEC.

That rejects the **gated** variant, on the grounds that a public repo's Pages
cannot be gated. It was written before the content split, and it never evaluated
the option actually taken here: a **public** page linking to gated destinations.
The objection does not apply to it.

### Rejected alternatives

| Option                          | Why not                                                                                                                                                                                                                          |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Generate Zendesk Guide articles | Builds a publishing pipeline to gate content that does not need gating. See above.                                                                                                                                               |
| Zendesk Guide custom page       | Full HTML/CSS/JS is available on Guide Professional or Enterprise, but it ties the page to an unconfirmed plan tier, opts the theme out of Zendesk's automatic updates, and adds a deploy path the repo does not otherwise have. |
| GitHub Pages gated behind GHEC  | An org-wide plan cost to gate a list that is agreed public.                                                                                                                                                                      |
| Cloud Run behind IAP            | New infrastructure to serve one static page.                                                                                                                                                                                     |
| Publish via a Dagster asset     | Couples content deploys to the orchestrator, for what is a static render.                                                                                                                                                        |
| Keep the Google Site, mirror it | Preserves the maintenance burden being escaped and creates a second source of truth.                                                                                                                                             |

## Source layout

```text
src/launch/
├── CLAUDE.md          # domain conventions, including the public-content rule
├── links.yml          # tool catalog, one entry per tool
├── groups.yml         # topical domains, families, and the promo cards
├── README.md          # field reference and what "verified" requires
├── RUNBOOK.md         # the task sequence for finishing the catalog
└── build.py           # renders the page
```

`views.yml` is retired. Role views are tabs on one page rather than five
separate documents, so per-view titles and intro copy move into the template.

The rendered page is written to `docs/launch/index.html` at build time and is
**not committed** — `docs/launch/` is gitignored. Committing a generated
artifact guarantees it drifts the first time someone edits `links.yml` without
regenerating.

## Catalog schema

```yaml
- id: attendance_dashboard
  name: Attendance Dashboard
  url: https://tableau.example/attendance
  description:
    Monitor ADA, chronic absenteeism, suspension, and attendance calls.
  audiences: [teachers, leaders, ops, region]
  system: tableau
  group: attendance # NEW — topical domain, see groups.yml
  access: limited # optional badge
  guide: https://teamschools.zendesk.com/hc/en-us/articles/000 # optional
  regions: [newark] # optional
```

Required: `id`, `name`, `url`, `description`, `audiences`, `system`, `group`.
Optional: `access`, `guide`, `regions`.

**Two fields are new in this revision**, both surfaced by designing against the
real data rather than in the abstract:

- **`group`** — a topical domain (Attendance and behavior, Academics and
  assessment, and so on). `audiences` is role-based; `group` is subject-based.
  They are different axes and neither derives from the other. Without `group`,
  the All view is a flat list of 46 items.
- **families**, declared in `groups.yml` rather than per entry — collapse
  region-variant tools into one row with region sub-links. The three GPA Rosters
  and four Student Contact Info Feeds become two rows instead of seven. This is
  a modelling improvement, not styling: the variants pad the list without adding
  meaning.

`audiences` controls **relevance, never visibility**. It decides which tab a
tool appears under. It is not access control; the destination system enforces
that.

## Rendering

One page, `docs/launch/index.html`, self-contained apart from a webfont link.

- **Tabs** for All plus the four role views, counts included.
- **Search** across name, description, and family name.
- **Filters** by topical domain and by source system.
- **Grouped list** by domain, each group headed and counted.
- **Every role tab is one click from All**, so a mistagged entry costs a reader
  a click and never access.
- Client-side only. No server, no build-time per-view duplication.

## Build and deploy

This is the part that makes it automatic, and the part most worth attacking.

**Build.** `src/launch/build.py` reads `links.yml` and `groups.yml`, validates
them, and writes `docs/launch/index.html`.

**Deploy.** The existing
[mkdocs-gh-deploy.yaml](../../../.github/workflows/mkdocs-gh-deploy.yaml) gains
`src/launch/**` in its push-paths filter and a build step before
`mkdocs gh-deploy`. MkDocs copies non-Markdown files in `docs_dir` through
verbatim, so the page lands at `teamschools.github.io/teamster/launch/`.

**One writer to `gh-pages`, and this is not optional.** `mkdocs gh-deploy`
force-pushes the `gh-pages` branch, replacing its contents wholesale. A second
workflow publishing the launch page independently would work until the next docs
change silently wiped it. The build therefore runs **inside** the existing job,
not beside it.

### The coupling this introduces

Putting the build inside the docs job means **a failure in `build.py` fails the
docs deploy**. That is a real cost and needs a deliberate answer rather than
discovery in production.

The position taken here: **fail the job.** A launch page built from an invalid
catalog is worse than a stale one, and a silently-skipped build produces a page
that looks current and is not. The mitigation is that validation runs at pull
request time, so a merge that would break the build should not reach `main` —
the deploy-time failure is a backstop, not the primary gate.

Rejected alternative: `continue-on-error` on the build step, letting docs deploy
regardless. That converts a loud failure into a stale page nobody notices, which
is the exact failure mode the Google Site has today.

### Ordering within the job

Build must run **before** `mkdocs gh-deploy`, because `gh-deploy` builds and
pushes in one command. There is no post-deploy hook to slot into.

## Validation

Runs on every pull request touching `src/launch/**`, and again at build time.

Schema checks:

- Required fields present, enum values known
- `id` values unique
- Every value in `audiences` is a known view id
- **Every entry has a `group`, and it is a known group id.** A tool with no
  group cannot be placed on the page — the build fails rather than dropping it
  silently, which would otherwise remove a tool from the launch page with no
  error anywhere.
- Every family member named in `groups.yml` exists in `links.yml` and carries a
  `regions:` value
- URLs well-formed and HTTPS

Content lint — deliberately narrow, because the catalog is names, descriptions,
and links, and legitimately contains none of the following:

- No email addresses
- No phone-shaped strings
- No sign-in guidance

These are decidable and near-zero-false-positive **on this corpus
specifically**. They are not a general content-safety mechanism, and they are
not what keeps sensitive prose out of git — the content split does that.

Validation will not block merge until the check is added to the
`required_status_checks` ruleset, which currently lists only `dbt Cloud` and
`Trunk Check Runner`. That requires repo-admin rights and has lead time.

### Google-hosted tools still need a sharing check

The catalog is safe to publish because its URLs require sign-in. **That holds
for Tableau but not automatically for Google Drive.** A file shared "anyone with
the link" is gated by its URL, so publishing that URL hands it out. The catalog
includes three GPA Rosters and four Student Contact Info Feeds carrying
student-level data.

**Publishing to a public, crawlable GitHub Pages site raises the stakes relative
to the earlier Zendesk design** — a URL on a sitemapped public page is more
exposed than the same URL behind a sign-in.

The obvious implementation of the check does not work. Drive's
`permissions.list` returns the full permission set only to a caller that
administers the file; to any other caller it returns just the owner. A naive
assertion reads "no groups, no `anyone`" and passes on a file it knows nothing
about — a check that fails open. This was hit during design: all four Contact
Info Feeds returned owner-only, while the data team confirms each is
region-group shared with CMO access and none is link-shared.

The check is therefore only meaningful run as an identity that **administers the
files** — a Workspace admin credential or domain-wide delegation — and it must
**fail loudly on an owner-only result** rather than treating it as a pass.
Provisioning that identity is a prerequisite, not an implementation detail.

## Testing

- **Unit tests on the render and validation functions.** Pure, no network. Given
  a fixture catalog, assert the rendered output and each validation failure.
- **A build smoke test in CI**: build against the real catalog and assert the
  output contains every tool. Catches a filter or grouping bug that produces a
  valid-looking page missing half the list.
- **Link health** on a schedule rather than at build time: HEAD every URL,
  report failures, and assert Drive sharing for `google-*` entries. Build-time
  checking would make an unrelated vendor outage break the docs deploy.

## Failure handling

| Failure                    | Behavior                                                                                                      |
| -------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Validation fails on a PR   | Pull request blocked, once the check is required. Nothing publishes.                                          |
| `build.py` fails on `main` | Docs deploy fails loudly. Previous page stays live, since `gh-pages` is untouched.                            |
| Bad content merged         | Revert; the next deploy republishes. Note this does not remove it from git history or from any public mirror. |
| A destination URL dies     | Page still builds and deploys. The scheduled link-health job reports it.                                      |

## Open dependencies

Substantially fewer than the previous draft, because the Zendesk publishing path
is gone.

1. **An admin identity for the Drive sharing check.** Without it the check fails
   open, which is worse than no check. Needed before the scheduled job is
   trusted, not before the page ships.
1. **Adding the validation check to the `required_status_checks` ruleset.**
   Repo-admin, has lead time.
1. **Whether the public page should discourage indexing.** A GitHub Pages site
   is more discoverable than the current Google Site — sitemapped and crawled.
   The status quo is already public, so this is not new exposure, but it is a
   step up in findability and deserves a deliberate call. A `robots` meta tag is
   the cheap answer.
1. **Help Center visibility for the prose articles.** Unchanged from the
   previous draft and independent of this page: the Data categories are
   currently readable without signing in.

Resolved by this revision and no longer dependencies: the Zendesk Guide write
credential and its blast radius, Guide plan tier, article section placement, and
the article-manifest design.

## Out of scope for phase 1

| Item                   | Disposition                                                                                                                                                 |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Okta bookmark tiles    | Follow-on. Reuses `links.yml`. Introduces Terraform, which this repo has none of today.                                                                     |
| Claude discovery skill | Follow-on. Reuses `links.yml`. Distribution surface undecided.                                                                                              |
| Ticket-response agent  | Follow-on. `links.yml` is the right spine; synonyms and access-request paths are not in it and should be derived from real ticket text rather than guessed. |
| Metrics glossary       | Becomes a catalog entry pointing at the existing Apps Script URL, which is reachable independently of the Google Site.                                      |
| Prose migration        | Our Team, Support, Topline, and Blog are authored in Zendesk directly. See _The content split_.                                                             |
| Google Site retirement | Needs its own cutover plan: content freeze, redirects, a named owner for deletion, and an answer for existing bookmarks.                                    |

## Tracked follow-ups

A review of the live Google Site surfaced content remediation items spanning
published contact details, sign-in guidance that is both stale and inadvisable
to publish, and a team page needing rework. Tracked in Asana with specifics
recorded there rather than in this public repository.

## Decisions log

| Decision                                    | Rationale                                                                                                        |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Public static page, no gate                 | The catalog carries nothing worth gating; every destination gates itself. Removes an entire publishing pipeline. |
| Catalog public in git, prose in Zendesk     | The repo is public; splitting by sensitivity beats a private repo or a lint gauntlet.                            |
| Build inside the existing MkDocs job        | `mkdocs gh-deploy` force-pushes `gh-pages`; a second writer would be silently clobbered.                         |
| Fail the docs deploy on a bad catalog build | A stale page that looks current is worse than a loud failure. PR validation is the primary gate.                 |
| `group` as a required field                 | Role tags and topical domains are different axes. Missing groups fail the build rather than dropping tools.      |
| Families declared in `groups.yml`           | Seven region-variant rows become two. A modelling fix, not styling.                                              |
| Link health scheduled, not at build time    | A vendor outage should not break the docs deploy.                                                                |
| Retire `views.yml`                          | Role views are tabs on one page, not five documents.                                                             |
