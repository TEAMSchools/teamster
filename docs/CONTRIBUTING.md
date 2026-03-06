# Welcome to the TEAMster contributing guide

Read our [Code of Conduct](CODE_OF_CONDUCT.md) to keep our community
approachable and respectable.

In this guide you will get an overview of the contribution workflow from
creating a branch, creating a pull request, reviewing, and merging the pull
request.

Here are some resources to help you get started with open source contributions:

- [GitHub flow](https://docs.github.com/en/get-started/quickstart/github-flow)
- [Collaborating with pull requests](https://docs.github.com/en/github/collaborating-with-pull-requests)

## Project structure

All source code is in the `src/` directory.

`src/teamster/` contains all Dagster code, organized as:

- `core/` — shared resources, IO managers, and utilities
- `libraries/` — reusable asset builders and resource definitions (one
  subpackage per integration)
- `code_locations/` — per-school Dagster definitions (`kipptaf`, `kippnewark`,
  `kippcamden`, `kippmiami`, `kipppaterson`)

`src/dbt/` contains all dbt code, organized by
[project](https://docs.getdbt.com/docs/build/projects).

### dbt Projects

`kipptaf` is the homebase for all CMO-level reporting. This project contains
views that aggregate regional tables as well as CMO-specific data. This is the
**only** project that dbt Cloud is configured to work with.

`kippnewark`, `kippcamden`, `kippmiami`, and `kipppaterson` contain regional
configurations that ensure their data is loaded into their respective datasets.

Other projects (e.g. `powerschool`, `deanslist`, `iready`) contain code for
systems used across multiple regions. Keeping these projects as installable
dependencies allows the code to be maintained in one place and shared across
projects.

### Model conventions

Models follow standard prefixes reflecting their layer in the data flow.

#### Staging (`stg_`)

Modular building blocks from source data.

- File naming: `stg_{source}__{entity}.sql`
- **`contract: enforced: true`** — required on all staging models
- **Uniqueness test** — required: either a single-column `unique:` test or
  `dbt_utils.unique_combination_of_columns` for composite keys

#### Intermediate (`int_`)

Layers of logic with clear and specific purposes, preparing staging models to
join into the entities we want.

- Folder structure: subdirectories by area of business concern
- File naming: `int_{business_concern}__{entity}_{verb}.sql`
  - Business concerns: `assessments`, `surveys`, `people`
  - Verbs: `pivot`, `unpivot`, `rollup`
- **Uniqueness test** — required: either a single-column `unique:` test or
  `dbt_utils.unique_combination_of_columns` for composite keys

#### Marts / Extracts (`rpt_`)

Wide, rich views of the entities our organization cares about, or extracts
consumed by reporting tools and applications.

- **`contract: enforced: true`** — required on all marts and extract models.
  These are the last stop before data reaches an external reporting tool
  (Tableau, PowerSchool, Google Sheets, etc.). Schema changes break downstream
  [exposures](https://docs.getdbt.com/reference/exposure-properties) and must be
  made deliberately.
- **Uniqueness test** — required: either a single-column `unique:` test or
  `dbt_utils.unique_combination_of_columns` for composite keys

### Exposures

Every external tool that consumes our data must have a
[dbt exposure](https://docs.getdbt.com/reference/exposure-properties) defined in
the consuming project (typically `src/dbt/kipptaf/models/exposures/`). Exposures
make the dependency graph explicit and power Dagster asset lineage.

**All exposures** require a `name`, `label`, `type`, `owner`, `depends_on`
(listing every model the tool uses), and a `url` linking to the external
tool/workbook/sheet:

```yaml
exposures:
  - name: exposure_name_snake_case
    label: Human Readable Title
    type: dashboard | application | analysis
    owner:
      name: Data Team
    depends_on:
      - ref("rpt_tableau__some_model")
    url: https://...
    config:
      meta:
        dagster:
          kinds:
            - tableau # or: googlesheets, powerschool, etc.
```

**Tableau dashboards** that refresh on a schedule must additionally include the
Tableau workbook LSID and a `cron_schedule` under `asset.metadata`. Workbooks
without a scheduled refresh can omit the `asset` block:

```yaml
config:
  meta:
    dagster:
      kinds:
        - tableau
      asset:
        metadata:
          id: <tableau-workbook-lsid-uuid>
          cron_schedule: "0 7 * * *" # omit entirely if no scheduled refresh
```

## Account setup

### GitHub

To contribute on GitHub, you must be a member of our
[Data Team](https://github.com/orgs/TEAMSchools/teams/data-team), and your
ability to approve and merge pull requests depends on your membership in one of
these subgroups:

- [Analytics Engineers](https://github.com/orgs/TEAMSchools/teams/analytics-engineers)
- [Data Engineers](https://github.com/orgs/TEAMSchools/teams/data-engineers)
- [Admins](https://github.com/orgs/TEAMSchools/teams/admins)

### Google Workspace

To access our BigQuery project and its datasets, you must be a member of our
**TEAMster Analysts KTAF** Google security group.

### dbt Cloud

#### Dataset

When you first login to dbt Cloud, you will be asked to set up **Development
credentials**.

dbt will create a development "branch" of the database for every user, and it
will name datasets using a prefix that is unique to you.

By default, this is your username, but please prefix it with an underscore (`_`)
to avoid cluttering up our BigQuery navigation. BigQuery will hide any datasets
that begin with an underscore from the left nav.

![Alt text](images/dbt_cloud/development_credentials.png)

#### sqlfmt

<!-- adapted from https://docs.getdbt.com/docs/cloud/dbt-cloud-ide/lint-format#format-sql -->

To format SQL code, we use [sqlfmt](https://sqlfmt.com/), an uncompromising SQL
query formatter that works with Jinja templating.

To confirm that dbt Cloud is set up to use sqlfmt:

1. Make sure you're on a development branch. Formatting isn't available on main
   or read-only branches.
2. Open a `.sql` file and click on the **Code Quality** tab.
3. Click on the <kbd>&lt;/&gt; Config</kbd> button on the right side of the
   console.
4. In the code quality tool config pop-up, select the `sqlfmt` radio button.
5. Go to the console section (below the file editor) and click
   <kbd>Format</kbd>.
6. This auto-formats your code in the file editor.

## Make Changes

### Create a branch

[Version control basics](https://docs.getdbt.com/docs/collaborate/git/version-control-basics)

![Alt text](images/dbt_cloud/create_branch.png)

### Make your changes

...

### Commit your changes

![Alt text](images/dbt_cloud/commit_sync.png)

### Open a pull request

When you're finished making changes, create a
[Pull Request](https://docs.github.com/en/pull-requests) ("PR").

1. On dbt Cloud, click
   ![Create a pull request on GitHub](images/dbt_cloud/create_pull_request.png)
2. On the GitHub page that pops up, click "Create pull request"
   ![Alt text](images/github/create_pull_request.png)
3. Fill in the pull request template and click "Create pull request".

## Code review

Once created, [Zapier](https://zapier.com/) will create a task for your pull
request in our
[Teamster Asana Project](https://app.asana.com/0/1205971774138578/1205971926225838).

- [x] Find yours by the **title** or **number**
- [x] Update the **due date** and **assignee**
- [x] Ensure that you are a **follower** on the task

GitHub will automatically assign default reviewers based on the location of the
code changes submitted:

| Filepath                           | Default Approvers                                                                    |
| ---------------------------------- | ------------------------------------------------------------------------------------ |
| `src/dbt/kipptaf/models/extracts/` | [Analytics Engineers](https://github.com/orgs/TEAMSchools/teams/analytics-engineers) |
| `src/teamster/`                    | [Data Engineers](https://github.com/orgs/TEAMSchools/teams/data-engineers)           |
| `docs/`                            | [Data Team](https://github.com/orgs/TEAMSchools/teams/data-team)                     |
| All other directories              | [Admins](https://github.com/orgs/TEAMSchools/teams/admins)                           |

A series of automatic checks will then run on the submitted code.

### Resolving merge conflicts

If you run into merge issues, see this
[git tutorial](https://github.com/skills/resolve-merge-conflicts) to help you
resolve merge conflicts and other issues.

### Trunk

[Trunk](https://trunk.io/) runs multiple linters that check for common errors
and enforce style.

| Language | Linter(s)                                                                                   |
| -------- | ------------------------------------------------------------------------------------------- |
| SQL      | [SQLFluff](https://docs.sqlfluff.com/en/stable/rules.html), [sqlfmt](https://sqlfmt.com/)   |
| Python   | [Ruff](https://docs.astral.sh/ruff/rules/), [Pyright](https://github.com/microsoft/pyright) |

Run locally with:

```bash
trunk check
trunk fmt
```

### dbt Cloud

dbt Cloud will create a branch dataset for your pull request on BigQuery and
attempt to build modified files.

If there are any issues with your code, the check will fail, and you can find
the reasons by:

1. Clicking on the `Details` link
2. Expanding the **Invoke `dbt build ...`** section
3. Selecting **Debug Logs**

![Alt text](images/github/dbt_cloud_check.png)

![Alt text](images/dbt_cloud/deploy_run_build.png)

- We may ask for changes to be made before a PR can be merged, either using
  [suggested changes](https://docs.github.com/en/github/collaborating-with-pull-requests/incorporating-feedback-in-your-pull-request)
  or pull request comments. You can apply suggested changes directly through the
  UI, or make other changes in your branch and commit them.
- As you update your PR and apply changes, mark each conversation as
  [resolved](https://docs.github.com/en/github/collaborating-with-pull-requests/commenting-on-a-pull-request#resolving-conversations).

## Your PR is merged

Congratulations!

Once your PR is merged:

- GitHub triggers a Dagster deployment
- Dagster scans for code changes every 5 minutes
- Dagster launches a run to update all changed models
