import re
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path

from teamster.libraries.nj_isr.models import IsrFormatError, Record, SourceFile

# The token follows the 6-character access code on page 1 with no separator, so
# the pattern must not start with a word boundary.
FOOTER_RE = re.compile(r"(\d{4})\.(\1_\d{3})\.(\d+)")

_FILENAME_RE = re.compile(
    r"^(?P<year>\d{4})_(?P<season>[A-Za-z]+)_(?P<district>\d+)-(?P<school>\d+)"
    r"_ISR_(?P<program>SLA|GPA)(?:_(?P<variant>Combined|Single))?"
    r"(?:_(?P<reissue>\d{6}))?\.pdf$",
    re.IGNORECASE,
)
_PROGRAMS = {"SLA": "NJSLA", "GPA": "NJGPA"}

_STATE_ID_RE = re.compile(r"Student ID:\s*(\d{10})")
_DOB_RE = re.compile(r"Date of Birth:\s*(\d{2}/\d{2}/\d{2})")
_GRADE_RE = re.compile(r"ENROLLED GRADE:\s*(\d+)")
_NAME_LINE_RE = re.compile(r"^([^\r\n]*?)[ \t]*ENROLLED GRADE:", re.MULTILINE)
_NOT_TESTED_RE = re.compile(r"NOT TESTED", re.IGNORECASE)

_SUBJECT_MARKERS = (
    ("ELA", "English Language Arts"),
    ("Math", "Mathematics"),
    ("Science", "Science"),
)


def parse_source_filename(path: Path) -> SourceFile | None:
    """Describe a state ISR PDF from its filename.

    Args:
        path: Path to a PDF named
            `{year}_{season}_{district}-{school}_ISR_{SLA|GPA}[_{Combined|Single}][_{MMDDYY}].pdf`.

    Returns:
        The parsed file, or None for label files and names that do not match.

    Raises:
        IsrFormatError: If the trailing `_MMDDYY` is not a real date.
    """
    match = _FILENAME_RE.match(path.name)

    if match is None:
        return None

    reissue_date: date | None = None
    if match["reissue"] is not None:
        try:
            reissue_date = datetime.strptime(match["reissue"], "%m%d%y").date()
        except ValueError as e:
            raise IsrFormatError(
                f"{path.name}: reissue date {match['reissue']} is not MMDDYY"
            ) from e

    return SourceFile(
        path=path,
        year=int(match["year"]),
        season=match["season"],
        district=match["district"],
        school_code=match["school"],
        program=_PROGRAMS[match["program"].upper()],
        variant=(match["variant"] or "").capitalize(),
        reissue_date=reissue_date,
    )


def _page_seqs(source: SourceFile, pages: list[str]) -> list[int]:
    """Return the record seq of every page, from the footer tokens."""
    name = source.path.name
    seqs: list[int | None] = []

    for number, text in enumerate(pages, start=1):
        tokens = {(m[1], int(m[3])) for m in FOOTER_RE.finditer(text)}

        if len(tokens) > 1:
            raise IsrFormatError(f"{name}: page {number} names more than one record")

        if not tokens:
            seqs.append(None)
            continue

        ((footer_district, seq),) = tokens

        if footer_district != source.district:
            raise IsrFormatError(
                f"{name}: page {number} footer district {footer_district} does not "
                f"match filename district {source.district}"
            )

        seqs.append(seq)

    # a footer-less page belongs to a record only when the tokens around it agree
    previous: list[int | None] = []
    last: int | None = None
    for seq in seqs:
        last = seq if seq is not None else last
        previous.append(last)

    following: list[int | None] = [None] * len(seqs)
    last = None
    for index in range(len(seqs) - 1, -1, -1):
        last = seqs[index] if seqs[index] is not None else last
        following[index] = last

    resolved: list[int] = []
    for index, seq in enumerate(seqs):
        before = previous[index]
        if seq is not None:
            resolved.append(seq)
        elif before is not None and before == following[index]:
            resolved.append(before)
        else:
            raise IsrFormatError(
                f"{name}: page {index + 1} has no footer token and is not inside "
                "a record"
            )

    return resolved


def _printed_name(pages: Sequence[str]) -> str:
    """Read the printed name that sits before the first "ENROLLED GRADE:" label.

    The name is the text before the label on the same line. When that is empty,
    it is the nearest non-empty line above on the same page, never an earlier
    page: page 1 ends in the access code glued to the footer token. A candidate
    with a digit or a footer token is not a name, so the result is "" and the
    index shows "Unknown student".
    """
    for page in pages:
        match = _NAME_LINE_RE.search(page)

        if match is None:
            continue

        candidate = match[1].strip()
        if not candidate:
            above = [line.strip() for line in page[: match.start()].splitlines()]
            candidate = next((line for line in reversed(above) if line), "")

        if any(c.isdigit() for c in candidate) or FOOTER_RE.search(candidate):
            return ""

        return candidate

    return ""


def _parse_dob(name: str, seq: int, text: str) -> date | None:
    match = _DOB_RE.search(text)

    if match is None:
        return None

    try:
        return datetime.strptime(match[1], "%m/%d/%y").date()
    except ValueError as e:
        raise IsrFormatError(
            f"{name}: record {seq} has an invalid date of birth"
        ) from e


def _build_record(
    source: SourceFile, seq: int, page_start: int, page_end: int, pages: list[str]
) -> Record:
    name = source.path.name
    text = "\n".join(pages)

    state_ids = set(_STATE_ID_RE.findall(text))
    if len(state_ids) != 1:
        raise IsrFormatError(
            f"{name}: record {seq} has {len(state_ids)} distinct state IDs, "
            "expected exactly 1 (a state ID is 10 digits after 'Student ID:')"
        )

    grade_match = _GRADE_RE.search(text)

    return Record(
        source=source,
        seq=seq,
        page_start=page_start,
        page_end=page_end,
        state_id=state_ids.pop(),
        printed_name=_printed_name(pages),
        printed_dob=_parse_dob(name, seq, text),
        grade=int(grade_match[1]) if grade_match else None,
        subjects=tuple(
            subject for subject, marker in _SUBJECT_MARKERS if marker in text
        ),
        not_tested=_NOT_TESTED_RE.search(text) is not None,
    )


def segment_pages(source: SourceFile, pages: list[str]) -> list[Record]:
    """Cut a file's page texts into one record per student.

    A page's footer token names its record. A page without a token belongs to
    the record whose tokens surround it.

    Args:
        source: The file the pages come from.
        pages: Text of each page, in order.

    Returns:
        The records, in file order.

    Raises:
        IsrFormatError: If a footer district differs from the filename, `seq`
            does not run from 1 without gaps, a page falls outside every
            record, or a record does not have exactly 1 state ID.
    """
    seqs = _page_seqs(source, pages)
    name = source.path.name

    records: list[Record] = []
    start = 0
    for index in range(1, len(pages) + 1):
        if index < len(pages) and seqs[index] == seqs[start]:
            continue

        seq = seqs[start]
        if seq != len(records) + 1:
            raise IsrFormatError(
                f"{name}: page {start + 1} starts seq {seq}, expected "
                f"seq {len(records) + 1}"
            )

        records.append(
            _build_record(
                source,
                seq=seq,
                page_start=start + 1,
                page_end=index,
                pages=pages[start:index],
            )
        )
        start = index

    return records


def scan_folder(
    input_dir: Path, read_pages: Callable[[Path], list[str]]
) -> list[Record]:
    """Segment every state ISR PDF in a folder and its subfolders.

    Args:
        input_dir: Folder holding the state's PDFs.
        read_pages: Returns the text of each page of a PDF.

    Returns:
        The records of every ISR file, in filename order. Label files and
        other names are skipped.

    Raises:
        IsrFormatError: If the files cover more than one program, or a file
            fails segmentation.
    """
    sources = sorted(
        (
            source
            for path in input_dir.rglob("*")
            if path.is_file() and (source := parse_source_filename(path)) is not None
        ),
        key=lambda source: source.path.name,
    )

    programs = sorted({source.program for source in sources})
    if len(programs) > 1:
        raise IsrFormatError(
            f"{input_dir} mixes programs {', '.join(programs)}; "
            "run one program at a time"
        )

    return [
        record
        for source in sources
        for record in segment_pages(source, read_pages(source.path))
    ]


def _correction_key(record: Record) -> tuple[str, str, str, str]:
    source = record.source
    return (source.district, source.program, source.variant, record.state_id)


def apply_corrections(
    records: Sequence[Record],
) -> tuple[list[Record], list[Record], list[Record]]:
    """Replace original records with the state's corrected ones.

    A corrected record replaces every original with the same district, program,
    variant, and state ID. When several correction files share that key, the
    file with the latest reissue date wins (ties go to the later filename) and
    every record from that file stays, so a repeat inside it is still reported
    by `find_duplicate_state_ids`.

    Args:
        records: Records from every file, originals and corrections.

    Returns:
        A tuple of `(kept, replaced_originals, unpaired_corrections)`, each in
        input order. `replaced_originals` also holds the corrections that a
        later correction file superseded. An unpaired correction has no original to
        replace and stays in `kept`.
    """
    winning_file: dict[tuple[str, str, str, str], tuple[date, Path]] = {}
    for record in records:
        reissue_date = record.source.reissue_date
        if reissue_date is None:
            continue

        key = _correction_key(record)
        candidate = (reissue_date, record.source.path)
        if key not in winning_file or candidate > winning_file[key]:
            winning_file[key] = candidate

    originals = {
        _correction_key(record)
        for record in records
        if record.source.reissue_date is None
    }

    kept: list[Record] = []
    replaced: list[Record] = []
    unpaired: list[Record] = []
    for record in records:
        key = _correction_key(record)

        if record.source.reissue_date is None:
            (replaced if key in winning_file else kept).append(record)
        elif (record.source.reissue_date, record.source.path) != winning_file[key]:
            replaced.append(record)
        else:
            kept.append(record)
            if key not in originals:
                unpaired.append(record)

    return kept, replaced, unpaired


def find_duplicate_state_ids(records: Sequence[Record]) -> list[Record]:
    """Return every record whose state ID repeats within a district file group.

    The same student appears once in the Combined file and once in the Single
    file by design, so a repeat counts only within a district, program, and
    variant.

    Args:
        records: Records to check.

    Returns:
        The records that share a state ID, in input order.
    """
    counts = Counter(_correction_key(record) for record in records)
    return [record for record in records if counts[_correction_key(record)] > 1]
