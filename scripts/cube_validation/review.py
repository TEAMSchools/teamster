"""`ask-owner`: the owner's review issue and its questions file."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from . import answers, report, sort
from .config import ViewConfig
from .pipeline import Refusal
from .results import latest_run


def ask_owner(
    configs: list[ViewConfig],
    domain: str,
    cache_root: Path,
    *,
    now: datetime,
    view_files: list[Path],
    comments: list[str],
    json_file: Path,
) -> str:
    """Return the review-issue body from each view's latest saved run.

    Reads only the local cache: each run and its triage (see
    `sort.checked_sort`), matching triage items to decisions by their stubs,
    and to cause decisions by the causes the sort explained. What is ready is
    asked; what is not settled yet (items still in `investigate`, and
    comparisons missing, stale or skipped, `sort.comparisons_waiting`) is
    counted under "Still with the analyst" and never asked; the items one by
    one go to a file beside the questions JSON (`still_file`), linked the
    same way.
    Nothing is posted; a question with no triage evidence, a decision waiting
    to be re-confirmed (asked again only once decided again), and a body near
    GitHub's cap are named on stderr.

    Args:
        configs: The views to review.
        domain: The domain whose owner reviews.
        cache_root: The run cache.
        now: The current time, to say whether a hand check's pinned SQL still
            runs.
        view_files: Each config's validation file, in order: stored explanation
            paths are relative to its directory.
        comments: Receives the follow-up comments a long body's Reproduce
            blocks move to (`report.render_review_issue`).
        json_file: Where the questions JSON is written (`reviews/` beside the
            validation file); the body links it at the commit that holds it,
            instead of carrying it.

    Raises:
        Refusal: A view has no usable saved run (see `latest_run`), or its
            triage is missing, stale, unreadable, or has a cause decision and
            a `group` decision disagreeing (see `sort.checked_sort`). Or
            `json_file` or the open items' file is new or changed, or its
            commit is not pushed (each is written; commit and push them, then
            review again).
    """
    saved = [latest_run(cfg, cache_root) for cfg in configs]
    runs = [run for run, _ in saved]
    # Stored explanation paths are relative to each validation file's directory.
    bases = [f.parent for f in view_files]
    proven = {
        run.view: sort.checked_sort(run, run_json, cfg.decisions, base)
        for (run, run_json), cfg, base in zip(saved, configs, bases, strict=True)
    }
    found = {view: sort.posted_sort(loaded) for view, loaded in proven.items()}
    unsettled = [u for run in runs for u in sort.unsettled(run, found[run.view])]
    still = report.still_with_analyst(
        unsettled,
        {
            run.view: sort.comparisons_waiting(cfg, run, proven[run.view])
            for run, cfg in zip(runs, configs, strict=True)
        },
        {run.view: sort.formulas_not_compared(proven[run.view]) for run in runs},
    )
    # One question per unanswered owner cause, over the groups it decides.
    causes = {
        run.view: sort.cause_asks(
            run, proven[run.view], cfg.decisions, sort.doc_leads(cfg)
        )
        for run, cfg in zip(runs, configs, strict=True)
    }
    definitions = {
        cfg.view: {c.id: c.definitions for c in cfg.comparisons if c.definitions}
        for cfg in configs
    }
    sources = {
        cfg.view: explanation_source(f)
        for cfg, f in zip(configs, view_files, strict=True)
    }
    questions = answers.questions_json(
        runs,
        configs,
        definitions,
        found,
        now,
        causes,
        sources,
    )
    # The analyst's other calls, which the body reports without asking.
    decided = {
        run.view: sort.cause_asks(run, proven[run.view], cfg.decisions, owner=False)
        for run, cfg in zip(runs, configs, strict=True)
    }
    files: list[tuple[Path, list[dict] | str]] = [
        (json_file, report.posted_json(questions))
    ]
    if unsettled:
        detail = report.unsettled_detail(unsettled, json_file.stem)
        files.append((still_file(json_file), detail))
    elif still_file(json_file).exists():
        # An earlier review's list would stay committed with nothing linking
        # it; it says so instead, in the same commit as the JSON.
        files.append((still_file(json_file), report.nothing_unsettled(json_file.stem)))
    link, *more = _review_files(files)
    still_link = more if unsettled else []
    unpublished = {
        cfg.view: {c.id for c in cfg.comparisons if c.unpublished} for cfg in configs
    }
    body = report.render_review_issue(
        domain,
        runs,
        definitions,
        questions,
        causes,
        comments,
        decided,
        link,
        still,
        unpublished,
        still_link[0] if still_link else None,
    )
    if len(body) > report.BODY_WARN_CHARS:
        # stderr, so the warning never lands in the issue body.
        print(
            f"warning: the body is {len(body):,} characters; GitHub refuses an "
            "issue body over 65,536, so review fewer views at a time",
            file=sys.stderr,
        )
    for q in questions:
        if not q["evidence"]:
            # stderr, so the note never lands in the issue body.
            print(
                f"{q['id']}: no triage evidence; `sort` the view to add it",
                file=sys.stderr,
            )
    for run in runs:
        if ids := [d.id for d in run.applied.reconfirm]:
            # stderr, so the note never lands in the issue body. A decision
            # waiting here asks nothing until it is decided again.
            n = len(ids)
            print(
                f"{run.view}: {n} decision{'' if n == 1 else 's'} to re-confirm, "
                f"left out of the questions: {', '.join(ids)}; see `To re-confirm` "
                "in its result",
                file=sys.stderr,
            )
    if waiting := report.untasked(d for cfg in configs for d in cfg.decisions):
        # stderr, so the reminder never lands in the issue body.
        print(
            'After posting, fill in `task: "#<issue>"` on: ' + ", ".join(waiting),
            file=sys.stderr,
        )
    return body


def review_file(view_files: list[Path], configs: list[ViewConfig], domain: str) -> Path:
    """Where a review's questions JSON is kept: `reviews/` beside the first
    validation file, named for its view, or for the domain across views."""
    name = configs[0].view if len(configs) == 1 else _slug(domain)
    return Path(view_files[0]).parent / "reviews" / f"{name}.json"


def still_file(json_file: Path) -> Path:
    """Where the open items are listed one by one: beside the questions JSON,
    named for it (`reviews/<view>-still-with-analyst.md`)."""
    return json_file.with_name(f"{json_file.stem}-still-with-analyst.md")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "review"


def _review_files(files: list[tuple[Path, list[dict] | str]]) -> list[str]:
    """Each file's link (`_review_file`), in order.

    Raises:
        Refusal: Any file was written or is not pushed; every file is
            written first, so one commit takes them all.
    """
    links, refused = [], []
    for path, data in files:
        try:
            links.append(_review_file(path, data))
        except Refusal as exc:
            refused.append(str(exc))
    if refused:
        raise Refusal("; ".join(refused))
    return links


def _review_file(path: Path, data: list[dict] | str) -> str:
    """A posted review file's link at the commit that holds it.

    `data` is the questions JSON, compared by content, or a Markdown text,
    compared with its whitespace collapsed; so the commit hook's formatting
    is no change.

    Raises:
        Refusal: The file was new or held other content (now written), or
            it is not committed and pushed as it stands.
    """
    try:
        text = path.read_text()
        held = text.split() if isinstance(data, str) else json.loads(text)
    except (OSError, ValueError):
        held = None
    if held != (data.split() if isinstance(data, str) else data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            data if isinstance(data, str) else json.dumps(data, indent=2) + "\n"
        )
        raise Refusal(
            f"wrote {path}: commit and push it, then run `ask-owner` again; the "
            "issue links it at that commit"
        )
    link = committed_link(path)
    if link is None:
        raise Refusal(
            f"{path} is not committed and pushed as it stands: commit and push "
            "it, then run `ask-owner` again"
        )
    return link


def committed_link(path: Path) -> str | None:
    """The GitHub link to `path` at HEAD, or None.

    None unless the file is tracked with no change since HEAD and HEAD is on
    a remote branch (a pushed commit), so the link opens once posted and
    keeps opening after the branch is gone.
    """
    base = path.parent
    try:
        top = Path(_git(base, "rev-parse", "--show-toplevel"))
        changed = _git(base, "status", "--porcelain", "--", path.name)
        tracked = _git(base, "ls-files", "--", path.name)
        sha = _git(base, "rev-parse", "HEAD")
        pushed = _git(base, "branch", "-r", "--contains", sha)
        remote = _git(base, "remote", "get-url", "origin")
        relative = path.resolve().relative_to(top.resolve())
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None
    found = _GITHUB.search(remote)
    if changed or not tracked or not pushed or not found:
        return None
    return f"https://github.com/{found['repo']}/blob/{sha}/{relative.as_posix()}"


_GITHUB = re.compile(r"github\.com[:/](?P<repo>[\w.-]+/[\w.-]+?)(?:\.git)?/?$")


def _git(directory: Path, *args: str) -> str:
    # trunk-ignore(bandit/B603,bandit/B607): git from PATH with a static argv and no shell
    done = subprocess.run(
        ["git", "-C", str(directory), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def explanation_source(view_file: Path) -> answers.ExplanationSource:
    """Where a validation file's stored explanations live: its repo path and the
    branch URL of its directory, for an owner's Reproduce block.

    Outside a git checkout, a GitHub remote or a branch, the link is left out.
    The remote's address is read for its `owner/repo` only, never copied.
    """
    view_file = Path(view_file)
    base = view_file.parent
    try:
        top = Path(_git(base, "rev-parse", "--show-toplevel"))
        branch = _git(base, "branch", "--show-current")
        remote = _git(base, "remote", "get-url", "origin")
        relative = view_file.resolve().relative_to(top.resolve())
    except (OSError, ValueError, subprocess.CalledProcessError):
        return answers.ExplanationSource(str(view_file), base)
    found = _GITHUB.search(remote)
    blob = None
    if found and branch:
        blob = (
            f"https://github.com/{found['repo']}/blob/{branch}/"
            f"{relative.parent.as_posix()}"
        )
    return answers.ExplanationSource(relative.as_posix(), base, blob)
