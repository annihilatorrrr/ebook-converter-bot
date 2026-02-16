from ebook_converter_bot.utils.convert import Converter


def test_is_supported_input_type_handles_missing_name() -> None:
    assert Converter().is_supported_input_type(None) is False


def test_is_supported_input_type_is_case_insensitive() -> None:
    assert Converter().is_supported_input_type("Book.EPUB") is True
