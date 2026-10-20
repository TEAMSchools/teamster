import argparse
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from google.cloud import bigquery

from teamster.libraries.nj_isr.drive import (
    GoogleDriveApi,
    folder_id_from_url,
    load_credentials,
)
from teamster.libraries.nj_isr.pdf_io import read_page_texts, write_output_pdf
from teamster.libraries.nj_isr.publish import publish
from teamster.libraries.nj_isr.run import (
    RunPlan,
    administration_year,
    build_plan,
    investigation_rows,
    missing_districts,
    summarize,
    write_investigation_csv,
)
from teamster.libraries.nj_isr.warehouse import load_crosswalk, load_students

BIGQUERY_PROJECT = "teamster-332318"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m teamster.libraries.nj_isr",
        description=(
            "Split state ISR PDFs by each student's current school and publish "
            "them, with a regional index Sheet, to Google Drive."
        ),
    )
    parser.add_argument("--input", required=True, type=Path, help="Folder of PDFs")
    parser.add_argument(
        "--root-folder",
        help="Link or ID of the Drive folder that holds the region folders",
    )
    parser.add_argument(
        "--school-year",
        type=int,
        help="Academic year for current enrollment (default: administration year)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Plan and print, touch no Drive file"
    )
    parser.add_argument("--local-out", type=Path, help="Folder for the output PDFs")
    parser.add_argument(
        "--checks-out",
        type=Path,
        help=(
            "CSV for the investigation list, which holds student names "
            "(default: nj_isr_checks_<tag>.csv next to the input folder)"
        ),
    )
    parser.add_argument(
        "--create-missing-folders",
        action="store_true",
        help="Create region and school folders that Drive does not have",
    )
    parser.add_argument(
        "--page-anchor",
        action="store_true",
        help="Link each index row to its page in the PDF",
    )

    args = parser.parse_args(argv)

    if not args.dry_run and not args.root_folder:
        parser.error("--root-folder is required unless --dry-run")

    return args


def _write_pdfs(plan: RunPlan, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return {file.file_name: write_output_pdf(file, out_dir) for file in plan.files}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    admin_year = administration_year(args.input)
    school_year = args.school_year or admin_year

    client = bigquery.Client(project=BIGQUERY_PROJECT)
    # the state crosswalk's academic year is the one before the spring test
    crosswalk = load_crosswalk(client, admin_year - 1)
    students, by_state_id = load_students(client, school_year)

    plan = build_plan(
        args.input,
        read_pages=read_page_texts,
        crosswalk=crosswalk,
        by_state_id=by_state_id,
        students=students,
        school_year=school_year,
    )
    print(summarize(plan, None))

    checks_rows = investigation_rows(plan)
    checks_path = write_investigation_csv(
        checks_rows,
        args.checks_out or args.input.parent / f"nj_isr_checks_{plan.tag}.csv",
    )
    print(f"Investigation list: {len(checks_rows)} rows -> {checks_path}")

    absent = missing_districts(plan)
    if absent:
        message = (
            f"No original state file for district(s) {', '.join(absent)}. "
            "A partial input would overwrite those schools' files with a subset "
            "of their students."
        )

        if not args.dry_run:
            print(f"\nStopping, nothing was published. {message}", file=sys.stderr)
            return 1

        print(f"\nWarning: {message}")

    if args.dry_run:
        if args.local_out:
            _write_pdfs(plan, args.local_out)
            print(f"\nWrote {len(plan.files)} PDFs to {args.local_out}")

        return 0

    with tempfile.TemporaryDirectory() as temp_dir:
        pdf_paths = _write_pdfs(plan, args.local_out or Path(temp_dir))

        api = GoogleDriveApi(load_credentials())
        result = publish(
            api,
            folder_id_from_url(args.root_folder),
            plan.files,
            pdf_paths,
            plan.rows_by_region,
            program=plan.program,
            admin=plan.admin,
            tag=plan.tag,
            ran_at=datetime.now(),
            create_missing=args.create_missing_folders,
            page_anchor=args.page_anchor,
        )

    print(summarize(plan, result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
