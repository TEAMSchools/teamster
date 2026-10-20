from datetime import date
from pathlib import Path

import pytest

from teamster.libraries.nj_isr.models import IsrFormatError, Record, SourceFile
from teamster.libraries.nj_isr.segment import (
    apply_corrections,
    find_duplicate_state_ids,
    parse_source_filename,
    scan_folder,
    segment_pages,
)

SRC = SourceFile(
    path=Path("2026_Spring_7325-965_ISR_SLA_Combined.pdf"),
    year=2026,
    season="Spring",
    district="7325",
    school_code="965",
    program="NJSLA",
    variant="Combined",
    reissue_date=None,
)

SUBJECT_PAGES = ("English Language Arts", "Mathematics")


def _footer(seq: int, district: str = "7325") -> str:
    return f"{district}.{district}_965.{seq}"


def _inner_page(
    sid: str,
    dob: str | None,
    subject: str,
    extra_sid: str | None,
    footer: str = "",
    name: str = "ALEX B. RIVERA",
    name_on_own_line: bool = False,
) -> str:
    """Build a page in the shape pdfium returns.

    Lines end in CRLF, the name and grade share one line, and the state ID and
    birth date share one line. `name_on_own_line` gives the older shape, with the
    name on the line above the grade.
    """
    if name_on_own_line:
        lines = [subject, name, " ENROLLED GRADE: 5"]
    else:
        lines = [subject, f"{name} ENROLLED GRADE: 5"]

    id_line = f"Student ID: {sid}"
    if dob is not None:
        id_line += f" Date of Birth: {dob}"
    lines.append(id_line + " Date of Testing: SPRING 2026")

    if extra_sid is not None:
        lines.append(f"Student ID: {extra_sid}")
    return "\r\n".join(lines) + footer


def record(
    seq: int,
    sid: str,
    *,
    code: str = "ab1234",
    district: str = "7325",
    dob: str | None = "03/04/15",
    subjects: tuple[str, ...] = SUBJECT_PAGES,
    extra_sid: str | None = None,
    name: str = "ALEX B. RIVERA",
    name_on_own_line: bool = False,
) -> list[str]:
    """Build a 4-page Combined record: cover, 2 subject pages, closing page."""
    footer = _footer(seq, district)
    subject_text = [*subjects, "", ""][:2]

    def page(subject: str, extra: str | None, footer: str = "") -> str:
        return _inner_page(
            sid,
            dob,
            subject,
            extra,
            footer,
            name=name,
            name_on_own_line=name_on_own_line,
        )

    return [
        f"Student Report\nFamily Portal Access Code:\n{code}{footer}",
        page(subject_text[0], None),
        page(subject_text[1], extra_sid),
        page("", None, footer),
    ]


def njgpa_record(seq: int, sid: str) -> list[str]:
    """Build a 2-page NJGPA record with the footer token on both pages."""
    footer = _footer(seq)
    return [
        _inner_page(sid, "03/04/15", "Mathematics", None, footer=footer),
        _inner_page(sid, "03/04/15", "", None, footer=footer),
    ]


def rec(
    *,
    state_id: str,
    file: str = "2026_Spring_7325-965_ISR_SLA_Combined.pdf",
    seq: int = 1,
) -> Record:
    source = parse_source_filename(Path(file))
    assert source is not None
    return Record(
        source=source,
        seq=seq,
        page_start=1,
        page_end=4,
        state_id=state_id,
        printed_name="ALEX B. RIVERA",
        printed_dob=None,
        grade=5,
        subjects=("ELA", "Math"),
        not_tested=False,
    )


def test_parse_source_filename():
    s = parse_source_filename(Path("2026_Spring_7325-965_ISR_SLA_Combined.pdf"))
    assert s is not None
    assert (s.year, s.season, s.district, s.school_code) == (
        2026,
        "Spring",
        "7325",
        "965",
    )
    assert (s.program, s.variant, s.reissue_date) == ("NJSLA", "Combined", None)

    r = parse_source_filename(Path("2026_Spring_1799-111_ISR_SLA_Combined_100226.pdf"))
    assert r is not None
    assert r.reissue_date == date(2026, 10, 2)

    g = parse_source_filename(Path("2026_Spring_7325-965_ISR_GPA.pdf"))
    assert g is not None
    assert (g.program, g.variant) == ("NJGPA", "")

    assert parse_source_filename(Path("2026_Spring_7325-965_Labels_SLA.pdf")) is None
    assert parse_source_filename(Path("notes.txt")) is None


def test_parse_source_filename_rejects_impossible_reissue_date():
    with pytest.raises(IsrFormatError, match="reissue"):
        parse_source_filename(Path("2026_Spring_7325-965_ISR_SLA_Combined_139926.pdf"))


def test_segment_reads_a_multi_part_hyphenated_name_on_the_real_shape():
    recs = segment_pages(
        SRC, record(1, "1000000001", name="MARY-ANN O'NEIL DE LA CRUZ-SMITH JR.")
    )
    assert recs[0].printed_name == "MARY-ANN O'NEIL DE LA CRUZ-SMITH JR."
    assert recs[0].grade == 5
    assert recs[0].state_id == "1000000001"


def test_segment_reads_a_name_on_the_line_above_the_grade():
    recs = segment_pages(
        SRC, record(1, "1000000001", name="ALEX B. RIVERA", name_on_own_line=True)
    )
    assert recs[0].printed_name == "ALEX B. RIVERA"
    assert recs[0].grade == 5


def test_missing_name_never_reads_the_access_code_on_page_1():
    # the name line is blank and is the first line of its page, so the line
    # above it in the joined record text is page 1's access code and footer
    pages = record(1, "1000000001", code="qz7x2w", name="", subjects=())

    assert pages[1].startswith("\r\n ENROLLED GRADE:")
    assert segment_pages(SRC, pages)[0].printed_name == ""


@pytest.mark.parametrize(
    "name, name_on_own_line",
    [("SPRING 2026", True), ("1000000001", False), ("AB 7325.7325_965.1", False)],
)
def test_printed_name_rejects_a_line_with_a_digit(name, name_on_own_line):
    pages = record(1, "1000000001", name=name, name_on_own_line=name_on_own_line)

    assert segment_pages(SRC, pages)[0].printed_name == ""


def test_segment_two_combined_records():
    recs = segment_pages(SRC, record(1, "1000000001") + record(2, "1000000002"))
    assert [(r.seq, r.page_start, r.page_end) for r in recs] == [(1, 1, 4), (2, 5, 8)]
    assert recs[0].page_count == 4
    assert recs[0].state_id == "1000000001"
    assert recs[0].printed_name == "ALEX B. RIVERA"
    assert recs[0].printed_dob == date(2015, 3, 4)
    assert recs[0].grade == 5
    assert recs[0].subjects == ("ELA", "Math")
    assert recs[0].not_tested is False
    assert recs[1].state_id == "1000000002"


def test_footer_glued_to_code_ending_in_digits():
    recs = segment_pages(SRC, record(1, "1000000001", code="cc5787"))
    assert recs[0].seq == 1


def test_footer_on_every_page_njgpa_style():
    recs = segment_pages(SRC, njgpa_record(1, "1000000001"))
    assert (recs[0].page_start, recs[0].page_end) == (1, 2)


def test_missing_dob_and_subjects_do_not_fail():
    recs = segment_pages(SRC, record(1, "1000000001", dob=None, subjects=()))
    assert recs[0].printed_dob is None
    assert recs[0].subjects == ()


def test_not_tested_and_science_are_detected():
    pages = record(1, "1000000001", subjects=("Science", "not tested"))
    recs = segment_pages(SRC, pages)
    assert recs[0].subjects == ("Science",)
    assert recs[0].not_tested is True


@pytest.mark.parametrize(
    "pages, message",
    [
        (record(1, "1000000001") + record(3, "1000000002"), "seq"),  # gap
        (record(1, "1000000001", district="1799"), "district"),  # footer != filename
        (
            record(1, "1000000001")[:3] + ["no footer"] + record(2, "1000000002"),
            "page",
        ),  # orphan page
        (record(1, "1000000001", extra_sid="1000000009"), "state ID"),  # 2 IDs
        (record(1, "100000"), "state ID"),  # not 10 digits
    ],
)
def test_segment_stops_on_bad_structure(pages, message):
    with pytest.raises(IsrFormatError, match=message):
        segment_pages(SRC, pages)


def test_apply_corrections():
    orig = rec(state_id="1000000001", file="2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    other = rec(state_id="1000000002", file="2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    fix = rec(
        state_id="1000000001",
        file="2026_Spring_7325-965_ISR_SLA_Combined_100226.pdf",
    )
    late = rec(
        state_id="1000000001",
        file="2026_Spring_7325-965_ISR_SLA_Combined_101526.pdf",
    )
    stray = rec(
        state_id="1000000003",
        file="2026_Spring_7325-965_ISR_SLA_Combined_100226.pdf",
    )

    kept, replaced, unpaired = apply_corrections([orig, other, fix, late, stray])

    assert late in kept and fix not in kept and orig not in kept and other in kept
    assert replaced == [orig, fix]
    assert unpaired == [stray] and stray in kept


def test_duplicates_inside_a_correction_file_are_kept_and_reported():
    orig = rec(state_id="1000000001")
    fix_name = "2026_Spring_7325-965_ISR_SLA_Combined_100226.pdf"
    first = rec(state_id="1000000001", file=fix_name, seq=1)
    second = rec(state_id="1000000001", file=fix_name, seq=2)

    kept, replaced, unpaired = apply_corrections([orig, first, second])

    assert kept == [first, second]
    assert replaced == [orig]
    assert unpaired == []
    assert find_duplicate_state_ids(kept) == [first, second]


def test_duplicates_inside_an_unpaired_correction_file_are_kept():
    fix_name = "2026_Spring_7325-965_ISR_SLA_Combined_100226.pdf"
    first = rec(state_id="1000000001", file=fix_name, seq=1)
    second = rec(state_id="1000000001", file=fix_name, seq=2)

    kept, replaced, unpaired = apply_corrections([first, second])

    assert kept == [first, second]
    assert replaced == []
    assert unpaired == [first, second]


def test_apply_corrections_does_not_cross_variants():
    combined = rec(state_id="1000000001")
    single_fix = rec(
        state_id="1000000001",
        file="2026_Spring_7325-965_ISR_SLA_Single_100226.pdf",
    )

    kept, replaced, unpaired = apply_corrections([combined, single_fix])

    assert kept == [combined, single_fix]
    assert replaced == []
    assert unpaired == [single_fix]


def test_duplicate_state_ids_are_kept_and_reported():
    a, b = rec(state_id="1000000001", seq=1), rec(state_id="1000000001", seq=2)
    assert find_duplicate_state_ids([a, b]) == [a, b]


def test_same_state_id_in_combined_and_single_is_not_a_duplicate():
    combined = rec(state_id="1000000001")
    single = rec(state_id="1000000001", file="2026_Spring_7325-965_ISR_SLA_Single.pdf")
    assert find_duplicate_state_ids([combined, single]) == []


def _folder(tmp_path: Path, *names: str) -> Path:
    for name in names:
        (tmp_path / name).touch()
    return tmp_path


def test_scan_folder_sorts_by_filename_and_skips_labels(tmp_path: Path):
    folder = _folder(
        tmp_path,
        "2026_Spring_7325-965_ISR_SLA_Single.pdf",
        "2026_Spring_7325-965_ISR_SLA_Combined.pdf",
        "2026_Spring_7325-965_Labels_SLA.pdf",
        "readme.txt",
    )
    pages_by_name = {
        "2026_Spring_7325-965_ISR_SLA_Combined.pdf": record(1, "1000000001"),
        "2026_Spring_7325-965_ISR_SLA_Single.pdf": record(1, "1000000002"),
    }

    recs = scan_folder(folder, lambda path: pages_by_name[path.name])

    assert [(r.source.variant, r.state_id) for r in recs] == [
        ("Combined", "1000000001"),
        ("Single", "1000000002"),
    ]


def test_scan_folder_rejects_two_files_with_one_name(tmp_path: Path):
    name = "2026_Spring_7325-965_ISR_SLA_Combined.pdf"
    for folder in ("download 1", "download 2"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / name).touch()

    with pytest.raises(IsrFormatError, match=f"more than once.*{name}"):
        scan_folder(tmp_path, lambda path: record(1, "1000000001"))


def test_scan_folder_rejects_mixed_programs(tmp_path: Path):
    folder = _folder(
        tmp_path,
        "2026_Spring_7325-965_ISR_SLA_Combined.pdf",
        "2026_Spring_7325-965_ISR_GPA.pdf",
    )

    with pytest.raises(IsrFormatError, match="program"):
        scan_folder(folder, lambda path: record(1, "1000000001"))
