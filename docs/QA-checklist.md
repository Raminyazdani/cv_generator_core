# QA Checklist — Cover-Letter Feature Release

Use this checklist before merging the cover-letter feature to verify that
all scenarios work correctly end-to-end.

## 1. Batch generation

- [ ] `python generate_cv.py --type cover-letter` processes **all** JSON
      files in `data/cover_letter_datas/` and produces one PDF per file.
- [ ] `python generate_cv.py` (no `--type`) processes **all** CVs in
      `data/cvs/` — cover letters are **not** touched.

## 2. Single-file generation

- [ ] `python generate_cv.py --type cover-letter data/cover_letter_datas/ramin_google_en.json`
      generates only that one cover letter.
- [ ] `python generate_cv.py data/cvs/ramin_en.json` generates only that
      one CV.

## 3. Alternate layout selection

- [ ] A cover-letter JSON with `"options": {"template": "compact"}` uses
      the compact layout (`layout_compact.tex`).
- [ ] A cover-letter JSON for a Farsi (`_fa`) input automatically selects
      the RTL layout (`layout_rtl.tex`), even if `options.template` is set
      to something else.
- [ ] An invalid `options.template` value (e.g. `"template": "fancy"`)
      produces a clear error listing the allowed choices (`compact`,
      `default`, `rtl`).

## 4. Unchanged-file skip behavior

- [ ] Running the same command twice in a row skips all files the second
      time with a "no changes detected" message.
- [ ] Editing a cover-letter JSON and re-running causes only that file to
      be re-processed.

## 5. Template change invalidation

- [ ] Editing any file in `templates/cover_letter/` (e.g. `layout.tex`)
      causes **all** cover letters to be re-generated on the next run.
- [ ] Editing a CV-only template (e.g. `templates/header.tex`) does **not**
      invalidate cover-letter cache entries.

## 6. Cache versioning

- [ ] Deleting `.cvgen_cache.json` and re-running regenerates everything.
- [ ] Manually editing `.cvgen_cache.json` to have a different
      `__cache_version__` causes all entries to be discarded (full rebuild).

## 7. Coexistence with CV generation

- [ ] After generating both CVs and cover letters, the `output/` directory
      contains both `*_cover_letter.pdf` and CV PDFs without conflicts.
- [ ] Cache keys for CVs and cover letters use different prefixes (`""` vs
      `"cl:"`), so one never shadows the other.

## 8. Validation & error messages

- [ ] A JSON file missing `meta.type` or with `meta.type != "cover_letter"`
      is skipped with a message that names the expected value.
- [ ] A JSON file missing one or more of `sender`, `recipient`, `letter`,
      `sections` is skipped with a message listing every missing field.
- [ ] `--output-path out.pdf` with multiple input files produces a clear
      error explaining that a PDF path requires exactly one input file.

## 9. Automated test suite

- [ ] `python -m pytest tests/ -v` passes with zero failures.
- [ ] `python scripts/smoke_validate.py --cover-letters` validates all
      shipped data files without errors.
