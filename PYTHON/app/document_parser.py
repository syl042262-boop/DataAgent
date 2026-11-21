"""Isolated PDF/DOCX parsing worker; stdout contains only bounded extracted text."""

import sys
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from pypdf import PdfReader


def extract(path: Path, max_chars: int) -> str:
    pieces = []
    size = 0

    def append(value):
        nonlocal size
        size += len(value) + 1
        if size > max_chars:
            raise ValueError("Extracted document exceeds text limit")
        pieces.append(value)

    if path.suffix.lower() == ".pdf":
        for page in PdfReader(path).pages:
            append(page.extract_text() or "")
    else:
        # Check expanded XML size before python-docx materializes its document tree.
        with ZipFile(path) as archive:
            if sum(item.file_size for item in archive.infolist()) > max_chars * 8:
                raise ValueError("Expanded DOCX exceeds size limit")
        doc = Document(str(path))
        for paragraph in doc.paragraphs:
            append(paragraph.text)
        for table in doc.tables:
            for row in table.rows:
                append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(pieces)


if __name__ == "__main__":
    try:
        result = extract(Path(sys.argv[1]), int(sys.argv[2]))
        sys.stdout.buffer.write(result.encode("utf-8"))
    except Exception:  # noqa: BLE001 -- child errors are normalized by the parent
        sys.exit(1)
