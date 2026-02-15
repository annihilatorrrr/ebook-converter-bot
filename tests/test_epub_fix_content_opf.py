import posixpath
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from ebook_converter_bot.utils.epub import (
    fix_content_opf_problems,
    flatten_toc,
    set_epub_to_rtl,
    xml_parser,
)
from lxml import etree, html


def test_dedup_sort_and_case_fix(tmp_path: Path) -> None:
    epub_path = tmp_path / "book.epub"

    opf_path = "OEBPS/content.opf"
    page_1 = "OEBPS/Text/page_1.xhtml"
    page_2 = "OEBPS/Text/page_2.xhtml"
    page_3 = "OEBPS/Text/page_3.xhtml"

    opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>t</dc:title>
  </metadata>
  <manifest>
    <item id="intro" href="Text/intro.xhtml" media-type="application/xhtml+xml"/>
    <item id="book_info" href="Text/book_info.xhtml" media-type="application/xhtml+xml"/>
    <item id="page_2" href="Text/page_2.xhtml" media-type="application/xhtml+xml"/>
    <item id="page_1" href="Text/Page_1.xhtml" media-type="application/xhtml+xml"/>
    <item id="page_1" href="Text/page_1.xhtml" media-type="application/xhtml+xml"/>
    <item id="page_3" href="Text/page_3.xhtml" media-type="application/xhtml+xml"/>
    <item id="page_4" href="Text/page_4.xhtml" media-type="application/xhtml+xml"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="page_2"/>
    <itemref idref="page_1"/>
    <itemref idref="page_1"/>
    <itemref idref="page_3"/>
    <itemref idref="page_4"/>
  </spine>
</package>
"""

    with ZipFile(epub_path, "w", compression=ZIP_DEFLATED) as z:
        z.writestr(opf_path, opf)
        z.writestr(page_1, "<html/>")
        z.writestr(page_2, "<html/>")
        z.writestr(page_3, "<html/>")
        z.writestr("OEBPS/Text/intro.xhtml", "<html/>")
        z.writestr("OEBPS/Text/book_info.xhtml", "<html/>")
        z.writestr("OEBPS/nav.xhtml", "<html/>")

    fix_content_opf_problems(epub_path)

    with ZipFile(epub_path, "r") as z:
        fixed = z.read(opf_path)

    root = etree.fromstring(fixed, xml_parser)
    ns = root.tag.split("}")[0] + "}"

    manifest = root.find(f".//{ns}manifest")
    spine = root.find(f".//{ns}spine")
    assert manifest is not None
    assert spine is not None

    items = [c for c in list(manifest) if c.tag == f"{ns}item"]
    item_ids = [c.get("id") for c in items]
    assert item_ids.count("page_1") == 1
    assert "page_4" not in item_ids
    assert [c.get("id") for c in items if c.get("id", "").startswith("page_")] == [
        "page_1",
        "page_2",
        "page_3",
    ]

    hrefs = {c.get("id"): c.get("href") for c in items}
    assert hrefs["page_1"] == "Text/page_1.xhtml"

    itemrefs = [c for c in list(spine) if c.tag == f"{ns}itemref"]
    idrefs = [c.get("idref") for c in itemrefs]
    assert idrefs == ["intro", "book_info", "page_1", "page_2", "page_3"]

    opf_dir = posixpath.dirname(opf_path)
    resolved = posixpath.normpath(posixpath.join(opf_dir, hrefs["page_1"]))
    assert resolved == page_1


def test_fix_content_opf_dedups_zip_and_stores_mimetype(tmp_path: Path) -> None:
    epub_path = tmp_path / "book.epub"

    opf_path = "OEBPS/content.opf"
    opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>t</dc:title>
  </metadata>
  <manifest>
    <item id="page_2" href="Text/page_2.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="page_2"/>
  </spine>
</package>
"""

    with ZipFile(epub_path, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(opf_path, opf)
        z.writestr("OEBPS/Text/page_2.xhtml", "<html/>")

    with ZipFile(epub_path, "a", compression=ZIP_DEFLATED) as z:
        z.writestr(opf_path, "<not xml")

    fix_content_opf_problems(epub_path)

    with ZipFile(epub_path, "r") as z:
        assert z.getinfo("mimetype").compress_type == 0
        assert len([i for i in z.infolist() if i.filename.endswith(".opf")]) == 1
        assert len({i.filename for i in z.infolist()}) == len(z.infolist())
        root = etree.fromstring(z.read(opf_path), xml_parser)
        ns = root.tag.split("}")[0] + "}"
        assert root.find(f".//{ns}manifest") is not None
        assert root.find(f".//{ns}spine") is not None


def test_set_epub_to_rtl_dedups_and_is_idempotent(tmp_path: Path) -> None:
    epub_path = tmp_path / "book.epub"

    opf_path = "OEBPS/content.opf"
    opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>t</dc:title>
  </metadata>
  <manifest>
    <item id="intro" href="Text/intro.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="intro"/>
  </spine>
</package>
"""

    with ZipFile(epub_path, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(opf_path, opf)
        z.writestr("OEBPS/Styles/main.css", "body{}")

    with ZipFile(epub_path, "a", compression=ZIP_DEFLATED) as z:
        z.writestr(opf_path, "<not xml")
        z.writestr("OEBPS/Styles/main.css", "body{}")

    assert set_epub_to_rtl(epub_path) is True
    assert set_epub_to_rtl(epub_path) is False

    with ZipFile(epub_path, "r") as z:
        assert z.getinfo("mimetype").compress_type == 0
        assert len([i for i in z.infolist() if i.filename.endswith(".opf")]) == 1
        assert len({i.filename for i in z.infolist()}) == len(z.infolist())

        root = etree.fromstring(z.read(opf_path), xml_parser)
        ns = root.tag.split("}")[0] + "}"
        spine = root.find(f".//{ns}spine")
        assert spine is not None
        assert spine.get("page-progression-direction") == "rtl"

        css = z.read("OEBPS/Styles/main.css")
        assert css.startswith(b"* {direction: rtl !important;}\n")


def test_flatten_toc_dedups_and_is_idempotent(tmp_path: Path) -> None:
    epub_path = tmp_path / "book.epub"

    toc_path = "OEBPS/toc.ncx"
    nav_path = "OEBPS/nav.xhtml"
    ncx = b"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <navMap>
    <navPoint id="p1" playOrder="1">
      <navLabel><text>One</text></navLabel>
      <content src="Text/page_1.xhtml"/>
      <navPoint id="p1_1" playOrder="2">
        <navLabel><text>One.A</text></navLabel>
        <content src="Text/page_2.xhtml"/>
      </navPoint>
    </navPoint>
    <navPoint id="p2" playOrder="3">
      <navLabel><text>Two</text></navLabel>
      <content src="Text/page_3.xhtml"/>
    </navPoint>
  </navMap>
</ncx>
"""
    nav = b"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <body>
    <nav epub:type="toc" id="toc">
      <ol>
        <li><a href="Text/page_1.xhtml">One</a>
          <ol>
            <li><a href="Text/page_2.xhtml">One.A</a></li>
          </ol>
        </li>
        <li><a href="Text/page_3.xhtml">Two</a></li>
      </ol>
    </nav>
  </body>
</html>
"""

    with ZipFile(epub_path, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(toc_path, ncx)
        z.writestr(nav_path, nav)

    with ZipFile(epub_path, "a", compression=ZIP_DEFLATED) as z:
        z.writestr(toc_path, ncx)
        z.writestr(nav_path, nav)

    flatten_toc(epub_path)
    after_first = epub_path.read_bytes()
    flatten_toc(epub_path)
    assert epub_path.read_bytes() == after_first

    with ZipFile(epub_path, "r") as z:
        assert z.getinfo("mimetype").compress_type == 0
        assert len({i.filename for i in z.infolist()}) == len(z.infolist())
        assert len([i for i in z.infolist() if i.filename.endswith(".ncx")]) == 1
        assert len([i for i in z.infolist() if i.filename.endswith("nav.xhtml")]) == 1

        root = etree.fromstring(z.read(toc_path), xml_parser)
        ns = root.tag.split("}")[0] + "}"
        nav_map = root.find(f".//{ns}navMap")
        assert nav_map is not None
        nav_points = [c for c in list(nav_map) if c.tag == f"{ns}navPoint"]
        assert [p.get("playOrder") for p in nav_points] == ["1", "2", "3"]

        nav_root = html.fromstring(z.read(nav_path))
        toc_nav = nav_root.xpath('//nav[@id="toc"]')[0]
        toc_ol = toc_nav.xpath(".//ol")[0]
        assert toc_ol.xpath(".//li[./ol]") == []
