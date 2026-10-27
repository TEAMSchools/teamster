"""Command line: `uv run python -m scripts.cube_validation <command> ...`.

Commands: `discover`, `prove`, `check-api`, `run`, `review`. Exit codes: 0
done, 1 refused (the message says why), 2 usage error. This module parses
arguments and builds the clients; `pipeline.py` does the work. Tests replace
`make_warehouse`, `make_cube`, `tableau_session`, `utcnow` and `cache_root`.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import tableauserverclient as TSC

from . import pipeline, report, tableau
from .bq import CostCapError, ViewHistoryError, Warehouse
from .config import ConfigError, ViewConfig, load_view_config
from .cube_client import Cube, CubeError, CubeRefusal
from .moment import MomentError

EXPOSURES = (
    Path(__file__).resolve().parents[2] / "src/dbt/kipptaf/models/exposures/tableau.yml"
)
URL_VAR = "CUBE_REST_URL"
# trunk-ignore(bandit/B105): environment variable name, not a value
SECRET_VAR = "CUBE_API_SECRET"
EMAIL_VAR = "CUBE_VALIDATION_EMAIL"

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
    try:
        yield tableau.Tableau(server)
    finally:
        server.auth.sign_out()


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

    p = sub.add_parser("discover", help="rank workbook fields against a measure")
    view_file(p)
    email(p)
    p.add_argument("--measure", required=True, help="Cube measure short name")
    p.add_argument(
        "--exposure", action="append", default=[], help="limit to an exposure name"
    )

    p = sub.add_parser("prove", help="prove a probe against its sheet once")
    view_file(p)
    which = p.add_mutually_exclusive_group(required=True)
    which.add_argument("--comparison", help="comparison id to prove")
    which.add_argument(
        "--check", action="store_true", help="list proofs older than their workbook"
    )
    p.add_argument("--value-column", help="export column holding the compared value")
    max_usd(p)

    p = sub.add_parser("check-api", help="Cube's API equals its compiled SQL")
    view_file(p)
    email(p)
    max_usd(p)

    p = sub.add_parser("run", help="validate a view at one fact build")
    view_file(p)
    p.add_argument("--moment", type=_moment, help="ISO time; the build ending by it")
    email(p)
    max_usd(p)

    p = sub.add_parser("review", help="print the domain-owner review issue body")
    p.add_argument("views", type=Path, nargs="+", help="validation files")
    p.add_argument("--domain", required=True, help="domain whose owner reviews")
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

    cfg = _load(args.view)

    if args.command == "run":
        cube = _cube(args)
        pipeline.run(
            cfg,
            wh=make_warehouse(),
            cube=cube,
            now=utcnow(),
            requested=args.moment,
            max_usd=args.max_usd,
            cache_root=cache_root(),
        )
        return 0

    if args.command == "check-api":
        cube = _cube(args)
        pipeline.check_api(
            cfg, wh=make_warehouse(), cube=cube, clock=utcnow, max_usd=args.max_usd
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
            )
        return 0

    # prove
    if args.check:
        with tableau_session() as tbl:
            pipeline.prove_check(cfg, tbl=tbl)
        return 0
    wh = make_warehouse()
    with tableau_session() as tbl:
        pipeline.prove(
            cfg,
            args.view,
            args.comparison,
            wh=wh,
            tbl=tbl,
            now=utcnow(),
            max_usd=args.max_usd,
            value_column=args.value_column,
        )
    return 0


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
