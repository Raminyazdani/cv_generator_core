"""Tests for the refactored core modules and document-specific orchestration.

Validates that:
 - Core modules are importable and expose the expected symbols.
 - The Jinja2 environment factory produces a correctly configured env.
 - CV-specific section template discovery works correctly.
 - Cover-letter build module exposes the expected orchestration hooks.
 - All symbols previously available on ``generate_cv`` are still re-exported.
"""

import os
from pathlib import Path

import pytest
from jinja2 import StrictUndefined

# ── Core modules ────────────────────────────────────────────────────────────
from core import settings as core_settings
from core.cache import (
    load_cache,
    save_cache,
    compute_file_hash,
    normalize_path_for_cache,
    cache_key_for_path,
    has_file_changed,
    compute_composite_hash,
)
from core.files import gather_input_files, resolve_output_target
from core.latex import latex_escape, file_exists, debug, types, cmt, cblock, find_pic, get_pic
from core.language import (
    parse_cv_filename,
    load_lang_map,
    make_translate_func,
    make_tr_filter,
    make_tr_raw_filter,
)
from core.jinja_env import create_jinja_env
from core.compile import compile_latex, finalize_pdf
from core.cleanup import rmtree_reliable

# ── Document-specific modules ──────────────────────────────────────────────
from cv.build import process_cv_file, get_cv_section_templates
from cover_letter.build import process_cover_letter_file, CL_PARTIAL_TEMPLATES, get_cl_layout

# ── Backward-compat wrapper ───────────────────────────────────────────────
import generate_cv


ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT_DIR / "templates"


# ── Tests: core.settings ────────────────────────────────────────────────────
class TestCoreSettings:
    """Shared settings module exposes expected constants."""

    def test_base_dir_exists(self):
        assert os.path.isdir(core_settings.BASE_DIR)

    def test_template_dir_exists(self):
        assert os.path.isdir(core_settings.TEMPLATE_DIR)

    def test_rtl_languages_is_set(self):
        assert isinstance(core_settings.RTL_LANGUAGES, set)
        assert "fa" in core_settings.RTL_LANGUAGES

    def test_cover_letter_path_defined(self):
        assert hasattr(core_settings, "COVER_LETTER_PATH")


# ── Tests: core.cache ──────────────────────────────────────────────────────
class TestCoreCache:
    """Cache utilities work correctly when imported from core."""

    def test_compute_file_hash_returns_hex(self, tmp_path):
        f = tmp_path / "sample.json"
        f.write_text('{"a": 1}', encoding="utf-8")
        h = compute_file_hash(f)
        assert isinstance(h, str) and len(h) == 64

    def test_cache_key_for_path_is_stable(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text("{}", encoding="utf-8")
        assert cache_key_for_path(f) == cache_key_for_path(f)

    def test_has_file_changed_via_core(self, tmp_path):
        f = tmp_path / "a.json"
        f.write_text("{}", encoding="utf-8")
        pdf = tmp_path / "a.pdf"
        changed, h = has_file_changed(f, {}, pdf)
        assert changed is True

    def test_cache_key_for_path_with_prefix(self, tmp_path):
        f = tmp_path / "letter.json"
        f.write_text("{}", encoding="utf-8")
        key_no_prefix = cache_key_for_path(f)
        key_cl = cache_key_for_path(f, prefix="cl:")
        assert key_cl.startswith("cl:")
        assert key_cl == "cl:" + key_no_prefix

    def test_cache_key_prefix_avoids_collision(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text("{}", encoding="utf-8")
        cv_key = cache_key_for_path(f)
        cl_key = cache_key_for_path(f, prefix="cl:")
        assert cv_key != cl_key

    def test_compute_composite_hash_single_file(self, tmp_path):
        f = tmp_path / "a.json"
        f.write_text('{"key": "value"}', encoding="utf-8")
        h = compute_composite_hash([f])
        assert isinstance(h, str) and len(h) == 64

    def test_compute_composite_hash_multiple_files(self, tmp_path):
        a = tmp_path / "a.json"
        b = tmp_path / "b.tex"
        a.write_text('{"key": 1}', encoding="utf-8")
        b.write_text("\\section{}", encoding="utf-8")
        h = compute_composite_hash([a, b])
        assert isinstance(h, str) and len(h) == 64

    def test_compute_composite_hash_order_independent(self, tmp_path):
        a = tmp_path / "a.json"
        b = tmp_path / "b.tex"
        a.write_text('{"key": 1}', encoding="utf-8")
        b.write_text("\\section{}", encoding="utf-8")
        h1 = compute_composite_hash([a, b])
        h2 = compute_composite_hash([b, a])
        assert h1 == h2

    def test_compute_composite_hash_detects_change(self, tmp_path):
        a = tmp_path / "a.json"
        b = tmp_path / "b.tex"
        a.write_text('{"key": 1}', encoding="utf-8")
        b.write_text("\\section{}", encoding="utf-8")
        h1 = compute_composite_hash([a, b])
        b.write_text("\\section{changed}", encoding="utf-8")
        h2 = compute_composite_hash([a, b])
        assert h1 != h2

    def test_compute_composite_hash_returns_none_for_missing(self, tmp_path):
        a = tmp_path / "exists.json"
        a.write_text("{}", encoding="utf-8")
        missing = tmp_path / "missing.json"
        assert compute_composite_hash([a, missing]) is None


# ── Tests: core.files ──────────────────────────────────────────────────────
class TestCoreFiles:
    """File-resolution utilities importable from core."""

    def test_gather_input_files_via_core(self, tmp_path):
        folder = tmp_path / "data"
        folder.mkdir()
        (folder / "a.json").write_text("{}", encoding="utf-8")
        files = gather_input_files([], folder)
        assert len(files) == 1

    def test_resolve_output_target_via_core(self, tmp_path):
        f = tmp_path / "x.json"
        f.write_text("{}", encoding="utf-8")
        out_dir, out_file = resolve_output_target(str(tmp_path / "out.pdf"), [f])
        assert out_file == tmp_path / "out.pdf"


# ── Tests: core.latex ──────────────────────────────────────────────────────
class TestCoreLatex:
    """LaTeX helpers importable from core."""

    def test_latex_escape_ampersand(self):
        assert r"\&" in latex_escape("a & b")

    def test_cmt_returns_comment(self):
        result = cmt("hello")
        assert result.startswith("% ")


# ── Tests: core.language ──────────────────────────────────────────────────
class TestCoreLanguage:
    """Language and translation utilities importable from core."""

    def test_parse_cv_filename_with_lang(self):
        base, lang,extra = parse_cv_filename("ramin_de.json")
        assert base == "ramin"
        assert lang == "de"

    def test_load_lang_map_via_core(self):
        lang_map = load_lang_map()
        assert isinstance(lang_map, dict)
        assert len(lang_map) > 0


# ── Tests: core.jinja_env ──────────────────────────────────────────────────
class TestCoreJinjaEnv:
    """Jinja2 environment factory creates correct configuration."""

    def test_custom_delimiters(self):
        lang_map = load_lang_map()
        env = create_jinja_env(lang_map, "en", "test", False)
        assert env.block_start_string == "<BLOCK>"
        assert env.variable_start_string == "<VAR>"

    def test_filters_registered(self):
        lang_map = load_lang_map()
        env = create_jinja_env(lang_map, "en", "test", False)
        assert "latex_escape" in env.filters
        assert "tr" in env.filters
        assert "tr_raw" in env.filters
        assert "cmt" in env.filters

    def test_globals_set(self):
        lang_map = load_lang_map()
        env = create_jinja_env(lang_map, "de", "ramin", True)
        assert env.globals["LANG"] == "de"
        assert env.globals["BASE_NAME"] == "ramin"
        assert env.globals["IS_RTL"] is True
        assert callable(env.globals["t"])

    def test_strict_undefined(self):
        lang_map = load_lang_map()
        env = create_jinja_env(lang_map, "en", "test", False)
        assert env.undefined is StrictUndefined


# ── Tests: cv.build ───────────────────────────────────────────────────────
class TestCVBuild:
    """CV-specific build orchestration works correctly."""

    def test_get_cv_section_templates_returns_tex_files(self):
        templates = get_cv_section_templates()
        assert len(templates) > 0
        for t in templates:
            assert t.endswith(".tex")
            assert not t.startswith("layout")

    def test_get_cv_section_templates_excludes_directories(self):
        templates = get_cv_section_templates()
        for t in templates:
            assert os.path.isfile(os.path.join(str(TEMPLATE_DIR), t))

    def test_process_cv_file_importable(self):
        assert callable(process_cv_file)


# ── Tests: cover_letter.build ────────────────────────────────────────────
class TestCoverLetterBuild:
    """Cover-letter build module provides orchestration hooks."""

    def test_process_cover_letter_file_importable(self):
        assert callable(process_cover_letter_file)

    def test_cl_partial_templates_defined(self):
        assert len(CL_PARTIAL_TEMPLATES) == 6
        assert "sender_header.tex" in CL_PARTIAL_TEMPLATES
        assert "body_sections.tex" in CL_PARTIAL_TEMPLATES

    def test_get_cl_layout_default(self):
        assert get_cl_layout({}, False) == "layout.tex"

    def test_get_cl_layout_rtl(self):
        assert get_cl_layout({}, True) == "layout_rtl.tex"

    def test_get_cl_layout_compact(self):
        assert get_cl_layout({"template": "compact"}, False) == "layout_compact.tex"


# ── Tests: backward compatibility ────────────────────────────────────────
class TestBackwardCompatibility:
    """All symbols previously on generate_cv are still accessible."""

    @pytest.mark.parametrize("name", [
        "load_cache", "save_cache", "compute_file_hash",
        "normalize_path_for_cache", "cache_key_for_path", "has_file_changed",
        "compute_composite_hash",
        "gather_input_files", "resolve_output_target",
        "latex_escape", "file_exists", "debug", "types", "cmt", "cblock",
        "find_pic", "get_pic",
        "parse_cv_filename", "load_lang_map", "make_translate_func",
        "make_tr_filter", "make_tr_raw_filter",
        "process_cv_file", "rmtree_reliable",
        "process_cover_letter_file", "CL_PARTIAL_TEMPLATES", "CL_LAYOUTS", "get_cl_layout",
        "COVER_LETTER_PATH",
        "main",
        "BASE_DIR", "CVS_PATH", "TEMPLATE_DIR", "RESULT_DIR",
        "LANG_ENGINE_DIR", "CACHE_FILE", "RTL_LANGUAGES", "SHOW_COMMENTS",
    ])
    def test_symbol_exists_on_generate_cv(self, name):
        assert hasattr(generate_cv, name), f"generate_cv.{name} not found"
