import json
import os
import re

from core.latex import latex_escape
from core.settings import LANG_ENGINE_DIR


def parse_cv_filename(filename):
    """
    Parse CV filename to extract base_name and language code.

    Supports patterns:
    - name-<lang>.json (e.g., ramin-de.json)
    - name_<lang>.json (e.g., ramin_fa.json)
    - name.json (defaults to lang='en')

    Returns (base_name, lang)
    """
    # Remove .json extension
    name = filename[:-5] if filename.lower().endswith('.json') else filename

    # Pattern: name-lang or name_lang where lang is 2-3 lowercase letters
    match = re.match(r'^(.+?)[-_]([a-z]{2,3})$', name)
    if match:
        return match.group(1), match.group(2)

    # No language suffix - default to English
    return name, "en"


def load_lang_map():
    """
    Load the translation mapping from Lang_engine/lang.json.

    Expected format:
    {
      "education": { "en": "Education", "de": "Ausbildung", "fa": "تحصیلات" },
      ...
    }
    """
    lang_file = os.path.join(LANG_ENGINE_DIR, "lang.json")

    if not os.path.exists(lang_file):
        raise SystemExit(
            f"[ERROR] Translation file not found at: {lang_file}\n"
            f"Expected format:\n"
            f'{{\n'
            f'  "education": {{ "en": "Education", "de": "Ausbildung", "fa": "تحصیلات" }},\n'
            f'  "email": {{ "en": "Email", "de": "E-Mail", "fa": "ایمیل" }}\n'
            f'}}'
        )

    with open(lang_file, encoding="utf-8") as f:
        return json.load(f)


def make_translate_func(lang_map, lang):
    """
    Create a translation function for a specific language.

    Returns a function t(key, default=None, escape=True) that:
    - Looks up LANG_MAP[key][lang]
    - Falls back to default, then LANG_MAP[key]["en"], then the raw key
    - LaTeX-escapes by default
    """
    def t(key, default=None, escape=True):
        result = None

        # Try to get translation for current language
        if key in lang_map:
            translations = lang_map[key]
            if lang in translations and translations[lang]:
                result = translations[lang]
            elif default is not None:
                result = default
            elif "en" in translations and translations["en"]:
                result = translations["en"]

        # Fallback to default or raw key
        if result is None:
            result = default if default is not None else key

        # LaTeX escape by default
        if escape:
            return latex_escape(result)
        return result

    return t


def make_tr_filter(lang_map, lang):
    """Create a |tr filter (LaTeX-escaped translation)."""
    t = make_translate_func(lang_map, lang)
    def tr_filter(key):
        return t(key, escape=True)
    return tr_filter


def make_tr_raw_filter(lang_map, lang):
    """Create a |tr_raw filter (unescaped translation)."""
    t = make_translate_func(lang_map, lang)
    def tr_raw_filter(key):
        return t(key, escape=False)
    return tr_raw_filter
