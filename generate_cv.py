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


# -------------------------
# Cache Management
# -------------------------
def load_cache():
    """Load the hash cache from the cache file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_cache(cache):
    """Save the hash cache to the cache file."""
    cache_path = Path(CACHE_FILE)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_suffix(".tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        os.replace(temp_path, cache_path)
    except IOError as e:
        print(f"⚠️  Warning: Could not save cache: {e}")
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def compute_file_hash(filepath: Path):
    """Compute SHA-256 hash of a file's contents."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except IOError:
        return None


def normalize_path_for_cache(path: Path) -> str:
    """Normalize a path for cache key stability across platforms."""
    resolved = path.expanduser().resolve()
    normalized = os.path.normcase(str(resolved))
    return normalized


def cache_key_for_path(path: Path) -> str:
    """Return a canonical cache key for a given input file path."""
    return normalize_path_for_cache(path)


def has_file_changed(filepath: Path, cache, output_pdf_path: Path):
    """
    Check if a file has changed since last processing.

    Returns (changed: bool, current_hash: str)
    """
    current_hash = compute_file_hash(filepath)
    if current_hash is None:
        return True, None

    cache_key = cache_key_for_path(filepath)
    cached_hash = cache.get(cache_key)
    if cached_hash == current_hash and output_pdf_path.exists():
        return False, current_hash
    return True, current_hash


def gather_input_files(files, default_dir: Path) -> list[Path]:
    """Resolve file and directory arguments into a list of JSON files."""
    if not files:
        candidates = [p for p in default_dir.iterdir() if p.is_file()]
    else:
        candidates = []
        for entry in files:
            path = Path(entry).expanduser()
            if not path.is_absolute() and not path.exists():
                candidate = default_dir / entry
                if candidate.exists():
                    path = candidate
            candidates.append(path)

    resolved_files = []
    for candidate in candidates:
        if candidate.is_dir():
            for item in candidate.iterdir():
                if item.is_file() and item.suffix.lower() == ".json":
                    resolved_files.append(item)
            continue
        if candidate.is_file():
            if candidate.suffix.lower() == ".json":
                resolved_files.append(candidate)
            else:
                log_verbose(f"  ⏭️  Skipping {candidate}: not a JSON file")
            continue
        resolved_files.append(candidate)

    deduped = []
    seen = set()
    for item in resolved_files:
        try:
            key = normalize_path_for_cache(item)
        except FileNotFoundError:
            key = os.path.normcase(str(item))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def resolve_output_target(output_path: str, input_files: list[Path]) -> tuple[Path, Path | None]:
    """Resolve output path configuration and validate constraints."""
    output_target = Path(output_path).expanduser()
    if output_target.suffix.lower() == ".pdf":
        if len(input_files) != 1:
            raise SystemExit("❌ --output-path may be a PDF file only when processing a single input file.")
        return output_target.parent, output_target
    if output_target.exists() and output_target.is_file():
        raise SystemExit("❌ --output-path must be a directory when processing multiple outputs.")
    return output_target, None


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
    name = filename[:-5] if filename.lower().endswith('.json') else filename
    
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
        f"-output-directory={orig_output_dir}",
        RENDERED_OUTPUT,
    ]

    # run the command to compile the LaTeX file
    log_verbose(f"    🔧 Running: {' '.join(command)}")
    subprocess.run(command, check=False)

    # Handle output files
    output_dir = orig_output_dir
    if output_dir.exists():
        for file in os.listdir(output_dir):
            file_path = output_dir / file
            if not file.endswith(".pdf"):
                os.remove(file_path)
            if file.endswith("rendered.pdf"):
                shutil.move(file_path, output_pdf_path)
                log_verbose(f"    📄 PDF generated: {output_pdf_path.name}")

    if not output_pdf_path.exists():
        print(f"❌ PDF generation failed for {people_path}")
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
    
    files_to_process = gather_input_files(args.files, Path(CVS_PATH))
    if not files_to_process:
        print("❌ No input files found to process.")
        return

    output_dir, output_file = resolve_output_target(output_path, files_to_process)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_verbose(f"📁 Output directory: {output_dir}")
    if output_file:
        log_verbose(f"📄 Output file override: {output_file}")
    
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
    
    log_verbose(f"📋 Processing {len(files_to_process)} input file(s)")

    # Track statistics
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    # Process each file
    for people in files_to_process:
        log_verbose(f"\n{'='*50}")
        log_verbose(f"📄 Checking: {people}")
        
        processed, skipped, current_hash = process_cv_file(
            people, lang_map, section_templates, cache, output_dir, output_file
        )

        if processed:
            processed_count += 1
            # Update cache with new hash
            if current_hash:
                cache_key = cache_key_for_path(people)
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
