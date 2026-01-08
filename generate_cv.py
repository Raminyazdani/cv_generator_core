import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import time
import uuid
import subprocess
from dataclasses import dataclass
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2.exceptions import TemplateError

# -------------------------
# Settings
# -------------------------

BASE_DIR = os.path.dirname(__file__)
CVS_PATH = os.path.join(BASE_DIR, "data", "cvs")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
RESULT_DIR = os.path.join(BASE_DIR, "result")
LANG_ENGINE_DIR = os.path.join(BASE_DIR, "Lang_engine")
CACHE_FILE = os.path.join(BASE_DIR, ".cvgen_cache.json")

# RTL languages
RTL_LANGUAGES = {"fa", "ar", "he"}

# Toggle whether template-inserted comments are emitted
SHOW_COMMENTS = True

# Global verbose flag (set by command-line argument)
VERBOSE = False


# -------------------------
# Verbose Logging
# -------------------------
def log_verbose(message):
    """Print message only if verbose mode is enabled."""
    if VERBOSE:
        print(message)


def canonicalize_path(path: Path) -> str:
    resolved = path.expanduser()
    try:
        resolved = resolved.resolve()
    except FileNotFoundError:
        resolved = resolved.absolute()
    return os.path.normcase(str(resolved))


def is_json_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".json"


def expand_input_paths(inputs: list[str]) -> list[Path]:
    expanded: list[Path] = []
    for raw in inputs:
        candidate = Path(raw)
        if candidate.is_dir():
            for entry in candidate.iterdir():
                if is_json_file(entry):
                    expanded.append(entry)
        elif candidate.exists():
            expanded.append(candidate)
        else:
            raise SystemExit(f"❌ Input path not found: {raw}")

    seen: set[str] = set()
    unique: list[Path] = []
    for path in expanded:
        key = canonicalize_path(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


@dataclass(frozen=True)
class OutputConfig:
    output_dir: Path
    explicit_pdf_path: Path | None = None


def resolve_output_config(output_path: str, input_paths: list[Path]) -> OutputConfig:
    output_candidate = Path(output_path)
    if output_candidate.exists() and output_candidate.is_dir():
        return OutputConfig(output_dir=output_candidate)

    if output_candidate.suffix.lower() == ".pdf":
        if len(input_paths) != 1:
            raise SystemExit("❌ --output-path as a PDF file is only allowed with a single input file.")
        return OutputConfig(output_dir=output_candidate.parent, explicit_pdf_path=output_candidate)

    return OutputConfig(output_dir=output_candidate)


# -------------------------
# Cache Management
# -------------------------
def load_cache():
    """Load the hash cache from the cache file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                raw_cache = json.load(f)
                normalized: dict[str, str] = {}
                for key, value in raw_cache.items():
                    path = Path(key)
                    if not path.is_absolute():
                        path = Path(BASE_DIR) / path
                    normalized_key = canonicalize_path(path)
                    if normalized_key not in normalized:
                        normalized[normalized_key] = value
                return normalized
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_cache(cache):
    """Save the hash cache to the cache file."""
    try:
        cache_path = Path(CACHE_FILE)
        tmp_path = cache_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        tmp_path.replace(cache_path)
    except IOError as e:
        print(f"⚠️  Warning: Could not save cache: {e}")


def compute_file_hash(filepath):
    """Compute SHA-256 hash of a file's contents."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except IOError:
        return None


def has_file_changed(cache_key, cache, output_pdf_path, filepath):
    """
    Check if a file has changed since last processing.
    
    Returns (changed: bool, current_hash: str)
    """
    current_hash = compute_file_hash(filepath)
    if current_hash is None:
        return True, None
    if not output_pdf_path.exists():
        return True, current_hash

    cached_hash = cache.get(cache_key)
    changed = cached_hash != current_hash
    return changed, current_hash


# -------------------------
# Utilities / Filters (defined once, outside loop)
# -------------------------
def latex_escape(s):
    """Escape LaTeX special chars in plain text."""
    if s is None:
        return ""
    s = str(s)
    # Order matters: backslash first.
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
    if os.path.exists(value):
        return True
    return False


def debug(value):
    print(value)
    print(type(value))
    return ""  # emit nothing in TeX


def types(value):
    print(type(value))
    return ""  # emit nothing in TeX


def cmt(s):
    """Emit a single LaTeX comment line, gated by SHOW_COMMENTS."""
    if not SHOW_COMMENTS or s is None:
        return ""
    return "% " + str(s).replace("\n", " ").strip() + "\n"


def cblock(s):
    """Emit multi-line LaTeX comment block, gated by SHOW_COMMENTS."""
    if not SHOW_COMMENTS or s is None:
        return ""
    lines = str(s).splitlines() or [str(s)]
    return "".join("% " + line + "\n" for line in lines)


def find_pic(opt_name):
    if os.path.exists(f"./data/pics/{opt_name}.jpg"):
        return True
    else:
        return False


def get_pic(opt_name):
    return f"./data/pics/{opt_name}.jpg"


# -------------------------
# Language Detection
# -------------------------
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
    name = filename[:-5] if filename.endswith('.json') else filename
    
    # Pattern: name-lang or name_lang where lang is 2-3 lowercase letters
    match = re.match(r'^(.+?)[-_]([a-z]{2,3})$', name)
    if match:
        return match.group(1), match.group(2)
    
    # No language suffix - default to English
    return name, "en"


# -------------------------
# Load Language Mapping
# -------------------------
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


# -------------------------
# Translation Function Factory
# -------------------------
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


# -------------------------
# Process Single CV File
# -------------------------
def run_xelatex(command: list[str]) -> bool:
    result = subprocess.run(command, check=False)
    return result.returncode == 0


def process_cv_file(input_path, lang_map, section_templates, cache, output_config):
    """
    Process a single CV JSON file and generate PDF.
    
    Args:
        input_path: Path to the JSON file to process
        lang_map: Translation mapping dictionary
        section_templates: List of template files to render
        cache: Hash cache dictionary for change detection
        output_config: Output configuration for generated PDFs
    
    Returns:
        tuple: (processed: bool, skipped: bool, current_hash: str or None)
    """
    if not is_json_file(input_path):
        log_verbose(f"  ⏭️  Skipping {input_path}: not a JSON file")
        return False, True, None

    # Parse filename to get base_name and language
    base_name, lang = parse_cv_filename(input_path.name)
    is_rtl = lang in RTL_LANGUAGES
    
    JSON_PATH = input_path
    cache_key = canonicalize_path(JSON_PATH)

    # Check if file exists
    if not JSON_PATH.exists():
        print(f"❌ File not found: {JSON_PATH}")
        return False, False, None

    pdf_name = f"{base_name}_{lang}.pdf"
    if output_config.explicit_pdf_path is not None:
        output_pdf_path = output_config.explicit_pdf_path
        output_dir = output_config.explicit_pdf_path.parent
    else:
        output_dir = output_config.output_dir
        output_pdf_path = output_dir / pdf_name

    # Check if file has changed using cache
    changed, current_hash = has_file_changed(cache_key, cache, output_pdf_path, JSON_PATH)
    if not changed:
        log_verbose(f"  ⏭️  Skipping {input_path}: file unchanged (cached)")
        print(f"⏭️  Skipping {input_path}: no changes detected")
        return False, True, current_hash

    log_verbose(f"  📄 Processing {input_path} (base: {base_name}, lang: {lang}, RTL: {is_rtl})")

    # -------------------------
    # Load data (no eval, no hacks)
    # -------------------------
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # Validate required structure - skip files that don't have the expected schema
    if "basics" not in data:
        print(f"⚠️  Skipping {input_path}: missing 'basics' key (incompatible schema)")
        return False, True, None

    # Create output directory structure: result/<base_name>/<lang>/sections/
    people_output_dir = Path(RESULT_DIR) / base_name / lang
    people_output_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR = people_output_dir / "sections"
    RENDERED_OUTPUT = people_output_dir / "rendered.tex"

    # -------------------------
    # Jinja environment
    # -------------------------
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
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

    # Create translation function for this language
    t_func = make_translate_func(lang_map, lang)

    # Filters & globals
    data["OPT_NAME"] = base_name

    env.filters["latex_escape"] = latex_escape
    env.filters["debug"] = debug
    env.filters["types"] = types
    env.filters["cmt"] = cmt
    env.filters["cblock"] = cblock
    env.filters["file_exists"] = file_exists
    env.filters["get_pic"] = get_pic
    env.filters["find_pic"] = find_pic
    
    # Add translation filters
    env.filters["tr"] = make_tr_filter(lang_map, lang)
    env.filters["tr_raw"] = make_tr_raw_filter(lang_map, lang)
    
    # Add globals for templates
    env.globals["SHOW_COMMENTS"] = SHOW_COMMENTS
    env.globals["LANG_MAP"] = lang_map
    env.globals["LANG"] = lang
    env.globals["BASE_NAME"] = base_name
    env.globals["IS_RTL"] = is_rtl
    env.globals["t"] = t_func

    # Vars available to templates (top-level JSON keys become variables)
    env_vars = {**data}
    env_vars["LANG_MAP"] = lang_map
    env_vars["LANG"] = lang
    env_vars["BASE_NAME"] = base_name
    env_vars["IS_RTL"] = is_rtl

    # -------------------------
    # Ensure output folder exists
    # -------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
        output_path = OUTPUT_DIR / f"{section_name}.tex"
        with open(output_path, "w", encoding="utf-8") as f:
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
    
    # Generate PDF output name with language suffix
    pdf_name = f"{base_name}_{lang}.pdf"
    command = [
        "xelatex",
        "-enable-etex",
        "-enable-installer",
        "-enable-mltex",
        "-interaction=nonstopmode",
        "-file-line-error",
        "-synctex=1",
        f"-output-directory={output_dir}",
        str(RENDERED_OUTPUT),
    ]

    # run the command to compile the LaTeX file
    log_verbose(f"    🔧 Running: {' '.join(command)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not run_xelatex(command):
        print(f"❌ PDF generation failed for {input_path}")
        return False, False, None

    # Handle output files
    if output_dir.exists():
        for file in os.listdir(output_dir):
            file_path = Path(output_dir) / file
            if not file.endswith(".pdf"):
                os.remove(file_path)
            if file.endswith("rendered.pdf"):
                shutil.move(file_path, output_pdf_path)
                log_verbose(f"    📄 PDF generated: {output_pdf_path.name}")

    if not output_pdf_path.exists():
        print(f"❌ Expected PDF not found at: {output_pdf_path}")
        return False, False, None

    return True, False, current_hash


# -------------------------
# Main Function
# -------------------------
def main():
    """Main entry point for the CV generator."""
    global VERBOSE
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Generate PDF CVs from JSON files using Jinja2 templates and LaTeX.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_cv.py                    # Process all JSON files in data/cvs/
  python generate_cv.py file1.json         # Process only file1.json
  python generate_cv.py file1.json file2.json  # Process multiple specific files
  python generate_cv.py --verbose          # Process all files with detailed output
  python generate_cv.py --verbose file1.json   # Process file1.json with detailed output
  python generate_cv.py --output-path ./pdfs   # Save PDFs to ./pdfs

Change Detection:
  The script uses a cache file (.cvgen_cache.json) to track file hashes.
  If a JSON file hasn't changed since the last PDF generation, it will be skipped.
  To force regeneration, delete the cache file or modify the JSON file.
"""
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Optional: Specific JSON file(s) to process. If not provided, all JSON files in data/cvs/ will be processed."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output showing detailed processing information."
    )
    parser.add_argument(
        "--output-path",
        help=(
            "Optional: Directory or PDF file path to save generated PDFs. "
            "Defaults to the standard output folder."
        ),
        default="./output"

    )
    
    args = parser.parse_args()
    VERBOSE = args.verbose
    output_path = args.output_path
    
    log_verbose("🔧 Verbose mode enabled")
    log_verbose(f"📁 Base directory: {BASE_DIR}")
    log_verbose(f"📁 CVs path: {CVS_PATH}")
    log_verbose(f"📁 Template directory: {TEMPLATE_DIR}")
    log_verbose(f"📁 Cache file: {CACHE_FILE}")
    
    # Ensure result and output directories exist
    if not os.path.exists(RESULT_DIR):
        os.makedirs(RESULT_DIR)
        log_verbose(f"📁 Created result directory: {RESULT_DIR}")
    
    if not os.path.exists(args.output_path):
        log_verbose(f"📁 Output path does not exist yet: {args.output_path}")
    
    # Load the translation map once
    log_verbose("📖 Loading translation map...")
    lang_map = load_lang_map()
    log_verbose(f"    ✓ Loaded {len(lang_map)} translation keys")
    
    # Load cache
    log_verbose("📖 Loading cache...")
    cache = load_cache()
    log_verbose(f"    ✓ Loaded cache with {len(cache)} entries")
    
    # Get list of templates (excluding layout templates which are handled separately)
    section_templates = [x for x in os.listdir(TEMPLATE_DIR) if not x.startswith("layout")]
    log_verbose(f"📝 Found {len(section_templates)} section templates")
    
    # Determine which files to process
    if args.files:
        files_to_process = expand_input_paths(args.files)
        log_verbose(f"📋 Processing {len(files_to_process)} specified file(s)")
    else:
        files_to_process = expand_input_paths([CVS_PATH])
        log_verbose(f"📋 Processing all {len(files_to_process)} JSON file(s) in {CVS_PATH}")

    output_config = resolve_output_config(output_path, files_to_process)
    output_config.output_dir.mkdir(parents=True, exist_ok=True)
    log_verbose(f"📁 Output directory: {output_config.output_dir}")

    # Track statistics
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    # Process each file
    for people in files_to_process:
        log_verbose(f"\n{'='*50}")
        log_verbose(f"📄 Checking: {people}")
        
        processed, skipped, current_hash = process_cv_file(
            people, lang_map, section_templates, cache, output_config
        )

        if processed:
            processed_count += 1
            # Update cache with new hash
            if current_hash:
                cache_key = canonicalize_path(people)
                cache[cache_key] = current_hash
                log_verbose(f"    💾 Cache updated for {people}")
        elif skipped:
            skipped_count += 1
        else:
            error_count += 1
                

    
    # Save updated cache
    log_verbose("\n💾 Saving cache...")
    save_cache(cache)
    
    # Print summary
    print(f"\n{'='*50}")
    print("📊 Summary:")
    print(f"   ✅ Processed: {processed_count}")
    print(f"   ⏭️  Skipped:   {skipped_count}")
    if error_count > 0:
        print(f"   ❌ Errors:    {error_count}")
    print(f"{'='*50}")


# -------------------------
# Cleanup Utilities (available for manual cleanup)
# -------------------------
def _clear_readonly_windows(root: Path) -> None:
    # Best-effort: remove "Read-only" attribute recursively (Windows)
    if os.name == "nt":
        try:
            subprocess.run(
                ["attrib", "-R", str(root / "*"), "/S", "/D"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True,
            )
        except Exception:
            pass


def _make_writable(path: str) -> None:
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass


def rmtree_reliable(path: str | os.PathLike, *, attempts: int = 25) -> None:
    """
    Reliably remove a directory tree, with retry logic for Windows file locks.
    
    Note: This function is available for cleanup but not called automatically
    to preserve generated results. Call manually if needed.
    """
    p = Path(path)

    if not p.exists():
        return

    p = p.resolve()

    try:
        renamed = p.with_name(f"{p.name}.__deleting__{uuid.uuid4().hex}")
        p.rename(renamed)
        p = renamed
    except Exception:
        pass

    def onerror(func, failed_path, exc_info):
        _make_writable(failed_path)
        try:
            func(failed_path)
        except Exception:
            raise

    for i in range(attempts):
        try:
            _clear_readonly_windows(p)
            shutil.rmtree(p, onerror=onerror)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            time.sleep(min(2.0, 0.05 * (2 ** i)))
        except OSError as e:
            time.sleep(min(2.0, 0.05 * (2 ** i)))

    _clear_readonly_windows(p)
    shutil.rmtree(p, onerror=onerror)


# -------------------------
# Entry Point
# -------------------------
if __name__ == "__main__":
    main()
