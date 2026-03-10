"""Cover-letter-specific document build orchestration.

Handles the cover-letter rendering pipeline: JSON loading, schema validation,
partial rendering, layout selection, and PDF compilation.

This module provides the orchestration hooks for cover-letter generation,
parallel to cv/build.py for CV generation. Both reuse the shared core/
utilities for caching, Jinja2 environment setup, LaTeX compilation, etc.
"""

import json
import os
from pathlib import Path

from jinja2.exceptions import TemplateError

from core import settings
from core.cache import (
    cache_key_for_path,
    compute_composite_hash,
)
from core.compile import compile_latex, finalize_pdf
from core.jinja_env import create_jinja_env
from core.language import parse_cv_filename
from core.settings import RTL_LANGUAGES, RESULT_DIR, TEMPLATE_DIR, log_verbose


# Cover letter partial templates (rendered in order)
CL_PARTIAL_TEMPLATES = [
    "sender_header.tex",
    "recipient.tex",
    "letter_meta.tex",
    "body_sections.tex",
    "signature.tex",
    "enclosures.tex",
]

# Cover letter layout templates
CL_LAYOUTS = {
    "default": "layout.tex",
    "compact": "layout_compact.tex",
    "rtl": "layout_rtl.tex",
}


def get_cl_layout(options, is_rtl):
    """
    Select the appropriate cover-letter layout template.

    Args:
        options: Options dict from the cover letter JSON (may contain 'template' key)
        is_rtl: Whether the language is right-to-left

    Returns:
        Template filename within cover_letter/ namespace
    """
    if is_rtl:
        return CL_LAYOUTS["rtl"]
    template_choice = (options or {}).get("template", "default")
    return CL_LAYOUTS.get(template_choice, CL_LAYOUTS["default"])


def process_cover_letter_file(
    input_path: Path,
    lang_map,
    cache,
    output_dir: Path,
    output_file: Path | None,
):
    """
    Process a single cover-letter JSON file and generate PDF.

    Args:
        input_path: Path to the cover-letter JSON file
        lang_map: Translation mapping dictionary
        cache: Hash cache dictionary for change detection
        output_dir: Directory for generated output PDFs
        output_file: Optional full PDF output path (only for single input)

    Returns:
        tuple: (processed: bool, skipped: bool, current_hash: str or None)
    """
    if input_path.suffix.lower() != ".json":
        log_verbose(f"  ⏭️  Skipping {input_path}: not a JSON file")
        return False, True, None

    # Parse filename to get base_name and language
    base_name, lang = parse_cv_filename(input_path.stem + input_path.suffix)
    is_rtl = lang in RTL_LANGUAGES

    # Check if file exists
    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        return False, False, None

    pdf_name = f"{base_name}_{lang}_cover_letter.pdf"
    output_pdf_path = output_file or (output_dir / pdf_name)

    # ── Cache-aware skip: composite hash of JSON + all template files ──
    cl_template_dir = Path(TEMPLATE_DIR) / "cover_letter"
    template_files = sorted(cl_template_dir.glob("*.tex"))
    all_inputs = [input_path] + template_files

    current_hash = compute_composite_hash(all_inputs)
    cache_key = cache_key_for_path(input_path, prefix="cl:")

    if current_hash is not None:
        cached_hash = cache.get(cache_key)
        if cached_hash == current_hash and output_pdf_path.exists():
            log_verbose(f"  ⏭️  Skipping {input_path}: file unchanged (cached)")
            print(f"⏭️  Skipping {input_path}: no changes detected")
            return False, True, current_hash

    log_verbose(f"  📄 Processing cover letter {input_path} (base: {base_name}, lang: {lang}, RTL: {is_rtl})")

    # -------------------------
    # Load data
    # -------------------------
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    # Validate cover-letter schema
    if data.get("meta", {}).get("type") != "cover_letter":
        print(f"⚠️  Skipping {input_path}: not a cover letter (meta.type != 'cover_letter')")
        return False, True, None

    for required_key in ("sender", "recipient", "letter", "sections"):
        if required_key not in data:
            print(f"⚠️  Skipping {input_path}: missing required key '{required_key}'")
            return False, True, None

    # Create output directory structure: result/<base_name>/<lang>/cover_letter/sections/
    cl_output_dir = os.path.join(RESULT_DIR, base_name, lang, "cover_letter")
    if not os.path.exists(cl_output_dir):
        os.makedirs(cl_output_dir)
    sections_dir = os.path.join(cl_output_dir, "sections")
    rendered_output = os.path.join(cl_output_dir, "rendered.tex")

    # -------------------------
    # Jinja environment
    # -------------------------
    env = create_jinja_env(lang_map, lang, base_name, is_rtl)

    # Context variables
    data["OPT_NAME"] = base_name
    env_vars = {**data}
    env_vars["LANG_MAP"] = lang_map
    env_vars["LANG"] = lang
    env_vars["BASE_NAME"] = base_name
    env_vars["IS_RTL"] = is_rtl

    # -------------------------
    # Ensure output folder exists
    # -------------------------
    os.makedirs(sections_dir, exist_ok=True)

    # -------------------------
    # Render partial templates
    # -------------------------
    for tmpl_file in CL_PARTIAL_TEMPLATES:
        tmpl_path = f"cover_letter/{tmpl_file}"
        try:
            template = env.get_template(tmpl_path)
            rendered = template.render(env_vars)
        except TemplateError as e:
            raise SystemExit(f"[Jinja error in {tmpl_path}] {e}") from e

        # Write section file
        section_name = os.path.splitext(tmpl_file)[0]
        section_output_path = os.path.join(sections_dir, f"{section_name}.tex")
        with open(section_output_path, "w", encoding="utf-8") as f:
            f.write(rendered)

        # Store for inline embedding in layout
        env_vars[f"{section_name}_section"] = rendered
        log_verbose(f"    ✓ Rendered partial: {section_name}")

    print(f"✅ Cover letter sections rendered to '{sections_dir}'.")

    # -------------------------
    # Render layout with embedded sections
    # -------------------------
    layout_name = get_cl_layout(data.get("options"), is_rtl)
    layout_path = f"cover_letter/{layout_name}"
    try:
        layout_template = env.get_template(layout_path)
        rendered_layout = layout_template.render(env_vars)
    except TemplateError as e:
        raise SystemExit(f"[Jinja error in {layout_path}] {e}") from e

    # Collapse accidental double blank lines
    rendered_layout = rendered_layout.replace("\n\n\n", "\n\n")

    with open(rendered_output, "w", encoding="utf-8") as f:
        f.write(rendered_layout)

    rtl_info = " (RTL mode)" if is_rtl else ""
    print(f"✅ Cover letter rendered.tex generated for {base_name} ({lang}){rtl_info}.")
    print(f"➡️  Compile with: xelatex {rendered_output}")

    # Generate PDF
    compile_latex(rendered_output, output_dir)

    # Handle output files
    if not finalize_pdf(output_dir, output_pdf_path):
        print(f"❌ PDF generation failed for {input_path}")
        return False, False, None

    return True, False, current_hash
