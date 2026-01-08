#!/usr/bin/env python3
"""
CV Generation Test Script

This script tests the CV generation pipeline without requiring LaTeX.
It validates that templates render correctly and produce expected output.

Usage:
    python scripts/test_cv_generation.py
"""

__test__ = False

import json
import os
import re
import sys
from pathlib import Path

# Add project root to path
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import Jinja2
try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    from jinja2.exceptions import TemplateError
except ImportError:
    print("❌ jinja2 not installed. Run: pip install jinja2")
    sys.exit(1)

# Paths
CVS_PATH = PROJECT_ROOT / "data" / "cvs"
TEMPLATE_DIR = PROJECT_ROOT / "templates"
VISUAL_PROOF_DIR = PROJECT_ROOT / "docs" / "visual-proof"


def latex_escape(s):
    """Escape LaTeX special chars in plain text."""
    if s is None:
        return ""
    s = str(s)
    repl = [
        ("\\", r"\textbackslash{}"),
        ("&",  r"\&"),
        ("%",  r"\%"),
        ("$",  r"\$"),
        ("#",  r"\#"),
        ("_",  r"\_"),
        ("{",  r"\{"),
        ("}",  r"\}"),
        ("~",  r"\textasciitilde{}"),
        ("^",  r"\textasciicircum{}"),
    ]
    for k, v in repl:
        s = s.replace(k, v)
    return s


def file_exists(value):
    return os.path.exists(value) if value else False


def debug(value):
    return ""


def types(value):
    return ""


def cmt(s):
    if s is None:
        return ""
    return "% " + str(s).replace("\n", " ").strip() + "\n"


def cblock(s):
    if s is None:
        return ""
    lines = str(s).splitlines() or [str(s)]
    return "".join("% " + line + "\n" for line in lines)


def find_pic(opt_name):
    return os.path.exists(f"./data/pics/{opt_name}.jpg")


def get_pic(opt_name):
    return f"./data/pics/{opt_name}.jpg"


def create_jinja_env():
    """Create the Jinja2 environment matching generate_cv.py."""
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
        undefined=StrictUndefined
    )
    
    # Register filters
    env.filters["latex_escape"] = latex_escape
    env.filters["debug"] = debug
    env.filters["types"] = types
    env.filters["cmt"] = cmt
    env.filters["cblock"] = cblock
    env.filters["file_exists"] = file_exists
    env.filters["get_pic"] = get_pic
    env.filters["find_pic"] = find_pic
    env.globals["SHOW_COMMENTS"] = True
    
    return env


def test_cv_rendering(cv_path: Path, env: Environment) -> tuple:
    """
    Test rendering a CV file through all templates.
    
    Returns (success: bool, rendered_sections: dict, errors: list, cv_data: dict)
    """
    errors = []
    rendered_sections = {}
    
    # Load CV data
    try:
        with open(cv_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, {}, [f"Failed to load {cv_path.name}: {e}"], {}
    
    people_name = cv_path.stem
    data["OPT_NAME"] = people_name
    
    # Detect RTL language from filename (e.g., ramin_fa.json)
    RTL_LANGUAGES = {"fa", "ar", "he"}
    match = re.match(r'^(.+?)[-_]([a-z]{2,3})$', people_name)
    if match:
        base_name, lang = match.group(1), match.group(2)
    else:
        base_name, lang = people_name, "en"
    is_rtl = lang in RTL_LANGUAGES
    
    env_vars = {**data}
    env_vars["LANG"] = lang
    env_vars["BASE_NAME"] = base_name
    env_vars["IS_RTL"] = is_rtl
    
    # Add translation function stub for testing
    def t(key, default=None, escape=True):
        result = default if default is not None else key
        if escape:
            return latex_escape(result)
        return result
    env.globals["t"] = t
    env.filters["tr"] = lambda key: latex_escape(key)
    env.filters["tr_raw"] = lambda key: key
    
    # Get template files
    template_files = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith('.tex')]
    
    # Render each template (except layout templates)
    for tmpl_file in template_files:
        if tmpl_file.startswith("layout"):
            continue
            
        try:
            template = env.get_template(tmpl_file)
            rendered = template.render(env_vars)
            section_name = os.path.splitext(tmpl_file)[0]
            rendered_sections[section_name] = rendered
            env_vars[f"{section_name}_section"] = rendered
        except TemplateError as e:
            errors.append(f"Template error in {tmpl_file}: {e}")
    
    # Render layout if no errors so far
    # Select appropriate layout based on RTL
    if not errors:
        layout_template_name = "layout_rtl.tex" if is_rtl else "layout.tex"
        try:
            layout_template = env.get_template(layout_template_name)
            rendered_layout = layout_template.render(env_vars)
            rendered_sections["layout"] = rendered_layout
        except TemplateError as e:
            errors.append(f"Layout template error ({layout_template_name}): {e}")
    
    success = len(errors) == 0
    return success, rendered_sections, errors, data


def check_rendered_output(rendered_sections: dict, cv_name: str, cv_data: dict) -> list:
    """
    Check rendered output for issues like 'undefined' strings.
    
    Returns list of issues found.
    """
    issues = []
    
    # Mapping from template name to JSON data key
    SECTION_TO_DATA_KEY = {
        "publications": "publications",
        "projects": "projects", 
        "references": "references",
        "certificates": "workshop_and_certifications",
        "experience": "experiences",
        "skills": "skills",
        "language": "languages",
        "education": "education",
        "header": "basics",
        "layout": None,  # Layout is always rendered
    }
    
    # Sections that can be legitimately empty if source data is empty
    OPTIONAL_SECTIONS = {"publications", "projects", "references", "certificates", 
                         "experience", "skills", "language"}
    
    for section_name, content in rendered_sections.items():
        # Check for literal 'undefined' (case insensitive)
        if "undefined" in content.lower():
            issues.append(f"{cv_name}/{section_name}: Contains 'undefined'")
        
        # Check for empty sections (just whitespace)
        # Only flag as issue if the source data has content
        if not content.strip():
            # Get the corresponding data key using the mapping
            data_key = SECTION_TO_DATA_KEY.get(section_name)
            
            if data_key is None:
                # Layout or unknown section - skip empty check
                continue
                
            source_data = cv_data.get(data_key)
            
            if section_name not in OPTIONAL_SECTIONS:
                # Required sections should not be empty
                issues.append(f"{cv_name}/{section_name}: Section is empty")
            elif source_data and len(source_data) > 0:
                # Optional section has data but rendered empty - this is a bug
                issues.append(f"{cv_name}/{section_name}: Section has data but rendered empty")
            # else: Optional section with no data - this is expected
    
    return issues


def save_visual_proof(rendered_sections: dict, cv_name: str):
    """Save rendered sections as visual proof."""
    VISUAL_PROOF_DIR.mkdir(parents=True, exist_ok=True)
    
    cv_dir = VISUAL_PROOF_DIR / cv_name
    cv_dir.mkdir(exist_ok=True)
    
    for section_name, content in rendered_sections.items():
        output_file = cv_dir / f"{section_name}.tex"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
    
    # Create a summary file
    summary_file = cv_dir / "RENDERING_PROOF.txt"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(f"CV Generation Proof for: {cv_name}\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Sections rendered: {len(rendered_sections)}\n")
        for section, content in rendered_sections.items():
            lines = len(content.splitlines())
            chars = len(content)
            f.write(f"  - {section}: {lines} lines, {chars} chars\n")
        f.write("\n✅ All sections rendered successfully\n")


def main():
    print("=" * 60)
    print("🧪 CV Generation Test")
    print("=" * 60)
    
    # Create Jinja environment
    env = create_jinja_env()
    
    # Get all CV files
    cv_files = list(CVS_PATH.glob("*.json"))
    
    if not cv_files:
        print(f"❌ No CV files found in {CVS_PATH}")
        sys.exit(1)
    
    print(f"\n📋 Testing {len(cv_files)} CV file(s)...\n")
    
    all_passed = True
    
    for cv_path in sorted(cv_files):
        cv_name = cv_path.stem
        print(f"\n🔄 Processing: {cv_name}")
        
        success, rendered_sections, errors, cv_data = test_cv_rendering(cv_path, env)
        
        if not success:
            all_passed = False
            print(f"  ❌ Rendering failed")
            for error in errors:
                print(f"      - {error}")
            continue
        
        # Check rendered output
        issues = check_rendered_output(rendered_sections, cv_name, cv_data)
        if issues:
            all_passed = False
            print(f"  ⚠️  Output issues found")
            for issue in issues:
                print(f"      - {issue}")
        else:
            print(f"  ✅ Rendered successfully ({len(rendered_sections)} sections)")
        
        # Save visual proof
        save_visual_proof(rendered_sections, cv_name)
        print(f"  📁 Visual proof saved to docs/visual-proof/{cv_name}/")
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("✅ All CV generation tests PASSED")
        print(f"📁 Visual proofs saved to: {VISUAL_PROOF_DIR}")
        sys.exit(0)
    else:
        print("❌ Some tests FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
