# Cube sandbox

A separate Cube Cloud deployment reading a separate BigQuery project, filled
with fabricated data. It lets an outside party build against KTAF's semantic
layer without ever holding a credential that reads real student or staff data.

Design:
[2026-09-11-cube-sandbox-build-design.md](https://github.com/TEAMSchools/teamster/blob/main/docs/superpowers/specs/2026-09-11-cube-sandbox-build-design.md).
Tracked in [#5266](https://github.com/TEAMSchools/teamster/issues/5266).

## Who uses it, and what they see

| Tier | Who        | Holds                               | Data sees      |
| ---- | ---------- | ----------------------------------- | -------------- |
| 1    | MasterBorn | The kit source, sandbox credentials | Synthetic only |
| 2    | KTAF devs  | An app built on the kit             | Synthetic only |
| 3    | KTAF staff | The finished app                    | Production     |

MasterBorn has no Cube Cloud account and no web UI, so no Playground and no data
model browser. They keep using the sandbox after the production cutover: the
repoint grants the product's end users access, not MasterBorn's engineers.

## What differs from production

Three things, and only the second needs a mechanism.

| What                 | Sandbox versus production                       |
| -------------------- | ----------------------------------------------- |
| Model files          | Identical                                       |
| Revision             | Older — a tagged commit on `main`'s own history |
| Deployment variables | `CUBEJS_DB_BQ_PROJECT_ID` and its credentials   |

The model files are identical because every `sql_table:` is project-unqualified,
so the same files read a different warehouse from one variable. There is no
sandbox branch — the sandbox needs a revision, not a branch. A forked sandbox
YAML would mean the kit is no longer building against the production semantic
layer.

The sandbox deployment also sets `CUBEJS_DB_BQ_CREDENTIALS` explicitly. Without
it `cube.js` falls back to Cube Cloud's ambient host identity
([#4466](https://github.com/TEAMSchools/teamster/issues/4466)), which denies
everyone — and a deployment that denies everyone looks exactly like perfect
isolation, so the isolation test would pass for the wrong reason.

## Sandbox latency is not representative

9 of the 21 tables are BigQuery views in production and flat tables in the
sandbox, so the sandbox is systematically faster. Rebuilding view chains for
fabricated data would be absurd, so the rule is stated instead:

!!! warning "Tell the partner in writing"

    Sandbox latency must not be used to size timeouts, pick page sizes, or
    decide what to cache.

## Emulating a persona

Personas are declared in `src/cube/sandbox/personas.yml` — hand-written, never
generated, because `canaries.yml` names them and a persona referenced by name
has to survive a seed change.

### The seven identities

| Address                                      | Students       | Staff PII                                               |
| -------------------------------------------- | -------------- | ------------------------------------------------------- |
| `sheryl.swoopes@ktaf-sandbox.invalid`        | every location | every staff member                                      |
| `ororo.munroe@ktaf-sandbox.invalid`          | her school     | her reporting chain, which has one person in it         |
| `zydrunas.ilgauskas@ktaf-sandbox.invalid`    | his region     | teaching staff in his region                            |
| `karl-anthony.maximoff@ktaf-sandbox.invalid` | every location | his chain, plus anyone below his rank in his department |
| `shaquille.oquinn@ktaf-sandbox.invalid`      | his school     | **denied** — reporting chain is empty                   |
| `aja.ogwumike@ktaf-sandbox.invalid`          | **denied**     | **denied**                                              |
| `unresolvable@ktaf-sandbox.invalid`          | **denied**     | **denied**                                              |

Every `*_scope` column of `dim_staff_cube_access`, per persona:

| Scope column               | Swoopes      | Munroe          | Ilgauskas      | Ogwumike | Maximoff                      | O'Quinn         |
| -------------------------- | ------------ | --------------- | -------------- | -------- | ----------------------------- | --------------- |
| `student_location_scope`   | network      | school          | region         | none     | network                       | school          |
| `staff_location_scope`     | network      | school          | region         | none     | network                       | school          |
| `staff_department_scope`   | all          | own_group       | all            | none     | own_group                     | own_group       |
| `staff_pii_scope`          | all_in_scope | reporting_chain | teaching_staff | none     | reporting_chain_or_below_rank | reporting_chain |
| `staff_compensation_scope` | all_in_scope | none            | none           | none     | reporting_chain               | none            |
| `staff_observations_scope` | none         | reporting_chain | none           | none     | all_in_scope                  | none            |
| `staff_benefits_scope`     | all_in_scope | reporting_chain | none           | none     | none                          | none            |

Reporting chains: Munroe → Ilgauskas, and Maximoff → Ogwumike. Everyone else has
an empty chain.

`staff_location_scope` and `staff_department_scope` are the remit pair, and they
are the two a reader misses. They reach `access.js` as the parameters `locScope`
and `deptScope`, so searching that file for `*_scope` finds five columns rather
than seven. `hasRemit` is the AND of both resolving non-empty, so a persona that
omits them default-denies on `staff_pii` whatever its `staff_pii_scope` says.

Three of the seven deny, each for a different reason, and the differences are
the point:

- **O'Quinn** — his remit is deliberately non-empty, so a `staff_pii` refusal is
  attributable to the empty chain alone. Production cannot reach that branch,
  because Cube hard-errors on an `equals []` row filter instead of returning
  zero rows ([#4269](https://github.com/TEAMSchools/teamster/issues/4269)).
- **Ogwumike** — `none` on all seven axes: a real row that resolves to no groups
  at all. She can still read `staff_directory`, which any resolved identity can.
- **Unresolvable Odinson** — no `dim_staff_cube_access` row whatsoever. Denied
  even `staff_directory`, which is the only way to distinguish "known user with
  no access" from "unknown user".

### The two paths

Both cover every persona the manifest fabricates.

- **SQL API** — open one connection per persona, with the persona's address as
  the connecting user and the deployment's SQL password. Identity is the
  connecting user, so the connection _is_ the switch; there is no in-session
  swap and none is needed.
- **REST** — mint a token carrying the persona's `email` claim, signed with the
  sandbox deployment's API secret. `checkAuth` verifies the signature and
  resolves that identity.

Holding a deployment's API secret therefore means being able to become any
persona on it. On the sandbox that is the point, and it is safe because every
row is fabricated — which is also exactly why the sandbox is a separate
deployment with its own secret.

`CUBE_IMPERSONATORS` governs the Cube Cloud web UI, which MasterBorn does not
have, and is KTAF-only.

### The canaries

Ten assertions over those identities, in `src/cube/sandbox/canaries.yml`. KTAF
CI owns the file and MasterBorn's kit suite runs it unmodified, so it carries no
PII and names only fabricated people.

| Persona      | View                                       | Expect  |
| ------------ | ------------------------------------------ | ------- |
| Ogwumike     | `student_attendance_enrollment_daily_view` | BLOCKED |
| Unresolvable | `student_attendance_enrollment_daily_view` | BLOCKED |
| Ogwumike     | `staff_pii`                                | BLOCKED |
| Swoopes      | `student_attendance_enrollment_daily_view` | ROWS    |
| Ilgauskas    | `staff_pii`                                | ROWS    |
| Munroe       | `staff_pii`                                | ROWS    |
| O'Quinn      | `staff_pii`                                | BLOCKED |
| Maximoff     | `staff_pii`                                | ROWS    |
| Ilgauskas    | `staff_directory`                          | ROWS    |
| Unresolvable | `staff_directory`                          | BLOCKED |

`BLOCKED` asserts the real SQL API denial text,
`Table or CTE with name '<view>' not found`. **A quiet zero rows against a
`BLOCKED` canary is a failure, not a pass.** That single rule is what forces
sign-off against the deployment: a dev-mode server downgrades a hard denial to
an empty result, so a dev-mode run would report a falsely clean suite
([#4605](https://github.com/TEAMSchools/teamster/issues/4605)).

At least one `ROWS` canary is required. A suite of denials alone goes green
against a deployment that denies everyone, which looks identical to perfect
isolation.

Cube Cloud routes on the database name, so the runner needs the deployment name
passed explicitly — its default suits a local Cube server and no cloud
deployment:

```bash
uv run python scripts/cube_rls_matrix.py \
  --expect src/cube/sandbox/canaries.yml \
  --host <sql api host> --port <sql api port> \
  --dbname <deployment name> --password <sql api password>
```

## The reserved name namespace

Every fabricated person takes a surname from
`src/cube/sandbox/reserved_names.yml`, and nothing else uses these words. A
closed list of _plausible_ names would prove only provenance — a real student
could be called Jayden Rodriguez too — so an invented surname makes the
appearance of the name the proof. It works the way `example.com` does:
self-identifying because it is reserved and published, not because the string is
impossible.

!!! note "Publishing the list is what reserves it"

    A namespace nobody published is not reserved. These 58 surnames are
    reserved for synthetic people and must not be used for anything else.
    They come from WNBA and NBA players active within the last thirty years
    and from Marvel characters. No KTAF staff member and no KTAF student
    carries any of them, which is what makes a surname here
    self-identifying, and `uv run python -m teamster.cube_sandbox.collisions`
    re-checks that against production and fails on a single match. The
    reserved surnames are:

    Taurasi, Swoopes, Catchings, Fowles, Griner, Ionescu,
    McCoughtry, Ogwumike, Delle Donne, Plum, Diggins-Smith,
    Sutton-Brown, Weatherspoon, Vandersloot, Ogunbowale, Meesseman,
    Holdsclaw, Magbegor, Loyd, Ndour, Antetokounmpo, Dončić, Jokić,
    Embiid, Wembanyama, Ginóbili, Nowitzki, Mutombo, Divac, Kukoč,
    Gasol, O'Quinn, Ilgauskas, Porziņģis, Valančiūnas, Siakam,
    Gobert, Şengün, Haliburton, Stark, Romanoff, Danvers, Maximoff,
    Murdock, Rambeau, Natchios, Odinson, Osborn, Quill, Strange,
    Toomes, Frost, Howlett, LeBeau, Munroe, Pryde, Rasputin,
    Worthington.

Given names stay realistic, because that is where the character classes that
break interfaces live — apostrophes, hyphens, diacritics, internal spaces,
single characters, overflow lengths. Each given name carries the class it
exercises, so coverage can assert every class is present rather than trusting a
random sample to include the hard ones.

Addresses are on a domain under `.invalid`, which RFC 2606 guarantees never
resolves, so a fabricated address cannot collide with a real account and no mail
can reach a synthetic person even by accident.

## Deploying

The sandbox runs in **CLI mode**, not Git mode. Git mode deploys on every push
to the tracked branch and leaves deliberateness resting on branch discipline;
CLI mode means nothing deploys until someone runs the command.

This is a deliberate, scoped exception to
[`src/cube/CLAUDE.md`](https://github.com/TEAMSchools/teamster/blob/main/src/cube/CLAUDE.md)'s
"no manual deploy command", which applies to the production deployment.

```bash
git checkout sandbox-YYYY.MM.DD
cd src/cube && npx cubejs-cli deploy
```

## Bumping the pin

One pin covers the model, the schema snapshot and the catalog together. Pinning
them separately would make the checks compare the wrong pair.

**The review is scheduled; the bump is not.** Read the drift report monthly.
Bump when MasterBorn asks, or when KTAF has a reason — the kit needs a member
that does not exist yet, or the repoint is getting worse. A drift threshold that
compels a bump is tracking `main` with extra steps, and it reopens the failure
the design rejects: MasterBorn's in-flight build moving under them without
anyone deciding. Analytics engineering owns the bump.

Each bump, in order:

1. Move the single pin — model, snapshot and catalog together.
2. Regenerate the catalog and commit it, so the move is a reviewable diff.
3. Tag the commit `sandbox-YYYY.MM.DD`.
4. Take the member-level diff of additions, removals and retypes as the release
   note.
5. Send that note to MasterBorn **before** deploying. A note arriving after the
   surface changed is a changelog, not a warning, and warning is the point.
6. Deploy that checkout.
7. Re-run the coverage, canary and divergence suites against the new state.

!!! warning "Refreshing an artifact is not deploying it"

    A refresh lands as a reviewed pull request and changes nothing MasterBorn
    sees. The diff accumulated between bumps is the release note the bump
    ships.

## The toolchain

Everything except the load step and the live checks runs from committed files
with no cloud access.

| Command                                                     | Does                                                | Needs the sandbox?  |
| ----------------------------------------------------------- | --------------------------------------------------- | ------------------- |
| `uv run python -m teamster.cube_sandbox.snapshot`           | Refresh the schema snapshot from production         | No (needs prod)     |
| `uv run python -m teamster.cube_sandbox.manifest`           | Regenerate `coverage_manifest.yml`                  | No                  |
| `uv run python -m teamster.cube_sandbox.checks`             | Assert model, snapshot and manifest agree           | No                  |
| `uv run python -m teamster.cube_sandbox.collisions`         | Assert no reserved surname belongs to a real person | No (needs prod)     |
| `uv run python -m teamster.cube_sandbox.generate --scale …` | Write one Avro file per table to a local directory  | No                  |
| `uv run python -m teamster.cube_sandbox.coverage`           | Score the generated Avro against the manifest       | No                  |
| `uv run python -m teamster.cube_sandbox.load`               | Stage to GCS, create the tables, load, verify       | Yes                 |
| `uv run scripts/cube_sandbox_isolation.py`                  | Both isolation legs, as the sandbox service account | Yes                 |
| `uv run scripts/cube_sandbox_deny_policy.py`                | Assert `deny-sandbox-bigquery` still exists         | No (needs prod IAM) |
| `uv run scripts/cube_rls_matrix.py --expect <canaries>`     | Assert the canaries                                 | Yes                 |
| `uv run python -m teamster.cube_sandbox.divergence`         | Assert the three query pairs still disagree         | Yes                 |
| `uv run python -m teamster.cube_sandbox.mutate`             | Score whether the canaries are load-bearing         | Yes                 |
| `uv run python -m teamster.cube_sandbox.meta_check`         | Assert `/meta` matches the pinned catalog           | Yes                 |

The last three read their connection details from the environment and exit with
a message naming what is missing rather than falling back to localhost. A suite
that quietly measures a dev server reports on a deployment nobody ships.

`.github/workflows/cube-sandbox-contract.yaml` runs the consistency check, a
`tiny` generate-and-score, and the unit tests on every pull request touching
`src/cube/`, the toolchain, `scripts/`, or the dbt marts whose `not_null` tests
the manifest reads.

### The first real load

Everything up to the load runs anywhere. The load needs the sandbox service
account key and nothing else; it never touches `teamster-332318`.

```bash
# 1. Both isolation legs, as the sandbox service account. A failure here
#    blocks generation: an isolation regression must stop synthetic writes.
uv run scripts/cube_sandbox_isolation.py --key-stdin

# 2. Model, snapshot and manifest agree at this commit.
uv run python -m teamster.cube_sandbox.checks

# 3. Prove the generator against the contract before spending an hour on
#    production scale. Same generator, same seed — only the multiplier differs.
uv run python -m teamster.cube_sandbox.generate --scale tiny
uv run python -m teamster.cube_sandbox.coverage --avro-dir build/cube_sandbox/tiny

# 4. Production scale, then the load: GCS upload, CREATE OR REPLACE TABLE from
#    the pinned snapshot, load, and a column-and-type check against it.
uv run python -m teamster.cube_sandbox.generate --scale full
uv run python -m teamster.cube_sandbox.load --avro-dir build/cube_sandbox/full

# 5. Assert the result.
uv run scripts/cube_rls_matrix.py --expect src/cube/sandbox/canaries.yml
uv run python -m teamster.cube_sandbox.divergence
```

Step 4 needs `GOOGLE_APPLICATION_CREDENTIALS` pointing at the sandbox service
account key, and the `teamster-cube-sandbox-staging` bucket to exist. Step 5
needs `CUBE_SANDBOX_SQL_HOST` and `CUBE_SANDBOX_SQL_PASSWORD`, and runs against
the sandbox deployment's **production** environment — never a Dev Mode one,
which returns zero rows where production denies
([#4605](https://github.com/TEAMSchools/teamster/issues/4605)).

!!! warning "BigQuery ignores a load job's schema for AVRO"

    Google's own guidance is explicit: "Specifying a schema is supported when
    you load CSV and JSON (newline delimited) files. When you load Avro,
    Parquet, ORC, Firestore export data, or Datastore export data, the schema
    is automatically retrieved from the self-describing source data."

    So the spec's "create each table's schema explicitly from the pinned
    snapshot" cannot be done by passing `LoadJobConfig.schema`. `load.py`
    creates the table from the snapshot first and then loads with
    `WRITE_TRUNCATE_DATA`, which keeps the existing table's schema, and
    `CREATE_NEVER`, so no load can conjure an Avro-shaped table of its own.
    `assert_complete` then compares column names **and types** against the
    snapshot — a `NUMERIC` that landed as `FLOAT64` is exactly the drift a
    name-only check waves through.

### The coverage contract

`src/cube/sandbox/coverage_manifest.yml` lists every cell the data must contain,
each marked `uncovered` until the generator fills it. It is **generated, not
hand-written**, so a new production column, view or scope value becomes a loud
uncovered cell rather than an absence nobody notices.

A column needs both a null row and a non-null row, except where one of three
derived exemptions applies: it is a join or surrogate key, a column an
`access_policy` filters on, or a column dbt asserts is never null. All three are
derived structurally — none is a list, and none is a rule about the column's
name.

!!! note "A missing exemption is a dbt ticket, not a manifest edit"

    `INFORMATION_SCHEMA` reports every `kipptaf_marts` column `NULLABLE`, so
    it exempts nothing. A column that is never null in practice but carries
    no dbt `not_null` test is a missing test. The sandbox nulling it surfaces
    that, and the fix belongs in dbt.

### Isolation

| Thing             | Value                                                              |
| ----------------- | ------------------------------------------------------------------ |
| Sandbox project   | `teamster-cube-sandbox`, dataset `kipptaf_marts`, US               |
| Service account   | `cube-cloud-sandbox@teamster-cube-sandbox.iam.gserviceaccount.com` |
| Its roles         | `bigquery.jobUser`, `bigquery.dataViewer`, sandbox project only    |
| Cross-project IAM | None, in either direction                                          |
| Deny policy       | `deny-sandbox-bigquery` on `teamster-332318`                       |

The isolation test has two legs and **both must run or neither counts**: the
sandbox account is refused on production, and the same account in the same run
reads the sandbox successfully. A service account whose credentials are broken
fails the production read exactly like an isolated one, so without the positive
leg the test goes green on the day the sandbox breaks.

It is two scripts because it needs two identities. One account holding both
would be a step toward the cross-project binding the design exists to prevent.

## Known gaps

- **Nothing has been loaded.** The generator, the coverage gate and the load
  step all run, and a `tiny` run scores zero uncovered cells against the
  committed manifest — but no one has yet run the load against the sandbox
  project, so the dataset does not exist and no query has been served from it.
  See _The first real load_.
- **Eight manifest cells are not scored by counting rows**: `hasRemit` and
  `hasChain` each way, the unresolvable identity, and the three divergences. The
  generator produces all eight, and unit tests assert the first five directly
  against the generated rows — but proving them end to end needs a live query,
  so `coverage.py` reports them UNPROVEN and the canary and divergence suites
  own them, each with its own non-zero exit.
- **Mutation testing perturbs the model only.** `mutate.py` deletes one
  `access_policy` block at a time and requires a canary to flip red. The spec's
  other arm — perturbing a persona's scope value — reaches a deployment only
  through a regenerate, a reload, and the expiry of `resolveAccess`'s per-email
  cache at the next midnight ET. That is a cycle, not a mutation run, so the
  runner does not drive it and does not report a score for it.
- Nothing on the analytics side holds `iam.googleapis.com/denypolicies.list` on
  `teamster-332318`, so `cube_sandbox_deny_policy.py` exits UNPROVEN rather than
  PASS.
- `cube-catalog-meta.json` is not yet on `main`, so the `/meta` check has no
  current pinned catalog to compare against and says so rather than inventing
  one.
