# ARG Passing + Cache Integrity Fix Report

## Root causes
- **Input path handling was rigid**: the CLI always assumed inputs were basenames under `data/cvs/`, so explicit file paths or directories were misinterpreted or rejected. This blocked folder inputs and made `--output-path` behavior inconsistent when inputs were outside the default folder.
- **Cache keys were not canonical**: cache entries were keyed by the string passed in, which could collide for files with identical basenames in different folders.
- **Output path handling was directory-only**: `--output-path` was always treated as a directory, so providing a PDF file path did not work and skip checks were tied to the wrong location.
- **Cache writes were non-atomic and updates happened even on failed builds**: cache writes could be interrupted and LaTeX failures still allowed cache updates.

## What changed
- Added robust input resolution, directory expansion, and de-duplication using canonical paths.
- Implemented canonical cache keys (absolute + Windows case-folding) to prevent collisions.
- Added output-path parsing rules to distinguish directories vs a single PDF target.
- Enforced skip logic that requires both unchanged input hash and existing output PDF.
- Added atomic cache writes and avoided cache updates on failed LaTeX runs.
- Added regression tests to cover folder inputs, output-path rules, skip logic, and cache key uniqueness.

## How to reproduce the old bug
1. Run `python generate_cv.py data/cvs_temp` with a folder of JSON files; only the default folder was processed, and folders were not expanded.
2. Run `python generate_cv.py data/cvs/ramin.json --output-path ./out.pdf`; the output path was treated as a directory, not a PDF target.
3. Use two JSON files with the same name in different directories; cache entries could collide because they used non-canonical keys.

## How to verify the fix
- Run tests:
  - `pytest`
- Manual checks:
  - `python generate_cv.py`
  - `python generate_cv.py --output-path ./pdfs`
  - `python generate_cv.py data/cvs_temp/ramin_en.json --output-path ./temp`
  - `python generate_cv.py data/cvs_temp --output-path ./temp`

## Notes about folder input behavior
- Folder inputs are treated as **non-recursive** expansions of JSON files (case-insensitive `.json`). This matches the existing behavior where default processing lists only the direct contents of `data/cvs/`.
