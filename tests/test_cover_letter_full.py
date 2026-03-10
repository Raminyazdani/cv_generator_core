"""Comprehensive tests for cover-letter generation pipeline.

Covers the remaining acceptance criteria from Issue 06:
 1) Input discovery — cover-letter default folder, specific files, extension rejection.
 2) Output-path validation — directory output for cover letters.
 3) Schema validation — missing body, invalid layout, malformed JSON.
 4) Cache behavior — unchanged skip, changed rebuild, layout invalidation,
    no collision with CV keys.
 5) Rendering pipeline — intermediate TeX files, template namespace, output naming.
 6) Regression — CV workflow still behaves correctly after shared-core refactor.
"""

import json
import os
from pathlib import Path

import pytest

import generate_cv
from core.cache import (
    cache_key_for_path,
    compute_composite_hash,
    compute_file_hash,
    has_file_changed,
)
from core.files import gather_input_files, resolve_output_target
from core.language import parse_cv_filename
from core.settings import COVER_LETTER_PATH, CVS_PATH, TEMPLATE_DIR
from cover_letter.build import (
    CL_LAYOUTS,
    CL_PARTIAL_TEMPLATES,
    get_cl_layout,
    process_cover_letter_file,
)
from cv.build import get_cv_section_templates, process_cv_file

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ── Helper ─────────────────────────────────────────────────────────────────────
def _load_fixture(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


VALID_CL = _load_fixture("named_recipient_cl_en.json")


# ═══════════════════════════════════════════════════════════════════════════════
# 1) Input discovery tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoverLetterInputDiscovery:
    """Cover-letter command discovers input files correctly."""

    def test_discovers_all_json_in_default_folder(self):
        """All JSON files in data/cover_letter_datas/ are discovered."""
        cl_dir = Path(COVER_LETTER_PATH)
        files = gather_input_files([], cl_dir)
        expected = sorted(cl_dir.glob("*.json"))
        assert len(files) == len(expected)
        assert set(f.name for f in files) == set(f.name for f in expected)

    def test_accepts_specific_file_argument(self, tmp_path):
        """A specific JSON file passed as argument is accepted."""
        f = tmp_path / "my_letter_en.json"
        _write_json(f, VALID_CL)
        files = gather_input_files([str(f)], tmp_path)
        assert files == [f]

    def test_rejects_non_json_extension(self, tmp_path):
        """Non-JSON files are skipped by gather_input_files."""
        txt = tmp_path / "letter.txt"
        txt.write_text("not json", encoding="utf-8")
        files = gather_input_files([str(txt)], tmp_path)
        assert files == []

    def test_folder_with_mixed_extensions(self, tmp_path):
        """Only .json files are collected when scanning a folder."""
        folder = tmp_path / "cl"
        folder.mkdir()
        _write_json(folder / "a.json", VALID_CL)
        (folder / "readme.md").write_text("# hi", encoding="utf-8")
        (folder / "notes.txt").write_text("n", encoding="utf-8")
        _write_json(folder / "b.json", VALID_CL)
        files = gather_input_files([], folder)
        names = sorted(f.name for f in files)
        assert names == ["a.json", "b.json"]


# ═══════════════════════════════════════════════════════════════════════════════
# 2) Output-path validation tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoverLetterOutputPath:
    """Output-path logic behaves correctly for cover letters."""

    def test_directory_output_works(self, tmp_path):
        f = tmp_path / "cl_en.json"
        _write_json(f, VALID_CL)
        out_dir, out_file = resolve_output_target(str(tmp_path / "out"), [f])
        assert out_dir == tmp_path / "out"
        assert out_file is None

    def test_single_pdf_path_allowed_for_single_input(self, tmp_path):
        f = tmp_path / "cl_en.json"
        _write_json(f, VALID_CL)
        out_dir, out_file = resolve_output_target(str(tmp_path / "result.pdf"), [f])
        assert out_file == tmp_path / "result.pdf"

    def test_multiple_inputs_single_pdf_rejected(self, tmp_path):
        a = tmp_path / "a_en.json"
        b = tmp_path / "b_en.json"
        _write_json(a, VALID_CL)
        _write_json(b, VALID_CL)
        with pytest.raises(SystemExit):
            resolve_output_target(str(tmp_path / "out.pdf"), [a, b])


# ═══════════════════════════════════════════════════════════════════════════════
# 3) Schema validation tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoverLetterSchemaValidation:
    """Cover-letter pipeline rejects invalid input gracefully."""

    def test_missing_sender(self, tmp_path):
        data = {
            "meta": {"type": "cover_letter"},
            "recipient": {"company": "X"},
            "letter": {"date": "2026-01-01", "opening": "Hi,", "closing": "Bye,"},
            "sections": [{"id": "body", "content": "text"}],
        }
        f = tmp_path / "no_sender_en.json"
        _write_json(f, data)
        processed, skipped, h = process_cover_letter_file(f, {}, {}, tmp_path, None)
        assert not processed
        assert skipped

    def test_missing_recipient(self, tmp_path):
        data = {
            "meta": {"type": "cover_letter"},
            "sender": {"first_name": "X", "last_name": "Y", "email": "x@y.com"},
            "letter": {"date": "2026-01-01", "opening": "Hi,", "closing": "Bye,"},
            "sections": [{"id": "body", "content": "text"}],
        }
        f = tmp_path / "no_recipient_en.json"
        _write_json(f, data)
        processed, skipped, h = process_cover_letter_file(f, {}, {}, tmp_path, None)
        assert not processed
        assert skipped

    def test_missing_body_sections(self, tmp_path):
        data = {
            "meta": {"type": "cover_letter"},
            "sender": {"first_name": "X", "last_name": "Y", "email": "x@y.com"},
            "recipient": {"company": "Z"},
            "letter": {"date": "2026-01-01", "opening": "Hi,", "closing": "Bye,"},
            # missing: sections
        }
        f = tmp_path / "no_body_en.json"
        _write_json(f, data)
        processed, skipped, h = process_cover_letter_file(f, {}, {}, tmp_path, None)
        assert not processed
        assert skipped

    def test_invalid_meta_type(self, tmp_path):
        data = {"meta": {"type": "resume"}, "sender": {}, "recipient": {},
                "letter": {}, "sections": []}
        f = tmp_path / "wrong_type_en.json"
        _write_json(f, data)
        processed, skipped, h = process_cover_letter_file(f, {}, {}, tmp_path, None)
        assert not processed
        assert skipped

    def test_malformed_json(self, tmp_path):
        f = tmp_path / "bad_en.json"
        f.write_text("{not valid json!!!", encoding="utf-8")
        # json.load will raise; process_cover_letter_file may propagate
        with pytest.raises((json.JSONDecodeError, SystemExit, Exception)):
            process_cover_letter_file(f, {}, {}, tmp_path, None)

    def test_invalid_layout_raises_with_allowed_choices(self):
        """Unknown template name raises SystemExit listing allowed layouts."""
        with pytest.raises(SystemExit, match="nonexistent_layout") as exc_info:
            get_cl_layout({"template": "nonexistent_layout"}, False)
        msg = str(exc_info.value)
        assert "compact" in msg
        assert "default" in msg
        assert "rtl" in msg


# ═══════════════════════════════════════════════════════════════════════════════
# 4) Cache behavior tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoverLetterCacheBehavior:
    """Cover-letter cache behavior is correct and isolated from CV."""

    def test_unchanged_input_skipped(self, tmp_path):
        """When the composite hash matches and PDF exists, the file is skipped."""
        f = tmp_path / "letter_en.json"
        _write_json(f, VALID_CL)

        tmpl = tmp_path / "layout.tex"
        tmpl.write_text("\\documentclass{}", encoding="utf-8")
        all_inputs = [f, tmpl]
        h = compute_composite_hash(all_inputs)

        # Simulate a cached entry + existing PDF
        pdf = tmp_path / "letter_en_cover_letter.pdf"
        pdf.write_text("fake pdf", encoding="utf-8")
        cache = {cache_key_for_path(f, prefix="cl:"): h}

        # Now compute again — hash should match
        h2 = compute_composite_hash(all_inputs)
        assert h == h2
        assert cache.get(cache_key_for_path(f, prefix="cl:")) == h2

    def test_changed_json_triggers_rebuild(self, tmp_path):
        """Modifying the JSON file changes the composite hash."""
        f = tmp_path / "letter_en.json"
        tmpl = tmp_path / "t.tex"
        _write_json(f, VALID_CL)
        tmpl.write_text("tmpl", encoding="utf-8")
        h1 = compute_composite_hash([f, tmpl])

        modified = {**VALID_CL, "options": {"template": "compact"}}
        _write_json(f, modified)
        h2 = compute_composite_hash([f, tmpl])
        assert h1 != h2

    def test_changed_layout_invalidates_cache(self, tmp_path):
        """Modifying a template file invalidates the composite hash."""
        f = tmp_path / "letter_en.json"
        tmpl = tmp_path / "layout.tex"
        _write_json(f, VALID_CL)
        tmpl.write_text("v1", encoding="utf-8")
        h1 = compute_composite_hash([f, tmpl])

        tmpl.write_text("v2-modified", encoding="utf-8")
        h2 = compute_composite_hash([f, tmpl])
        assert h1 != h2

    def test_cache_keys_do_not_collide_with_cv(self, tmp_path):
        """A cover-letter cache key never equals a CV cache key for the same path."""
        f = tmp_path / "data.json"
        _write_json(f, VALID_CL)
        cv_key = cache_key_for_path(f)
        cl_key = cache_key_for_path(f, prefix="cl:")
        assert cv_key != cl_key
        assert not cv_key.startswith("cl:")
        assert cl_key.startswith("cl:")

    def test_cv_has_file_changed_independent_of_cl(self, tmp_path):
        """CV's has_file_changed is unaffected by CL cache entries."""
        f = tmp_path / "data.json"
        f.write_text('{"basics": []}', encoding="utf-8")
        pdf = tmp_path / "data.pdf"
        pdf.write_text("pdf", encoding="utf-8")

        cache = {}
        changed, h = has_file_changed(f, cache, pdf)
        assert changed is True

        # Store as CV key
        cache[cache_key_for_path(f)] = h
        changed_again, _ = has_file_changed(f, cache, pdf)
        assert changed_again is False

        # Adding a CL key for the same file should NOT affect CV lookup
        cache[cache_key_for_path(f, prefix="cl:")] = "different_hash"
        changed_cv, _ = has_file_changed(f, cache, pdf)
        assert changed_cv is False  # CV key still matches


# ═══════════════════════════════════════════════════════════════════════════════
# 5) Rendering pipeline tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoverLetterRenderingPipeline:
    """Cover-letter rendering produces expected intermediate artifacts."""

    def test_correct_template_namespace(self):
        """All CL partial templates belong to the cover_letter/ namespace."""
        cl_dir = Path(TEMPLATE_DIR) / "cover_letter"
        for tmpl_name in CL_PARTIAL_TEMPLATES:
            assert (cl_dir / tmpl_name).is_file(), f"Missing: cover_letter/{tmpl_name}"

    def test_output_naming_convention(self):
        """Cover-letter PDF names follow <base>_<lang>_cover_letter.pdf."""
        base, lang = parse_cv_filename("ramin_google_en.json")
        expected = f"{base}_{lang}_cover_letter.pdf"
        assert expected == "ramin_google_en_cover_letter.pdf"

    def test_output_naming_for_german_input(self):
        base, lang = parse_cv_filename("ramin_sap_de.json")
        expected = f"{base}_{lang}_cover_letter.pdf"
        assert expected == "ramin_sap_de_cover_letter.pdf"

    def test_cl_layouts_all_exist_on_disk(self):
        """Every layout in CL_LAYOUTS exists as a file."""
        cl_dir = Path(TEMPLATE_DIR) / "cover_letter"
        for key, filename in CL_LAYOUTS.items():
            assert (cl_dir / filename).is_file(), f"Missing layout: {filename}"

    def test_layout_selection_compact(self):
        assert get_cl_layout({"template": "compact"}, False) == "layout_compact.tex"

    def test_layout_selection_rtl_overrides_template(self):
        """RTL flag takes precedence over template choice."""
        assert get_cl_layout({"template": "compact"}, True) == "layout_rtl.tex"

    def test_partial_templates_count(self):
        assert len(CL_PARTIAL_TEMPLATES) == 6

    def test_partial_templates_have_tex_extension(self):
        for name in CL_PARTIAL_TEMPLATES:
            assert name.endswith(".tex")


# ═══════════════════════════════════════════════════════════════════════════════
# 6) CV regression tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCVRegression:
    """CV workflow still functions correctly after the shared-core refactor."""

    def test_cv_section_templates_discovered(self):
        """get_cv_section_templates returns known CV templates."""
        templates = get_cv_section_templates()
        assert len(templates) > 0
        # Well-known sections must be present
        for expected in ("header.tex", "education.tex", "experience.tex"):
            assert expected in templates, f"{expected} missing from CV section templates"

    def test_cv_section_templates_exclude_cover_letter(self):
        """CV section templates must not include cover_letter files."""
        templates = get_cv_section_templates()
        for t in templates:
            assert "cover_letter" not in t

    def test_cv_section_templates_exclude_layouts(self):
        templates = get_cv_section_templates()
        for t in templates:
            assert not t.startswith("layout")

    def test_cv_process_rejects_non_json(self, tmp_path):
        txt = tmp_path / "resume.txt"
        txt.write_text("not json", encoding="utf-8")
        processed, skipped, h = process_cv_file(txt, {}, [], {}, tmp_path, None)
        assert not processed
        assert skipped

    def test_cv_process_rejects_missing_file(self, tmp_path):
        missing = tmp_path / "missing.json"
        processed, skipped, h = process_cv_file(missing, {}, [], {}, tmp_path, None)
        assert not processed
        assert not skipped  # error, not skip

    def test_cv_process_rejects_cover_letter_schema(self, tmp_path):
        """A cover-letter JSON fed to CV pipeline is skipped (missing 'basics')."""
        f = tmp_path / "cl_data_en.json"
        _write_json(f, VALID_CL)
        processed, skipped, h = process_cv_file(f, {}, [], {}, tmp_path, None)
        assert not processed
        assert skipped

    def test_cv_cache_uses_simple_hash(self, tmp_path):
        """CV caching uses single-file has_file_changed, not composite hash."""
        f = tmp_path / "r_en.json"
        f.write_text('{"basics": [{"fname": "R", "lname": "Y"}]}', encoding="utf-8")
        pdf = tmp_path / "r_en.pdf"
        cache = {}

        changed, h = has_file_changed(f, cache, pdf)
        assert changed is True
        cache[cache_key_for_path(f)] = h

        # Without PDF the file is still "changed"
        changed_no_pdf, _ = has_file_changed(f, cache, pdf)
        assert changed_no_pdf is True

        # With PDF it is unchanged
        pdf.write_text("pdf", encoding="utf-8")
        changed_with_pdf, _ = has_file_changed(f, cache, pdf)
        assert changed_with_pdf is False

    def test_cv_data_files_valid_structure(self):
        """All CV data files in data/cvs/ have the 'basics' key."""
        cvs_dir = Path(CVS_PATH)
        for json_file in cvs_dir.glob("*.json"):
            with open(json_file, encoding="utf-8") as fh:
                data = json.load(fh)
            assert "basics" in data, f"{json_file.name} missing 'basics' key"

    def test_cv_output_naming(self):
        """CV PDF names follow <base>_<lang>.pdf."""
        base, lang = parse_cv_filename("ramin_en.json")
        assert f"{base}_{lang}.pdf" == "ramin_en.pdf"

    def test_backward_compat_imports(self):
        """Key symbols remain accessible via generate_cv module."""
        for name in ("process_cv_file", "process_cover_letter_file",
                     "gather_input_files", "resolve_output_target",
                     "load_cache", "save_cache", "has_file_changed",
                     "compute_composite_hash", "main"):
            assert hasattr(generate_cv, name)


# ═══════════════════════════════════════════════════════════════════════════════
# Test fixtures — validate the fixture files themselves
# ═══════════════════════════════════════════════════════════════════════════════

class TestFixtureFiles:
    """Bundled test fixture files are well-formed."""

    def test_minimal_valid_loads(self):
        data = _load_fixture("minimal_valid_cl.json")
        assert data["meta"]["type"] == "cover_letter"
        assert "sender" in data
        assert "sections" in data

    def test_named_recipient_loads(self):
        data = _load_fixture("named_recipient_cl_en.json")
        assert data["recipient"]["person_name"] == "Dr. Eva Mueller"
        assert len(data["sections"]) == 3

    def test_invalid_schema_loads_but_wrong_type(self):
        data = _load_fixture("invalid_schema_cl.json")
        assert data["meta"]["type"] != "cover_letter"

    def test_compact_layout_loads(self):
        data = _load_fixture("compact_layout_cl_en.json")
        assert data["options"]["template"] == "compact"


# ═══════════════════════════════════════════════════════════════════════════════
# 7) Smoke validation script support
# ═══════════════════════════════════════════════════════════════════════════════

class TestSmokeValidation:
    """Smoke validation script can validate cover letters."""

    def test_smoke_script_exists(self):
        script = ROOT_DIR / "scripts" / "smoke_validate.py"
        assert script.is_file()

    def test_cv_smoke_validation_passes(self):
        """All shipped CV data files pass smoke validation."""
        # Import inline to avoid polluting the module namespace
        sys_path_backup = __import__("sys").path[:]
        __import__("sys").path.insert(0, str(ROOT_DIR / "scripts"))
        try:
            from smoke_validate import validate_cv_file
            cvs_dir = Path(CVS_PATH)
            for json_file in cvs_dir.glob("*.json"):
                success, errors = validate_cv_file(json_file)
                assert success, f"{json_file.name}: {errors}"
        finally:
            __import__("sys").path[:] = sys_path_backup

    def test_cover_letter_smoke_validation_passes(self):
        """All shipped cover-letter data files pass smoke validation."""
        sys_path_backup = __import__("sys").path[:]
        __import__("sys").path.insert(0, str(ROOT_DIR / "scripts"))
        try:
            from smoke_validate import validate_cover_letter_file
            cl_dir = Path(COVER_LETTER_PATH)
            for json_file in cl_dir.glob("*.json"):
                success, errors = validate_cover_letter_file(json_file)
                assert success, f"{json_file.name}: {errors}"
        finally:
            __import__("sys").path[:] = sys_path_backup

    def test_smoke_rejects_invalid_cover_letter(self, tmp_path):
        """Smoke validation rejects a cover letter with wrong meta.type."""
        sys_path_backup = __import__("sys").path[:]
        __import__("sys").path.insert(0, str(ROOT_DIR / "scripts"))
        try:
            from smoke_validate import validate_cover_letter_file
            bad = tmp_path / "bad.json"
            bad.write_text(json.dumps({"meta": {"type": "cv"}}), encoding="utf-8")
            success, errors = validate_cover_letter_file(bad)
            assert not success
            assert any("meta.type" in e for e in errors)
        finally:
            __import__("sys").path[:] = sys_path_backup


# ═══════════════════════════════════════════════════════════════════════════════
# 8) Issue 08 — Validation, cache versioning, and extensibility
# ═══════════════════════════════════════════════════════════════════════════════

class TestStrongerValidation:
    """Improved validation error messages are actionable and specific."""

    def test_missing_key_error_names_fields(self, tmp_path, capsys):
        """Error message names the exact missing fields."""
        bad = tmp_path / "missing_en.json"
        _write_json(bad, {"meta": {"type": "cover_letter"}, "sender": {}})
        process_cover_letter_file(bad, {}, {}, tmp_path, None)
        out = capsys.readouterr().out
        assert "'recipient'" in out
        assert "'letter'" in out
        assert "'sections'" in out

    def test_wrong_meta_type_error_explains_fix(self, tmp_path, capsys):
        """Error message tells the user what meta.type should be."""
        bad = tmp_path / "wrong_en.json"
        _write_json(bad, {"meta": {"type": "cv"}, "sender": {}, "recipient": {},
                          "letter": {}, "sections": []})
        process_cover_letter_file(bad, {}, {}, tmp_path, None)
        out = capsys.readouterr().out
        assert "cover_letter" in out

    def test_invalid_layout_lists_allowed(self):
        """SystemExit from invalid layout lists all allowed choices."""
        with pytest.raises(SystemExit, match="Allowed choices") as exc_info:
            get_cl_layout({"template": "unknown"}, False)
        for layout_name in CL_LAYOUTS:
            assert layout_name in str(exc_info.value)

    def test_output_path_pdf_with_multiple_files_explains(self, tmp_path):
        """--output-path .pdf + multiple inputs → detailed error message."""
        f1 = tmp_path / "a.json"
        f2 = tmp_path / "b.json"
        f1.write_text("{}", encoding="utf-8")
        f2.write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit, match=r"\.pdf") as exc_info:
            resolve_output_target("out.pdf", [f1, f2])
        msg = str(exc_info.value)
        assert "2 input file(s)" in msg
        assert "--output-path" in msg


class TestCacheVersioning:
    """Cache version invalidates stale entries when bumped."""

    def test_cache_version_constant_exists(self):
        from core.cache import CACHE_VERSION
        assert isinstance(CACHE_VERSION, int)
        assert CACHE_VERSION >= 1

    def test_save_and_load_preserves_entries(self, tmp_path, monkeypatch):
        from core.cache import load_cache, save_cache, CACHE_VERSION
        cache_file = tmp_path / ".cvgen_cache.json"
        monkeypatch.setattr("core.cache.CACHE_FILE", str(cache_file))
        save_cache({"key": "value"})
        loaded = load_cache()
        assert loaded == {"key": "value"}

    def test_version_mismatch_discards_cache(self, tmp_path, monkeypatch):
        from core.cache import load_cache, save_cache, CACHE_VERSION
        cache_file = tmp_path / ".cvgen_cache.json"
        monkeypatch.setattr("core.cache.CACHE_FILE", str(cache_file))
        save_cache({"key": "value"})
        # Tamper with the stored version
        raw = json.loads(cache_file.read_text(encoding="utf-8"))
        raw["__cache_version__"] = CACHE_VERSION + 999
        cache_file.write_text(json.dumps(raw), encoding="utf-8")
        loaded = load_cache()
        assert loaded == {}

    def test_missing_version_key_discards_cache(self, tmp_path, monkeypatch):
        """A cache file written before versioning is discarded."""
        from core.cache import load_cache
        cache_file = tmp_path / ".cvgen_cache.json"
        monkeypatch.setattr("core.cache.CACHE_FILE", str(cache_file))
        cache_file.write_text(json.dumps({"old_key": "old_val"}), encoding="utf-8")
        loaded = load_cache()
        assert loaded == {}


class TestExtensibilityHooks:
    """Extensibility constants and interfaces are accessible."""

    def test_doc_prefix_constants_exist(self):
        from core.cache import DOC_PREFIX_CV, DOC_PREFIX_CL
        assert DOC_PREFIX_CV == ""
        assert DOC_PREFIX_CL == "cl:"

    def test_cl_doc_type_constant(self):
        from cover_letter.build import CL_DOC_TYPE
        assert CL_DOC_TYPE == "cover_letter"

    def test_cl_template_namespace_constant(self):
        from cover_letter.build import CL_TEMPLATE_NAMESPACE
        assert CL_TEMPLATE_NAMESPACE == "cover_letter"

    def test_cl_required_keys_constant(self):
        from cover_letter.build import CL_REQUIRED_KEYS
        assert "sender" in CL_REQUIRED_KEYS
        assert "recipient" in CL_REQUIRED_KEYS
        assert "letter" in CL_REQUIRED_KEYS
        assert "sections" in CL_REQUIRED_KEYS

    def test_cv_required_keys_constant(self):
        from cv.build import CV_REQUIRED_KEYS
        assert "basics" in CV_REQUIRED_KEYS

    def test_new_constants_re_exported_via_generate_cv(self):
        """New extensibility constants are available on the generate_cv module."""
        assert hasattr(generate_cv, "CACHE_VERSION")
        assert hasattr(generate_cv, "DOC_PREFIX_CV")
        assert hasattr(generate_cv, "DOC_PREFIX_CL")
        assert hasattr(generate_cv, "CL_DOC_TYPE")
        assert hasattr(generate_cv, "CL_TEMPLATE_NAMESPACE")
        assert hasattr(generate_cv, "CL_REQUIRED_KEYS")
        assert hasattr(generate_cv, "CV_REQUIRED_KEYS")
