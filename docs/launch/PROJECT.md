# Data launch page — project overview

Orientation for anyone picking up this work. [README.md](README.md) is the field
reference and [RUNBOOK.md](RUNBOOK.md) is the task sequence; this is the why,
the scope, and where it stands.

Last updated 2026-08-11.

## The problem

The data team's launch page — the thing staff open to find a dashboard — lives
on a Google Site. It is edited by hand, has no version history worth the name,
and the same tool list is maintained separately on five different role pages,
which have drifted apart. Nobody can review a change before it goes live.

It has to reach roughly **1,800 staff** across Newark, Camden, Miami and
Paterson: classroom teachers through assistant superintendents.

## The shape of the solution

**Split the content by how sensitive it is.**

| Content                                          | Lives in | Why                                                                                        |
| ------------------------------------------------ | -------- | ------------------------------------------------------------------------------------------ |
| The tool catalog — names, descriptions, URLs     | git      | Already public on the Google Site. A list of nouns and links that only open behind sign-in |
| Prose — Our Team, support runbook, Topline, blog | Zendesk  | Authored by humans who are not going to write YAML, and gated by Okta                      |

**The catalog becomes a static page with no authentication.** It carries nothing
worth gating, and every destination gates itself: Tableau by SSO, Google Sheets
by Workspace group, Zendesk guides by Okta. That removes the whole problem that
made "put it on GitHub Pages behind auth" hard — the auth was never needed.

**Only `status: verified` entries publish.** Verification is a release gate, not
a quality note. Nothing reaches 1,800 people on the strength of a scrape.

```text
  docs/launch/links.yml     44 tools, each with a status
  docs/launch/groups.yml    topical groups, families, promo cards, threshold
  docs/launch/template.html the page shell
           |
           v
  docs/launch/build.py      load -> select -> validate -> render
           |
           v
  MkDocs hook -> teamschools.github.io/teamster/launch/
```

## Where it stands

| Item                                                               | State                                                                        |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| Issue [#4761](https://github.com/TEAMSchools/teamster/issues/4761) | Open. The parent. Reopened after a linked-branch merge auto-closed it        |
| PR [#4763](https://github.com/TEAMSchools/teamster/pull/4763)      | **Merged.** Catalog, README and RUNBOOK are on `main`                        |
| PR [#4767](https://github.com/TEAMSchools/teamster/pull/4767)      | **Merged.** Catalog verification — 39 of 44 verified, 5 still `needs-review` |
| PR [#4762](https://github.com/TEAMSchools/teamster/pull/4762)      | Open. Design spec for the page itself                                        |
| Issue [#4818](https://github.com/TEAMSchools/teamster/issues/4818) | Open. Reopened — tracks this implementation work                             |
| PR [#4819](https://github.com/TEAMSchools/teamster/pull/4819)      | **Merged.** Design spec for the build and gate is on `main`                  |
| PR [#4816](https://github.com/TEAMSchools/teamster/pull/4816)      | **Merged.** `analytics-engineers` own `/docs/launch/`                        |
| Google Site                                                        | Still live. Retirement is gated on a cutover threshold, not yet set          |

The catalog on `main` is 44 entries — 34 Tableau, 7 Google Sheets, 3 AppSheet —
and **39 are verified** (5 `needs-review`), so the page would already publish.
That was deliberate: it made this the safe window to build the pipeline, before
verification caught up.

## Who owns what

| Work                                                    | Owner                                                                  |
| ------------------------------------------------------- | ---------------------------------------------------------------------- |
| Verifying the 44 catalog entries                        | Intern, tracked on #4767                                               |
| Triaging which Google Sheets exposures are staff-facing | Anthony — needs judgement about which reports real people actually use |
| The build pipeline, validation and CI gate              | Data team, specced on #4819                                            |
| Prose content in Zendesk                                | Not started; no owner yet                                              |

## Decided — please don't relitigate

Each of these was argued and settled. The reasoning is in the specs if you want
it.

1. **The tool catalog is public.** It is already public today on the Google
   Site.
1. **Prose stays in Zendesk**, authored there rather than migrated into git.
1. **No Zendesk publishing pipeline.** An earlier design generated Guide
   articles through the API. It existed to gate a list that needs no gate.
1. **Only verified entries publish.**
1. **Don't scrape the dbt exposures into the catalog.** There are 63 Google
   Sheets exposures and staff-facing ones appear in every naming category, so no
   heuristic sorts them.
1. **Don't move the catalog into the exposure YAMLs.** Measured: zero of 44
   entries have a matching exposure URL. Exposures record lineage, not
   destinations.

## Open — needs a decision

1. **The cutover threshold.** How much of the catalog has to be verified before
   the Google Site is retired. A related number, the minimum verified count
   before the page publishes at all, is seeded at 25 in the build spec.
1. **An admin identity for the Drive sharing check.** Without one the check
   fails open: `permissions.list` returns only the owner to a caller that does
   not administer the file, so a naive assertion passes on a file it knows
   nothing about.
1. **Required status checks.** Ruleset `816683` requires only dbt Cloud and
   Trunk, and `strict_required_status_checks_policy` is `false`. Until the new
   check is added the gate is advisory, and without strict mode two PRs green in
   isolation can still break `main`.
1. **Whether the page should discourage search indexing.** Currently specced
   with a `noindex` meta tag.

## Sequence

1. Verification on #4767 is done — 39 of 44 entries are verified.
1. The build-gate design spec, #4819, is done too — merged to `main`.
1. The build pipeline itself lands next, tracked on #4818 (this branch). With
   verification already ahead of the threshold, it becomes the first live
   publish as soon as it merges.
1. The per-entry `group` field and grouped rendering follow.
1. Prose moves into Zendesk.
1. Once the catalog crosses the cutover threshold, the Google Site is retired
   and redirected.

## One thing that will bite you

The MkDocs deploy workflow fires on `docs/**`. Once the build is wired in, **a
catalog that fails validation on `main` freezes all documentation publishing**,
not just the launch page. That coupling is deliberate — it is the cost of having
one code path — and the PR gate is the thing that keeps it from happening. Do
not wire the build into the deploy before the gate exists.

## Where things live

| Path                                                                 | What                                         |
| -------------------------------------------------------------------- | -------------------------------------------- |
| `docs/launch/links.yml`                                              | The catalog. Source of truth                 |
| `docs/launch/README.md`                                              | Field reference and what "verified" requires |
| `docs/launch/RUNBOOK.md`                                             | The verification task sequence               |
| `docs/superpowers/specs/2026-08-06-launch-page-design.md`            | What the page is (on #4762)                  |
| `docs/superpowers/specs/2026-08-11-launch-page-build-gate-design.md` | How it gets built (on #4819)                 |

Both specs are working documents, not published reference pages.
