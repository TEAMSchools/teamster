# dbt SQL and Model Design Standard — Design

Refs [#5789](https://github.com/TEAMSchools/teamster/issues/5789).

## Context

Reviewers re-argue the same SQL style and model layout questions in PR after PR.
The rules exist, but they live in 3 places that disagree:

- `docs/reference/dbt-conventions.md` (published) says pass-through CTEs are
  fine and that `DISTINCT` needs a free-text comment.
- `.claude/rules/dbt-sql.md` bans import CTEs and requires a specific `DISTINCT`
  annotation. It is about 460 lines that mix rules, BigQuery traps, and a
  benchmark table.
- `src/dbt/kipptaf/models/marts/CLAUDE.md` holds the mart naming rubric (R1-R10)
  and the strict-chain FK rules.

Most mechanical rules are checked by hand. Nothing written covers how models are
laid out from source to consumer, and the repo shows it:

- 131 of 259 kipptaf `rpt_` models read `stg_` directly; 3 read a mart.
- `dim_`/`fct_` models make 64 `ref()` calls to `stg_`.
- 26 exposure dependencies point below the consumer layer (14 `int_`, 7 `base_`,
  3 `stg_`, 2 `snapshot_`).
- 19 uniqueness grains are shared by 2 or more `int_` models, covering 57 of the
  165 tested `int_` models. Some are deliberate fan-in; some are the same entity
  rebuilt in another layer (the enrollment chain
  `int_powerschool__student_enrollment_union` →
  `int_students__student_enrollment_union` →
  `int_extracts__student_enrollments`).
- `student_key` is hashed independently in 7 marts, with no shared macro.
- #5362, #5365, and #5368 each cleaned up a model that read across layers.

## Decisions

| Question                  | Decision                                                                   |
| ------------------------- | -------------------------------------------------------------------------- |
| Audience                  | Analysts, analytics engineers, and Claude review against 1 standard        |
| Base framework            | dbt Labs project-structure and SQL style guides, plus a list of deviations |
| Existing code             | Style rules apply to touched code; edge rules use a baseline ratchet       |
| Layout                    | A target architecture, not a description of today                          |
| Consumer core             | Marts: `rpt_` reads `dim_`/`fct_` wherever a mart covers the entity        |
| Intermediate organization | Source-tier `int_` under source folders; domain `int_` in tagged folders   |
| Layer-rule enforcement    | A manifest check script (not dbt-project-evaluator, not review-only)       |

## 1. Where the standard lives

The `.claude/rules/` files are the source of truth. The published page is built
from them.

Rules fall into 3 tiers:

- Tier 1: a CI check enforces the rule. Reviewers do not comment on it.
- Tier 2: a review rubric of judgment calls, each with a good and bad example.
- Tier 3: Claude-only reference notes (BigQuery and dbt gotchas). Not review
  criteria and not published.

- `.claude/rules/dbt-architecture.md` (new, `paths:` under
  `src/dbt/**/models/**`): layers, allowed edges, intermediate kinds,
  duplication rules, keys, and the mart rubric R1-R10 moved out of
  `marts/CLAUDE.md`.
- `.claude/rules/dbt-sql.md` (restructured): style rules first, then the
  Claude-only gotchas.
- Each rule has a stable ID (`A1…` architecture, `S1…` style) and a fixed shape:
  rule (1 sentence), why (1 line), good and bad example, enforced by (a check
  name or "review").
- The human-facing part of each rule file sits between `pymdownx.snippets`
  section markers. `docs/reference/dbt-conventions.md` becomes a stub that
  includes those sections, so its URL does not change. Text outside the markers
  (load notes, tool traps, the `dbt_utils.deduplicate` cost table) stays
  Claude-only.
- Text inside the markers is written for a human reader: plain sentences and an
  example per rule.
- `mkdocs.yml` enables `pymdownx.snippets` with a `base_path` that reaches
  `.claude/rules/`. `mkdocs-gh-deploy.yaml` adds `.claude/rules/dbt-*.md` to its
  trigger paths.
- The top of the page states the change process: a rule changes through a PR to
  its rule file. A reviewer who disagrees with a rule opens an issue; the
  feature PR follows the current rule.

## 2. Target layers and allowed edges

### Layers

| Layer         | Does                                                                                              | Lives in (kipptaf)                      |
| ------------- | ------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `stg_`        | 1 source table: rename, cast, filter soft-deletes, dedup source duplicates, unpivot a wide source | `<source>/staging/`                     |
| Source `int_` | Logic within 1 source system                                                                      | `<source>/intermediate/`                |
| Domain `int_` | Cross-source business entities and identity resolution                                            | Folders tagged `+meta: {layer: domain}` |
| Marts         | `dim_`/`fct_`/`bridge_`, the core every consumer reads                                            | `marts/`                                |
| `rpt_`        | Thin shaping of marts for 1 tool, including tool-specific pivots                                  | `extracts/<tool>/`                      |

Adding a domain folder is normal: 1 config line in `dbt_project.yml`, visible in
the diff. An `int_` outside a tagged folder is source-tier.

### Allowed edges

A changed model that reads outside its row fails CI (subject to the baseline in
section 5).

| Model         | May read                                                                                   |
| ------------- | ------------------------------------------------------------------------------------------ |
| `stg_`        | `source()`                                                                                 |
| Source `int_` | `stg_` and source `int_` in the same source folder; `source()` for district union wrappers |
| Domain `int_` | `stg_`, any source `int_`, domain `int_`, `snapshot_`                                      |
| Marts         | Domain `int_`, other marts                                                                 |
| `rpt_`        | Marts, domain `int_`                                                                       |
| Exposures     | `rpt_`, marts; Cube reads marts only                                                       |

`rpt_` → `rpt_` is not allowed. `base_` counts as domain `int_` until #2541
renames it.

### Intermediate kinds

Every `int_` outputs exactly 1 grain and does 1 of 2 kinds of work. The name
suffix says which:

| Kind    | What happens to the grain                                  | Name                                                   |
| ------- | ---------------------------------------------------------- | ------------------------------------------------------ |
| Build   | Keeps a grain; assembles columns (joins, decodes, cleanup) | No suffix                                              |
| Reshape | Changes the grain                                          | `_pivot`, `_unpivot`, `_rollup`, `_scaffold`, `_union` |

A crosswalk is a build model whose entity is a mapping
(`int_people__location_crosswalk`); "crosswalk" is part of the entity name, not
a suffix. New models follow the suffix rule. Existing names stay.

### Duplication

- 1 model per grain within each source folder, and 1 across the domain folders.
  A reshape model is the canonical model for its output grain.
- CI warns when a new or changed `int_` shares a uniqueness grain with another
  model, excluding its direct parents and siblings that share 1 consumer (the
  topline fan-in into `int_topline__student_metrics`). The author reuses the
  existing model or explains the difference in the PR.

### Review rules

- An `rpt_` reads a mart whenever 1 covers the entity. Reading a domain `int_`
  needs a linked issue for the missing mart.
- Dedup happens only in `stg_` or source `int_`. A dedup further down hides an
  upstream bug.
- Long in the core, wide at the edge. An `int_` pivot is fine when its output
  grain is reused; a pivot read by 1 `rpt_` belongs inside that `rpt_`.
- Identity is resolved in the domain `int_`. Surrogate keys are hashed in marts
  through 1 macro per entity (`{{ student_key(...) }}`); a direct
  `generate_surrogate_key` call for an entity key fails CI.

### Other projects

Source packages hold `stg_` and source `int_` only. District projects hold
package config, district-only source models, and thin `rpt_` wrappers over
kipptaf extracts. Cross-region business logic lives only in kipptaf.

## 3. SQL style

Base: dbt Labs "How we style our SQL". Rules the repo already follows stay:
lowercase, trailing commas, explicit `inner join`/`left join`, CTEs over
subqueries.

Parent rule: ANSI SQL or a dbt macro first. BigQuery-only syntax must do
something standard SQL cannot.

| Rule                             | dbt Labs    | Us                     | Why                                                       |
| -------------------------------- | ----------- | ---------------------- | --------------------------------------------------------- |
| Import CTEs                      | Recommended | Banned                 | A CTE with no logic; `ref()` in `from` reads the same     |
| `qualify`                        | Allowed     | Banned                 | Not ANSI; a ranked column plus `where` does the same      |
| `group by 1, 2` / `group by all` | Allowed     | Banned                 | Both break silently when the select list changes          |
| Table aliases                    | Full names  | Short initials (`enr`) | Repo norm; unique in the query, drawn from the model name |

- Select-list order: the 7-bucket complexity order stays a house rule, checked
  in review. sqlfluff ST06 is a separate lint rule. The rule file gives each its
  own heading.
- Booleans: `is_`/`has_` everywhere, except an `rpt_` whose tool needs Y/N text;
  the conversion happens in that `rpt_`.
- `if()` for 1 condition; `case` for 2 or more branches.

Review rubric (Tier 2):

1. Grain is stated and tested.
2. Dedup sits in the right layer; `DISTINCT` is not masking duplicates.
3. The model sits in the right layer and has the right kind (build or reshape).
4. An `rpt_` reads a mart when 1 exists.
5. Join types are right; filters sit in `ON` or `WHERE` correctly.
6. Date-range joins are half-open where intervals abut.
7. Nested logic is split into named columns past 1 level.
8. Comments say only what the line cannot show.

## 4. Enforcement

| Check                      | Runs                                  | Covers                                                                                                                                                                                 |
| -------------------------- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| sqlfluff config            | Trunk hooks and CI                    | Positional `group by` (AM06 `explicit`); subqueries in `from`/`join`/`where` (ST05 `both`)                                                                                             |
| Banned-syntax trunk linter | Trunk hooks and CI                    | `qualify`, `group by all`, `union all corresponding` (regex)                                                                                                                           |
| Manifest check             | New GitHub workflow on `src/dbt/` PRs | Fails: disallowed edge, unknown `int_` suffix on a new model, entity key without its macro, exposure below `rpt_`/marts, `select *` in a final `rpt_`/mart select. Warns: shared grain |
| claude-review              | Existing workflow                     | Tier 2 rubric only, citing rule IDs; never comments on what the checks above cover                                                                                                     |

- The manifest check runs `dbt parse` on each changed project and checks changed
  models. A district model read in kipptaf through `source()` gets its layer
  from its table-name prefix.
- Exemptions: `config.meta.standard_exempt: {<rule id>: <reason>}` on the model.
  Lint rules keep `trunk-ignore`.
- `.trunk/trunk.yaml` is Edit-denied for Claude; the plan drafts the linter
  block and the user applies it.
- Top-level `order by` and import CTEs need a parse tree to detect reliably.
  They stay review rules until a parse-based check proves worth building.

Not built: dbt-project-evaluator, a custom sqlfluff plugin, checks over
unchanged models.

## 5. Rollout

1. Rule files, rule IDs, snippets stub page, deploy trigger. Docs only; no dbt
   CI.
2. Entity key macros (`student_key`, `staff_key`, …). Each reproduces today's
   hash exactly, verified by comparing compiled SQL, so no Cube hash churn.
   Existing marts adopt the macro when touched.
3. sqlfluff config and the banned-syntax linter block.
4. Manifest check, its workflow, domain-folder tags, and the baseline file.
5. claude-review prompt.

Baseline ratchet: the first run of the manifest check writes today's edge
violations to a checked-in baseline file. CI fails on a violation missing from
the file, and on a baseline line whose violation is gone, so the list only
shrinks. Style rules stay touched-code-only.

After about 2 months, list the most-used `standard_exempt` entries and
`trunk-ignore`s. A rule that keeps getting exempted gets a rule-change PR.

## To verify during planning

- `pymdownx.snippets` can include a file outside `docs/` through `base_path`,
  and the rule-file frontmatter stays outside the included sections.
- claude-review loads `.claude/rules/` the way local sessions do; if not, its
  prompt points at the 2 rule files.
- A `+meta` change in `dbt_project.yml` may mark every tagged model
  `state:modified` in dbt Cloud CI. Test on 1 folder first; if it does, the
  domain folder list moves into the check script's config.
- ST05 `both` leaves the blessed `(select min(x) from unnest([...]))` form
  alone.
- `dbt parse` runs in a GitHub Action without warehouse credentials.
