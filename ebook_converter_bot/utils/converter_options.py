from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from telethon import Button
from telethon.tl.types import KeyboardButtonCallback

HIGHLIGHTED_FORMATS: set[str] = {"azw3", "docx", "epub", "kfx", "mobi", "pdf"}


@dataclass
class ConversionRequestState:
    input_file_path: str
    queued_at: float
    input_ext: str
    force_rtl: bool = False
    fix_epub: bool = False
    flat_toc: bool = False


def format_button_rows(
    request_id: str,
    output_types: list[str],
    *,
    per_row: int = 3,
) -> list[list[KeyboardButtonCallback]]:
    buttons = [
        Button.inline(
            f"🔸 {output_type}" if output_type in HIGHLIGHTED_FORMATS else output_type,
            data=f"fmt|{output_type}|{request_id}",
        )
        for output_type in output_types
    ]
    return [buttons[i : i + per_row] for i in range(0, len(buttons), per_row)]


def build_options_keyboard(  # noqa: PLR0913
    request_id: str,
    state: ConversionRequestState,
    *,
    force_rtl_label: str,
    fix_epub_label: str,
    flat_toc_label: str,
    back_to_formats_label: str,
    cancel_label: str,
) -> list[list[KeyboardButtonCallback]]:
    rows = [
        [
            Button.inline(
                f"{force_rtl_label}: {'✅' if state.force_rtl else '❌'}",
                data=f"opt|rtl|{request_id}",
            )
        ]
    ]
    if state.input_ext == "epub":
        rows.extend(
            [
                [
                    Button.inline(
                        f"{fix_epub_label}: {'✅' if state.fix_epub else '❌'}",
                        data=f"opt|fix_epub|{request_id}",
                    )
                ],
                [
                    Button.inline(
                        f"{flat_toc_label}: {'✅' if state.flat_toc else '❌'}",
                        data=f"opt|flat_toc|{request_id}",
                    )
                ],
            ]
        )
    rows.append([Button.inline(back_to_formats_label, data=f"view|formats|{request_id}")])
    rows.append([Button.inline(cancel_label, data=f"cancel|{request_id}")])
    return rows


def toggle_request_option(state: ConversionRequestState, option_key: str) -> bool:
    if option_key == "rtl":
        state.force_rtl = not state.force_rtl
        return True
    if option_key == "fix_epub" and state.input_ext == "epub":
        state.fix_epub = not state.fix_epub
        return True
    if option_key == "flat_toc" and state.input_ext == "epub":
        state.flat_toc = not state.flat_toc
        return True
    return False


def cleanup_expired_requests(
    queue: dict[str, ConversionRequestState],
    *,
    ttl_seconds: int,
) -> None:
    now: float = monotonic()
    for random_id, state in list(queue.items()):
        if now - state.queued_at <= ttl_seconds:
            continue
        queue.pop(random_id, None)
        Path(state.input_file_path).unlink(missing_ok=True)
