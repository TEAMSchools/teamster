"""Command line: `uv run python -m scripts.cube_validation <command> ...`.

Commands: `discover`, `prove`, `check-api`, `run`, `review`, `members`,
`inventory-workbook`, `inventory`. Exit codes: 0
done, 1 refused (the message says why), 2 usage error. This module parses
arguments and builds the clients; `pipeline.py` does the work. Tests replace
`make_warehouse`, `make_cube`, `tableau_session`, `utcnow` and `cache_root`.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import os
import sys
import urllib.parse

# trunk-ignore(bandit/B405): only ParseError is used; the workbook is parsed in builder
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import tableauserverclient as TSC

from . import builder, pipeline, report, tableau
from .bq import CostCapError, ViewHistoryError, Warehouse
from .config import (
    DEFAULT_FACT_DATASET,
    ConfigError,
    ViewConfig,
    load_view_config,
    with_fact_dataset,
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
)


def make_warehouse() -> Warehouse:
    """BigQuery through application default credentials."""
    return Warehouse()


def _warehouse(args: argparse.Namespace) -> Warehouse:
    """A warehouse that shares its view cache and daily spend with other runs."""
    wh = make_warehouse()
    wh.configure_local(cache_root(), args.max_usd_per_day)
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
    return report.CACHE_ROOT


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
    p.add_argument(
        "--exposure", action="append", default=[], help="limit to an exposure name"
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
            default=DEFAULT_FACT_DATASET,
            help="the fact's dataset: kipptaf_marts, or zz_<user>_kipptaf_marts "
            "for your dbt dev build",
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
        print(pipeline.review(configs, args.domain, cache_root()))
        return 0

    if args.command == "members":
        return _members(_cube(args))

    if args.command == "inventory-workbook":
        return _inventory_workbook(args.twb)

    if args.command == "inventory":
        return _inventory(args.catalog, args.slug, args.review, args.asana)

    cfg = with_fact_dataset(
        _load(args.view), getattr(args, "fact_dataset", DEFAULT_FACT_DATASET)
    )

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

    if args.command == "check-api":
        cube = _cube(args)
        pipeline.check_api(
            cfg, wh=_warehouse(args), cube=cube, clock=utcnow, max_usd=args.max_usd
        )
        return 0

    if args.command == "discover":
        cube = _cube(args)
        with tableau_session() as tbl:
            pipeline.discover(
                cfg,
                args.measure,
                cube=cube,
                tbl=tbl,
                exposures_path=EXPOSURES,
                only=args.exposure,
                caption=args.caption,
                limit=None if args.all else args.limit,
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
    saved = cache_root() / "members.json"
    if not saved.is_file():
        raise pipeline.Refusal(f"{saved}: missing; run `members` first")

    try:
        found = [
            builder.Member(**m)
            for m in json.loads(saved.read_text(encoding="utf-8"))["members"]
        ]
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
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0

    try:
        return _dispatch(args)
    except REFUSALS as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
