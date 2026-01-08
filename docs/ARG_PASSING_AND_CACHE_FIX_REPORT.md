# ARG PASSING AND CACHE FIX REPORT

## Root causes
- Positional CLI arguments were treated as bare filenames within `data/cvs/`, so absolute/relative file paths and folders were not respected, and folder inputs were never expanded. (`generate_cv.py`, `process_cv_file` and `main` logic.)
- Cache keys were stored as whatever path string happened to be used, which allowed collisions and stale skips when the same basename existed in multiple folders or when paths were spelled differently. (`has_file_changed`, cache update.)
- Skip logic only checked output files based on string joins, which failed when `--output-path` was a PDF file, and cache writes could still occur even if compilation failed. (`has_file_changed`, `process_cv_file`.)

## What changed
- Added path normalization helpers to canonicalize inputs, expand folder arguments into JSON files, and deduplicate based on canonical paths.
- Implemented output-path resolution with explicit handling for directory vs PDF file paths and enforced the “single input for PDF output path” rule.
- Updated cache load/save to normalize keys and use atomic writes, and updated skip logic to require the expected output PDF to exist.
- Introduced a test seam for LaTeX compilation and added regression tests for folder expansion, output-path behavior, cache identity, and skip logic.

## How to reproduce the old bugs
1. Run `python generate_cv.py ./data/cvs_temp/ramin_en.json --output-path ./temp` and observe the script tried to find `data/cvs/./data/cvs_temp/ramin_en.json` or otherwise failed due to treating the path as a filename.
2. Run `python generate_cv.py ./data/cvs_temp --output-path ./temp` and observe that the directory is treated as a file and skipped, instead of expanding JSONs.
3. Use two files with the same basename in different folders and observe cache collisions because the cache key did not canonicalize the full path.

## How to verify the fix
1. Run `pytest` to execute the regression tests.
2. Run the acceptance commands:
   - `python generate_cv.py`
   - `python generate_cv.py --output-path ./pdfs`
   - `python generate_cv.py ./data/cvs_temp/ramin_en.json --output-path ./temp`
   - `python generate_cv.py ./data/cvs_temp --output-path ./temp`
3. Re-run each command without changes and confirm the cache skips regeneration while the output PDF still exists.

## Notes about folder input behavior
- Folder arguments are treated as a flat (non-recursive) set of JSON files, matching the repository’s existing “list the directory” behavior for `data/cvs/`.
