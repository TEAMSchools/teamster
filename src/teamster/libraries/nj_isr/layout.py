from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from teamster.libraries.nj_isr.match import TRANSFER_FOLDER, Placement
from teamster.libraries.nj_isr.models import IsrFormatError, Record, SourceFile

SEE_REPORT = "See report"
UNKNOWN_STUDENT = "Unknown student"

INDEX_HEADER = [
    "Student",
    "Student number",
    "Grade when tested",
    "Subject",
    "Where to find it",
    "School last spring",
    "Open the report",
    "Page",
    "Note",
]


@dataclass(frozen=True)
class Entry:
    placement: Placement
    page_in_file: int  # first page of this record in the output file


@dataclass(frozen=True)
class OutputFile:
    region: str
    schoolid: int | None  # None means the region's transfer folder
    file_name: str
    entries: tuple[Entry, ...]

    @property
    def page_count(self) -> int:
        return sum(e.placement.record.page_count for e in self.entries)


@dataclass(frozen=True)
class IndexRow:
    student: str  # "Last, First"
    student_number: str  # "" when unmatched
    grade: str
    subject: str  # "ELA" | "Math" | "Science" | "See report"
    where: str
    last_spring_school: str
    file_name: str
    page: int
    note: str


def admin_label(source: SourceFile) -> str:
    return f"{source.season} {source.year}"


def tag_value(source: SourceFile) -> str:
    return f"{source.year}_{source.season}_{source.program}"


def report_label(source: SourceFile) -> str:
    """Name of the report type, which also separates output files.

    Every NJGPA file is "NJGPA Reports"; the variant splits only NJSLA.
    """
    if source.program == "NJGPA":
        return "NJGPA Reports"
    if source.variant in ("", "Combined"):
        return f"{source.program} Reports"
    if source.variant == "Single":
        return f"{source.program} Science Reports"
    raise IsrFormatError(f"unknown report variant {source.variant!r}")


def year_folder_name(program: str, admin: str) -> str:
    return f"{admin} {program} ISRs"


def index_sheet_name(region: str, program: str, admin: str) -> str:
    return f"{region} {program} Reports Index - {admin}"


def shortcut_name(program: str, admin: str) -> str:
    return f"00 - Find a student's {program} report - {admin}"


def _printed_name_parts(printed_name: str) -> tuple[str, str]:
    """Split a printed name into (last, first): the last word is the last name."""
    tokens = printed_name.split()
    if not tokens:
        return "", ""
    return tokens[-1].title(), " ".join(tokens[:-1]).title()


def _name_parts(placement: Placement) -> tuple[str, str]:
    student = placement.resolution.student
    if student is not None:
        return student.last_name, student.first_name
    return _printed_name_parts(placement.record.printed_name)


def _sort_key(placement: Placement) -> tuple[bool, str, str, int, str, int]:
    student = placement.resolution.student
    last, first = _name_parts(placement)
    return (
        student is None,
        last.casefold(),
        first.casefold(),
        student.student_number if student is not None else 0,
        str(placement.record.source.path),
        placement.record.seq,
    )


def _file_name(placement: Placement) -> str:
    source = placement.record.source
    where = (
        f"{placement.region} {TRANSFER_FOLDER}"
        if placement.schoolid is None
        else placement.where
    )
    return f"{where} - {report_label(source)} - {admin_label(source)}.pdf"


def build_output_files(placements: Sequence[Placement]) -> list[OutputFile]:
    """Group placements into one file per destination folder and report type.

    Students are sorted matched-first, then by name. Each entry carries the page
    its record starts on in the combined file.

    Raises:
        IsrFormatError: If 2 groups produce the same file name, for example 2
            schools with one name. Links and local PDFs are keyed by file name,
            so one school's file would overwrite the other's.
    """
    groups = defaultdict[tuple[str, int | None, str, str], list[Placement]](list)
    for placement in placements:
        source = placement.record.source
        key = (
            placement.region,
            placement.schoolid,
            report_label(source),
            admin_label(source),
        )
        groups[key].append(placement)

    files: list[OutputFile] = []
    for (region, schoolid, _label, _admin), members in groups.items():
        entries: list[Entry] = []
        next_page = 1
        for placement in sorted(members, key=_sort_key):
            entries.append(Entry(placement, next_page))
            next_page += placement.record.page_count
        files.append(
            OutputFile(
                region=region,
                schoolid=schoolid,
                file_name=_file_name(members[0]),
                entries=tuple(entries),
            )
        )

    names = Counter(f.file_name for f in files)
    doubled = sorted(name for name, count in names.items() if count > 1)
    if doubled:
        raise IsrFormatError(
            f"duplicate output file name: {', '.join(map(repr, doubled))}; "
            "2 destinations would write the same file"
        )

    return sorted(files, key=lambda f: (f.region, f.schoolid is None, f.file_name))


def _record_keys(records: Sequence[Record]) -> Counter[tuple[str, int]]:
    return Counter((str(r.source.path), r.seq) for r in records)


def check_conservation(
    records_in: Sequence[Record],
    replaced: Sequence[Record],
    files: Sequence[OutputFile],
) -> None:
    """Raise unless every record not replaced by a correction is in exactly 1 file."""
    expected = _record_keys(records_in)
    expected.subtract(_record_keys(replaced))
    actual = _record_keys([e.placement.record for f in files for e in f.entries])

    missing = [k for k in expected if expected[k] > actual[k]]
    unexpected = [k for k in actual if actual[k] > max(expected[k], 0)]
    if missing or unexpected:
        raise IsrFormatError(
            f"conservation: {len(missing)} record(s) lost, "
            f"{len(unexpected)} record(s) unexpected or duplicated; "
            f"lost={[(Path(p).name, s) for p, s in missing]}, "
            f"unexpected={[(Path(p).name, s) for p, s in unexpected]}"
        )


def _note(placement: Placement) -> str:
    record = placement.record
    notes: list[str] = []
    if record.source.reissue_date is not None:
        d = record.source.reissue_date
        notes.append(f"Corrected by the state on {d.month}/{d.day}")
    if record.not_tested:
        notes.append("Not tested in at least 1 subject - see report")
    reason = placement.resolution.reason
    if reason == "no_candidate":
        notes.append("Not matched to a KTAF student")
    elif reason in ("failed_confirmation", "source_conflict"):
        notes.append("Needs a check by the Data team")
    return "; ".join(notes)


def _student_label(placement: Placement) -> str:
    last, first = _name_parts(placement)
    if not last and not first:
        return UNKNOWN_STUDENT
    return f"{last}, {first}" if first else last


def index_rows(files: Sequence[OutputFile]) -> dict[str, list[IndexRow]]:
    """Build index rows per region, one per student per subject."""
    by_region = defaultdict[str, list[IndexRow]](list)
    for file in files:
        for entry in file.entries:
            placement = entry.placement
            record = placement.record
            student = placement.resolution.student
            label = _student_label(placement)
            note = _note(placement)
            for subject in record.subjects or (SEE_REPORT,):
                by_region[file.region].append(
                    IndexRow(
                        student=label,
                        student_number=(str(student.student_number) if student else ""),
                        grade="" if record.grade is None else str(record.grade),
                        subject=subject,
                        where=placement.where,
                        last_spring_school=(
                            (student.last_spring_school or "") if student else ""
                        ),
                        file_name=file.file_name,
                        page=entry.page_in_file,
                        note=note,
                    )
                )
    return {
        region: sorted(
            rows,
            key=lambda r: (r.student.casefold(), r.subject, r.file_name, r.page),
        )
        for region, rows in by_region.items()
    }


def _link_cell(url: str | None, page: int, *, page_anchor: bool) -> str:
    if not url:
        return ""
    target = f"{url}#page={page}" if page_anchor else url
    return f'=HYPERLINK("{target.replace(chr(34), "%22")}", "Open report")'


def sheet_tabs(
    rows: Sequence[IndexRow],
    links: Mapping[str, str],
    *,
    region: str,
    program: str,
    admin: str,
    ran_at: datetime,
    page_anchor: bool,
) -> dict[str, list[list[str]]]:
    """Cell values for the index Sheet's "All reports" and "About" tabs."""
    all_reports: list[list[str]] = [
        [f"{region} {program} reports - {admin}"],
        ["1. Press Ctrl+F (Cmd+F on a Mac) and type the student's last name."],
        ["2. Click the blue link in that student's row."],
        ["3. Go to the page number in the Page column."],
        INDEX_HEADER,
    ]
    all_reports.extend(
        [
            row.student,
            row.student_number,
            row.grade,
            row.subject,
            row.where,
            row.last_spring_school,
            _link_cell(links.get(row.file_name), row.page, page_anchor=page_anchor),
            str(row.page),
            row.note,
        ]
        for row in rows
    )

    about = [
        [
            "What this is",
            f"Every {admin} {program} Individual Student Report for {region}, "
            "one row per student per subject.",
        ],
        ["Last updated", ran_at.strftime("%Y-%m-%d %H:%M")],
        ["Can't find a report?", "Submit a ticket to the Data team."],
        [
            "Students who left KTAF",
            "Their reports are in the Transfer Out & Unmatched folder next to "
            "this Sheet.",
        ],
    ]
    return {"All reports": all_reports, "About": about}
