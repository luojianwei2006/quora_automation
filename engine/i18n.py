"""
Internationalization (i18n) support.
Loads language packs from JSON files and provides translation lookup.
"""
import json
import os
from typing import Optional

_LANG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "static", "lang",
)

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": {"name": "English", "native": "English"},
    "zh": {"name": "中文", "native": "简体中文"},
}

_default_lang = "en"
_cached_packs: dict[str, dict] = {}


def load_lang_pack(lang_code: str) -> dict:
    """Load a language pack from JSON file."""
    if lang_code in _cached_packs:
        return _cached_packs[lang_code]

    filepath = os.path.join(_LANG_DIR, f"{lang_code}.json")
    if not os.path.exists(filepath):
        return {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            pack = json.load(f)
        _cached_packs[lang_code] = pack
        return pack
    except Exception:
        return {}


def t(key: str, lang_code: str = "en", **kwargs) -> str:
    """
    Translate a key to the given language.
    Falls back to English if key not found.
    Supports simple variable substitution: {{var}}.
    """
    # Try requested language first
    pack = load_lang_pack(lang_code)
    if key in pack:
        value = pack[key]
        if kwargs:
            for k, v in kwargs.items():
                value = value.replace(f"{{{{{k}}}}}", str(v))
        return value

    # Fallback to English
    if lang_code != "en":
        en_pack = load_lang_pack("en")
        if key in en_pack:
            value = en_pack[key]
            if kwargs:
                for k, v in kwargs.items():
                    value = value.replace(f"{{{{{k}}}}}", str(v))
            return value

    # Return key itself if nothing found
    return key


class I18n:
    """I18n helper class for Flask template injection."""

    def __init__(self, lang_code: str = "en"):
        self.lang_code = lang_code
        self._pack = load_lang_pack(lang_code)

    def translate(self, key: str, **kwargs) -> str:
        return t(key, self.lang_code, **kwargs)

    def __call__(self, key: str, **kwargs) -> str:
        return self.translate(key, **kwargs)

    @property
    def lang_info(self) -> dict:
        return SUPPORTED_LANGUAGES.get(self.lang_code, SUPPORTED_LANGUAGES["en"])


def get_lang_from_accept_header(accept_language: str) -> str:
    """Parse Accept-Language header to determine language preference."""
    if not accept_language:
        return _default_lang
    # Simple: check for zh in the header
    if "zh" in accept_language.lower():
        return "zh"
    return "en"


def get_lang_from_cookie(cookie_value: Optional[str]) -> str:
    """Get language from cookie value."""
    if cookie_value in SUPPORTED_LANGUAGES:
        return cookie_value
    return ""
