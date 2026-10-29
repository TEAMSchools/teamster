"""Command line: `uv run python -m scripts.cube_validation <command> ...`.

Commands: `discover`, `preflight`, `prove`, `check-api`, `run`, `triage`,
`triage confirm`, `add-decisions`, `reapply`, `review`, `record-answers`, `members`,
`inventory-workbook`, `inventory`. Exit
codes: 0 done, 1 refused (the message says why), 2 usage error. This module parses
arguments and builds the clients; `pipeline.py` does the work. Tests replace
`make_warehouse`, `make_cube`, `tableau_session`, `utcnow` and `cache_root`.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import dataclasses
import json
import os
import sys
import tempfile
import urllib.parse

# trunk-ignore(bandit/B405): only ParseError is used; the workbook is parsed in builder
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import tableauserverclient as TSC
import yaml

from . import (
    answers,
    builder,
    confirm,
    pipeline,
    preflight,
    report,
    tableau,
    trace,
    triage,
)
from .bq import CostCapError, ViewHistoryError, Warehouse
from .config import (
    ConfigError,
    ViewConfig,
    load_view_config,
    replace_text,
    with_fact_dataset,
    write_decision,
)
from .cube_client import Cube, CubeError, CubeRefusal
from .moment import MomentError

EXPOSURES = (
    Path(__file__).resolve().parents[2] / "src/dbt/kipptaf/models/exposures/tableau.yml"
)
URL_VAR = "CUBE_REST_URL"
# trunk-ignore(bandit/B105): environment variable name, not a value
SECRET_VAR = "CUBE_API_SECRET"
EMAIL_VAR = "CUBE_VALIDATION_EMAIL"
# Points every command at another cache, such as a copy of a run to rework.
CACHE_VAR = "CUBE_VALIDATION_CACHE"
# Every run on this machine shares 1 daily BigQuery cap (UTC day).
DAILY_MAX_USD = 3.0

# Errors that mean "stopped on purpose or by a check". Anything else is a bug
# and keeps its traceback; no message here carries a secret.
REFUSALS = (
    pipeline.Refusal,
    ConfigError,
    CostCapError,
    ViewHistoryError,
    MomentError,
    CubeRefusal,
    CubeError,
    tableau.RefreshMovedError,
    answers.AnswerError,
)


def make_warehouse() -> Warehouse:
    """BigQuery through application default credentials."""
    return Warehouse()


def _warehouse(args: argparse.Namespace) -> Warehouse:
    """A warehouse that shares its view cache and daily spend with other runs."""
    wh = make_warehouse()
    # One day's ledger per machine, wherever the cache is.
    wh.configure_local(cache_root(), args.max_usd_per_day, ledger_dir=report.CACHE_ROOT)
    return wh


def make_cube(base_url: str, secret: str, email: str) -> Cube:
    return Cube(base_url, secret, email)


@contextlib.contextmanager
def tableau_session() -> Iterator[tableau.Tableau]:
    """Sign in with the PAT in the environment and sign out afterwards.

    Raises:
        pipeline.Refusal: A sign-in variable is unset, or Tableau refused the
            token. The message names variables, never their values.
    """
    missing = [name for name in tableau.ENV_VARS if not os.environ.get(name)]
    if missing:
        raise pipeline.Refusal(f"set {', '.join(missing)} to sign in to Tableau")
    try:
        server = tableau.sign_in_from_env()
    except TSC.ServerResponseError as exc:
        raise pipeline.Refusal(
            f"Tableau refused the sign-in: {exc.code} {exc.summary}"
        ) from exc
    tbl = tableau.Tableau(server, sign_in=tableau.sign_in_from_env)
    try:
        yield tbl
    finally:
        if problem := tbl.sign_out():
            print(f"warning: Tableau sign-out failed: {problem}", file=sys.stderr)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def cache_root() -> Path:
    """The local cache: `CUBE_VALIDATION_CACHE` when set, else `report.CACHE_ROOT`."""
    return Path(os.environ.get(CACHE_VAR) or report.CACHE_ROOT)


def _cube(args: argparse.Namespace) -> Cube:
    """Build the Cube client, refusing with the variable a value is missing from."""
    url = os.environ.get(URL_VAR)
    if not url:
        raise pipeline.Refusal(f"set {URL_VAR} (it ends in /cubejs-api/v1)")
    secret = os.environ.get(SECRET_VAR)
    if not secret:
        raise pipeline.Refusal(f"set {SECRET_VAR} to sign Cube tokens")
    email = getattr(args, "email", None) or os.environ.get(EMAIL_VAR)
    if not email:
        raise pipeline.Refusal(
            f"pass --email or set {EMAIL_VAR} to a network-grant email"
        )
    return make_cube(url, secret, email)


def _cube_host() -> str:
    """The host and port of `CUBE_REST_URL`, without any userinfo."""
    parts = urllib.parse.urlparse(os.environ.get(URL_VAR, ""))
    host = parts.hostname or ""

    return f"{host}:{parts.port}" if parts.port else host


def _moment(value: str) -> datetime:
    try:
        return pipeline.utc(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.cube_validation",
        description="Validate Cube measures against dashboards, anchors and identities.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def view_file(p: argparse.ArgumentParser) -> None:
        p.add_argument("view", type=Path, help="src/cube/validation/<view>.yml")

    def email(p: argparse.ArgumentParser) -> None:
        p.add_argument("--email", help=f"network-grant email; or set {EMAIL_VAR}")

    def max_usd(p: argparse.ArgumentParser) -> None:
        p.add_argument("--max-usd", type=float, default=5.0, help="BigQuery cap")
        p.add_argument(
            "--max-usd-per-day",
            type=float,
            default=DAILY_MAX_USD,
            help="BigQuery cap across every run today (UTC)",
        )

    p = sub.add_parser("discover", help="rank workbook fields against a measure")
    view_file(p)
    email(p)
    p.add_argument("--measure", required=True, help="Cube measure short name")
    source = p.add_mutually_exclusive_group()
    source.add_argument(
        "--exposure", action="append", default=[], help="limit to an exposure name"
    )
    source.add_argument(
        "--twb",
        type=Path,
        help="read this local .twb instead of downloading; no Tableau sign-in",
    )
    p.add_argument(
        "--caption", help="the dashboard's name for the measure; ranks first"
    )
    shown = p.add_mutually_exclusive_group()
    shown.add_argument("--limit", type=int, default=5, help="candidates to print")
    shown.add_argument("--all", action="store_true", help="print every candidate")

    def fact_dataset(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--fact-dataset",
            help="read the fact from this dataset instead of the validation "
            "file's: kipptaf_marts, or zz_<user>_kipptaf_marts for your dbt dev "
            "build",
        )

    p = sub.add_parser(
        "preflight", help="list what each sheet needs before prove, offline"
    )
    view_file(p)
    p.add_argument(
        "--twb", type=Path, help="the local .twb to read (required); no Tableau sign-in"
    )
    p.add_argument(
        "--sheet",
        action="append",
        default=[],
        help="check this sheet instead of the comparisons' sheets; repeat it",
    )

    p = sub.add_parser("prove", help="prove a probe against its sheet once")
    view_file(p)
    fact_dataset(p)
    which = p.add_mutually_exclusive_group(required=True)
    which.add_argument(
        "--comparison",
        action="append",
        help="comparison id to prove; repeat it to prove several from one export",
    )
    which.add_argument(
        "--check", action="store_true", help="list proofs older than their workbook"
    )
    p.add_argument(
        "--headers",
        action="store_true",
        help="print each cut's export headers and stop; nothing is probed or written",
    )
    max_usd(p)

    p = sub.add_parser("check-api", help="Cube's API equals its compiled SQL")
    view_file(p)
    fact_dataset(p)
    email(p)
    max_usd(p)

    p = sub.add_parser("run", help="validate a view at one fact build")
    view_file(p)
    fact_dataset(p)
    p.add_argument("--moment", type=_moment, help="ISO time; the build ending by it")
    email(p)
    max_usd(p)

    p = sub.add_parser("triage", help="sort each open item of a run into a pile")
    view_file(p)
    fact_dataset(p)
    email(p)
    max_usd(p)
    p.add_argument(
        "--no-trace",
        action="store_true",
        help="skip tracing unmatched rows to the step that drops them",
    )
    p.add_argument(
        "--manifest",
        type=Path,
        default=trace.MANIFEST,
        help="dbt manifest with compiled SQL for the tables the trace descends into",
    )
    p.add_argument(
        "--trace-max-minutes",
        type=float,
        default=trace.TRACE_MAX_MINUTES,
        help="stop the trace after this long, keeping what it found",
    )
    p.add_argument(
        "--no-proofs",
        action="store_true",
        help="skip re-running the view's stored proofs (`triage confirm`)",
    )

    # `triage confirm ...` on the command line; see `main`.
    p = sub.add_parser(
        "triage-confirm",
        help="prove a comparison bucket's row groups with one classification query",
    )
    view_file(p)
    fact_dataset(p)
    email(p)
    max_usd(p)
    p.add_argument("--comparison", required=True, help="the comparison it proves")
    p.add_argument(
        "--bucket", choices=confirm.PROVABLE, help="the unmatched rows it classifies"
    )
    p.add_argument(
        "--sql",
        type=Path,
        help="the proof's SQL; defaults to the stored proof, to re-run an edit",
    )
    p.add_argument(
        "--cause",
        action="append",
        default=[],
        help="<bucket>=<side>:<plain words>, for every bucket the query returns",
    )
    p.add_argument(
        "--items",
        action="append",
        default=[],
        help="triage item ids to report (comma-separated); all are proven",
    )
    p.add_argument(
        "--cells",
        action="store_true",
        help="confirm the comparison's cell set from its proven groups; no query",
    )

    p = sub.add_parser(
        "add-decisions", help="write an approved triage batch as decisions"
    )
    view_file(p)
    p.add_argument(
        "approved",
        type=Path,
        help='JSON list of {"id", "call", "reason", "task", "item"}',
    )

    p = sub.add_parser(
        "reapply", help="apply the file's decisions to the saved run, offline"
    )
    view_file(p)

    p = sub.add_parser(
        "record-answers", help="write a domain owner's answers comment as decisions"
    )
    p.add_argument("views", type=Path, nargs="+", help="validation files")
    p.add_argument(
        "--comment", type=Path, required=True, help="the answers comment's body"
    )
    p.add_argument("--author", required=True, help="the comment author's login")
    p.add_argument(
        "--yes", action="store_true", help="write; without it, only print the changes"
    )

    p = sub.add_parser("review", help="print the domain-owner review issue body")
    p.add_argument("views", type=Path, nargs="+", help="validation files")
    p.add_argument("--domain", required=True, help="domain whose owner reviews")

    p = sub.add_parser("members", help="list Cube measures and the ones sharing SQL")
    email(p)

    p = sub.add_parser(
        "inventory-workbook", help="list the fields each worksheet of a .twb uses"
    )
    p.add_argument("twb", type=Path, help="a downloaded .twb file")

    p = sub.add_parser(
        "inventory", help="join the gap catalog, workbook review and Asana per field"
    )
    p.add_argument("catalog", type=Path, help="the gap catalog markdown")
    p.add_argument("slug", help="the dashboard's slug in the catalog")
    p.add_argument("--review", type=Path, required=True, help="inventory-workbook JSON")
    p.add_argument("--asana", type=Path, required=True, help="JSON of field, status")
    return parser


def _load(path: Path) -> ViewConfig:
    if not path.is_file():
        raise pipeline.Refusal(f"{path}: no such validation file")
    return load_view_config(path)


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "review":
        configs = [_load(v) for v in args.views]
        print(
            pipeline.review(
                configs,
                args.domain,
                cache_root(),
                now=utcnow(),
                view_files=args.views,
            )
        )
        return 0

    if args.command == "record-answers":
        return _record_answers(args.views, args.comment, args.author, args.yes)

    if args.command == "members":
        return _members(_cube(args))

    if args.command == "inventory-workbook":
        return _inventory_workbook(args.twb)

    if args.command == "inventory":
        return _inventory(args.catalog, args.slug, args.review, args.asana)

    cfg = _load(args.view)
    # Without the flag the file's `fact:` is used exactly as written.
    if getattr(args, "fact_dataset", None) is not None:
        cfg = with_fact_dataset(cfg, args.fact_dataset)

    if args.command == "run":
        cube = _cube(args)
        pipeline.run(
            cfg,
            wh=_warehouse(args),
            cube=cube,
            now=utcnow(),
            requested=args.moment,
            max_usd=args.max_usd,
            cache_root=cache_root(),
            cube_host=_cube_host(),
        )
        return 0

    if args.command == "triage":
        triage.run_triage(
            cfg,
            wh=_warehouse(args),
            cube=_cube(args),
            max_usd=args.max_usd,
            cache_root=cache_root(),
            trace_rows=not args.no_trace,
            manifest=args.manifest,
            trace_max_minutes=args.trace_max_minutes,
            proofs=None if args.no_proofs else confirm.proofs_dir(args.view, cfg.view),
        )
        return 0

    if args.command == "triage-confirm":
        if not args.cells and not args.bucket:
            raise pipeline.Refusal("pass --bucket, or --cells")
        if args.cells:
            # No query runs, so no warehouse or Cube is needed.
            wh, cube = None, None
        else:
            wh, cube = _warehouse(args), _cube(args)
        return confirm.run_confirm(
            cfg,
            args.view,
            wh=wh,
            cube=cube,
            max_usd=args.max_usd,
            cache_root=cache_root(),
            comparison=args.comparison,
            bucket=args.bucket,
            sql=args.sql,
            causes=args.cause,
            items=[i for flag in args.items for i in flag.split(",") if i],
            cells=args.cells,
        )

    if args.command == "add-decisions":
        return _add_decisions(cfg, args.view, args.approved)

    if args.command == "reapply":
        _reapply(cfg)
        return 0

    if args.command == "check-api":
        cube = _cube(args)
        pipeline.check_api(
            cfg, wh=_warehouse(args), cube=cube, clock=utcnow, max_usd=args.max_usd
        )
        return 0

    if args.command == "preflight":
        return _preflight(cfg, args.twb, args.sheet)

    if args.command == "discover":
        cube = _cube(args)
        if args.twb is not None and not args.twb.is_file():
            raise pipeline.Refusal(f"{args.twb}: no such workbook file")
        # A local workbook needs no Tableau sign-in; Cube still compiles the
        # measure.
        session = contextlib.nullcontext() if args.twb else tableau_session()
        with session as tbl:
            pipeline.discover(
                cfg,
                args.measure,
                cube=cube,
                tbl=tbl,
                exposures_path=EXPOSURES,
                only=args.exposure,
                caption=args.caption,
                limit=None if args.all else args.limit,
                twb_path=args.twb,
            )
        return 0

    # prove
    if args.check:
        with tableau_session() as tbl:
            pipeline.prove_check(cfg, tbl=tbl)
        return 0
    captures: dict = {}
    with tableau_session() as tbl:
        if args.headers:
            refused = _each(
                args.comparison,
                tbl,
                lambda cid: pipeline.prove_headers(
                    cfg, args.view, cid, tbl=tbl, captures=captures
                ),
            )
        else:
            wh = _warehouse(args)
            refused = _each(
                args.comparison,
                tbl,
                lambda cid: pipeline.prove(
                    cfg,
                    args.view,
                    cid,
                    wh=wh,
                    tbl=tbl,
                    now=utcnow(),
                    max_usd=args.max_usd,
                    captures=captures,
                    failures_dir=cache_root() / cfg.view,
                ),
            )
    return 1 if refused else 0


RUN_AGAIN = (
    "Run `run` again only when the data, the Cube model or the dashboard "
    "changed, or for new comparisons."
)


def _reapply(cfg: ViewConfig) -> None:
    """Re-apply a file's decisions to its saved run and say what is open."""
    run = pipeline.reapply(cfg, cache_root())
    counts = (
        f"{len(run.applied.open)} open groups, {len(run.applied.open_gaps)} open "
        f"gaps, {len(run.applied.open_cells)} open cell diffs"
    )
    if run.applied.reconfirm:
        counts += f", {len(run.applied.reconfirm)} decisions to re-confirm"
    print(
        f"Re-applied decisions to the saved run of "
        f"{run.moment.end:%Y-%m-%d %H:%M} UTC: {counts}"
    )


def _reapply_written(paths: list[Path]) -> None:
    """Re-apply after a write; a view with no usable run says so and goes on.

    The decisions are already written, so a missing or older saved run is not
    a refusal here: the analyst runs `run` for that view instead.
    """
    refused = False
    for path in paths:
        try:
            _reapply(_load(path))
        except pipeline.Refusal as exc:
            print(f"{path}: not re-applied: {exc}", file=sys.stderr)
            refused = True
    if not refused:
        print(RUN_AGAIN)


def _write_all(writes: list[tuple[Path, dict]]) -> None:
    """Write each decision, restoring every file if any write fails."""
    originals = {path: path.read_text() for path, _ in writes}
    try:
        for path, decision in writes:
            write_decision(path, decision)
    except BaseException:
        for path, text in originals.items():
            replace_text(path, text)
        raise


def _check_claims(writes: list[tuple[Path, dict]], also=None) -> None:
    """Refuse, before writing, a batch whose decisions would claim one item twice.

    The writes are rehearsed on copies, so the check reads the decisions the
    way the loader will read the real file. `also(cfg)`, when given, checks
    each rehearsed file's config too.
    """
    with tempfile.TemporaryDirectory() as tmp:
        copies: dict[Path, Path] = {}
        for i, path in enumerate(dict.fromkeys(p for p, _ in writes)):
            copy = Path(tmp) / str(i) / path.name
            copy.parent.mkdir()
            copy.write_text(path.read_text())
            copies[path] = copy
        for path, decision in writes:
            write_decision(copies[path], decision)
        for path, copy in copies.items():
            try:
                rehearsed = load_view_config(copy)
                pipeline.check_claims(rehearsed, cache_root())
                if also is not None:
                    also(rehearsed)
            except pipeline.Refusal as exc:
                raise pipeline.Refusal(f"{path}: {exc}; nothing written") from exc


def _add_decisions(cfg: ViewConfig, path: Path, approved_path: Path) -> int:
    """Write an approved triage batch into the view's `decisions:`.

    Stubs and proven causes come from the triage beside the latest run and
    fingerprints from that run; a cause already decided keeps its decision
    (see `answers.approved_decisions`). Refuses while that triage is stale or
    holds an unproven item (see `triage.proven_triage`), or when a cause
    decision would disagree with a `group` decision on one group. The whole
    batch is written or none of it.
    """
    approved = _read_json(approved_path, "approved")
    run, run_json = pipeline.latest_run(cfg, cache_root())
    saved = triage.proven_triage(run, run_json, cfg.decisions, path.parent)

    decisions = answers.approved_decisions(
        approved, saved, run.fingerprints, existing=cfg.decisions
    )
    writes = [(path, d) for d in decisions]

    def agree(rehearsed: ViewConfig) -> None:
        items = copy.deepcopy(saved.get("items", []))
        triage.mark_decided(run, items, rehearsed.decisions, refuse=True)

    _check_claims(writes, agree)
    _write_all(writes)
    had = {d.id for d in cfg.decisions}
    for d in decisions:
        done = "re-approved" if d["id"] in had else "wrote"
        print(f"{path}: {done} {d['id']} ({d['call']})")
    _reapply_written([path])
    return 0


def _record_answers(views: list[Path], comment: Path, author: str, yes: bool) -> int:
    """Print what an answers comment changes; write it only with `yes`.

    Any answer that does not fit refuses the whole comment, and a failed
    write restores every file, so a comment is written whole or not at all.
    """
    if not comment.is_file():
        raise pipeline.Refusal(f"{comment}: no such comment file")
    configs = [(str(v), _load(v)) for v in views]
    changes = answers.answer_changes(
        answers.parse_answers(comment.read_text(encoding="utf-8")), configs
    )

    print(f"Comment by {author}")
    pending = []
    for c in changes:
        if (
            c.call[0] == c.call[1]
            and c.task[0] == c.task[1]
            and c.reason[0] == c.reason[1]
        ):
            print(f"{c.path}: {c.decision}: already recorded")
        else:
            pending.append(c)
    changes = pending
    for c in changes:
        where = f"{c.path}: {c.decision}"
        if c.call[0] != c.call[1]:
            print(f"{where}: call {c.call[0]} -> {c.call[1]}")
        if c.task[0] != c.task[1]:
            print(f"{where}: task {c.task[0] or '(none)'} -> {c.task[1]}")
        if c.reason[0] != c.reason[1]:
            print(f"{where}: reason -> {c.reason[1]}")
    if not yes:
        print("Nothing written; confirm with the analyst, then re-run with --yes.")
        return 0

    writes = []
    for c in changes:
        path = Path(c.path)
        raw = yaml.safe_load(path.read_text())["decisions"]
        decision = dict(next(d for d in raw if d.get("id") == c.decision))
        decision.update(call=c.call[1], reason=c.reason[1])
        if c.task[1]:
            decision["task"] = c.task[1]
        if decision.get("cause"):
            # Answered: `review` asks it no more, and it is never re-approved
            # on a changed proof.
            decision["answer"] = c.call[1]
        writes.append((path, decision))
    if not writes:
        print("Nothing to write; every answer is already recorded.")
        return 0
    _write_all(writes)
    print(f"Wrote {len(writes)} decisions.")
    _reapply_written([Path(p) for p in dict.fromkeys(c.path for c in changes)])
    return 0


def _members(cube: Cube) -> int:
    """Write `members.json` under the cache root; print measures sharing SQL."""
    skipped: list[dict] = []
    found = builder.members(cube, skipped)

    for item in skipped:
        print(f"skipped {item['name']}: {item['reason']}", file=sys.stderr)

    path = cache_root() / "members.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"members": [dataclasses.asdict(m) for m in found], "skipped": skipped},
            indent=2,
        )
    )
    print(f"{len(found)} members written to {path}")

    for group in builder.same_sql(found):
        print(f"same SQL: {', '.join(m.name for m in group)}")

    return 0


def _saved_members() -> list[builder.Member]:
    """The members `members` saved, or a refusal to run it first."""
    saved = cache_root() / "members.json"
    if not saved.is_file():
        raise pipeline.Refusal(f"{saved}: missing; run `members` first")
    try:
        return [
            builder.Member(**m)
            for m in json.loads(saved.read_text(encoding="utf-8"))["members"]
        ]
    except (TypeError, KeyError, json.JSONDecodeError) as exc:
        raise pipeline.Refusal(f"{saved}: unreadable ({exc!r}); run `members`") from exc


def _preflight(cfg: ViewConfig, twb: Path | None, sheets: list[str]) -> int:
    """Print each sheet's preflight checklist from a local `twb`.

    It never signs in to Tableau: a second sign-in with the shared token can
    end another session's.
    """
    if twb is None:
        raise pipeline.Refusal(
            "pass --twb <path>: preflight reads only a local workbook; download the "
            ".twb once (the cube-validation runbook) and reuse it"
        )
    if not twb.is_file():
        raise pipeline.Refusal(f"{twb}: no such workbook file")
    members = _saved_members()
    text = twb.read_text(encoding="utf-8")
    print(preflight.report(cfg, lambda _: (twb.name, text), members, sheets))
    return 0


def _inventory_workbook(path: Path) -> int:
    """Print the fields a local `.twb` uses, as JSON."""
    if not path.is_file():
        raise pipeline.Refusal(f"{path}: no such workbook file")
    try:
        uses = builder.workbook_inventory(path.read_text(encoding="utf-8"))
    except ET.ParseError as exc:
        raise pipeline.Refusal(f"{path}: not a workbook ({exc})") from exc
    print(json.dumps([dataclasses.asdict(u) for u in uses], indent=2))
    return 0


def _read_json(path: Path, what: str) -> list:
    """The list in a JSON file, or a refusal naming `what`."""
    if not path.is_file():
        raise pipeline.Refusal(f"{path}: no such {what} file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise pipeline.Refusal(f"{path}: not JSON ({exc})") from exc
    if not isinstance(data, list):
        raise pipeline.Refusal(f"{path}: expected a JSON list")
    return data


def _inventory(catalog: Path, slug: str, review: Path, asana: Path) -> int:
    """Print a dashboard's fields from 3 sources as a markdown table, then JSON."""
    if not catalog.is_file():
        raise pipeline.Refusal(f"{catalog}: no such catalog file")
    found = _saved_members()

    try:
        uses = [
            builder.FieldUse(**{**u, "sheets": tuple(u["sheets"])})
            for u in _read_json(review, "review")
        ]
        items = [
            {"field": a["field"], "status": a["status"]}
            for a in _read_json(asana, "asana")
        ]
    except (TypeError, KeyError, json.JSONDecodeError) as exc:
        raise pipeline.Refusal(f"unreadable input ({exc!r})") from exc

    rows = builder.inventory(
        builder.catalog_rows(catalog.read_text(encoding="utf-8"), slug),
        uses,
        items,
        found,
    )

    print("| field | kind | member | sources | disagreement |")
    print("| --- | --- | --- | --- | --- |")
    for r in rows:
        cells = [r.field, r.kind, r.member, ", ".join(r.sources), r.disagreement]
        print("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    print()
    print(json.dumps([dataclasses.asdict(r) for r in rows], indent=2))
    return 0


def _each(ids: list[str], tbl: tableau.Tableau, step) -> int:
    """Run `step` per comparison id and count the refusals.

    One comparison's refusal or Tableau error does not stop the others. A 401
    (Tableau ended the session) signs in again and retries that id once.
    """
    refused = 0
    for cid in ids:
        for attempt in (1, 2):
            try:
                step(cid)
            except TSC.ServerResponseError as exc:
                if attempt == 1 and str(exc.code).startswith("401"):
                    print(
                        f"Tableau ended the session ({exc.code}) during {cid}; "
                        "signing in again",
                        file=sys.stderr,
                    )
                    try:
                        tbl.reconnect()
                    except TSC.ServerResponseError as again:
                        raise pipeline.Refusal(
                            f"Tableau refused the sign-in: {again.code} {again.summary}"
                        ) from again
                    continue
                print(
                    f"refused: {cid}: Tableau answered {exc.code} {exc.summary}",
                    file=sys.stderr,
                )
                refused += 1
            except REFUSALS as exc:
                print(f"refused: {exc}", file=sys.stderr)
                refused += 1
            break
    return refused


def main(argv: list[str]) -> int:
    """Run the validator.

    Args:
        argv: Command line arguments after the program name.

    Returns:
        0 when the command finished, 1 when it refused (the reason goes to
        stderr), 2 for a usage error.
    """
    if argv[:2] == ["triage", "confirm"]:
        argv = ["triage-confirm", *argv[2:]]
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0

    try:
        return _dispatch(args)
    except REFUSALS as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
