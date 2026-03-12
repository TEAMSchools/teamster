# Contributing

Read our [Code of Conduct](CODE_OF_CONDUCT.md) to keep our community
approachable and respectful.

## Make Changes

Create a branch, make your changes, and commit them. See
[GitHub flow](https://docs.github.com/en/get-started/quickstart/github-flow) for
the basics.

When you're ready, open a
[pull request](https://docs.github.com/en/pull-requests) against `main` and fill
in the PR template.

## Code Review

Once a PR is opened, [Zapier](https://zapier.com/) creates a task for it in our
[Teamster Asana project](https://app.asana.com/0/1205971774138578/1205971926225838).

- [ ] Find yours by **title** or **number**
- [ ] Set the **due date** and **assignee**
- [ ] Make sure you are a **follower** on the task

GitHub automatically assigns default reviewers based on the files changed:

| Filepath                           | Default approvers                                                                    |
| ---------------------------------- | ------------------------------------------------------------------------------------ |
| `src/dbt/kipptaf/models/extracts/` | [Analytics Engineers](https://github.com/orgs/TEAMSchools/teams/analytics-engineers) |
| `src/teamster/`                    | [Data Engineers](https://github.com/orgs/TEAMSchools/teams/data-engineers)           |
| `docs/`                            | [Data Team](https://github.com/orgs/TEAMSchools/teams/data-team)                     |
| All other directories              | [Admins](https://github.com/orgs/TEAMSchools/teams/admins)                           |

### Automated checks

Two checks run on every PR:

**Trunk** — lints Python and SQL. If it fails, run `trunk check` and `trunk fmt`
locally to reproduce and fix the issues.

**dbt Cloud** — builds modified models in a branch dataset. If it fails:

1. Click **Details** on the failing check.
2. Expand **Invoke `dbt build ...`**.
3. Select **Debug Logs**.

### Merge conflicts

If your branch has conflicts with `main`, see
[Resolving a merge conflict](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/addressing-merge-conflicts/resolving-a-merge-conflict-using-the-command-line).

As you address review feedback, mark each conversation as
[resolved](https://docs.github.com/en/github/collaborating-with-pull-requests/commenting-on-a-pull-request#resolving-conversations).

## After Merge

Once your PR merges:

- GitHub triggers a Dagster deployment
- Dagster scans for code changes every 5 minutes
- Dagster launches a run to update all changed models
