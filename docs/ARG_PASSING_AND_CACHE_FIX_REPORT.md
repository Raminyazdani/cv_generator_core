# CLI Argument Passing + Cache Fix Report

## Root causes
- **Positional inputs were treated as bare filenames** inside `data/cvs/`, so passing a file path or a folder path could not resolve correctly and folders were never expanded. This caused file arguments to fail or be silently skipped, and folder arguments were ignored.
- **Cache keys were based on raw input strings** tied to `data/cvs/` paths, leading to collisions when two files shared a basename in different directories and preventing consistent cache reuse across relative/absolute path variants.
- **Output path handling assumed a directory** in all cases, which made `--output-path` behave incorrectly when pointing at a PDF file and confused output existence checks for caching.
- **Cache updates occurred even when output artifacts were missing**, because output existence wasn’t tied to the specific resolved PDF path.

## What changed
- Added robust input expansion for **files and folders** (non-recursive) with JSON-only filtering and deduplication using canonical paths.
- Introduced **canonical cache keys** based on normalized absolute paths to avoid collisions and to handle relative path variants and case normalization.
- Implemented **output-path resolution** that distinguishes directories vs PDF file paths, enforcing the “single input for PDF output” rule.
- Updated skip logic to require the **actual output PDF path** to exist, and ensured cache writes happen only after successful PDF creation.
- Added atomic cache saves to avoid corruption on write failures.

## How to reproduce the old bug
1. Run with an explicit file path:
   ```bash
   python generate_cv.py ./data/cvs/ramin.json
   ```
   The previous implementation would still look for `data/cvs/./data/cvs/ramin.json` and fail.
2. Run with a folder argument:
   ```bash
   python generate_cv.py ./data/cvs
   ```
   The previous implementation treated this as a file and did not expand JSON files.
3. Run with `--output-path` pointing at a PDF file:
   ```bash
   python generate_cv.py ./data/cvs/ramin.json --output-path ./pdfs/custom.pdf
   ```
   The previous implementation treated this as a directory, so skip checks and output placement were inconsistent.

## How to verify the fix
1. Default behavior (no args):
   ```bash
   python generate_cv.py
   ```
   Run twice; the second run should skip unchanged files if output PDFs exist.
2. Output directory override:
   ```bash
   python generate_cv.py --output-path ./pdfs
   ```
   Run twice; outputs should be in `./pdfs/` and skipped on the second run if unchanged.
3. Single explicit file + output override:
   ```bash
   python generate_cv.py ./data/cvs_temp/ramin_en.json --output-path ./temp
   ```
   Run twice; only that PDF should be in `./temp/` and skipped on the second run if unchanged.
4. Folder input expansion (non-recursive):
   ```bash
   python generate_cv.py ./data/cvs_temp --output-path ./temp
   ```
   All `.json` files in `./data/cvs_temp` should be processed; non-JSON files are ignored.

## Notes about folder input behavior
- Folder inputs are **expanded non-recursively**: only JSON files directly in the provided directory are processed.
- JSON detection is **case-insensitive** (`.json`, `.JSON`, etc.).
- Duplicate paths (e.g., repeated files or overlapping folders) are deduplicated by canonical path.
