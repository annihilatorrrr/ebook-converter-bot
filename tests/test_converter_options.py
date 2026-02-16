from pathlib import Path
from time import monotonic

from ebook_converter_bot.utils.converter_options import (
    ConversionRequestState,
    build_options_keyboard,
    cleanup_expired_requests,
    format_button_rows,
    toggle_request_option,
)
from telethon.tl.types import KeyboardButtonCallback


def test_format_button_rows_are_chunked_to_three() -> None:
    rows: list[list[KeyboardButtonCallback]] = format_button_rows(
        "12345678",
        ["azw3", "docx", "epub", "fb2", "htmlz", "kepub", "kfx"],
    )
    assert [len(row) for row in rows] == [3, 3, 1]
    assert rows[0][0].text == "🔸 azw3"
    assert rows[0][0].data == b"fmt|azw3|12345678"
    assert rows[1][2].text == "kepub"


def test_options_keyboard_shows_epub_only_toggles_for_epub_input() -> None:
    epub_state = ConversionRequestState(
        input_file_path="/tmp/book.epub",  # noqa: S108
        queued_at=monotonic(),
        input_ext="epub",
    )
    non_epub_state = ConversionRequestState(
        input_file_path="/tmp/book.pdf",  # noqa: S108
        queued_at=monotonic(),
        input_ext="pdf",
    )

    epub_rows = build_options_keyboard(
        "12345678",
        epub_state,
        force_rtl_label="Force RTL",
        fix_epub_label="Fix EPUB before converting",
        flat_toc_label="Flatten EPUB TOC",
        back_to_formats_label="Back to formats",
        cancel_label="Cancel",
    )
    non_epub_rows = build_options_keyboard(
        "12345678",
        non_epub_state,
        force_rtl_label="Force RTL",
        fix_epub_label="Fix EPUB before converting",
        flat_toc_label="Flatten EPUB TOC",
        back_to_formats_label="Back to formats",
        cancel_label="Cancel",
    )

    assert [row[0].data for row in epub_rows] == [
        b"opt|rtl|12345678",
        b"opt|fix_epub|12345678",
        b"opt|flat_toc|12345678",
        b"view|formats|12345678",
        b"cancel|12345678",
    ]
    assert [row[0].data for row in non_epub_rows] == [
        b"opt|rtl|12345678",
        b"view|formats|12345678",
        b"cancel|12345678",
    ]


def test_toggle_request_option_mutates_only_selected_flag() -> None:
    state = ConversionRequestState(
        input_file_path="/tmp/book.epub",  # noqa: S108
        queued_at=monotonic(),
        input_ext="epub",
    )
    assert toggle_request_option(state, "rtl") is True
    assert state.force_rtl is True
    assert state.fix_epub is False
    assert state.flat_toc is False

    assert toggle_request_option(state, "fix_epub") is True
    assert state.fix_epub is True
    assert state.flat_toc is False

    assert toggle_request_option(state, "flat_toc") is True
    assert state.flat_toc is True


def test_toggle_request_option_rejects_epub_only_flags_for_non_epub() -> None:
    state = ConversionRequestState(
        input_file_path="/tmp/book.pdf",  # noqa: S108
        queued_at=monotonic(),
        input_ext="pdf",
    )
    assert toggle_request_option(state, "fix_epub") is False
    assert toggle_request_option(state, "flat_toc") is False


def test_cleanup_expired_requests_removes_stale_state_and_file(tmp_path: Path) -> None:
    stale_file = tmp_path / "stale.epub"
    fresh_file = tmp_path / "fresh.epub"
    stale_file.write_text("stale")
    fresh_file.write_text("fresh")
    queue = {
        "stale": ConversionRequestState(
            input_file_path=str(stale_file),
            queued_at=monotonic() - 100,
            input_ext="epub",
        ),
        "fresh": ConversionRequestState(
            input_file_path=str(fresh_file),
            queued_at=monotonic(),
            input_ext="epub",
        ),
    }

    cleanup_expired_requests(queue, ttl_seconds=60)

    assert "stale" not in queue
    assert stale_file.exists() is False
    assert "fresh" in queue
    assert fresh_file.exists() is True
