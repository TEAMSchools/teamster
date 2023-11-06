# Welcome to the Teamster contributing guide

Read our [Code of Conduct](CODE_OF_CONDUCT.md) to keep our community approachable and respectable.

In this guide you will get an overview of the contribution workflow from creating a branch, creating
a pull request, reviewing, and merging the pull request.

## New contributor guide

Here are some resources to help you get started with open source contributions:

- [Set up Git](https://docs.github.com/en/get-started/quickstart/set-up-git)
- [GitHub flow](https://docs.github.com/en/get-started/quickstart/github-flow)
- [Collaborating with pull requests](https://docs.github.com/en/github/collaborating-with-pull-requests)

## Getting started

### Account setup

- [ ] Google Workspace
- [ ] dbt Cloud
- [ ] GitHub

To contribute on GitHub, you must be a member of our
[Data Team](https://github.com/orgs/TEAMSchools/teams/data-team), and your ability to approve and
merge pull requests depends on your membership in one of these subgroups:

- [Analytics Engineers](https://github.com/orgs/TEAMSchools/teams/analytics-engineers)
- [Data Engineers](https://github.com/orgs/TEAMSchools/teams/data-engineers)
- [Admins](https://github.com/orgs/TEAMSchools/teams/admins)

To access our BigQuery project and its datasets, you must be a member of `TEAMster Analysts KTAF`.

### dbt Cloud configuration

#### Development Dataset

When you first login to dbt Cloud, you will be asked to set up **Development credentials**. Every
user gets their own development _branch_ of the database, and dbt will prefix every dataset it
generates with a name specific to you. By default, this will be your username, but please add an
underscore (`_`) to avoid cluttering up our BigQuery navigation. BigQuery will hide any datasets
that begin with an underscore from the left nav.

![Alt text](../images/dbt-cloud/settings_profile_credentials.png)

#### sqlfmt

<!-- adapted from https://docs.getdbt.com/docs/cloud/dbt-cloud-ide/lint-format#format-sql -->

To format our SQL code, we use [sqlfmt](https://sqlfmt.com/), an uncompromising SQL query formatter
that provides one way to format SQL and works with Jinja templating.

To enable sqlfmt:

1. Make sure you're on a development branch. Formatting isn't available on main or read-only
   branches.
2. Open a `.sql` file and click on the **Code Quality** tab.
3. Click on the <kbd></> Config</kbd> button on the right side of the console.
4. In the code quality tool config pop-up, you have the option to select **sqlfluff** or **sqlfmt**.
5. To format your code, select the `sqlfmt` radio button.
6. Once selected, go to the console section (located below the File editor) and select the
   <kbd>Format</kbd> button.
7. This button auto-formats your code in the File editor. Once you've auto-formatted, you'll see a
   message confirming the outcome.

## Make Changes

### Make changes in dbt Cloud

#### Create a branch

https://docs.getdbt.com/docs/collaborate/git/version-control-basics

![Alt text](../images/dbt-cloud/version-control.png)

#### Make your changes

- naming conventions
- Format button

#### Commit your changes

...

### Pull Request

When you're finished with the changes, create a **Pull Request** ("PR").

1. On dbt Cloud, click "Create a pull request on GitHub"
2. On the GitHub page that pops up, click "Create pull request"

- Fill the "Ready for review" template so that we can review your PR. This template helps reviewers
  understand your changes as well as the purpose of your pull request.
- Asana
- We may ask for changes to be made before a PR can be merged, either using
  [suggested changes](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/incorporating-feedback-in-your-pull-request)
  or pull request comments. You can apply suggested changes directly through the UI. You can make
  any other changes in your fork, then commit them to your branch.
- As you update your PR and apply changes, mark each conversation as
  [resolved](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/commenting-on-a-pull-request#resolving-conversations).
- If you run into any merge issues, checkout this
  [git tutorial](https://github.com/skills/resolve-merge-conflicts) to help you resolve merge
  conflicts and other issues.

You should always review your own PR first. For content changes, make sure that you:

- [ ] Confirm that the changes meet the user experience and goals outlined in the content design
      plan (if there is one).
- [ ] Compare your pull request's source changes to staging to confirm that the output matches the
      source and that everything is rendering as expected. This helps spot issues like typos,
      content that doesn't follow the style guide, or content that isn't rendering due to versioning
      problems. Remember that lists and tables can be tricky.
- [ ] Review the content for technical accuracy.
- [ ] Copy-edit the changes for grammar, spelling, and adherence to the
      [style guide](https://github.com/github/docs/blob/main/contributing/content-style-guide.md).
- [ ] If there are any failing checks in your PR, troubleshoot them until they're all passing.

- dbt action
- trunk action, sqlfluff style guide

### Your PR is merged

Congratulations :tada::tada: The GitHub team thanks you :sparkles:.

Once your PR is merged, your contributions will...

- deploy to Dagster
- SQL updates will take effect whenever the next update is triggered. The lag can vary significantly
  depending on the source of the data.
- If you need changes to appear immediately, we can force an update via Dagster. [how to communicate
  that?]
