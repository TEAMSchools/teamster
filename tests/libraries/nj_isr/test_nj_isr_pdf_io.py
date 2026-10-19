from datetime import date
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from teamster.libraries.nj_isr.layout import Entry, OutputFile
from teamster.libraries.nj_isr.match import Placement, Resolution
from teamster.libraries.nj_isr.models import Record, SourceFile
from teamster.libraries.nj_isr.pdf_io import read_page_texts, write_output_pdf


def blank_pdf(path: Path, widths: list[int]) -> Path:
    writer = PdfWriter()
    for width in widths:
        writer.add_blank_page(width=width, height=100)
    with path.open("wb") as f:
        writer.write(f)
    return path


def source(path: Path) -> SourceFile:
    return SourceFile(
        path=path,
        year=2026,
        season="Spring",
        district="7325",
        school_code="965",
        program="NJSLA",
        variant="Combined",
        reissue_date=None,
    )


def entry(path: Path, page_start: int, page_end: int, page_in_file: int = 1) -> Entry:
    record = Record(
        source=source(path),
        seq=1,
        page_start=page_start,
        page_end=page_end,
        state_id="1234567890",
        printed_name="ADAMS AL",
        printed_dob=date(2015, 1, 1),
        grade=5,
        subjects=("ELA",),
        not_tested=False,
    )
    placement = Placement(
        record=record,
        resolution=Resolution(student=None, reason="no_candidate"),
        region="Newark",
        schoolid=None,
        where="Transfer Out & Unmatched",
    )
    return Entry(placement, page_in_file)


def output_file(entries: list[Entry]) -> OutputFile:
    return OutputFile(
        region="Newark",
        schoolid=None,
        file_name="Newark Transfer Out & Unmatched - NJSLA Reports - Spring 2026.pdf",
        entries=tuple(entries),
    )


def test_write_output_pdf_keeps_entry_order(tmp_path):
    a = blank_pdf(tmp_path / "a.pdf", widths=[100, 101, 102, 103])
    b = blank_pdf(tmp_path / "b.pdf", widths=[200, 201])
    f = output_file(entries=[entry(a, 3, 4), entry(b, 1, 2)])
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    out = write_output_pdf(f, out_dir)

    widths = [int(p.mediabox.width) for p in PdfReader(out).pages]
    assert widths == [102, 103, 200, 201]
    assert out.name == f.file_name
    assert out.parent == out_dir


def test_write_output_pdf_interleaves_sources(tmp_path):
    a = blank_pdf(tmp_path / "a.pdf", widths=[100, 101, 102])
    b = blank_pdf(tmp_path / "b.pdf", widths=[200, 201])
    f = output_file(entries=[entry(a, 1, 1), entry(b, 2, 2), entry(a, 2, 3)])

    out = write_output_pdf(f, tmp_path)

    widths = [int(p.mediabox.width) for p in PdfReader(out).pages]
    assert widths == [100, 201, 101, 102]


def test_read_page_texts_returns_one_string_per_page(tmp_path):
    path = blank_pdf(tmp_path / "a.pdf", widths=[100, 101, 102])

    texts = read_page_texts(path)

    assert len(texts) == 3
    assert all(isinstance(t, str) for t in texts)
