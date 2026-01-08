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

# RTL languages
RTL_LANGUAGES = {"fa", "ar", "he"}

# Toggle whether template-inserted comments are emitted
SHOW_COMMENTS = True

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
# Main Processing Loop
# -------------------------
if not os.path.exists(RESULT_DIR):
    os.makedirs(RESULT_DIR)

# Load the translation map once
LANG_MAP = load_lang_map()

# Get list of templates (excluding layout templates which are handled separately)
SECTION_TEMPLATES = [x for x in os.listdir(TEMPLATE_DIR) if not x.startswith("layout")]

for people in os.listdir(CVS_PATH):
    if not people.endswith('.json'):
        continue
    
    # Parse filename to get base_name and language
    base_name, lang = parse_cv_filename(people)
    is_rtl = lang in RTL_LANGUAGES
    
    JSON_PATH = os.path.join(CVS_PATH, people)

    # -------------------------
    # Load data (no eval, no hacks)
    # -------------------------
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # Validate required structure - skip files that don't have the expected schema
    if "basics" not in data:
        print(f"⚠️  Skipping {people}: missing 'basics' key (incompatible schema)")
        continue

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
    t_func = make_translate_func(LANG_MAP, lang)

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
    env.filters["tr"] = make_tr_filter(LANG_MAP, lang)
    env.filters["tr_raw"] = make_tr_raw_filter(LANG_MAP, lang)
    
    # Add globals for templates
    env.globals["SHOW_COMMENTS"] = SHOW_COMMENTS
    env.globals["LANG_MAP"] = LANG_MAP
    env.globals["LANG"] = lang
    env.globals["BASE_NAME"] = base_name
    env.globals["IS_RTL"] = is_rtl
    env.globals["t"] = t_func

    # Vars available to templates (top-level JSON keys become variables)
    env_vars = {**data}
    env_vars["LANG_MAP"] = LANG_MAP
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
    for tmpl_file in SECTION_TEMPLATES:
        try:
            template = env.get_template(tmpl_file)
            rendered = template.render(env_vars)
        except TemplateError as e:
            raise SystemExit(f"[Jinja error in {tmpl_file}] {e}") from e

        # write section file
        section_name = os.path.splitext(tmpl_file)[0]
        output_path = os.path.join(OUTPUT_DIR, f"{section_name}.tex")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rendered)

        # also store for inline embedding in layout
        env_vars[f"{section_name}_section"] = rendered

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
    comand = fr"xelatex -enable-etex -enable-installer -enable-mltex -interaction=nonstopmode -file-line-error -synctex=1 -output-directory=.\output {RENDERED_OUTPUT} "

    # run the command to compile the LaTeX file
    os.system(comand)
    for file in os.listdir("./output"):
        if not file.endswith(".pdf"):
            os.remove(f"./output/{file}")
        if file.endswith("rendered.pdf"):
            shutil.move(f"./output/{file}", f"./output/{pdf_name}")


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


# Note: rmtree_reliable is available for cleanup but not called automatically
# to preserve generated results. Call manually if needed.
