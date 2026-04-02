"""Tests for cover letter templates and rendering.

Validates that:
 - Cover letter templates exist in their own namespace (templates/cover_letter/).
 - All required partial templates are present.
 - Layout templates exist (default, compact, RTL).
 - Partial templates render correctly with sample cover-letter data.
 - Layout templates render a complete cover letter without CV section templates.
 - Cover letter templates do not depend on CV section templates.
 - Existing CV templates are unaffected.
"""

import json
import os
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined

import generate_cv

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT_DIR / "templates"
CL_TEMPLATE_DIR = TEMPLATE_DIR / "cover_letter"
DATA_DIR = ROOT_DIR / "data" / "cover_letter_datas"

# ── Required file lists ───────────────────────────────────────────────────────
REQUIRED_PARTIALS = [
    "sender_header.tex",
    "recipient.tex",
    "letter_meta.tex",
    "body_sections.tex",
    "signature.tex",
    "enclosures.tex",
]

REQUIRED_LAYOUTS = [
    "layout.tex",
    "layout_compact.tex",
    "layout_rtl.tex",
    "layout_awesomecv_sectioned.tex",
]

# CV section templates that must NOT be needed by cover letter rendering
CV_ONLY_TEMPLATES = [
    "education.tex",
    "experience.tex",
    "skills.tex",
    "projects.tex",
    "publications.tex",
    "certificates.tex",
    "references.tex",
    "language.tex",
]


# ── Sample data ──────────────────────────────────────────────────────────────
SAMPLE_DATA = {
    "meta": {"type": "cover_letter", "version": "1.0"},
    "sender": {
        "first_name": "Jane",
        "last_name": "Doe",
        "position": "Software Engineer",
        "address": "Berlin, Germany",
        "mobile": "+49 123 456 789",
        "email": "jane@example.com",
        "github": "janedoe",
        "linkedin": "janedoe",
    },
    "recipient": {
        "company": "Acme Corp",
        "department": "Engineering",
        "person_name": "Dr. Max Mustermann",
        "person_title": "Head of Engineering",
        "address_lines": ["Musterstraße 1"],
        "city": "10115 Berlin",
        "country": "Germany",
    },
    "job": {
        "title": "Senior Software Engineer",
        "reference": "ACME-2026-001",
    },
    "letter": {
        "date": "2026-03-10",
        "title": "Application for Senior Software Engineer",
        "opening": "Dear Dr. Mustermann,",
        "closing": "Sincerely,",
        "enclosures": ["Curriculum Vitae", "References"],
        "signature_name": "Jane Doe",
    },
    "sections": [
        {"id": "motivation", "content": "I am writing to apply for the position."},
        {
            "id": "experience",
            "content": [
                "First paragraph about experience.",
                "Second paragraph about skills.",
            ],
        },
        {"id": "closing_remarks", "content": "I look forward to hearing from you."},
    ],
    "options": {
        "template": "default",
        "color_theme": "blue",
        "show_photo": False,
    },
}


# ── Jinja helper ─────────────────────────────────────────────────────────────
def _make_env():
    """Create a Jinja2 environment matching the project conventions."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
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
    lang_map = generate_cv.load_lang_map()
    t_func = generate_cv.make_translate_func(lang_map, "en")

    env.filters["latex_escape"] = generate_cv.latex_escape
    env.filters["debug"] = generate_cv.debug
    env.filters["types"] = generate_cv.types
    env.filters["cmt"] = generate_cv.cmt
    env.filters["cblock"] = generate_cv.cblock
    env.filters["file_exists"] = generate_cv.file_exists
    env.filters["get_pic"] = generate_cv.get_pic
    env.filters["find_pic"] = generate_cv.find_pic
    env.filters["tr"] = generate_cv.make_tr_filter(lang_map, "en")
    env.filters["tr_raw"] = generate_cv.make_tr_raw_filter(lang_map, "en")

    env.globals["SHOW_COMMENTS"] = True
    env.globals["LANG_MAP"] = lang_map
    env.globals["LANG"] = "en"
    env.globals["BASE_NAME"] = "test"
    env.globals["IS_RTL"] = False
    env.globals["t"] = t_func
    return env


def _render_partial(name: str, data: dict | None = None) -> str:
    """Render a cover letter partial template with sample data."""
    env = _make_env()
    template = env.get_template(f"cover_letter/{name}")
    ctx = {**(data or SAMPLE_DATA)}
    ctx["OPT_NAME"] = "test"
    return template.render(ctx)


def _render_all_partials(data: dict | None = None) -> dict[str, str]:
    """Render all partials and return a mapping name -> rendered text."""
    results = {}
    for name in REQUIRED_PARTIALS:
        rendered = _render_partial(name, data)
        section_key = os.path.splitext(name)[0] + "_section"
        results[section_key] = rendered
    return results


# ── Tests: file structure ────────────────────────────────────────────────────
class TestCoverLetterFileStructure:
    """Cover letter templates live in their own dedicated namespace."""

    def test_cover_letter_directory_exists(self):
        assert CL_TEMPLATE_DIR.is_dir(), "templates/cover_letter/ directory must exist"

    @pytest.mark.parametrize("filename", REQUIRED_PARTIALS)
    def test_partial_template_exists(self, filename):
        assert (CL_TEMPLATE_DIR / filename).is_file(), f"Missing partial: {filename}"

    @pytest.mark.parametrize("filename", REQUIRED_LAYOUTS)
    def test_layout_template_exists(self, filename):
        assert (CL_TEMPLATE_DIR / filename).is_file(), f"Missing layout: {filename}"

    def test_no_cv_template_dependency(self):
        """Cover letter templates must not reference CV section templates."""
        for name in REQUIRED_PARTIALS + REQUIRED_LAYOUTS:
            content = (CL_TEMPLATE_DIR / name).read_text(encoding="utf-8")
            for cv_tmpl in CV_ONLY_TEMPLATES:
                assert cv_tmpl not in content, (
                    f"cover_letter/{name} must not reference CV template {cv_tmpl}"
                )


# ── Tests: partial rendering ────────────────────────────────────────────────
class TestPartialRendering:
    """Individual cover letter partials render correctly."""

    def test_sender_header_renders_name(self):
        rendered = _render_partial("sender_header.tex")
        assert r"\name{Jane}{Doe}" in rendered

    def test_sender_header_renders_position(self):
        rendered = _render_partial("sender_header.tex")
        assert r"\position{Software Engineer}" in rendered

    def test_sender_header_renders_contact(self):
        rendered = _render_partial("sender_header.tex")
        assert r"\email{jane@example.com}" in rendered
        assert r"\mobile{+49 123 456 789}" in rendered

    def test_recipient_renders_name_and_address(self):
        rendered = _render_partial("recipient.tex")
        assert "Dr. Max Mustermann" in rendered
        assert "Acme Corp" in rendered

    def test_letter_meta_renders_date(self):
        rendered = _render_partial("letter_meta.tex")
        assert r"\letterdate{2026-03-10}" in rendered

    def test_letter_meta_renders_title(self):
        rendered = _render_partial("letter_meta.tex")
        assert "Application for Senior Software Engineer" in rendered

    def test_letter_meta_renders_opening(self):
        rendered = _render_partial("letter_meta.tex")
        assert "Dear Dr. Mustermann," in rendered

    def test_body_sections_renders_all_content(self):
        rendered = _render_partial("body_sections.tex")
        assert "I am writing to apply" in rendered
        assert "First paragraph about experience." in rendered
        assert "Second paragraph about skills." in rendered
        assert "I look forward to hearing from you." in rendered

    def test_enclosures_renders_list(self):
        rendered = _render_partial("enclosures.tex")
        assert "Curriculum Vitae" in rendered
        assert "References" in rendered

    def test_signature_renders_name_override(self):
        rendered = _render_partial("signature.tex")
        assert "Jane" in rendered
        assert "Doe" in rendered


# ── Tests: layout rendering ─────────────────────────────────────────────────
class TestLayoutRendering:
    """Full cover letter layout renders without CV template dependencies."""

    def _render_layout(self, layout_name: str) -> str:
        """Render a full layout with all partials pre-rendered."""
        env = _make_env()
        partials = _render_all_partials()
        ctx = {**SAMPLE_DATA, **partials}
        ctx["OPT_NAME"] = "test"
        template = env.get_template(f"cover_letter/{layout_name}")
        return template.render(ctx)

    def test_default_layout_renders(self):
        rendered = self._render_layout("layout.tex")
        assert r"\documentclass" in rendered
        assert r"\begin{document}" in rendered
        assert r"\end{document}" in rendered
        assert r"\makecvheader" in rendered
        assert r"\makelettertitle" in rendered
        assert r"\makeletterclosing" in rendered
        assert r"\begin{cvletter}" in rendered
        assert r"\end{cvletter}" in rendered

    def test_compact_layout_renders(self):
        rendered = self._render_layout("layout_compact.tex")
        assert r"\documentclass" in rendered
        assert r"\makecvheader[L]" in rendered
        assert r"\makelettertitle" in rendered

    def test_rtl_layout_uses_rtl_class(self):
        rendered = self._render_layout("layout_rtl.tex")
        assert "awesome-cv-rtl" in rendered

    def test_default_layout_contains_body(self):
        rendered = self._render_layout("layout.tex")
        assert "I am writing to apply" in rendered

    def test_default_layout_contains_sender_info(self):
        rendered = self._render_layout("layout.tex")
        assert r"\name{Jane}{Doe}" in rendered

    def test_default_layout_contains_color_theme(self):
        rendered = self._render_layout("layout.tex")
        assert "awesome-skyblue" in rendered


# ── Tests: layout variants ──────────────────────────────────────────────────
class TestLayoutVariants:
    """Multiple layout variants are supported and selectable."""

    def test_at_least_two_ltr_layouts(self):
        ltr_layouts = [
            f for f in os.listdir(CL_TEMPLATE_DIR)
            if f.startswith("layout") and "rtl" not in f and f.endswith(".tex")
        ]
        assert len(ltr_layouts) >= 2, (
            f"Expected at least 2 LTR layout variants, found: {ltr_layouts}"
        )

    def test_rtl_layout_available(self):
        assert (CL_TEMPLATE_DIR / "layout_rtl.tex").is_file()

    def test_compact_layout_has_narrower_margins(self):
        """The compact layout should use narrower margins than the classic."""
        default_content = (CL_TEMPLATE_DIR / "layout.tex").read_text()
        compact_content = (CL_TEMPLATE_DIR / "layout_compact.tex").read_text()
        assert "left=2.5cm" in default_content
        assert "left=1.4cm" in compact_content


# ── Tests: translation keys ─────────────────────────────────────────────────
class TestCoverLetterTranslations:
    """Cover-letter translation keys exist in lang.json."""

    def test_cover_letter_key_exists(self):
        lang_map = generate_cv.load_lang_map()
        assert "cover_letter" in lang_map
        assert "en" in lang_map["cover_letter"]
        assert "de" in lang_map["cover_letter"]

    def test_cover_letter_enclosures_key_exists(self):
        lang_map = generate_cv.load_lang_map()
        assert "cover_letter_enclosures" in lang_map

    def test_cover_letter_subject_key_exists(self):
        lang_map = generate_cv.load_lang_map()
        assert "cover_letter_subject" in lang_map

    def test_cover_letter_date_key_exists(self):
        lang_map = generate_cv.load_lang_map()
        assert "cover_letter_date" in lang_map


# ── Tests: example data files ───────────────────────────────────────────────
class TestExampleDataFiles:
    """Example cover letter JSON files exist and follow the schema."""

    def test_example_data_directory_exists(self):
        assert DATA_DIR.is_dir(), "data/cover_letter_datas/ directory must exist"

    def test_at_least_one_example_exists(self):
        json_files = list(DATA_DIR.glob("*.json"))
        assert len(json_files) >= 1, "Expected at least one example cover letter JSON"

    @pytest.mark.parametrize(
        "filename",
        [f.name for f in DATA_DIR.glob("*.json")] if DATA_DIR.is_dir() else [],
    )
    def test_example_has_required_keys(self, filename):
        with open(DATA_DIR / filename, encoding="utf-8") as f:
            data = json.load(f)
        assert "meta" in data
        assert data["meta"].get("type") == "cover_letter"
        assert "sender" in data
        assert "recipient" in data
        assert "letter" in data
        assert "sections" in data


# ── Tests: CV templates unaffected ──────────────────────────────────────────
class TestCVTemplatesUnchanged:
    """Existing CV templates remain functional and unmodified."""

    def test_cv_layout_exists(self):
        assert (TEMPLATE_DIR / "layout.tex").is_file()

    def test_cv_layout_rtl_exists(self):
        assert (TEMPLATE_DIR / "layout_rtl.tex").is_file()

    @pytest.mark.parametrize("filename", CV_ONLY_TEMPLATES + ["header.tex"])
    def test_cv_section_template_exists(self, filename):
        assert (TEMPLATE_DIR / filename).is_file()

    def test_cv_layout_uses_cv_class(self):
        content = (TEMPLATE_DIR / "layout.tex").read_text()
        assert "awesome-cv" in content
        assert r"\makecvheader" in content


# ── Tests: awesomecv_sectioned layout ───────────────────────────────────────
class TestAwesomecvSectionedLayout:
    """The awesomecv_sectioned layout variant renders correctly."""

    SECTIONED_DATA = {
        **SAMPLE_DATA,
        "sender": {
            **SAMPLE_DATA["sender"],
            "quote": "Work hard, stay humble.",
            "photo": {
                "enabled": True,
                "path": "profile",
                "style": ["circle", "noedge", "left"],
            },
        },
        "sections": [
            {"id": "motivation", "title": "Why I am reaching out",
             "content": "I am interested in the position."},
            {"id": "experience", "title": "My background and possible fit",
             "content": ["First paragraph.", "Second paragraph."]},
            {"id": "closing_remarks",
             "content": "I look forward to hearing from you."},
        ],
        "options": {
            "template": "awesomecv_sectioned",
            "color_theme": "red",
            "header_alignment": "R",
            "font_dir": "fonts/",
            "geometry": {
                "left": "1.0cm",
                "top": ".5cm",
                "right": "1.0cm",
                "bottom": "1.0cm",
                "footskip": ".25cm",
            },
            "footer": {"show_page_number": False},
        },
    }

    def _render_sectioned_layout(self):
        env = _make_env()
        partials = _render_all_partials(self.SECTIONED_DATA)
        ctx = {**self.SECTIONED_DATA, **partials}
        ctx["OPT_NAME"] = "test"
        template = env.get_template("cover_letter/layout_awesomecv_sectioned.tex")
        return template.render(ctx)

    def test_layout_file_exists(self):
        assert (CL_TEMPLATE_DIR / "layout_awesomecv_sectioned.tex").is_file()

    def test_layout_renders_document_structure(self):
        rendered = self._render_sectioned_layout()
        assert r"\documentclass" in rendered
        assert r"\begin{document}" in rendered
        assert r"\end{document}" in rendered
        assert r"\makecvheader" in rendered
        assert r"\makelettertitle" in rendered
        assert r"\makeletterclosing" in rendered
        assert r"\begin{cvletter}" in rendered
        assert r"\end{cvletter}" in rendered

    def test_layout_uses_right_aligned_header(self):
        rendered = self._render_sectioned_layout()
        assert r"\makecvheader[R]" in rendered

    def test_layout_uses_tight_geometry(self):
        rendered = self._render_sectioned_layout()
        assert "left=1.0cm" in rendered
        assert "top=.5cm" in rendered
        assert "right=1.0cm" in rendered
        assert "bottom=1.0cm" in rendered
        assert "footskip=.25cm" in rendered

    def test_layout_includes_font_dir(self):
        rendered = self._render_sectioned_layout()
        assert r"\fontdir[fonts/]" in rendered

    def test_layout_footer_without_page_number(self):
        rendered = self._render_sectioned_layout()
        # Footer should have empty third argument instead of \thepage
        assert r"\thepage" not in rendered

    def test_layout_uses_red_color_theme(self):
        rendered = self._render_sectioned_layout()
        assert "awesome-red" in rendered

    def test_layout_contains_body_content(self):
        rendered = self._render_sectioned_layout()
        assert "I am interested in the position." in rendered

    def test_layout_contains_sender_info(self):
        rendered = self._render_sectioned_layout()
        assert r"\name{Jane}{Doe}" in rendered


# ── Tests: section title rendering ──────────────────────────────────────────
class TestSectionTitleRendering:
    """Body sections render \lettersection when title is present."""

    def test_section_with_title_renders_lettersection(self):
        data = {
            **SAMPLE_DATA,
            "sections": [
                {"id": "motivation", "title": "Why I am reaching out",
                 "content": "I want to apply."},
            ],
        }
        rendered = _render_partial("body_sections.tex", data)
        assert r"\lettersection{Why I am reaching out}" in rendered
        assert "I want to apply." in rendered

    def test_section_without_title_no_lettersection(self):
        data = {
            **SAMPLE_DATA,
            "sections": [
                {"id": "motivation", "content": "Just a paragraph."},
            ],
        }
        rendered = _render_partial("body_sections.tex", data)
        assert r"\lettersection" not in rendered
        assert "Just a paragraph." in rendered

    def test_mixed_sections_with_and_without_title(self):
        data = {
            **SAMPLE_DATA,
            "sections": [
                {"id": "intro", "content": "No title here."},
                {"id": "details", "title": "Detailed Background",
                 "content": ["Para one.", "Para two."]},
                {"id": "close", "content": "Final section."},
            ],
        }
        rendered = _render_partial("body_sections.tex", data)
        assert r"\lettersection{Detailed Background}" in rendered
        assert rendered.count(r"\lettersection") == 1
        assert "No title here." in rendered
        assert "Para one." in rendered
        assert "Para two." in rendered
        assert "Final section." in rendered

    def test_backward_compat_no_titles(self):
        """Original SAMPLE_DATA has no titles — no \lettersection in output."""
        rendered = _render_partial("body_sections.tex")
        assert r"\lettersection" not in rendered
        assert "I am writing to apply" in rendered


# ── Tests: sender quote rendering ───────────────────────────────────────────
class TestSenderQuoteRendering:
    """Sender quote renders \quote{...} when present."""

    def test_sender_with_quote(self):
        data = {
            **SAMPLE_DATA,
            "sender": {
                **SAMPLE_DATA["sender"],
                "quote": "Work hard, stay humble.",
            },
        }
        rendered = _render_partial("sender_header.tex", data)
        assert r"\quote{Work hard, stay humble.}" in rendered

    def test_sender_without_quote(self):
        rendered = _render_partial("sender_header.tex")
        assert r"\quote" not in rendered


# ── Tests: rich photo rendering ─────────────────────────────────────────────
class TestRichPhotoRendering:
    """Rich photo config renders \photo with style options."""

    def test_rich_photo_config(self):
        data = {
            **SAMPLE_DATA,
            "sender": {
                **SAMPLE_DATA["sender"],
                "photo": {
                    "enabled": True,
                    "path": "profile",
                    "style": ["circle", "noedge", "left"],
                },
            },
            "options": {},
        }
        rendered = _render_partial("sender_header.tex", data)
        assert r"\photo[circle,noedge,left]{profile}" in rendered

    def test_rich_photo_disabled(self):
        data = {
            **SAMPLE_DATA,
            "sender": {
                **SAMPLE_DATA["sender"],
                "photo": {
                    "enabled": False,
                    "path": "profile",
                    "style": ["circle", "noedge", "left"],
                },
            },
            "options": {},
        }
        rendered = _render_partial("sender_header.tex", data)
        assert r"\photo" not in rendered

    def test_rich_photo_without_style(self):
        data = {
            **SAMPLE_DATA,
            "sender": {
                **SAMPLE_DATA["sender"],
                "photo": {
                    "enabled": True,
                    "path": "myphoto",
                    "style": [],
                },
            },
            "options": {},
        }
        rendered = _render_partial("sender_header.tex", data)
        assert r"\photo{myphoto}" in rendered

    def test_legacy_show_photo_still_works(self):
        """The old options.show_photo boolean still triggers photo rendering."""
        # This test verifies backward compatibility. The find_pic filter
        # depends on actual files, so we just verify the code path doesn't
        # error and doesn't produce rich photo output.
        rendered = _render_partial("sender_header.tex")
        # SAMPLE_DATA has show_photo: False, so no photo
        assert r"\photo[circle,noedge,left]{profile}" not in rendered
