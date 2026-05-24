from __future__ import annotations

from app.strings import DL_STRINGS, DOCS_STRINGS, HOME_STRINGS


def test_home_strings_have_same_keys_in_both_languages() -> None:
    assert set(HOME_STRINGS["en"].keys()) == set(HOME_STRINGS["ru"].keys())


def test_dl_strings_have_same_keys_in_both_languages() -> None:
    assert set(DL_STRINGS["en"].keys()) == set(DL_STRINGS["ru"].keys())


def test_home_strings_no_empty_values() -> None:
    for lang in ("en", "ru"):
        for key, value in HOME_STRINGS[lang].items():
            assert value.strip(), f"empty HOME_STRINGS[{lang}][{key}]"


def test_dl_strings_no_empty_values() -> None:
    for lang in ("en", "ru"):
        for key, value in DL_STRINGS[lang].items():
            assert value.strip(), f"empty DL_STRINGS[{lang}][{key}]"


def test_docs_strings_have_same_keys_in_both_languages() -> None:
    assert set(DOCS_STRINGS["en"].keys()) == set(DOCS_STRINGS["ru"].keys())


def test_docs_strings_no_empty_values() -> None:
    for lang in ("en", "ru"):
        for key, value in DOCS_STRINGS[lang].items():
            assert value.strip(), f"empty DOCS_STRINGS[{lang}][{key}]"


def test_dl_strings_includes_relative_time_units() -> None:
    # _relative_time in app/agent.py reads these.
    for lang in ("en", "ru"):
        for k in ("just_now", "minutes_ago", "hours_ago", "days_ago", "weeks_ago"):
            assert k in DL_STRINGS[lang], f"missing DL_STRINGS[{lang}][{k}]"
