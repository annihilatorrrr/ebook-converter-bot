from pathlib import Path
from zipfile import ZipFile

import pymupdf
import pytest
from ebook_converter_bot.utils.pdf import pdf_to_htmlz


def _find_font_file() -> Path | None:
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/Library/Fonts/Arial Unicode MS.ttf"),
        Path("/Library/Fonts/DejaVu Sans.ttf"),
        Path("/Library/Fonts/NotoNaskhArabic-Regular.ttf"),
    ]
    return next((p for p in candidates if p.exists()), None)


@pytest.mark.parametrize(
    ("page_1", "page_2", "rtl"),
    [
        ("Hello PDF", "Second page", False),
        ("مرحبا بالعالم", "الصفحة الثانية", True),
    ],
)
def test_extracts_text_to_htmlz(page_1: str, page_2: str, rtl: bool, tmp_path: Path) -> None:
    pdf_path = tmp_path / "book.pdf"
    htmlz_path = tmp_path / "book.htmlz"

    doc = pymupdf.open()
    if rtl:
        font_file = _find_font_file()
        if not font_file:
            pytest.skip("Arabic-capable font not found on this system")
        font = pymupdf.Font(fontfile=str(font_file))

        page = doc.new_page()
        tw = pymupdf.TextWriter(page.rect)
        tw.append((72, 72), page_1, font=font, fontsize=12, right_to_left=1)
        tw.write_text(page)

        page = doc.new_page()
        tw = pymupdf.TextWriter(page.rect)
        tw.append((72, 72), page_2, font=font, fontsize=12, right_to_left=1)
        tw.write_text(page)
    else:
        page = doc.new_page()
        page.insert_text((72, 72), page_1)
        page = doc.new_page()
        page.insert_text((72, 72), page_2)

    doc.save(str(pdf_path))
    doc.close()

    err = pdf_to_htmlz(pdf_path, htmlz_path)
    assert err is None
    assert htmlz_path.exists()

    with ZipFile(htmlz_path, "r") as z:
        assert "index.html" in z.namelist()
        html = z.read("index.html").decode()
        assert page_1 in html
        assert page_2 in html
