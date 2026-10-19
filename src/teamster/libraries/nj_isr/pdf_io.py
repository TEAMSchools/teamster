from pathlib import Path

import pypdfium2
from pypdf import PdfReader, PdfWriter

from teamster.libraries.nj_isr.layout import OutputFile


def read_page_texts(path: Path) -> list[str]:
    """Read the text of every page of a PDF, in page order."""
    document = pypdfium2.PdfDocument(path)
    try:
        return [
            document[i].get_textpage().get_text_range() for i in range(len(document))
        ]
    finally:
        document.close()


def write_output_pdf(file: OutputFile, out_dir: Path) -> Path:
    """Write one school's combined PDF and return its path.

    Pages are added straight from each source into a single writer, which then
    merges identical objects. Building a PDF per student and merging them would
    copy every font and image once per student.
    """
    readers: dict[Path, PdfReader] = {}
    writer = PdfWriter()

    for entry in file.entries:
        record = entry.placement.record
        source_path = record.source.path
        if source_path not in readers:
            readers[source_path] = PdfReader(source_path)
        reader = readers[source_path]
        for page_number in range(record.page_start, record.page_end + 1):
            writer.add_page(reader.pages[page_number - 1])

    writer.compress_identical_objects()

    out_path = out_dir / file.file_name
    with out_path.open("wb") as f:
        writer.write(f)
    return out_path
