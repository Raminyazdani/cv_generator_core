# ADR-001 — Cover Letter Generation Architecture

| Field       | Value                                |
|-------------|--------------------------------------|
| **Status**  | Accepted                             |
| **Date**    | 2026-03-10                           |
| **Author**  | Architecture review                  |
| **Issue**   | #1 — Design and lock the cover-letter feature architecture |

---

## Context

The project currently generates PDF documents exclusively from CV JSON files:

- Input data lives in `data/cvs/` as structured JSON.
- Jinja2 templates under `templates/` render individual sections (`header.tex`, `education.tex`, …) and merge them via a layout template (`layout.tex` / `layout_rtl.tex`).
- The Awesome-CV LaTeX class (`awesome-cv.cls`, `awesome-cv-rtl.cls`) provides styling.
- `generate_cv.py` orchestrates the full pipeline: file gathering → change detection → Jinja rendering → xelatex compilation → PDF output.
- A SHA-256 hash cache (`.cvgen_cache.json`) avoids reprocessing unchanged inputs.
- Language is parsed from the filename (`name_lang.json`), and RTL languages trigger alternate layout/class selection.

Cover letters differ from CVs in both data schema and rendered structure.
A cover letter typically contains an addressee, a subject line, a date, a greeting, body paragraphs, and a closing — none of which map to the CV section templates.
Forcing cover-letter logic into the CV-only pipeline would tangle the two document types and make both harder to maintain.

This ADR defines the architecture that allows cover-letter generation to coexist cleanly with CV generation.

---

## Decision Summary

| Concern                  | Decision                                                                                 |
|--------------------------|------------------------------------------------------------------------------------------|
| Input directory          | `data/cover_letter_datas/` (matches requested name); CLI `--input-path` override allowed |
| Output directory         | Same `--output-path` mechanism as CVs; default `./output`                                |
| Intermediate files       | `result/<base_name>/<lang>/cover_letter/` subtree                                        |
| Templates                | `templates/cover_letter/` dedicated namespace                                            |
| Generator architecture   | Extract shared helpers; add parallel `process_cover_letter_file()` orchestrator           |
| Cache                    | Single `.cvgen_cache.json` with prefixed keys (`cl:<path>`)                              |
| CLI                      | New `--type` flag (`cv` default, `cover-letter`); optional dedicated entry point later   |
| Translation / RTL        | Reuse existing `lang.json`, filename-based language parsing, and RTL layout selection     |

---

## 1  Input Directory Strategy

### Decision

| Item | Value |
|------|-------|
| Default directory | `data/cover_letter_datas/` |
| CLI override | `--input-path <dir-or-file>` (shared with CVs) |

### Rationale

The issue names `data/cover_letter_datas/` as the expected directory.
Although the plural form is unconventional, it is kept as-is for backward compatibility with the initial feature request.

The existing positional `files` argument and `gather_input_files()` already support arbitrary directories and file lists.
Adding `--input-path` as a named alias is optional; the positional argument already handles this:

```bash
python generate_cv.py --type cover-letter data/cover_letter_datas/
```

When no positional files are given and `--type cover-letter` is active, the default directory switches from `data/cvs/` to `data/cover_letter_datas/`.

### Folder layout

```
data/
├── cvs/                      # CV JSON files (existing)
│   ├── ramin_en.json
│   └── ...
├── cover_letter_datas/        # Cover letter JSON files (new)
│   ├── ramin_google_en.json
│   └── ...
└── pics/                      # Shared photos (existing)
```

### Cover Letter JSON Schema (proposed)

A cover letter JSON file uses a distinct top-level schema:

```json
{
  "meta": {
    "type": "cover_letter"
  },
  "basics": {
    "fname": "Ramin",
    "lname": "Yazdani",
    "email": "ramin@example.com",
    "phone": { "formatted": "+49 123 456 789" },
    "location": {
      "city": "Saarbrücken",
      "country": "Germany"
    }
  },
  "recipient": {
    "company": "Google",
    "department": "Engineering",
    "contact_name": "Dr. Jane Smith",
    "contact_title": "Hiring Manager",
    "address": {
      "street": "123 Main St",
      "city": "Munich",
      "postalCode": "80331",
      "country": "Germany"
    }
  },
  "letter": {
    "date": "2026-03-10",
    "subject": "Application for Software Engineer Position",
    "greeting": "Dear Dr. Smith,",
    "opening": "I am writing to express my interest in ...",
    "body": [
      "In my current role at ...",
      "My experience in ..."
    ],
    "closing": "I look forward to discussing ...",
    "sign_off": "Sincerely,"
  }
}
```

Key differences from CV JSON:

| Aspect | CV | Cover Letter |
|--------|-----|-------------|
| `basics` | Array of objects | Single object |
| Section keys | `education`, `experiences`, `skills`, … | `recipient`, `letter` |
| Identification | `meta.type` absent or `"cv"` | `meta.type == "cover_letter"` |

The `meta.type` field allows auto-detection when the `--type` flag is omitted, providing a fallback heuristic.

---

## 2  Output Strategy

### Decision

| Item | Value |
|------|-------|
| Default output directory | `./output` (same as CVs) |
| CLI control | `--output-path` (existing argument, shared) |
| Naming convention | `<base_name>_<lang>_cover_letter.pdf` |
| Co-location | CV and cover letter PDFs may share the same output directory |

### Rationale

Cover letter PDFs use a `_cover_letter` suffix in the filename to avoid collision with CV PDFs that use `<base_name>_<lang>.pdf`.

Examples:

```
output/
├── ramin_en.pdf                      # CV
├── ramin_en_cover_letter.pdf         # Cover letter
├── ramin_de.pdf                      # CV (German)
└── ramin_google_en_cover_letter.pdf  # Cover letter for Google
```

The `--output-path` argument works identically for both document types:
- Directory target: PDFs written into that directory.
- PDF file target: only valid for a single input file (existing constraint).

---

## 3  Result / Intermediate Directory Strategy

### Decision

Cover letter intermediate files live under a dedicated `cover_letter/` subdirectory within the existing `result/<base_name>/<lang>/` tree.

```
result/
└── ramin/
    └── en/
        ├── sections/                # CV sections (existing)
        │   ├── header.tex
        │   ├── education.tex
        │   └── ...
        ├── rendered.tex             # CV final layout (existing)
        ├── cover_letter/            # Cover letter intermediates (new)
        │   ├── sections/
        │   │   ├── header.tex
        │   │   ├── recipient.tex
        │   │   └── body.tex
        │   └── rendered.tex         # Cover letter final layout
```

### Rationale

- **No collisions**: The `cover_letter/` subtree is completely isolated from CV files in the same `result/<name>/<lang>/` directory.
- **Consistent structure**: Both document types follow the `sections/ → rendered.tex` pattern.
- **Debuggable**: Intermediate files remain inspectable for both document types side by side.
- **Cleanup**: The existing `rmtree_reliable()` utility can target either subtree independently.

---

## 4  Template Strategy

### Decision

Cover letter templates live in a dedicated `templates/cover_letter/` subdirectory.

```
templates/
├── layout.tex                  # CV LTR layout (existing)
├── layout_rtl.tex              # CV RTL layout (existing)
├── header.tex                  # CV header (existing)
├── education.tex               # CV education (existing)
├── ...                         # Other CV sections (existing)
└── cover_letter/               # Cover letter templates (new)
    ├── layout.tex              # Cover letter LTR layout
    ├── layout_rtl.tex          # Cover letter RTL layout
    ├── header.tex              # Sender + recipient info
    ├── recipient.tex           # Addressee block
    └── body.tex                # Greeting, paragraphs, closing
```

### Rationale

- **No reuse of CV section templates**: Cover letter sections have entirely different data and structure. Sharing `header.tex` or `experience.tex` would create fragile conditional branching.
- **Shared Jinja2 environment**: The custom delimiters (`<BLOCK>`, `<VAR>`, `/*/*/*`), filters (`latex_escape`, `tr`, `cmt`), and globals (`t()`, `LANG`, `IS_RTL`) are document-type agnostic. Cover letter templates reuse the same Jinja2 `Environment` configuration.
- **Shared LaTeX class**: Cover letter layouts reference the same `awesome-cv.cls` / `awesome-cv-rtl.cls` for consistent styling (fonts, colors, spacing). The `\makecvheader`, `\makelettertitle`, `\makeletterclosing` commands from Awesome-CV are designed for this.
- **Clear namespace**: `templates/cover_letter/` prevents naming collisions and makes template discovery unambiguous. The section template listing in `main()` filters by subdirectory based on document type.

### Template variable contract

Cover letter templates receive these variables:

| Variable | Source |
|----------|--------|
| `basics` | `data.basics` (single object, not array) |
| `recipient` | `data.recipient` |
| `letter` | `data.letter` |
| `LANG`, `IS_RTL`, `BASE_NAME` | Computed from filename (same as CV) |
| `t()`, `tr`, `tr_raw` | Translation helpers (same as CV) |
| `SHOW_COMMENTS` | Global setting (same as CV) |

---

## 5  Generator Architecture

### Decision

Extract shared infrastructure from `generate_cv.py` into reusable helpers. Keep document-type-specific orchestration in separate functions.

### Current state (CV only)

```
generate_cv.py
├── Settings (paths, constants)
├── Cache management (load_cache, save_cache, compute_file_hash, ...)
├── File gathering (gather_input_files, resolve_output_target)
├── Utilities / filters (latex_escape, cmt, find_pic, ...)
├── Language (parse_cv_filename, load_lang_map, make_translate_func, ...)
├── process_cv_file()         ← CV-specific orchestration
├── main()                    ← CLI entry point
└── Cleanup utilities
```

### Proposed state

```
generate_cv.py
├── Settings (paths, constants)                          # shared
├── Cache management                                     # shared
├── File gathering                                       # shared
├── Utilities / filters                                  # shared
├── Language detection & translation                     # shared
├── Jinja environment factory                            # shared (new)
│   └── create_jinja_env(template_dir, lang_map, lang, base_name, is_rtl)
├── process_cv_file()                                    # CV-specific (existing)
├── process_cover_letter_file()                          # CL-specific (new)
├── main()                                               # updated CLI entry point
└── Cleanup utilities                                    # shared
```

### Key changes

1. **`create_jinja_env()` factory** — The Jinja2 `Environment` setup (currently inline in `process_cv_file()`) is extracted into a shared factory. Both `process_cv_file()` and `process_cover_letter_file()` call this factory with the same configuration. This eliminates duplication of filter/global registration.

2. **`process_cover_letter_file()`** — A new function parallel to `process_cv_file()`. It:
   - Loads cover letter JSON.
   - Validates the cover-letter schema (`recipient`, `letter` keys).
   - Discovers section templates from `templates/cover_letter/`.
   - Writes intermediate files to `result/<name>/<lang>/cover_letter/`.
   - Selects `cover_letter/layout.tex` or `cover_letter/layout_rtl.tex`.
   - Compiles with xelatex.
   - Names the output PDF with `_cover_letter` suffix.

3. **`main()` update** — Routes to either `process_cv_file()` or `process_cover_letter_file()` based on the `--type` flag.

4. **No separate script** — Both document types are served from a single `generate_cv.py` entry point initially. A dedicated `generate_cover_letter.py` wrapper can be added later as a thin alias if warranted, but is not required for the initial implementation.

### What stays unchanged

- `parse_cv_filename()` — Works identically for cover letter filenames.
- `gather_input_files()` — Already handles arbitrary directories/files.
- `resolve_output_target()` — Works for any document type.
- `load_cache()` / `save_cache()` — Cache format is extended, not replaced.
- All existing filters and utilities.

---

## 6  Cache Strategy

### Decision

Extend the existing `.cvgen_cache.json` with prefixed keys to distinguish document types.

### Current format

```json
{
  "/absolute/path/data/cvs/ramin_en.json": "sha256hash..."
}
```

### Proposed format

```json
{
  "cv:/absolute/path/data/cvs/ramin_en.json": "sha256hash...",
  "cl:/absolute/path/data/cover_letter_datas/ramin_google_en.json": "sha256hash..."
}
```

### Key changes

1. **Prefixed keys** — `cv:` for CV entries, `cl:` for cover letter entries. This prevents collisions if a CV and a cover letter share the same filename path. Existing unprefixed entries are treated as `cv:` for backward compatibility.

2. **Template change detection** — The current cache only tracks JSON input file hashes. Cover letter implementation should extend the hash to include template file hashes as well:
   ```python
   combined_hash = hash(json_content + template_content)
   ```
   This ensures that template edits trigger regeneration. This improvement applies to both CVs and cover letters but is introduced as part of the cover letter work.

3. **Shared asset awareness** — Changes to `awesome-cv.cls` or layout templates should also invalidate the cache. This can be done by including the layout template hash in the combined hash, or by adding a separate `_layout_hash` entry that, when changed, invalidates all entries.

### Migration

- On first run after migration, existing unprefixed cache keys still match via a compatibility check in `has_file_changed()`.
- New entries are written with the prefix.
- Old entries are cleaned up when the cache is rewritten.

---

## 7  CLI Strategy

### Decision

Add a `--type` flag to the existing CLI. Default is `cv`.

### Interface

```bash
# CV generation (unchanged)
python generate_cv.py
python generate_cv.py data/cvs/ramin_en.json
python generate_cv.py --verbose --output-path ./pdfs

# Cover letter generation
python generate_cv.py --type cover-letter
python generate_cv.py --type cover-letter data/cover_letter_datas/ramin_google_en.json
python generate_cv.py --type cover-letter --verbose --output-path ./pdfs

# Explicit CV (same as default)
python generate_cv.py --type cv
```

### Argument definition

```python
parser.add_argument(
    "--type",
    choices=["cv", "cover-letter"],
    default="cv",
    help="Document type to generate. Default: cv."
)
```

### Behavior

| `--type` | Default input dir | Processing function | Output naming |
|----------|-------------------|---------------------|---------------|
| `cv` | `data/cvs/` | `process_cv_file()` | `<name>_<lang>.pdf` |
| `cover-letter` | `data/cover_letter_datas/` | `process_cover_letter_file()` | `<name>_<lang>_cover_letter.pdf` |

The positional `files` argument overrides the default directory for either type.

### Future consideration

If the project grows to support more document types, the `--type` flag naturally extends to additional choices. A dedicated `generate_cover_letter.py` script could be added as a convenience alias:

```python
# generate_cover_letter.py
import generate_cv
import sys
sys.argv.insert(1, "--type")
sys.argv.insert(2, "cover-letter")
generate_cv.main()
```

This is not required for the initial implementation.

---

## 8  Translation / RTL Strategy

### Decision

Cover letters reuse the existing translation and RTL infrastructure without modification.

### Language detection

Cover letter filenames follow the same convention as CVs:

```
ramin_google_en.json  →  base_name="ramin_google", lang="en"
ramin_google_de.json  →  base_name="ramin_google", lang="de"
ramin_google_fa.json  →  base_name="ramin_google", lang="fa"
```

The existing `parse_cv_filename()` handles this correctly since it matches the last `_<lang>` or `-<lang>` segment.

### Translation

- The `lang.json` file in `Lang_engine/` is extended with cover-letter-specific translation keys:

```json
{
  "cover_letter_subject": {
    "en": "Subject",
    "de": "Betreff",
    "fa": "موضوع"
  },
  "cover_letter_date": {
    "en": "Date",
    "de": "Datum",
    "fa": "تاریخ"
  }
}
```

- The `t()` function, `|tr`, and `|tr_raw` filters work identically in cover letter templates.
- New translation keys are namespaced with a `cover_letter_` prefix to avoid collisions with CV keys.

### RTL support

- Cover letters support RTL from day one.
- When `lang in RTL_LANGUAGES`, the cover letter pipeline selects `templates/cover_letter/layout_rtl.tex` and uses `awesome-cv-rtl.cls`.
- This matches the existing CV behavior exactly.

---

## Migration Impact on Current Code

### Files modified

| File | Change | Risk |
|------|--------|------|
| `generate_cv.py` | Extract `create_jinja_env()` factory; add `process_cover_letter_file()`; update `main()` with `--type` argument; update `cache_key_for_path()` to support prefixed keys | Medium — core file but changes are additive |
| `Lang_engine/lang.json` | Add cover-letter translation keys | Low — additive only |

### Files added

| File | Purpose |
|------|---------|
| `data/cover_letter_datas/` | Default input directory (initially empty or with an example) |
| `templates/cover_letter/layout.tex` | Cover letter LTR layout |
| `templates/cover_letter/layout_rtl.tex` | Cover letter RTL layout |
| `templates/cover_letter/header.tex` | Sender information |
| `templates/cover_letter/recipient.tex` | Addressee block |
| `templates/cover_letter/body.tex` | Letter body |
| `tests/test_cover_letter.py` | Cover-letter-specific tests |
| `scripts/example/minimal_cover_letter.json` | Minimal example |
| `docs/ADR-001-cover-letter-architecture.md` | This document |

### Files unchanged

| File | Reason |
|------|--------|
| `awesome-cv.cls` | Already supports letter commands (`\makelettertitle`, etc.) |
| `awesome-cv-rtl.cls` | Already supports RTL letter commands |
| `templates/header.tex` | CV-only; cover letters have their own header template |
| All other `templates/*.tex` | CV section templates; not shared with cover letters |
| `tests/test_cli_paths.py` | Existing tests continue to pass; no CV behavior changes |

---

## Risks and Trade-offs

### Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Cache key migration breaks existing cached entries | Low | Backward-compatible: unprefixed keys treated as `cv:` |
| Template changes silently missed by cache | Medium | Include template hash in combined cache hash |
| `parse_cv_filename()` mis-parses multi-segment cover letter names (e.g., `ramin_google_en.json`) | Low | Function already handles this correctly — it extracts the *last* `_<lang>` segment |
| Cover letter JSON schema evolves independently | Medium | Document schema in this ADR; validate with a JSON schema later |
| Single `generate_cv.py` grows too large | Low | The Jinja env factory extraction and separate `process_*` functions keep concerns separated; further splitting into modules is possible later |

### Trade-offs

| Trade-off | Chosen direction | Alternative considered |
|-----------|-----------------|----------------------|
| Single entry point vs. separate scripts | Single `generate_cv.py` with `--type` flag | Separate `generate_cover_letter.py` — rejected to avoid duplicating CLI boilerplate; can be added as thin wrapper later |
| Shared output directory vs. separate | Shared, with filename suffix differentiation | Separate `output/cover_letters/` — rejected to keep the simple `--output-path` contract |
| Shared cache file vs. separate | Shared `.cvgen_cache.json` with prefixed keys | Separate `.cvgen_cl_cache.json` — rejected to avoid managing two cache lifecycles |
| Folder name `cover_letter_datas` vs. `cover_letters` | `cover_letter_datas` (per issue requirement) | `cover_letters` — rejected for backward compatibility with the requested feature name |

---

## Final Folder Structure (complete)

```
cv_generator_core/
├── generate_cv.py                    # Unified generator (CV + cover letter)
├── awesome-cv.cls                    # LaTeX class - LTR
├── awesome-cv-rtl.cls               # LaTeX class - RTL
├── .cvgen_cache.json                 # Shared cache (prefixed keys)
│
├── data/
│   ├── cvs/                          # CV JSON inputs
│   ├── cover_letter_datas/           # Cover letter JSON inputs (new)
│   └── pics/                         # Shared photos
│
├── templates/
│   ├── layout.tex                    # CV LTR layout
│   ├── layout_rtl.tex               # CV RTL layout
│   ├── header.tex                   # CV header section
│   ├── education.tex                # CV education section
│   ├── experience.tex               # CV experience section
│   ├── skills.tex                   # CV skills section
│   ├── ... (other CV sections)
│   └── cover_letter/                 # Cover letter templates (new)
│       ├── layout.tex               # CL LTR layout
│       ├── layout_rtl.tex           # CL RTL layout
│       ├── header.tex               # Sender info
│       ├── recipient.tex            # Addressee block
│       └── body.tex                 # Letter body
│
├── result/                           # Intermediate rendered files
│   └── <name>/
│       └── <lang>/
│           ├── sections/             # CV sections
│           ├── rendered.tex          # CV final layout
│           └── cover_letter/         # CL intermediates (new)
│               ├── sections/
│               └── rendered.tex
│
├── Lang_engine/
│   ├── lang.json                    # Translation keys (extended)
│   └── ...
│
├── tests/
│   ├── test_cli_paths.py            # Existing CV tests
│   └── test_cover_letter.py         # Cover letter tests (new)
│
├── scripts/
│   └── example/
│       ├── minimal.json             # Minimal CV example
│       ├── empty.json               # Empty CV example
│       └── minimal_cover_letter.json # Minimal CL example (new)
│
└── docs/
    ├── ARG_PASSING_AND_CACHE_FIX_REPORT.md
    └── ADR-001-cover-letter-architecture.md  # This document
```

---

## Implementation Order (recommended)

The following issues should implement this architecture in order:

1. **Extract shared Jinja environment factory** from `process_cv_file()` — pure refactor, no behavior change.
2. **Add cover letter templates** in `templates/cover_letter/`.
3. **Add `process_cover_letter_file()`** function.
4. **Update `main()`** with `--type` flag and routing.
5. **Extend cache** with prefixed keys and template hash awareness.
6. **Add cover letter translation keys** to `lang.json`.
7. **Add tests** for cover letter pipeline.
8. **Add example cover letter JSON** and update documentation.

Each step can be implemented and tested independently.
