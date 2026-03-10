"""CV-specific document build orchestration.

Handles the CV rendering pipeline: JSON loading, schema validation,
section rendering, layout selection, and PDF compilation.
"""

import json
import os
from pathlib import Path

from jinja2.exceptions import TemplateError

from core import settings
from core.cache import has_file_changed
from core.compile import compile_latex, finalize_pdf
from core.jinja_env import create_jinja_env
from core.language import parse_cv_filename
from core.settings import RTL_LANGUAGES, RESULT_DIR, TEMPLATE_DIR, log_verbose


def get_cv_section_templates():
    """
    Discover CV section templates from the templates directory.

    Returns only .tex files that are not layout templates.
    Excludes directories (e.g. cover_letter/).
    """
    return [
        x for x in os.listdir(TEMPLATE_DIR)
        if os.path.isfile(os.path.join(TEMPLATE_DIR, x))
        and x.endswith(".tex")
        and not x.startswith("layout")
    ]


def process_cv_file(people_path: Path, lang_map, section_templates, cache, output_dir: Path, output_file: Path | None):
    """
    Process a single CV JSON file and generate PDF.

    Args:
        people_path: Path to the JSON file
        lang_map: Translation mapping dictionary
        section_templates: List of template files to render
        cache: Hash cache dictionary for change detection
        output_dir: Directory for generated output PDFs
        output_file: Optional full PDF output path (only for single input)

    Returns:
        tuple: (processed: bool, skipped: bool, current_hash: str or None)
    """
    if people_path.suffix.lower() != ".json":
        log_verbose(f"  ⏭️  Skipping {people_path}: not a JSON file")
        return False, True, None

    orig_output_dir = output_dir
    # Parse filename to get base_name and language
    base_name, lang = parse_cv_filename(people_path.stem + people_path.suffix)
    is_rtl = lang in RTL_LANGUAGES

    JSON_PATH = people_path

    # Check if file exists
    if not JSON_PATH.exists():
        print(f"❌ File not found: {JSON_PATH}")
        return False, False, None
    pdf_name = f"{base_name}_{lang}.pdf"
    output_pdf_path = output_file or (output_dir / pdf_name)

    # Check if file has changed using cache
    changed, current_hash = has_file_changed(JSON_PATH, cache, output_pdf_path)
    if not changed:
        log_verbose(f"  ⏭️  Skipping {people_path}: file unchanged (cached)")
        print(f"⏭️  Skipping {people_path}: no changes detected")
        return False, True, current_hash

    log_verbose(f"  📄 Processing {people_path} (base: {base_name}, lang: {lang}, RTL: {is_rtl})")

    # -------------------------
    # Load data (no eval, no hacks)
    # -------------------------
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # Validate required structure - skip files that don't have the expected schema
    if "basics" not in data:
        print(f"⚠️  Skipping {people_path}: missing 'basics' key (incompatible schema)")
        return False, True, None

    # Create output directory structure: result/<base_name>/<lang>/sections/
    people_output_dir = os.path.join(RESULT_DIR, base_name, lang)
    if not os.path.exists(people_output_dir):
        os.makedirs(people_output_dir)
    OUTPUT_DIR = os.path.join(people_output_dir, "sections")
    RENDERED_OUTPUT = os.path.join(people_output_dir, "rendered.tex")

    # -------------------------
    # Jinja environment
    # -------------------------
    env = create_jinja_env(lang_map, lang, base_name, is_rtl)

    # Vars available to templates (top-level JSON keys become variables)
    data["OPT_NAME"] = base_name
    env_vars = {**data}
    env_vars["LANG_MAP"] = lang_map
    env_vars["LANG"] = lang
    env_vars["BASE_NAME"] = base_name
    env_vars["IS_RTL"] = is_rtl

    # -------------------------
    # Ensure output folder exists
    # -------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # -------------------------
    # Render sections (write files + stash inline strings)
    # -------------------------
    for tmpl_file in section_templates:
        try:
            template = env.get_template(tmpl_file)
            rendered = template.render(env_vars)
        except TemplateError as e:
            raise SystemExit(f"[Jinja error in {tmpl_file}] {e}") from e

        # write section file
        section_name = os.path.splitext(tmpl_file)[0]
        section_output_path = os.path.join(OUTPUT_DIR, f"{section_name}.tex")
        with open(section_output_path, "w", encoding="utf-8") as f:
            f.write(rendered)

        # also store for inline embedding in layout
        env_vars[f"{section_name}_section"] = rendered
        log_verbose(f"    ✓ Rendered section: {section_name}")

    print(f"✅ Sections rendered to '{OUTPUT_DIR}'.")

    # -------------------------
    # Render layout with embedded sections
    # -------------------------
    # Select appropriate layout template based on language direction
    layout_template_name = "layout_rtl.tex" if is_rtl else "layout.tex"
    try:
        layout_template = env.get_template(layout_template_name)
        rendered_layout = layout_template.render(env_vars)
    except TemplateError as e:
        raise SystemExit(f"[Jinja error in {layout_template_name}] {e}") from e

    # Optional tiny cleanup: collapse accidental double blank lines
    rendered_layout = rendered_layout.replace("\n\n\n", "\n\n")

    with open(RENDERED_OUTPUT, "w", encoding="utf-8") as f:
        f.write(rendered_layout)

    rtl_info = " (RTL mode)" if is_rtl else ""
    print(f"✅ Final rendered.tex generated for {base_name} ({lang}){rtl_info}.")
    print(f"➡️  Compile with: xelatex {RENDERED_OUTPUT}")

    # Generate PDF
    compile_latex(RENDERED_OUTPUT, orig_output_dir)

    # Handle output files
    if not finalize_pdf(orig_output_dir, output_pdf_path):
        print(f"❌ PDF generation failed for {people_path}")
        return False, False, None

    return True, False, current_hash
