# CV & Cover Letter Generator – JSON → Awesome-CV PDF

Generate beautiful, professional PDF **CVs** and **cover letters** from structured JSON using [Jinja2](https://jinja.palletsprojects.com/) templates and the [Awesome-CV](https://github.com/posquit0/Awesome-CV) LaTeX class.

This project takes JSON input files — CVs from `data/cvs/` or cover letters from `data/cover_letter_datas/` — renders LaTeX using custom section templates in `templates/`, and compiles final PDFs using `xelatex`.

---

## Table of Contents

- [Features](#features)  
- [Project Structure](#project-structure)  
- [Prerequisites](#prerequisites)  
- [Installation](#installation)  
- [Usage](#usage)  
  - [Running the generator](#running-the-generator)  
  - [Cover Letter Generation](#cover-letter-generation)  
  - [Adding a new CV](#adding-a-new-cv)  
  - [Adding a new Cover Letter](#adding-a-new-cover-letter)  
  - [Adding a profile picture](#adding-a-profile-picture)  
- [Data Format (JSON Schema Overview)](#data-format-json-schema-overview)  
  - [CV Data Format](#cv-data-format)  
  - [Cover Letter Data Format](#cover-letter-data-format)  
- [Template System](#template-system)  
  - [Jinja2 configuration](#jinja2-configuration)  
  - [Available filters and helpers](#available-filters-and-helpers)  
  - [Main LaTeX layout (CV)](#main-latex-layout-cv)  
  - [Cover Letter Templates](#cover-letter-templates)  
- [Output and Intermediate Files](#output-and-intermediate-files)  
- [Caching and Change Detection](#caching-and-change-detection)  
- [Troubleshooting](#troubleshooting)  
- [Development Notes](#development-notes)  
  - [Adding a New CV Template Section](#adding-a-new-cv-template-section)  
  - [Adding a New Cover Letter Layout](#adding-a-new-cover-letter-layout)  
  - [Architecture and Migration Notes](#architecture-and-migration-notes)  
- [License](#license)  
- [Acknowledgements](#acknowledgements)

---

## Features

- **Multi-CV support**: Automatically generates a PDF for every JSON file in `data/cvs/`.
- **Cover letter generation**: Generate professional cover letters from JSON files in `data/cover_letter_datas/` using the `--type cover-letter` flag.
- **Beautiful layout**: Uses the popular Awesome-CV LaTeX class (`awesome-cv.cls`).
- **Modular sections**: Each CV section is a separate Jinja2/LaTeX template under `templates/`:
  - `header`, `education`, `experience`, `skills`, `language`, `projects`, `certificates`, `publications`, `references`, ...
- **Cover letter templates**: Dedicated partial templates under `templates/cover_letter/` with three layout variants (standard, compact, RTL).
- **Profile photo support**: Optional per-person images under `data/pics/`.
- **CV data reuse**: Cover letters can reference an existing CV JSON file via `sender.cv_data_path`, so sender information is not duplicated.
- **Hash-based caching**: Change detection for both CVs and cover letters using SHA-256 hashing. Cover letters use a composite hash over the JSON file and all cover-letter templates.
- **Robust cleanup**: Intermediate result directories are cleaned up reliably, with special handling for Windows file locks (e.g., OneDrive / antivirus).
- **Safe templating**: Uses `StrictUndefined` to catch missing fields early; custom LaTeX-escaping filter to avoid compilation errors.

---

## Project Structure

At a glance:

```text
cv_generator/
├─ awesome-cv.cls               # Awesome-CV LaTeX class (upstream)
├─ awesome-cv-rtl.cls           # Awesome-CV RTL variant
├─ generate_cv.py               # CLI entry point: JSON → LaTeX (Jinja2) → PDF
├─ README.md                    # This file
│
├─ core/                        # Shared document-generation utilities
│  ├─ settings.py               # Paths, constants, configuration
│  ├─ cache.py                  # SHA-256 hash caching and change detection
│  ├─ cleanup.py                # Windows-friendly directory cleanup
│  ├─ compile.py                # LaTeX compilation and PDF finalization
│  ├─ files.py                  # File gathering and path resolution
│  ├─ jinja_env.py              # Jinja2 environment setup
│  ├─ language.py               # Language detection and translation
│  └─ latex.py                  # LaTeX escaping and utility functions
│
├─ cv/                          # CV-specific orchestration
│  └─ build.py                  # CV rendering pipeline
│
├─ cover_letter/                # Cover-letter-specific orchestration
│  └─ build.py                  # Cover letter rendering pipeline
│
├─ data/
│  ├─ cvs/                      # Input JSON CVs (one file per person)
│  │  ├─ ramin_en.json
│  │  └─ ...
│  ├─ cover_letter_datas/       # Input JSON cover letters (one file per application)
│  │  ├─ ramin_google_en.json
│  │  ├─ ramin_sap_de.json
│  │  └─ ramin_techcorp_en.json
│  └─ pics/                     # Optional profile photos
│     ├─ ramin.jpg
│     └─ ...
│
├─ templates/                   # Jinja2+LaTeX section templates (CV)
│  ├─ layout.tex                # Main CV document layout
│  ├─ layout_rtl.tex            # RTL CV document layout
│  ├─ header.tex, education.tex, experience.tex, skills.tex, ...
│  └─ cover_letter/             # Cover letter templates
│     ├─ layout.tex             # Standard cover letter layout
│     ├─ layout_compact.tex     # Compact cover letter layout
│     ├─ layout_rtl.tex         # RTL cover letter layout
│     ├─ sender_header.tex      # Sender contact info partial
│     ├─ recipient.tex          # Recipient/addressee partial
│     ├─ letter_meta.tex        # Date, title, salutation partial
│     ├─ body_sections.tex      # Body content partial
│     ├─ signature.tex          # Signature block partial
│     └─ enclosures.tex         # Enclosures list partial
│
├─ docs/                        # Documentation
│  ├─ ADR-001-cover-letter-architecture.md  # Architecture decision record
│  ├─ cover-letter-schema.md               # Full cover letter JSON schema
│  └─ ARG_PASSING_AND_CACHE_FIX_REPORT.md  # Cache/arg fix report
│
├─ scripts/                     # Utility scripts
│  ├─ smoke_validate.py         # Input validation (supports --cover-letters)
│  └─ ...
│
├─ tests/                       # Test suite
│  ├─ test_cli_paths.py
│  ├─ test_core_modules.py
│  ├─ test_cover_letter_cli.py
│  ├─ test_cover_letter_full.py
│  └─ test_cover_letter_templates.py
│
├─ Lang_engine/                 # Language/translation support
│  └─ ...
│
└─ (generated at runtime)
   ├─ result/                   # Per-person intermediate .tex files (auto-cleaned)
   │  └─ <name>/<lang>/
   │     ├─ cv/sections/        # CV section .tex files
   │     └─ cover_letter/sections/  # Cover letter section .tex files
   └─ output/                   # Final generated PDFs
```

---

## Prerequisites

### 1. Python

- **Python 3.9+** recommended.
- Required Python packages:
  - `jinja2`

Install with:

```bash
pip install jinja2
```

(If you prefer, you can create a `requirements.txt` with `jinja2` and run `pip install -r requirements.txt`.)

### 2. LaTeX (XeLaTeX)

You **must** have a LaTeX distribution installed that provides `xelatex` and the fonts/packages used by Awesome-CV. Popular options:

- **Windows**: [MiKTeX](https://miktex.org/) or [TeX Live](https://www.tug.org/texlive/)

Make sure `xelatex` is available in your `PATH`.

The generator calls (simplified):

```bash
xelatex -interaction=nonstopmode -output-directory=./output <rendered.tex>
```

on Windows via `cmd.exe`, so ensure this works from a normal command prompt.

---

## Installation

1. **Clone this repository**:

```bash
git clone https://github.com/<your-username>/cv_generator.git
cd cv_generator
```

2. **Create a virtual environment (optional but recommended)**:

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. **Install Python dependencies**:

```bash
pip install jinja2
```

4. **Verify LaTeX**:

```bash
xelatex --version
```

If this fails, install a LaTeX distribution and ensure `xelatex` is on `PATH`.

---

## Usage

### Running the generator

From the project root:

```bash
# Generate all CVs (default)
python generate_cv.py

# Generate all cover letters
python generate_cv.py --type cover-letter
```

#### CV generation

When run without options (or with `--type cv`), the generator:

1. Loops over every JSON file in `data/cvs/`.
2. For each person:
   - **Checks if the file has changed** since the last PDF generation (using hash-based caching).
   - If unchanged, skips PDF generation for that file.
   - If changed, creates `result/<name>/sections/`.
   - Renders each template in `templates/` with that person's data into `result/<name>/sections/*.tex`.
   - Embeds all section content into `templates/layout.tex` and produces a combined LaTeX file `rendered.tex`.
   - Runs `xelatex` to compile the LaTeX to a PDF in `output/`.
   - Cleans up non-PDF files in `output/`.
   - Renames the compiled `rendered.pdf` to `<name>.pdf`.
3. After processing all people, removes the `result/` directory using a Windows-friendly cleanup helper.

Final CVs are written to:

```text
output/<name>.pdf
```

### Cover Letter Generation

Cover letter generation uses the same CLI with the `--type cover-letter` flag. Input JSON files live in `data/cover_letter_datas/` and follow a different schema from CVs (see [Cover Letter Data Format](#cover-letter-data-format)).

#### How cover letters differ from CVs

| Aspect | CV | Cover Letter |
|--------|-----|-------------|
| Input directory | `data/cvs/` | `data/cover_letter_datas/` |
| Template folder | `templates/` | `templates/cover_letter/` |
| Intermediate output | `result/<name>/<lang>/cv/` | `result/<name>/<lang>/cover_letter/` |
| Output naming | `<name>.pdf` | `<base_name>_<lang>_cover_letter.pdf` |
| Cache key prefix | (none) | `cl:` |
| Change detection | SHA-256 of JSON file | Composite SHA-256 of JSON + all cover-letter templates |
| Layouts | `layout.tex`, `layout_rtl.tex` | `layout.tex`, `layout_compact.tex`, `layout_rtl.tex` |
| Sender data | Inline in JSON | Inline or referenced from a CV JSON via `cv_data_path` |

#### End-to-end examples

**Example 1** — Generate all cover letters:

```bash
python generate_cv.py --type cover-letter
```

This processes every `*.json` file in `data/cover_letter_datas/` and writes PDFs to `output/`.

**Example 2** — Generate a single cover letter:

```bash
python generate_cv.py --type cover-letter data/cover_letter_datas/ramin_google_en.json
```

Produces `output/ramin_google_en_cover_letter.pdf`.

**Example 3** — Generate to a custom output directory or single PDF:

```bash
# Custom output directory
python generate_cv.py --type cover-letter --output-path ./my_letters

# Single PDF with custom filename
python generate_cv.py --type cover-letter data/cover_letter_datas/ramin_google_en.json --output-path ./application.pdf
```

#### Layout selection

Cover letter layouts are selected from `templates/cover_letter/`:

| Layout key | Template file | When used |
|------------|---------------|-----------|
| `default` | `layout.tex` | Default for LTR languages |
| `compact` | `layout_compact.tex` | Set `"template": "compact"` in `options` |
| `rtl` | `layout_rtl.tex` | Auto-selected for RTL languages (fa, ar, he) |

To select a layout, set the `template` field in the cover letter JSON `options` block:

```json
{
  "options": {
    "template": "compact"
  }
}
```

### Command-line options

The generator supports several command-line options:

```bash
# Process all CVs (default behavior)
python generate_cv.py

# Process all cover letters
python generate_cv.py --type cover-letter

# Process specific file(s) only
python generate_cv.py file1.json file2.json

# Enable verbose output for detailed processing information
python generate_cv.py --verbose
python generate_cv.py -v

# Custom output directory
python generate_cv.py --output-path ./pdfs

# Combine options
python generate_cv.py --type cover-letter --verbose ramin_google_en.json
```

To see all available options:

```bash
python generate_cv.py --help
```

### Verbose mode

Use the `--verbose` (or `-v`) flag to see detailed processing information:

```bash
python generate_cv.py --verbose
python generate_cv.py --type cover-letter --verbose
```

Verbose output includes:
- Which files are being checked
- Which files are skipped (and why)
- Which templates are being rendered
- Cache operations (loading/saving)
- PDF generation commands

---

### Adding a new CV

1. Create a new JSON file under `data/cvs/`, e.g.:

```text
data/cvs/jane_doe_en.json
```

2. Follow the existing structure in `ramin_en.json` (see [CV Data Format](#cv-data-format) below).
3. Optionally add a matching photo (`data/pics/jane_doe.jpg`).
4. Run:

```bash
python generate_cv.py
```

You should get:

```text
output/jane_doe_en.pdf
```

---

### Adding a new Cover Letter

1. Create a new JSON file under `data/cover_letter_datas/`. The filename must end with `_<lang>.json` where `<lang>` is a two-letter language code:

```text
data/cover_letter_datas/jane_google_en.json
```

2. Structure the JSON with the required top-level keys. At minimum you need:

```json
{
  "meta": { "type": "cover_letter" },
  "sender": {
    "cv_data_path": "../cvs/jane_doe_en.json",
    "position": "Software Engineer"
  },
  "recipient": {
    "company": "Google",
    "department": "Engineering"
  },
  "letter": {
    "date": "2026-03-10",
    "opening": "Dear Hiring Team,",
    "closing": "Sincerely,"
  },
  "sections": [
    {
      "id": "motivation",
      "content": "I am writing to express my interest in the Software Engineer position."
    },
    {
      "id": "closing_remarks",
      "content": "I look forward to hearing from you."
    }
  ]
}
```

> **Tip:** Use `"cv_data_path"` in the `sender` block to pull name, email, and contact info from an existing CV file instead of duplicating it. Any field you specify inline will override the CV value. See [Cover Letter Data Format](#cover-letter-data-format) for all available fields.

3. Run:

```bash
python generate_cv.py --type cover-letter data/cover_letter_datas/jane_google_en.json
```

4. You should get:

```text
output/jane_google_en_cover_letter.pdf
```

---

### Adding a profile picture

The generator expects photos in `data/pics/` with the same base name as the JSON file:

- CV file: `data/cvs/ramin.json`
- Photo:   `data/pics/ramin.jpg`

The `header.tex` template uses:

- `find_pic(OPT_NAME)` and `get_pic(OPT_NAME)` to detect and include the photo.
- If no matching `<name>.jpg` is found, it falls back to checking for `./profile_square.jpg` (relative to the project root).

---

## Data Format (JSON Schema Overview)

This project supports two document types, each with its own JSON schema.

### CV Data Format

The CV JSON schema is loosely based on [JSON Resume](https://jsonresume.org/) with some customizations. Look at files in `data/cvs/` for complete examples.

Below is a conceptual overview of key fields used by existing templates.

#### Basics

Used mostly by `header.tex` and `layout.tex`:

```jsonc
{
  "basics": [
    {
      "fname": "Ramin",
      "lname": "Yazdani",
      "label": ["Data Scientist", "Machine Learning Engineer"],
      "location": [
        {
          "city": "Saarbrücken",
          "region": "Saarland",
          "postalCode": "66123",
          "country": "Germany"
        }
      ],
      "phone": {
        "formatted": "+49 (0) 123 456789"
      },
      "email": "user@example.com"
    }
  ]
}
```

Notes:

- `fname` / `lname` required for `\name{...}{...}`.
- `label` is an array and rendered as the position line (`\position{...}`) with separators.
- `location` is an array; only the first entry is used to build a formatted address.
- `phone.formatted` and `email` are optional but recommended.

#### Profiles / Social links

Rendered in `header.tex`:

```jsonc
{
  "profiles": [
    {
      "network": "Github",
      "username": "your-github-id"
    },
    {
      "network": "Google Scholar",
      "username": "Display Name",
      "uuid": "wpZDx1cAAAAJ"
    },
    {
      "network": "LinkedIn",
      "username": "your-linkedin-id"
    }
  ]
}
```

Supported `network` values in the current template:

- `"Github"` → `\github{...}`
- `"Google Scholar"` → `\googlescholar{uuid}{google scholar :,username}`
- `"LinkedIn"` → `\linkedin{...}`

Extend `header.tex` if you want more platforms.

#### Education

Rendered in `education.tex`:

```jsonc
{
  "education": [
    {
      "studyType": "M.Sc.",
      "area": "Computer Science",
      "institution": "Some University",
      "location": "City, Country",
      "startDate": "2019",
      "endDate": "2021"
    }
  ]
}
```

The section is shown only if `education|length > 1` (i.e., more than one entry). If you want it to appear with a single entry, you can adjust that condition in `templates/education.tex`.

#### Experience

Rendered in `experience.tex`:

```jsonc
{
  "experiences": [
    {
      "institution": "Company Name",
      "role": "Job Title",
      "location": "City, Country",
      "duration": "2020 – Present",
      "primaryFocus": "Main focus of role",
      "description": "Additional description or responsibilities"
    }
  ]
}
```

- Both `primaryFocus` and `description` are optional; if either is present, they are rendered as bullet points (`cvitems`).
- Section is shown only if `experiences|length > 1`.

#### Skills

Rendered in `skills.tex` with a custom, two-row layout:

```jsonc
{
  "skills": {
    "Technical Skills": {
      "Programming": [
        { "short_name": "Python" },
        { "short_name": "C++" },
        { "short_name": "JavaScript" }
      ],
      "Data Science": [
        { "short_name": "Pandas" },
        { "short_name": "NumPy" },
        { "short_name": "Scikit-learn" }
      ]
    },
    "Soft Skills": {
      "Communication": [
        { "short_name": "Public speaking" },
        { "short_name": "Technical writing" }
      ]
    }
  }
}
```

Structure:

- Top level: **sections** (e.g. `"Technical Skills"`, `"Soft Skills"`).
- Second level: **categories** (e.g. `"Programming"`, `"Data Science"`).
- Items: each item must have a `short_name` field, used in the skills list.

#### Other Sections

There are templates for:

- `language.tex` – language skills.
- `projects.tex` – projects overview.
- `certificates.tex` – certifications and awards.
- `publications.tex` – academic or professional publications.
- `references.tex` – references.

Their expected JSON structure follows the examples in the `data/cvs/` directory. You can open each template under `templates/` to see exactly which keys are referenced and in what shape.

### Cover Letter Data Format

Cover letter JSON files live in `data/cover_letter_datas/` and use a distinct schema from CVs. For the full schema specification with all fields and validation rules, see [`docs/cover-letter-schema.md`](docs/cover-letter-schema.md).

Each JSON file represents **one cover letter** for a specific job application. The top-level keys are:

| Key | Required | Description |
|-----|----------|-------------|
| `meta` | **Yes** | Must contain `"type": "cover_letter"` |
| `sender` | **Yes** | Applicant info — inline or referenced from a CV via `cv_data_path` |
| `recipient` | **Yes** | Company / addressee information |
| `job` | No | Job title, reference number, location, etc. |
| `letter` | **Yes** | Date, salutation, closing, enclosures |
| `sections` | **Yes** | Ordered array of body content blocks |
| `options` | No | Layout variant, color theme, photo toggle |

#### Sender data — CV reference vs. inline

The `sender` block supports two modes:

1. **CV reference with overrides** — point to an existing CV JSON file; only override what differs:

   ```json
   {
     "sender": {
       "cv_data_path": "../cvs/ramin_en.json",
       "position": "Bioinformatics Researcher"
     }
   }
   ```

2. **Fully inline** — provide all fields directly:

   ```json
   {
     "sender": {
       "first_name": "Ramin",
       "last_name": "Yazdani",
       "position": "Bioinformatics Researcher",
       "email": "ramin@example.com",
       "mobile": "+49 123 456 789",
       "address": "Saarbrücken, Germany"
     }
   }
   ```

#### Sections — body content

The body is an ordered array of content blocks. Each block has a unique `id` and `content` (string or array of paragraphs):

```json
{
  "sections": [
    {
      "id": "motivation",
      "content": "I am writing to express my interest in the position."
    },
    {
      "id": "experience",
      "content": [
        "At Saarland University, I developed bioinformatics pipelines.",
        "I also contributed to open-source genomics tools."
      ]
    },
    {
      "id": "closing_remarks",
      "content": "I look forward to discussing my qualifications."
    }
  ]
}
```

#### Rendering options

```json
{
  "options": {
    "template": "default",
    "color_theme": "blue",
    "show_photo": true
  }
}
```

Available `template` values: `"default"`, `"compact"`. RTL layout is auto-selected for RTL languages.

> See [`docs/cover-letter-schema.md`](docs/cover-letter-schema.md) for the complete field reference, validation rules, and a full annotated example.

---

## Template System

### Jinja2 configuration

`generate_cv.py` sets up the Jinja2 environment with custom delimiters to avoid conflicts with LaTeX:

- **Blocks**: `<BLOCK> ... </BLOCK>`
- **Variables**: `<VAR> ... </VAR>`
- **Comments**: `/*/*/* ... */*/*/`

Key configuration in `generate_cv.py`:

```python
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
    undefined=StrictUndefined,
)
```

Each JSON file is loaded into `data`, then expanded into `env_vars` (so top-level JSON keys become template variables). Additionally:

- `env_vars["OPT_NAME"] = <file base name>` (e.g. `"ramin"`), used for photo lookup.

### Available filters and helpers

The script registers several custom filters/globals:

- `latex_escape(s)` (filter)  
  Escapes LaTeX special characters: `\`, `&`, `%`, `$`, `#`, `_`, `{`, `}`, `~`, `^`.

- `file_exists(path)` (filter)  
  Returns `True` if the given path exists on disk.

- `debug(value)` / `types(value)` (filters)  
  Print debugging info to stdout during rendering; emit nothing in the LaTeX output.

- `cmt(s)` / `cblock(s)` (filters)  
  Emit single-line or multi-line LaTeX comments, gated by `SHOW_COMMENTS`.

- `find_pic(opt_name)` (filter)  
  Checks whether `./data/pics/<opt_name>.jpg` exists.

- `get_pic(opt_name)` (filter)  
  Returns the relative path `./data/pics/<opt_name>.jpg`.

You can use them in templates like:

```latex
<VAR> basics[0]["fname"] | latex_escape </VAR>
<BLOCK> if OPT_NAME | find_pic </BLOCK>
  \photo[circle,noedge,left]{<VAR> OPT_NAME | get_pic </VAR>}
<BLOCK> endif </BLOCK>
```

---

### Main LaTeX layout (CV)

`templates/layout.tex` is the root document:

- Uses `\documentclass[11pt, a4paper]{./awesome-cv}`.
- Reconfigures some macros and spacing for sections, bullets, and skills.
- Includes the header via:

  ```latex
  <VAR> header_section | default('') </VAR>
  ```

- Sets up the header and footer:

  ```latex
  \makecvheader

  \makecvfooter
    {\today}
    {<VAR> basics[0]["fname"] | latex_escape </VAR> <VAR> basics[0]["lname"] | latex_escape </VAR>~~~·~~~Curriculum Vitae}
    {\thepage}
  ```

- Inlines all section contents:

  ```latex
  <VAR> education_section    | default('') </VAR>
  <VAR> experience_section   | default('') </VAR>
  <VAR> publications_section | default('') </VAR>
  <VAR> language_section     | default('') </VAR>
  <VAR> certificates_section | default('') </VAR>
  <VAR> skills_section       | default('') </VAR>
  <VAR> projects_section     | default('') </VAR>
  <VAR> references_section   | default('') </VAR>
  ```

Each of these is filled by `generate_cv.py` after rendering the corresponding template file.

### Cover Letter Templates

Cover letter templates live in `templates/cover_letter/` and consist of **6 partial templates** and **3 layout variants**.

#### Partial templates (rendered in order)

| Template | Purpose |
|----------|---------|
| `sender_header.tex` | Sender name, title, contact information |
| `recipient.tex` | Recipient / addressee block |
| `letter_meta.tex` | Date, subject line, opening salutation |
| `body_sections.tex` | Body content paragraphs (iterates over `sections` array) |
| `signature.tex` | Closing and signature |
| `enclosures.tex` | List of enclosed documents |

Each partial is rendered into a variable named `<partial_name>_section` (e.g., `sender_header_section`, `body_sections_section`) and then embedded into the layout template.

#### Layout variants

| Layout | File | Description |
|--------|------|-------------|
| Standard | `layout.tex` | Default for LTR languages |
| Compact | `layout_compact.tex` | Tighter spacing for shorter letters |
| RTL | `layout_rtl.tex` | Right-to-left languages (Persian, Arabic, Hebrew) |

The layout is selected automatically based on the language or explicitly via the `options.template` field in the JSON.

---

## Output and Intermediate Files

- **Intermediate (CV)**:
  - `result/<name>/<lang>/cv/sections/*.tex` – one file per template.
  - `result/<name>/<lang>/cv/rendered.tex` – final combined LaTeX document.

- **Intermediate (Cover letter)**:
  - `result/<name>/<lang>/cover_letter/sections/*.tex` – one file per partial template.
  - `result/<name>/<lang>/cover_letter/rendered.tex` – final combined LaTeX document.

- **Final PDFs**:
  - CVs: `output/<name>.pdf`
  - Cover letters: `output/<base_name>_<lang>_cover_letter.pdf`

After generation completes, the script:

1. Cleans up non-PDF files in `output/`.
2. Renames `rendered.pdf` to the appropriate output name.
3. Recursively removes `result/` with a custom, retrying `rmtree_reliable()` function that:
   - Removes the read-only attribute on Windows.
   - Retries on `PermissionError` / certain `OSError` cases.
   - Works better around OneDrive / Explorer / antivirus file locks.

---

## Caching and Change Detection

The generator uses a **hash-based caching mechanism** to avoid regenerating PDFs for unchanged files. Hashes are stored in `.cvgen_cache.json` in the project root.

### CV caching

- Each CV JSON file is hashed individually (SHA-256).
- Cache key: the normalized file path (e.g., `data/cvs/ramin_en.json`).
- If the JSON file has not changed since the last successful build, PDF generation is skipped.

### Cover letter caching

- Cover letters use a **composite hash**: the JSON file **plus all template files** in `templates/cover_letter/` are hashed together.
- Cache key: prefixed with `cl:` (e.g., `cl:data/cover_letter_datas/ramin_google_en.json`).
- This means changing *any* cover letter template invalidates *all* cover letter caches, ensuring template edits always trigger a rebuild.

### Forcing regeneration

To force regeneration of all PDFs:
1. Delete the `.cvgen_cache.json` file, or
2. Modify the JSON files you want to regenerate

---

## Troubleshooting

### `xelatex` command not found

**Symptom**: Terminal shows something like:

> 'xelatex' is not recognized as an internal or external command

**Fix**:

- Install MiKTeX or TeX Live.
- Add the directory containing `xelatex.exe` to your `PATH`.
- Verify with:

  ```bash
  xelatex --version
  ```

### LaTeX compilation errors

**Symptom**: PDF is not produced, or LaTeX logs show errors.

Common causes:

- Unescaped special characters in JSON (e.g., `#`, `%`, `_`).
- Missing fields referenced in templates (due to `StrictUndefined`).

**Tips**:

- Wrap dynamic content with `| latex_escape` in templates when in doubt.
- Ensure all keys used in templates exist in your JSON data.
- Run:

  ```bash
  python generate_cv.py
  ```

  and watch for Jinja `TemplateError` messages, which include the template file name.

### Cover letter: missing required fields

**Symptom**: Output shows `Skipping <file>: missing required key '<key>'` or `not a cover letter (meta.type != 'cover_letter')`.

**Fix**:

- Ensure your JSON contains all required top-level keys: `meta`, `sender`, `recipient`, `letter`, `sections`.
- The `meta.type` field must be exactly `"cover_letter"`.
- Every section block must have an `id` and `content` field.
- See [`docs/cover-letter-schema.md`](docs/cover-letter-schema.md) for the complete list of required fields.

### Cover letter: bad template name

**Symptom**: The generator falls back to the default layout or raises a template error.

**Fix**:

- Valid `options.template` values are `"default"` and `"compact"`. Any unrecognized value falls back to the `"default"` layout.
- RTL layout is selected automatically when the language code is `fa`, `ar`, or `he` -- you do not set it via `options.template`.

### Stale cache -- changes not reflected

**Symptom**: You edited a JSON file or template, but the PDF did not regenerate.

**Possible causes**:

- The cache file `.cvgen_cache.json` still holds the old hash.
- For cover letters, the composite hash includes all `templates/cover_letter/*.tex` files. If you only changed an external file (e.g. `awesome-cv.cls`), the cache will not detect it.

**Fix**:

- Delete `.cvgen_cache.json` and re-run:

  ```bash
  rm .cvgen_cache.json
  python generate_cv.py --type cover-letter
  ```

### Windows "Access is denied" when deleting `result/`

The script already includes robust cleanup logic (`rmtree_reliable`) with:

- Read-only flag clearing via `attrib`.
- Multiple retries with exponential backoff.

If you still hit issues, ensure:

- You're not keeping `result/` open in an editor that locks files.
- OneDrive (or similar) isn't aggressively syncing mid-delete; pausing sync temporarily can help.

---
## Right-to-Left (RTL) and Farsi/Persian Support

This CV generator includes built-in support for right-to-left (RTL) languages, specifically Persian (Farsi) and Arabic.

### How It Works

The generator automatically detects RTL languages from the CV filename:
- `name_fa.json` - Persian (Farsi)
- `name_ar.json` - Arabic  
- `name_he.json` - Hebrew

When an RTL language is detected, the generator:
1. Uses `layout_rtl.tex` instead of `layout.tex`
2. Uses `awesome-cv-rtl.cls` which adds RTL support via polyglossia and bidi packages
3. Sets `IS_RTL = true` in template variables

### Requirements for RTL/Farsi CVs

1. **XeLaTeX compiler**: RTL support requires XeLaTeX (not pdfLaTeX). This is already the default compiler used by the generator.

2. **Persian Font**: You need a Persian-capable font installed on your system. The class tries these fonts in order:
   - **Vazirmatn** (recommended) - A modern, open-source Persian font
     - Download from: https://github.com/rastikerdar/vazirmatn
   - **XB Niloofar** - Classic Persian font
   - **B Nazanin** - Traditional Persian font

3. **LaTeX Packages**: Ensure you have these packages installed:
   - `polyglossia` - for multilingual support
   - `bidi` - for bidirectional text

### Creating a Farsi CV

1. Create your CV JSON file with a Farsi suffix:
   ```text
   data/cvs/yourname_fa.json
   ```

2. Use Persian text in your JSON data:
   ```json
   {
     "basics": [
       {
         "fname": "رامین",
         "lname": "یزدانی",
         "label": ["توسعه‌دهنده", "دانشمند داده"]
       }
     ]
   }
   ```

3. Run the generator:
   ```bash
   python generate_cv.py
   ```

4. The output PDF will be created with proper RTL layout:
   ```text
   output/yourname_fa.pdf
   ```

### Installing Vazirmatn Font

**Windows:**
1. Download `Vazirmatn.zip` from https://github.com/rastikerdar/vazirmatn/releases
2. Extract and install the `.ttf` files (right-click → Install)
3. Restart your LaTeX environment if it was running

**Linux:**
```bash
# Download and extract to fonts directory
wget https://github.com/rastikerdar/vazirmatn/releases/download/v33.003/vazirmatn-v33.003.zip
unzip vazirmatn-v33.003.zip -d ~/.local/share/fonts/
fc-cache -fv
```

**macOS:**
1. Download from https://github.com/rastikerdar/vazirmatn/releases
2. Double-click the `.ttf` files to install via Font Book

### Customizing RTL Templates

If you need to customize the RTL layout:

- **`templates/layout_rtl.tex`** - The main RTL document layout
- **`awesome-cv-rtl.cls`** - The RTL class file with font and direction settings

Both files are separate from their LTR counterparts to ensure backward compatibility.

---

## Development Notes

### Adding a New CV Template Section

1. Create a new template file in `templates/` (e.g. `volunteering.tex`).
2. Reference new JSON data in the template (`<VAR> volunteering ... </VAR>`).
3. `generate_cv.py` automatically picks up **all** files in `templates/` as section templates:

   ```python
   SECTION_TEMPLATES = [x for x in os.listdir(TEMPLATE_DIR)]
   ```

4. Add a line to `layout.tex` to embed it:

   ```latex
   <VAR> volunteering_section | default('') </VAR>
   ```

### Adding a New Cover Letter Layout

To create a new cover letter layout variant (e.g. `"academic"`):

1. **Create the layout template** in `templates/cover_letter/`, e.g. `layout_academic.tex`. Use `layout.tex` as a starting point. The layout receives all partial sections as variables:

   ```latex
   <VAR> sender_header_section | default('') </VAR>
   <VAR> recipient_section | default('') </VAR>
   <VAR> letter_meta_section | default('') </VAR>
   <VAR> body_sections_section | default('') </VAR>
   <VAR> signature_section | default('') </VAR>
   <VAR> enclosures_section | default('') </VAR>
   ```

2. **Register the layout** in `cover_letter/build.py` by adding an entry to the `CL_LAYOUTS` dictionary:

   ```python
   CL_LAYOUTS = {
       "default": "layout.tex",
       "compact": "layout_compact.tex",
       "rtl": "layout_rtl.tex",
       "academic": "layout_academic.tex",   # ← new
   }
   ```

3. **Use it** in a cover letter JSON file:

   ```json
   {
     "options": {
       "template": "academic"
     }
   }
   ```

4. To add a new **partial template** (e.g. a custom header), add the `.tex` file to `templates/cover_letter/` and list its filename in the `CL_PARTIAL_TEMPLATES` array in `cover_letter/build.py`. The rendered content will be available as `<name>_section` in the layout template.

### Debugging template data

- Use `|debug` or `|types` filters in templates to understand what's being passed in.
- Example:

  ```latex
  <VAR> basics | debug </VAR>
  ```

### Commenting in templates

- Use LaTeX comments (`%`) or the `cmt` / `cblock` filters.
- Toggle `SHOW_COMMENTS` in `core/settings.py` to control whether these get emitted.

### Architecture and Migration Notes

The codebase was refactored from a single `generate_cv.py` into a modular package structure:

| Package | Purpose |
|---------|---------|
| `core/` | Document-agnostic utilities: caching, file I/O, Jinja2 env, LaTeX compilation, language detection |
| `cv/` | CV-specific build orchestration (`process_cv_file()`) |
| `cover_letter/` | Cover-letter-specific build orchestration (`process_cover_letter_file()`) |
| `generate_cv.py` | Thin CLI wrapper that re-exports all public symbols from the above packages |

**Backward compatibility**: All public symbols previously available from `generate_cv.py` are still importable from it. Tests and scripts that `import generate_cv` continue to work unchanged.

**Adding a new document type** in the future:

1. Create a new package (e.g. `portfolio/`) with a `build.py` containing a `process_portfolio_file()` function.
2. Add a new `--type` choice in `generate_cv.py`'s argument parser.
3. Add templates under `templates/portfolio/`.
4. Add input data files under `data/portfolio_datas/`.
5. Add the new default directory path to `core/settings.py`.

---

## License

- The **Awesome-CV class** (`awesome-cv.cls`) is licensed under **LPPL v1.3c**: <http://www.latex-project.org/lppl>
- The **Awesome-CV template** design and layout are originally by:
  - Claud D. Park – <https://github.com/posquit0/Awesome-CV> – licensed under **CC BY-SA 4.0**.

For this repository’s own Python code and templates, choose and declare a license that fits your needs (e.g. MIT, Apache 2.0, GPL, etc.), and add a `LICENSE` file accordingly.

---

## Acknowledgements

- **Awesome-CV** by [posquit0](https://github.com/posquit0/Awesome-CV) for the class file and design.
- The Jinja2 project for the templating engine.
- LaTeX community and TeX distributions that make high‑quality PDF generation possible.

