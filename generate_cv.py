"""CV Generator — thin CLI entry point.

This module serves as the main entry point for CV generation.  It delegates
to the shared ``core`` package for document-agnostic helpers (caching, file
resolution, LaTeX utilities, Jinja2 environment, compilation) and to the
``cv`` package for CV-specific orchestration.

All public symbols that were previously defined here are re-exported so
that existing callers (tests, scripts) continue to work unchanged.
"""

import argparse
import os
from pathlib import Path

# ── Re-export shared core utilities ──────────────────────────────────────────
from core.settings import (  # noqa: F401
    BASE_DIR,
    CVS_PATH,
    TEMPLATE_DIR,
    RESULT_DIR,
    LANG_ENGINE_DIR,
    CACHE_FILE,
    RTL_LANGUAGES,
    SHOW_COMMENTS,
    log_verbose,
)
from core import settings as _settings

from core.cache import (  # noqa: F401
    load_cache,
    save_cache,
    compute_file_hash,
    normalize_path_for_cache,
    cache_key_for_path,
    has_file_changed,
)

from core.files import (  # noqa: F401
    gather_input_files,
    resolve_output_target,
)

from core.latex import (  # noqa: F401
    latex_escape,
    file_exists,
    debug,
    types,
    cmt,
    cblock,
    find_pic,
    get_pic,
)

from core.language import (  # noqa: F401
    parse_cv_filename,
    load_lang_map,
    make_translate_func,
    make_tr_filter,
    make_tr_raw_filter,
)

from core.jinja_env import create_jinja_env  # noqa: F401

from core.compile import compile_latex, finalize_pdf  # noqa: F401

from core.cleanup import (  # noqa: F401
    rmtree_reliable,
)

# ── Re-export CV-specific orchestration ─────────────────────────────────────
from cv.build import process_cv_file, get_cv_section_templates  # noqa: F401

# Module-level VERBOSE kept for backward compatibility (delegates to settings)
VERBOSE = _settings.VERBOSE


# -------------------------
# Main Function
# -------------------------
def main():
    """Main entry point for the CV generator."""
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
    _settings.VERBOSE = args.verbose
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

    # Get list of CV section templates
    section_templates = get_cv_section_templates()
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
# Entry Point
# -------------------------
if __name__ == "__main__":
    main()
