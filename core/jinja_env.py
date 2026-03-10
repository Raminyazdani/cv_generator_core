from jinja2 import Environment, FileSystemLoader, StrictUndefined

from core import settings
from core.latex import latex_escape, debug, types, cmt, cblock, file_exists, get_pic, find_pic
from core.language import make_translate_func, make_tr_filter, make_tr_raw_filter


def create_jinja_env(lang_map, lang, base_name, is_rtl):
    """
    Create and configure a Jinja2 environment for document rendering.

    This factory sets up the shared Jinja2 environment with custom delimiters,
    filters, and globals used by both CV and cover-letter rendering pipelines.

    Args:
        lang_map: Translation mapping dictionary
        lang: Language code (e.g., 'en', 'de', 'fa')
        base_name: Base name extracted from input filename
        is_rtl: Whether the language is right-to-left

    Returns:
        Configured Jinja2 Environment instance
    """
    env = Environment(
        loader=FileSystemLoader(settings.TEMPLATE_DIR),
        block_start_string="<BLOCK>",
        block_end_string="</BLOCK>",
        variable_start_string="<VAR>",
        variable_end_string="</VAR>",
        comment_start_string="/*/*/*",
        comment_end_string="*/*/*/",
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )

    # Create translation function for this language
    t_func = make_translate_func(lang_map, lang)

    # Register filters
    env.filters["latex_escape"] = latex_escape
    env.filters["debug"] = debug
    env.filters["types"] = types
    env.filters["cmt"] = cmt
    env.filters["cblock"] = cblock
    env.filters["file_exists"] = file_exists
    env.filters["get_pic"] = get_pic
    env.filters["find_pic"] = find_pic
    env.filters["tr"] = make_tr_filter(lang_map, lang)
    env.filters["tr_raw"] = make_tr_raw_filter(lang_map, lang)

    # Register globals
    env.globals["SHOW_COMMENTS"] = settings.SHOW_COMMENTS
    env.globals["LANG_MAP"] = lang_map
    env.globals["LANG"] = lang
    env.globals["BASE_NAME"] = base_name
    env.globals["IS_RTL"] = is_rtl
    env.globals["t"] = t_func

    return env
