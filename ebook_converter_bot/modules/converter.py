"""Converter."""

import asyncio
from pathlib import Path
from random import sample
from string import digits
from time import monotonic
from typing import cast

from telethon import Button, events

from ebook_converter_bot.bot import BOT
from ebook_converter_bot.db.curd import get_lang
from ebook_converter_bot.utils.analytics import analysis
from ebook_converter_bot.utils.convert import Converter
from ebook_converter_bot.utils.converter_options import (
    ConversionRequestState,
    build_options_keyboard,
    cleanup_expired_requests,
    format_button_rows,
    set_request_option,
)
from ebook_converter_bot.utils.i18n import translate as _
from ebook_converter_bot.utils.telegram import tg_exceptions_handler

MAX_ALLOWED_FILE_SIZE = 26214400  # 25 MB
QUEUE_TTL_SECONDS = 1800  # 30 minutes

converter = Converter()
if "converter_queue" not in BOT.__dict__:
    BOT.__dict__["converter_queue"] = {}
queue: dict[str, ConversionRequestState] = cast(
    dict[str, ConversionRequestState], BOT.__dict__["converter_queue"]
)


async def cleanup_queue_loop() -> None:
    while True:
        cleanup_expired_requests(queue, ttl_seconds=QUEUE_TTL_SECONDS)
        sleep_task = asyncio.create_task(asyncio.sleep(60))
        done, _ = await asyncio.wait(
            {sleep_task, BOT.disconnected}, return_when=asyncio.FIRST_COMPLETED
        )
        if BOT.disconnected in done:
            sleep_task.cancel()
            break


queue_cleanup_task = BOT.loop.create_task(cleanup_queue_loop())


def render_screen(
    request_id: str,
    state: ConversionRequestState,
    lang: str,
    *,
    show_options: bool = False,
) -> tuple[str, list[list]]:
    summary_parts: list[str] = []
    if state.force_rtl:
        summary_parts.append(_("Force RTL", lang))
    if state.input_ext == "epub" and state.fix_epub:
        summary_parts.append(_("Fix EPUB before converting", lang))
    if state.input_ext == "epub" and state.flat_toc:
        summary_parts.append(_("Flatten EPUB TOC", lang))
    summary = "\n".join(summary_parts)
    if show_options:
        message_text = (
            f"{_('Conversion options:', lang)}\n\n{summary}"
            if summary
            else _("Conversion options:", lang)
        )
        buttons = build_options_keyboard(
            request_id,
            state,
            force_rtl_label=_("Force RTL", lang),
            fix_epub_label=_("Fix EPUB before converting", lang),
            flat_toc_label=_("Flatten EPUB TOC", lang),
            back_to_formats_label=_("Back to formats", lang),
            cancel_label=_("Cancel", lang),
        )
        return message_text, buttons
    message_text = (
        f"{_('Select the format you want to convert to:', lang)}\n\n{summary}"
        if summary
        else _("Select the format you want to convert to:", lang)
    )
    buttons = format_button_rows(request_id, converter.supported_output_types, per_row=3)
    buttons.append(
        [
            Button.inline(_("Options ⚙️", lang), data=f"view|opts|{request_id}"),
            Button.inline(_("Cancel", lang), data=f"cancel|{request_id}"),
        ]
    )
    return message_text, buttons


async def get_request_state(
    event: events.CallbackQuery.Event,
    request_id: str,
    *,
    pop: bool = False,
) -> ConversionRequestState | None:
    cleanup_expired_requests(queue, ttl_seconds=QUEUE_TTL_SECONDS)
    lang = get_lang(event.chat_id)
    state = queue.pop(request_id, None) if pop else queue.get(request_id)
    if not state:
        await event.answer(
            _("This conversion request expired. Please send the file again.", lang),
            alert=True,
        )
        return None
    input_file = Path(state.input_file_path)
    if not input_file.exists():
        queue.pop(request_id, None)
        await event.answer(
            _("The source file is no longer available. Please send it again.", lang),
            alert=True,
        )
        return None
    if not pop:
        state.queued_at = monotonic()
    return state


@BOT.on(events.NewMessage(func=lambda x: x.message.file and x.is_private))
@BOT.on(events.NewMessage(pattern="/convert", func=lambda x: x.message.is_reply))
@tg_exceptions_handler
async def file_converter(event: events.NewMessage.Event) -> None:
    """Convert ebook to another format."""
    lang = get_lang(event.chat_id)
    if event.pattern_match:
        message = await event.get_reply_message()
        if not message or not message.file:
            await event.reply(_("Reply to a supported file to convert it.", lang))
            return
        file = message.file
    else:
        message = event.message
        file = event.message.file
    if not file:
        return
    file_name = file.name or ""
    if not converter.is_supported_input_type(file_name):
        # Unsupported file
        await event.reply(_("The file you sent is not a supported type!", lang))
        return
    if file.size > MAX_ALLOWED_FILE_SIZE:
        await event.reply(_("Files larger than 25 MB are not supported!", lang))
        return
    reply = await event.reply(_("Downloading the file...", lang))
    download_dir = Path("/tmp/ebook_converter_bot")  # noqa: S108
    download_dir.mkdir(parents=True, exist_ok=True)
    downloaded = await message.download_media(download_dir)
    if not downloaded:
        await reply.edit(_("Failed to download the file. Please send it again.", lang))
        return
    cleanup_expired_requests(queue, ttl_seconds=QUEUE_TTL_SECONDS)
    random_id = "".join(sample(digits, 8))
    while random_id in queue:
        random_id = "".join(sample(digits, 8))
    queue[random_id] = ConversionRequestState(
        input_file_path=downloaded,
        queued_at=monotonic(),
        input_ext=file_name.lower().split(".")[-1],
    )
    message_text, buttons = render_screen(random_id, queue[random_id], lang)
    await reply.edit(message_text, buttons=buttons)


@BOT.on(events.CallbackQuery(pattern=r"view\|(opts|formats)\|\d+"))
@tg_exceptions_handler
async def view_switch_callback(event: events.CallbackQuery.Event) -> None:
    _view, view_name, request_id = event.data.decode().split("|")
    lang = get_lang(event.chat_id)
    state = await get_request_state(event, request_id)
    if not state:
        return
    if view_name == "opts":
        message_text, buttons = render_screen(request_id, state, lang, show_options=True)
        await event.edit(message_text, buttons=buttons)
        return
    message_text, buttons = render_screen(request_id, state, lang)
    await event.edit(message_text, buttons=buttons)


@BOT.on(events.CallbackQuery(pattern=r"opt\|(rtl|fix_epub|flat_toc)\|[01]\|\d+"))
@tg_exceptions_handler
async def options_toggle_callback(event: events.CallbackQuery.Event) -> None:
    _opt, option_key, enabled_flag, request_id = event.data.decode().split("|")
    lang = get_lang(event.chat_id)
    state = await get_request_state(event, request_id)
    if not state:
        return
    if not set_request_option(state, option_key, enabled_flag == "1"):
        await event.answer(_("This option is available only for EPUB input.", lang), alert=True)
        return
    message_text, buttons = render_screen(request_id, state, lang, show_options=True)
    await event.edit(message_text, buttons=buttons)


@BOT.on(events.CallbackQuery(pattern=r"cancel\|\d+"))
@tg_exceptions_handler
async def cancel_conversion_callback(event: events.CallbackQuery.Event) -> None:
    _cancel, request_id = event.data.decode().split("|")
    lang = get_lang(event.chat_id)
    state = queue.pop(request_id, None)
    if not state:
        await event.answer(
            _("This conversion request expired. Please send the file again.", lang),
            alert=True,
        )
        return
    Path(state.input_file_path).unlink(missing_ok=True)
    await event.edit(_("Conversion request canceled.", lang))


@BOT.on(events.CallbackQuery(pattern=r"fmt\|[\w-]+\|\d+"))
@tg_exceptions_handler
@analysis
async def converter_callback(
    event: events.CallbackQuery.Event,
) -> tuple[str, str] | None:
    """Converter callback handler."""
    lang = get_lang(event.chat_id)
    converted = False
    _fmt, output_type, request_id = event.data.decode().split("|")
    state = await get_request_state(event, request_id, pop=True)
    if not state:
        return None
    reply = await event.edit(_("Converting the file to {}...", lang).format(output_type))
    input_file = Path(state.input_file_path)
    output_file, converted_to_rtl, conversion_error = await converter.convert_ebook(
        input_file,
        output_type,
        force_rtl=state.force_rtl,
        fix_epub=state.fix_epub if state.input_ext == "epub" else False,
        flat_toc=state.flat_toc if state.input_ext == "epub" else False,
    )
    if output_file.exists():
        message_text = ""
        if state.force_rtl and converted_to_rtl:
            message_text += _("Converted to RTL successfully!\n", lang)
        message_text += _("Done! Uploading the converted file...", lang)
        await reply.edit(message_text)
        await event.client.send_file(event.chat, output_file, reply_to=reply, force_document=True)
        converted = True
    else:
        input_file_name = input_file.name
        error_message = _("Failed to convert the file (`{}`) to {} :(", lang).format(
            input_file_name, output_type
        )
        if conversion_error:
            error_message += f"\n\n`{conversion_error}`"
        await reply.edit(error_message)
    input_file.unlink(missing_ok=True)
    output_file.unlink(missing_ok=True)
    if converted:
        return state.input_ext, output_type
    return None
