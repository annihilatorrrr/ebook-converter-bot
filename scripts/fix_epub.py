# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ebook_converter_bot.utils.epub import fix_content_opf_problems, flatten_toc, set_epub_to_rtl


def main() -> None:
    p = argparse.ArgumentParser(description="Fix common EPUB issues (content.opf duplicates/case/order)")
    p.add_argument("inputs", nargs="*", help="Input .epub files or directories (default: *.epub in cwd)")
    p.add_argument("--out-dir", help="Write fixed copies to this directory (default: modify in place)")
    p.add_argument("--flat-toc", action="store_true", help="Also flatten toc.ncx and nav.xhtml")
    p.add_argument("--rtl", action="store_true", help="Also set page-progression-direction=rtl and inject RTL css")
    args = p.parse_args()

    inputs = [Path(x) for x in args.inputs] if args.inputs else sorted(Path().glob("*.epub"))
    epubs: list[Path] = []
    for x in inputs:
        if x.is_dir():
            epubs.extend(sorted(x.glob("*.epub")))
        else:
            epubs.append(x)

    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    for epub in epubs:
        out = epub
        if out_dir:
            out = out_dir / epub.name
            shutil.copyfile(epub, out)

        fix_content_opf_problems(out)
        if args.flat_toc:
            flatten_toc(out)
        if args.rtl:
            set_epub_to_rtl(out)
        print(f"{epub} -> {out}")


if __name__ == "__main__":
    main()
