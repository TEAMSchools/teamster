# Guides

## Account Setup

### GitHub

To contribute, you must be a member of our
[Data Team](https://github.com/orgs/TEAMSchools/teams/data-team). Your ability
to approve and merge pull requests depends on your subgroup:

- [Analytics Engineers](https://github.com/orgs/TEAMSchools/teams/analytics-engineers)
- [Data Engineers](https://github.com/orgs/TEAMSchools/teams/data-engineers)
- [Admins](https://github.com/orgs/TEAMSchools/teams/admins)

### Google Workspace

To access our BigQuery project and its datasets, you must be a member of the
**TEAMster Analysts KTAF** Google security group.

### dbt Cloud

#### Development dataset

dbt Cloud creates a personal development dataset in BigQuery for each user,
named using your username as a prefix. Please prefix yours with an underscore
(`_`) — BigQuery hides datasets starting with `_` from the left nav, keeping the
project list readable.

Set this in **Account settings → Credentials → Development credentials**.

#### sqlfmt

<!-- adapted from https://docs.getdbt.com/docs/cloud/dbt-cloud-ide/lint-format#format-sql -->

We use [sqlfmt](https://sqlfmt.com/) for SQL formatting. To enable it in dbt
Cloud:

1. Open a `.sql` file on a development branch.
2. Click the **Code Quality** tab in the console, then **`</> Config`**.
3. Select the `sqlfmt` radio button.
4. Click **Format** to auto-format the file.

## Guides

| Guide                                     | Description                                                            |
| ----------------------------------------- | ---------------------------------------------------------------------- |
| [Codespaces](codespaces.md)               | Setting up and using GitHub Codespaces                                 |
| [Local Development](local-development.md) | Installing dependencies, running Dagster locally, linting, and testing |
| [Dagster](dagster.md)                     | Tableau scheduling, backfills, branch deployments, monitoring runs     |
| [Google Sheets & Forms](google-sheets.md) | Adding and updating Google Sheets and Forms sources                    |
| [dbt Development](dbt-development.md)     | Targets, defer, staging external sources, cross-project workflows      |
