import html
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pymupdf

BLOCK_MIN_FIELDS = 7
TEXT_BLOCK_TYPE = 0


def _block_to_paragraphs(text: str) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    for line in (i.strip() for i in text.splitlines()):
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def pdf_to_htmlz(input_file: Path, output_file: Path) -> str | None:
    parts: list[str] = []
    total_non_ws = 0

    with pymupdf.open(str(input_file)) as doc:
        for page in doc:
            blocks = page.get_text("blocks", sort=True)
            for block in blocks:
                if len(block) < BLOCK_MIN_FIELDS:
                    continue
                text = block[4] or ""
                block_type = block[6]
                if block_type != TEXT_BLOCK_TYPE or not text:
                    continue
                for p in _block_to_paragraphs(text):
                    total_non_ws += len("".join(p.split()))
                    parts.append(f"<p>{html.escape(p)}</p>")
            parts.append("<hr />")

    if total_non_ws == 0:
        return "No extractable text found in PDF (scanned/image PDF)."

    title = html.escape(input_file.stem)
    body = "\n".join(parts).rstrip()
    html_bytes = f'<html><head><meta charset="utf-8"><title>{title}</title></head><body>{body}</body></html>'.encode()

    with ZipFile(output_file, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("index.html", html_bytes)

    return None
