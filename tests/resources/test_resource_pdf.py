import re

from pypdf import PdfReader


def test_read_pdf():
    data = []

    reader = PdfReader("env/test/2332 - FY23 - Survey 2 - Detail Cap Report.pdf")

    for page in reader.pages:
        matches = re.finditer(
            pattern=(
                r"\s+(?P<school_number>\d+)"
                r"\s+(?P<student_id>\d+)"
                r"\s+(?P<florida_student_id>[\dX]+)"
                r"\s+(?P<student_name>[\D]+)"
                r"\s+(?P<grade>\w+)"
                r"\s+(?P<fte_capped>[\d\.]+)"
                r"\s+(?P<fte_uncapped>[\d\.]+)"
            ),
            string=page.extract_text(),
        )

        data.extend([m.groupdict() for m in matches])

    assert len(data) == 1050
