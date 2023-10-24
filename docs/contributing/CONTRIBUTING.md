# Welcome to the Teamster contributing guide

Read our [Code of Conduct](CODE_OF_CONDUCT.md) to keep our community approachable and respectable.

In this guide you will get an overview of the contribution workflow from opening an issue, creating
a PR, reviewing, and merging the PR.

## New contributor guide

To get an overview of the project, read the [README](/) file. Here are some resources to help you
get started with open source contributions:

- [Finding ways to contribute to open source on GitHub](https://docs.github.com/en/get-started/exploring-projects-on-github/finding-ways-to-contribute-to-open-source-on-github)
- [Set up Git](https://docs.github.com/en/get-started/quickstart/set-up-git)
- [GitHub flow](https://docs.github.com/en/get-started/quickstart/github-flow)
- [Collaborating with pull requests](https://docs.github.com/en/github/collaborating-with-pull-requests)

## Getting started

To navigate our codebase with confidence, see
[the introduction to working in the docs repository](/contributing/working-in-docs-repository.md)
:confetti_ball:. For more information on how we write our markdown files, see
[the GitHub Markdown reference](contributing/content-markup-reference.md).

Check to see what [types of contributions](/contributing/types-of-contributions.md) we accept before
making changes. Some of them don't even require writing a single line of code :sparkles:.

## Issues

### Create a new issue

If you spot a problem with the docs,
[search if an issue already exists](https://docs.github.com/en/github/searching-for-information-on-github/searching-on-github/searching-issues-and-pull-requests#search-by-the-title-body-or-comments).
If a related issue doesn't exist, you can open a new issue using a relevant
[issue form](https://github.com/github/docs/issues/new/choose).

## Make Changes

### Make changes in dbt Cloud

1. "Create branch"
2. Make your changes
3. Commit your changes

### Commit your update

Commit the changes once you are happy with them. Don't forget to
[self-review](/contributing/self-review.md) to speed up the review process:zap:.

### Pull Request

When you're finished with the changes, create a pull request, also known as a PR.

1. On dbt Cloud: "Create a pull request on GitHub"
2. On GitHub: "Create pull request"

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

### Your PR is merged

Congratulations :tada::tada: The GitHub team thanks you :sparkles:.

Once your PR is merged, your contributions will...

- deploy to Dagster
- SQL updates will take effect whenever the next update is triggered. The lag can vary significantly
  depending on the source of the data.
- If you need changes to appear immediately, we can force an update via Dagster. [how to communicate
  that?]
