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

| Filepath                            | Default approvers                                                                    |
| ----------------------------------- | ------------------------------------------------------------------------------------ |
| `src/dbt/kipptaf/models/extracts/`  | [Analytics Engineers](https://github.com/orgs/TEAMSchools/teams/analytics-engineers) |
| `src/dbt/kipptaf/models/marts/`     | [Analytics Engineers](https://github.com/orgs/TEAMSchools/teams/analytics-engineers) |
| `src/dbt/kipptaf/models/metrics/`   | [Analytics Engineers](https://github.com/orgs/TEAMSchools/teams/analytics-engineers) |
| `src/dbt/kipptaf/models/exposures/` | [Analytics Engineers](https://github.com/orgs/TEAMSchools/teams/analytics-engineers) |
| `src/teamster/`                     | [Data Engineers](https://github.com/orgs/TEAMSchools/teams/data-engineers)           |
| `docs/`                             | [Data Team](https://github.com/orgs/TEAMSchools/teams/data-team)                     |
| All other directories               | [Admins](https://github.com/orgs/TEAMSchools/teams/admins)                           |

### Automated checks

Several checks run automatically on every non-draft PR:

**Trunk** — lints Python and SQL. Note: Pyright is excluded from the CI check;
run `trunk check` locally to catch type errors before pushing. Fix any failures
with `trunk check` and `trunk fmt`.

**dbt Cloud** — builds modified dbt models in a branch dataset on BigQuery. If
it fails, click **Details** on the failing check, expand **Invoke
`dbt build ...`**, and select **Debug Logs**.

**Dagster Cloud** — builds Docker images for any affected code locations and
creates a branch deployment. Triggered only when relevant source paths change.
Skipped on draft PRs.

**Claude Code Review** — posts an automated code review comment when the PR is
opened or marked ready for review.

### Merge conflicts

If your branch has conflicts with `main`, see
[Resolving a merge conflict](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/addressing-merge-conflicts/resolving-a-merge-conflict-using-the-command-line).

As you address review feedback, mark each conversation as
[resolved](https://docs.github.com/en/github/collaborating-with-pull-requests/commenting-on-a-pull-request#resolving-conversations).

## After Merge

Once your PR merges to `main`, GitHub Actions rebuilds Docker images for any
affected code locations and deploys them to Dagster Cloud production. Your
changes are live once the deploy workflow completes.
