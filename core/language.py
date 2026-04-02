import json
import os
import re

from core.latex import latex_escape
from core.settings import LANG_ENGINE_DIR


import re


def parse_cv_filename(filename: str):
    """
    Parse a filename into:

        (base_name, lang, extra)

    Supported examples:
    - ramin_en.json                          -> ("ramin", "en", "")
    - ramin_yazdani_en.json                 -> ("ramin_yazdani", "en", "")
    - ramin_en_google.json                  -> ("ramin", "en", "google")
    - ramin_yazdani_en_google_cover_letter.json
                                             -> ("ramin_yazdani", "en", "google_cover_letter")
    - ramin_yazdani,google_cover_letter.json
                                             -> ("ramin_yazdani", "en", "google_cover_letter")

    Rules:
    1. If a comma exists, it explicitly separates base_name from the rest.
       Example: "ramin_yazdani,google_cover_letter.json"
    2. Otherwise, split by "_" or "-".
    3. The first standalone 2-3 lowercase-letter token is treated as language.
    4. Tokens after language become "extra".
    5. If no language token exists, lang defaults to "en".
    6. When no language token exists, known suffix patterns at the end are
       extracted into "extra" (e.g. google, cover_letter, awesomecv_sectioned).

    Returns:
        tuple[str, str, str]
    """

    # Remove extension
    name = filename[:-5] if filename.lower().endswith(".json") else filename
    name = name.strip()

    if not name:
        return "", "en", ""

    # ------------------------------------------------------------
    # 1) Explicit base / extra split via comma
    # ------------------------------------------------------------
    if "," in name:
        base_part, tail_part = name.split(",", 1)
        base_name = base_part.strip()
        tail_part = tail_part.strip()

        # tail may itself start with a lang token, e.g. "en_google_cover_letter"
        tail_tokens = [t for t in re.split(r"[_-]+", tail_part) if t]
        if tail_tokens and re.fullmatch(r"[a-z]{2,3}", tail_tokens[0]):
            lang = tail_tokens[0]
            extra = "_".join(tail_tokens[1:])
        else:
            lang = "en"
            extra = "_".join(tail_tokens)

        return base_name, lang, extra

    # ------------------------------------------------------------
    # 2) Normal tokenization by "_" or "-"
    # ------------------------------------------------------------
    tokens = [t for t in re.split(r"[_-]+", name) if t]

    if not tokens:
        return "", "en", ""

    # ------------------------------------------------------------
    # 3) Find first language token
    # ------------------------------------------------------------
    lang_index = None
    for i, token in enumerate(tokens):
        if re.fullmatch(r"[a-z]{2,3}", token):
            lang_index = i
            break

    if lang_index is not None:
        base_name = "_".join(tokens[:lang_index])
        lang = tokens[lang_index]
        extra = "_".join(tokens[lang_index + 1:])
        return base_name, lang, extra

    # ------------------------------------------------------------
    # 4) No language token found -> default to en
    #    Try to peel off known suffixes from the end as "extra"
    # ------------------------------------------------------------
    lang = "en"

    # Add/adjust these as your project grows
    known_suffix_patterns = [
        ("awesomecv", "sectioned"),
        ("cover", "letter"),
        ("google",),
        ("compact",),
        ("default",),
        ("rtl",),
        ("academic",),
        ("cv",),
        ("resume",),
        ("cl",),
    ]

    remaining = tokens[:]
    extracted_suffix = []

    while remaining:
        matched = None

        # Longest match first
        for pattern in sorted(known_suffix_patterns, key=len, reverse=True):
            n = len(pattern)
            if len(remaining) >= n and tuple(remaining[-n:]) == pattern:
                matched = pattern
                break

        if matched is None:
            break

        remaining = remaining[: -len(matched)]
        extracted_suffix = list(matched) + extracted_suffix

    if remaining:
        base_name = "_".join(remaining)
        extra = "_".join(extracted_suffix)
        return base_name, lang, extra

    # Fallback: if everything got consumed as suffix, keep original name as base
    return name, lang, ""


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
