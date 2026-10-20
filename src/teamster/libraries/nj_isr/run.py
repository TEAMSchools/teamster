import csv
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from teamster.libraries.nj_isr.destinations import (
    PROGRAM_DISTRICTS,
    REGION_BY_DISTRICT,
    REGION_FOLDERS,
    SCHOOL_FOLDERS,
)
from teamster.libraries.nj_isr.layout import (
    IndexRow,
    OutputFile,
    admin_label,
    build_output_files,
    check_conservation,
    index_rows,
    tag_value,
)
from teamster.libraries.nj_isr.match import (
    TRANSFER_FOLDER,
    Placement,
    Resolution,
    Student,
    place,
    resolve,
)
from teamster.libraries.nj_isr.models import IsrFormatError, MissingFolderError, Record
from teamster.libraries.nj_isr.publish import PublishResult
from teamster.libraries.nj_isr.segment import (
    apply_corrections,
    find_duplicate_state_ids,
    find_source_files,
    scan_folder,
)

INVESTIGATION_COLUMNS = (
    "issue",
    "filed_in",
    "region",
    "output_file",
    "page",
    "printed_name",
    "printed_birth_date",
    "state_id",
    "student_number",
    "powerschool_last_name",
    "powerschool_first_name",
    "powerschool_birth_date",
    "source_file",
    "source_seq",
)

_PARTIAL_ISSUES = {"last name": "birth date differs", "birth date": "last name differs"}
_UNMATCHED_ISSUES = {
    "failed_confirmation": "name and birth date differ",
    "source_conflict": "state and PowerSchool point to different students",
    "no_candidate": "no student for this state ID",
}
_RESOLVED_ISSUE = "state and PowerSchool disagreed; resolved"
_DUPLICATE_ISSUE = "state ID appears more than once in a file"


@dataclass(frozen=True)
class RunPlan:
    """Everything a run will do, worked out before any file is written.

    Attributes:
        program: "NJSLA" or "NJGPA".
        admin: Administration label, for example "Spring 2026".
        tag: Value that marks this run's Drive files.
        school_year: Academic year used to find each student's current school.
        records_in: Every record read, originals and corrections.
        replaced: Records that a correction replaced.
        unpaired_corrections: Corrections with no original to replace.
        duplicates: Records whose state ID repeats within a district file group.
        placements: Where each kept record is filed.
        files: The output files, one per destination folder and report type.
        rows_by_region: Index rows for each region's Sheet.
    """

    program: str
    admin: str
    tag: str
    school_year: int
    records_in: list[Record]
    replaced: list[Record]
    unpaired_corrections: list[Record]
    duplicates: list[Record]
    placements: list[Placement]
    files: list[OutputFile]
    rows_by_region: dict[str, list[IndexRow]]


def administration_year(input_dir: Path) -> int:
    """Read the administration year from the ISR filenames in a folder.

    Raises:
        IsrFormatError: If the folder has no ISR files, 2 files share a
            filename, or the files come from more than one year.
    """
    years = {source.year for source in find_source_files(input_dir)}

    if not years:
        raise IsrFormatError(f"no state ISR files found in {input_dir}")

    if len(years) > 1:
        raise IsrFormatError(
            f"{input_dir} mixes administration years "
            f"{', '.join(map(str, sorted(years)))}"
        )

    return years.pop()


def _place_record(
    record: Record,
    crosswalk: Mapping[str, set[int]],
    by_state_id: Mapping[str, set[int]],
    students: Mapping[int, Student],
) -> Placement:
    resolution = resolve(record, crosswalk, by_state_id, students)
    testing_region = REGION_BY_DISTRICT[record.source.district]
    placement = place(record, resolution, testing_region)

    # A student now enrolled outside the regions with report folders (Miami)
    # is filed with the region that administered the test.
    if placement.region not in REGION_FOLDERS:
        return Placement(record, resolution, testing_region, None, TRANSFER_FOLDER)

    return placement


def build_plan(
    input_dir: Path,
    *,
    read_pages: Callable[[Path], list[str]],
    crosswalk: Mapping[str, set[int]],
    by_state_id: Mapping[str, set[int]],
    students: Mapping[int, Student],
    school_year: int | None = None,
) -> RunPlan:
    """Read a folder of state ISR PDFs and decide where every record goes.

    Args:
        input_dir: Folder holding the state's PDFs.
        read_pages: Returns the text of each page of a PDF.
        crosswalk: State ID to student numbers from the state test file.
        by_state_id: State ID to student numbers from PowerSchool.
        students: PowerSchool students by student number.
        school_year: Academic year for current enrollment. Defaults to the
            administration year.

    Returns:
        The plan, with every record accounted for.

    Raises:
        IsrFormatError: If the files mix programs or administrations, a file
            fails segmentation, or a record is lost or duplicated.
        MissingFolderError: If a current school has no Drive folder name.
    """
    records_in = scan_folder(input_dir, read_pages)

    if not records_in:
        raise IsrFormatError(f"no state ISR files found in {input_dir}")

    admins = sorted({admin_label(r.source) for r in records_in})
    if len(admins) > 1:
        raise IsrFormatError(
            f"{input_dir} mixes administrations {', '.join(admins)}; "
            "run one administration at a time"
        )

    first = records_in[0].source
    kept, replaced, unpaired = apply_corrections(records_in)
    duplicates = find_duplicate_state_ids(kept)

    placements = [
        _place_record(record, crosswalk, by_state_id, students) for record in kept
    ]

    unknown_schools = sorted(
        {
            (p.region, p.schoolid, p.where)
            for p in placements
            if p.schoolid is not None and (p.region, p.schoolid) not in SCHOOL_FOLDERS
        }
    )
    if unknown_schools:
        raise MissingFolderError(
            "no folder name is configured for: "
            + "; ".join(
                f"{where!r} ({region}, schoolid {schoolid})"
                for region, schoolid, where in unknown_schools
            )
        )

    files = build_output_files(placements)
    check_conservation(records_in, replaced, files)

    return RunPlan(
        program=first.program,
        admin=admin_label(first),
        tag=tag_value(first),
        school_year=first.year if school_year is None else school_year,
        records_in=records_in,
        replaced=replaced,
        unpaired_corrections=unpaired,
        duplicates=duplicates,
        placements=placements,
        files=files,
        rows_by_region=index_rows(files),
    )


def missing_districts(plan: RunPlan) -> list[str]:
    """District codes the program needs that have no original record in the run.

    A run without every district would overwrite the other districts' files
    with a subset of their students. `PROGRAM_DISTRICTS` lists the districts
    each program tests.
    """
    present = {
        record.source.district
        for record in plan.records_in
        if record.source.reissue_date is None
    }
    return [
        district
        for district in PROGRAM_DISTRICTS[plan.program]
        if district not in present
    ]


def _iso(value: date | None) -> str:
    return "" if value is None else value.isoformat()


def _resolved_disagreement(resolution: Resolution) -> bool:
    """Whether the 2 sources named different students and 1 was confirmed."""
    return resolution.reason == "matched" and len(resolution.candidates) == 2


def _issues(placement: Placement, duplicates: set[tuple[Path, int]]) -> list[str]:
    """The investigation-list issues for a placement, none for a clean match."""
    resolution = placement.resolution
    record = placement.record
    issues: list[str] = []

    if resolution.reason == "matched":
        if partial := _PARTIAL_ISSUES.get(resolution.matched_on):
            issues.append(partial)
    else:
        issues.append(_UNMATCHED_ISSUES[resolution.reason])

    if _resolved_disagreement(resolution):
        issues.append(_RESOLVED_ISSUE)

    if (record.source.path, record.seq) in duplicates:
        issues.append(_DUPLICATE_ISSUE)

    return issues


def _student_columns(resolution: Resolution) -> dict[str, str]:
    student = resolution.student
    if student is None and len(resolution.candidates) == 1:
        student = resolution.candidates[0]

    if student is None:
        return {
            "student_number": "; ".join(
                str(c.student_number) for c in resolution.candidates
            ),
            "powerschool_last_name": "",
            "powerschool_first_name": "",
            "powerschool_birth_date": "",
        }

    return {
        "student_number": str(student.student_number),
        "powerschool_last_name": student.last_name,
        "powerschool_first_name": student.first_name,
        "powerschool_birth_date": _iso(student.dob),
    }


def investigation_rows(plan: RunPlan) -> list[dict[str, str]]:
    """List every record the Data team should check, 1 row per issue.

    The issues: a partial match (filed in the student's school but agreeing
    with PowerSchool on only the last name or only the birth date), an
    unmatched record, a source disagreement resolved by name and birth date,
    and a state ID repeated within a file. A record with 2 issues has 2 rows.
    The rows hold student names and birth dates and are never written to Drive
    or git.
    """
    duplicates = {(record.source.path, record.seq) for record in plan.duplicates}
    rows: list[dict[str, str]] = []
    for file in plan.files:
        for entry in file.entries:
            placement = entry.placement
            record = placement.record
            for issue in _issues(placement, duplicates):
                rows.append(
                    {
                        "issue": issue,
                        "filed_in": placement.where,
                        "region": placement.region,
                        "output_file": file.file_name,
                        "page": str(entry.page_in_file),
                        "printed_name": record.printed_name,
                        "printed_birth_date": _iso(record.printed_dob),
                        "state_id": record.state_id,
                        **_student_columns(placement.resolution),
                        "source_file": record.source.path.name,
                        "source_seq": str(record.seq),
                    }
                )

    return sorted(
        rows,
        key=lambda r: (
            r["region"],
            r["issue"],
            r["printed_name"],
            r["source_file"],
            int(r["source_seq"]),
        ),
    )


def write_investigation_csv(rows: Sequence[Mapping[str, str]], path: Path) -> Path:
    """Write the investigation list as a CSV with a header row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter[str](handle, fieldnames=INVESTIGATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _record_label(record: Record) -> str:
    return f"{record.source.path.name} seq {record.seq}"


def summarize(plan: RunPlan, result: PublishResult | None) -> str:
    """Describe a plan, and a publish result if there is one, for the terminal.

    The text holds student names and state IDs and is never written to Drive
    or git.
    """
    lines = [f"{plan.program} {plan.admin}: {len(plan.placements)} records filed"]

    counts = Counter((p.region, p.where) for p in plan.placements)
    lines.append("")
    lines.append("Records by destination")
    for (region, where), count in sorted(
        counts.items(),
        key=lambda item: (item[0][0], item[0][1] == TRANSFER_FOLDER, item[0][1]),
    ):
        lines.append(f"{region}  {where}  {count} records")

    lines.append("")
    lines.append("School folders")
    schools = sorted(
        {
            (p.region, p.where, p.schoolid)
            for p in plan.placements
            if p.schoolid is not None
        }
    )
    for region, where, schoolid in schools:
        lines.append(f"{region}  {where} -> {SCHOOL_FOLDERS[(region, schoolid)]}")

    lines.append("")
    lines.append(f"Corrections applied: {len(plan.replaced)}")
    lines.append(f"Unpaired corrections: {len(plan.unpaired_corrections)}")
    for record in plan.unpaired_corrections:
        lines.append(f"  {_record_label(record)}")

    lines.append("")
    lines.append(f"Duplicate state IDs: {len(plan.duplicates)}")
    for record in plan.duplicates:
        lines.append(f"  {record.state_id}  {_record_label(record)}")

    partial = [
        p
        for p in plan.placements
        if p.resolution.reason == "matched" and p.resolution.matched_on != "both"
    ]
    unmatched = [p for p in plan.placements if p.resolution.reason != "matched"]
    resolved = [p for p in plan.placements if _resolved_disagreement(p.resolution)]
    lines.append("")
    lines.append(f"Partial matches (on the investigation list): {len(partial)}")
    lines.append(
        f"Source disagreements resolved by name and birth date: {len(resolved)}"
    )
    lines.extend(f"  {_record_label(p.record)}" for p in resolved)
    lines.append(f"Unmatched: {len(unmatched)}")
    for placement in unmatched:
        record = placement.record
        lines.append(
            f"  {_record_label(record)}  {record.printed_name or '(no name)'}  "
            f"{placement.resolution.reason}"
        )

    if result is not None:
        lines.append("")
        lines.append(f"Root folder: {result.root_name}")
        lines.append(f"Root folder readers: {', '.join(result.root_readers)}")

        lines.append("")
        if result.orphans_kept:
            lines.append(
                "Files no longer produced (kept; rerun with --allow-trash to "
                f"remove): {len(result.orphans_kept)}"
            )
            lines.extend(f"  {name}" for name in result.orphans_kept)
        else:
            lines.append(f"Trashed: {len(result.trashed)}")
            lines.extend(f"  {name}" for name in result.trashed)

        for region in sorted(result.sheets):
            lines.append("")
            lines.append(f"{region} index Sheet: {result.sheets[region]}")
            lines.append(
                f"{region} readers: {', '.join(result.readers.get(region, []))}"
            )

    return "\n".join(lines)
