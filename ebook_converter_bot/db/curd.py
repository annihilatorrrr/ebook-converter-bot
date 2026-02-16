from collections.abc import Callable
from functools import wraps
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import sum as sql_sum

from ebook_converter_bot.db.models.analytics import Analytics
from ebook_converter_bot.db.models.chat import Chat
from ebook_converter_bot.db.models.preference import Preference
from ebook_converter_bot.db.session import get_session


def with_session(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with get_session() as session:
            return func(*args, session=session, **kwargs)

    return wrapper


@with_session
def generate_analytics_columns(formats: list[str], *, session: Session) -> None:
    existing = {row[0] for row in session.query(Analytics.format).all()}
    missing = [f for f in formats if f not in existing]
    if not missing:
        return
    session.add_all([Analytics(format=i) for i in missing])
    session.commit()


@with_session
def update_format_analytics(file_format: str, output: bool = False, *, session: Session) -> None:
    file_format_analytics: Analytics | None = (
        session.query(Analytics).filter(Analytics.format == file_format).first()
    )
    if not file_format_analytics:
        return
    if output:
        file_format_analytics.output_times += 1
    else:
        file_format_analytics.input_times += 1
    session.commit()


@with_session
def add_chat_to_db(user_id: int, user_name: str, chat_type: int, *, session: Session) -> None:
    if not session.query(Chat).filter(Chat.user_id == user_id).first():
        session.add(Chat(user_id=user_id, user_name=user_name, type=chat_type))
        session.commit()


@with_session
def remove_chat(user_id: int, *, session: Session) -> bool:
    chat = session.query(Chat).filter(Chat.user_id == user_id).first()
    if not chat:
        return False
    session.delete(chat)
    session.commit()
    return True


@with_session
def increment_usage(user_id: int, *, session: Session) -> None:
    chat = session.query(Chat).filter(Chat.user_id == user_id).first()
    if not chat:
        return
    chat.usage_times += 1
    session.commit()


@with_session
def update_language(user_id: int, language: str, *, session: Session) -> None:
    chat: Preference | None = (
        session.query(Preference).filter(Preference.user_id == user_id).first()
    )
    if not chat:
        chat = Preference(user_id=user_id, language=language)
        session.add(chat)
    else:
        chat.language = language
    session.commit()


@with_session
def get_lang(user_id: int, *, session: Session) -> str:
    language: str = (
        session.query(Preference.language).filter(Preference.user_id == user_id).scalar()
    )
    return language or "en"


@with_session
def get_chats_count(*, session: Session) -> tuple[int, int]:
    all_chats = session.query(Chat).count()
    active_chats = session.query(Chat).filter(Chat.usage_times > 0).count()
    return all_chats, active_chats


@with_session
def get_usage_count(*, session: Session) -> tuple[int, int]:
    usage_times: int = session.query(sql_sum(Chat.usage_times)).scalar() or 0
    output_times: int = session.query(sql_sum(Analytics.output_times)).scalar() or 0
    return usage_times, output_times


@with_session
def get_top_formats(*, session: Session) -> tuple[dict[str, int], dict[str, int]]:
    out_formats: list[Analytics] = (
        session.query(Analytics).order_by(Analytics.output_times.desc()).limit(5).all()
    )
    in_formats: list[Analytics] = (
        session.query(Analytics).order_by(Analytics.input_times.desc()).limit(5).all()
    )
    return {i.format: i.output_times for i in out_formats}, {
        i.format: i.input_times for i in in_formats
    }


@with_session
def get_all_chats(*, session: Session) -> list[Chat]:
    return session.query(Chat).all()
