import asyncio
from pathlib import Path

from ebook_converter_bot.utils.convert import ConversionOptions, Converter


def _capture_commands(converter: Converter) -> list[list[str]]:
    commands: list[list[str]] = []

    async def fake_run(command: list[str]) -> tuple[int | None, str]:
        commands.append(command)
        return 0, ""

    converter._run_command = fake_run  # type: ignore[method-assign]
    return commands


def _contains_flag_pair(command: list[str], flag: str, value: str) -> bool:
    try:
        index = command.index(flag)
    except ValueError:
        return False
    return index + 1 < len(command) and command[index + 1] == value


def test_docx_options_are_applied_only_when_changed(tmp_path: Path) -> None:
    async def run() -> None:
        converter = Converter()
        commands = _capture_commands(converter)
        input_file = tmp_path / "book.txt"
        input_file.write_text("hello")

        await converter.convert_ebook(
            input_file,
            "docx",
            options=ConversionOptions(
                smarten_punctuation=True,
                change_justification="left",
                remove_paragraph_spacing=True,
                docx_page_size="a4",
                docx_no_toc=True,
            ),
        )

        command = commands[0]
        assert "--smarten-punctuation" in command
        assert "--remove-paragraph-spacing" in command
        assert _contains_flag_pair(command, "--change-justification", "left")
        assert _contains_flag_pair(command, "--docx-page-size", "a4")
        assert "--docx-no-toc" in command

    asyncio.run(run())


def test_epub_options_are_applied_only_when_changed(tmp_path: Path) -> None:
    async def run() -> None:
        converter = Converter()
        commands = _capture_commands(converter)
        input_file = tmp_path / "book.txt"
        input_file.write_text("hello")

        await converter.convert_ebook(
            input_file,
            "epub",
            options=ConversionOptions(
                epub_version="3",
                epub_inline_toc=True,
                epub_remove_background=True,
            ),
        )

        command = commands[0]
        assert _contains_flag_pair(command, "--epub-version", "3")
        assert "--epub-inline-toc" in command
        assert _contains_flag_pair(
            command, "--filter-css", "background,background-color,background-image"
        )

    asyncio.run(run())


def test_pdf_options_are_applied_only_when_changed(tmp_path: Path) -> None:
    async def run() -> None:
        converter = Converter()
        commands = _capture_commands(converter)
        input_file = tmp_path / "book.txt"
        input_file.write_text("hello")

        await converter.convert_ebook(
            input_file,
            "pdf",
            options=ConversionOptions(
                pdf_paper_size="a4",
                pdf_page_numbers=True,
            ),
        )

        command = commands[0]
        assert _contains_flag_pair(command, "--paper-size", "a4")
        assert "--pdf-page-numbers" in command

    asyncio.run(run())


def test_format_specific_flags_do_not_leak_to_other_outputs(tmp_path: Path) -> None:
    async def run() -> None:
        converter = Converter()
        commands = _capture_commands(converter)
        input_file = tmp_path / "book.txt"
        input_file.write_text("hello")

        await converter.convert_ebook(
            input_file,
            "fb2",
            options=ConversionOptions(
                docx_page_size="a4",
                docx_no_toc=True,
                epub_version="3",
                epub_inline_toc=True,
                epub_remove_background=True,
                pdf_paper_size="letter",
                pdf_page_numbers=True,
            ),
        )

        command = commands[0]
        assert "--docx-page-size" not in command
        assert "--docx-no-toc" not in command
        assert "--epub-version" not in command
        assert "--epub-inline-toc" not in command
        assert "--filter-css" not in command
        assert "--paper-size" not in command
        assert "--pdf-page-numbers" not in command

    asyncio.run(run())


def test_epub_remove_background_applies_for_epub_input_to_epub_output(tmp_path: Path) -> None:
    async def run() -> None:
        converter = Converter()
        commands = _capture_commands(converter)
        input_file = tmp_path / "book.epub"
        input_file.write_text("hello")

        await converter.convert_ebook(
            input_file,
            "epub",
            options=ConversionOptions(epub_remove_background=True),
        )

        command = commands[0]
        assert command[0] == "ebook-convert"
        assert command[1] == str(input_file)
        assert command[2].endswith("_.epub")
        assert _contains_flag_pair(
            command, "--filter-css", "background,background-color,background-image"
        )

    asyncio.run(run())
