# CLI Argument Passing + Cache Integrity Fix Report

## Root Causes
- **Cache collisions and path mismatches**: cache entries were keyed by the raw JSON path string from `CVS_PATH`, which caused collisions when different directories contained the same filename and broke skip behavior for explicit paths. The output check also relied on the output directory + PDF name even when `--output-path` specified a file. (`generate_cv.py`)
- **Input resolution limitations**: positional arguments were treated as filenames only, so folder inputs were not expanded, and relative paths outside `data/cvs/` were not normalized. (`generate_cv.py`)
- **Output-path handling**: `--output-path` was always treated as a directory, so a PDF filepath was never validated and could not be used safely. (`generate_cv.py`)

## What Changed
- **Canonical cache keys + output-aware skip checks**: cache keys now use normalized, resolved paths and skip requires the output PDF to exist in the current target. (`generate_cv.py`)
- **Folder expansion and deduplication**: positional arguments now expand directories into JSON files (non-recursive) and dedupe by canonical path. (`generate_cv.py`)
- **Output-path validation**: PDF output path is supported only for a single input file; multiple inputs with a PDF output path now error. (`generate_cv.py`)
- **Safe cache writes**: cache is written atomically via a temp file + rename. (`generate_cv.py`)
- **Regression tests** for folder expansion, mixed inputs, cache identity, skip semantics, and output-path rules. (`tests/test_cli_paths.py`)

## How to Reproduce the Old Bug
1. Run `python generate_cv.py data/cvs_temp` to pass a directory path — it was treated as a file and failed to expand.
2. Run `python generate_cv.py data/cvs/ramin.json --output-path ./out.pdf` — the output was treated as a directory and never used as a filepath.
3. Run with two different JSON files that share the same basename in different folders — cache entries collided, causing incorrect skips or rebuilds.

## How to Verify the Fix
1. Default run:
   - `python generate_cv.py`
2. Output directory override:
   - `python generate_cv.py --output-path ./pdfs`
3. Single file with output override:
   - `python generate_cv.py ./data/cvs_temp/ramin_en.json --output-path ./temp/output.pdf`
4. Folder input:
   - `python generate_cv.py ./data/cvs_temp --output-path ./temp`
5. Run `pytest` to execute regression tests.

## Folder Input Behavior Notes
- Passing a directory argument expands **only the JSON files in that folder (non-recursive)**.
- Non-JSON files are ignored; nested folders are not scanned unless they are explicitly passed.
