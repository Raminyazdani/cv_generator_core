# CV Generator – JSON → Awesome-CV PDF

Generate beautiful, professional PDF resumes from structured JSON using [Jinja2](https://jinja.palletsprojects.com/) templates and the [Awesome-CV](https://github.com/posquit0/Awesome-CV) LaTeX class.

This project takes one or more JSON CV files from `data/cvs/`, renders LaTeX using custom section templates in `templates/`, and compiles final PDFs (one per person) using `xelatex`.

---

## Table of Contents

- [Features](#features)  
- [Project Structure](#project-structure)  
- [Prerequisites](#prerequisites)  
- [Installation](#installation)  
- [Usage](#usage)  
  - [Running the generator](#running-the-generator)  
  - [Adding a new CV](#adding-a-new-cv)  
  - [Adding a profile picture](#adding-a-profile-picture)  
- [Data Format (JSON Schema Overview)](#data-format-json-schema-overview)  
  - [Basics](#basics)  
  - [Profiles / Social links](#profiles--social-links)  
  - [Education](#education)  
  - [Experience](#experience)  
  - [Skills](#skills)  
  - [Other Sections](#other-sections)  
- [Template System](#template-system)  
  - [Jinja2 configuration](#jinja2-configuration)  
  - [Available filters and helpers](#available-filters-and-helpers)  
  - [Main LaTeX layout](#main-latex-layout)  
- [Output and Intermediate Files](#output-and-intermediate-files)  
- [Troubleshooting](#troubleshooting)  
- [Development Notes](#development-notes)  
- [License](#license)  
- [Acknowledgements](#acknowledgements)

---

## Features

- **Multi-CV support**: Automatically generates a PDF for every JSON file in `data/cvs/`.
- **Beautiful layout**: Uses the popular Awesome-CV LaTeX class (`awesome-cv.cls`).
- **Modular sections**: Each CV section is a separate Jinja2/LaTeX template under `templates/`:
  - `header`, `education`, `experience`, `skills`, `language`, `projects`, `certificates`, `publications`, `references`, ...
- **Profile photo support**: Optional per-person images under `data/pics/`.
- **Robust cleanup**: Intermediate result directories are cleaned up reliably, with special handling for Windows file locks (e.g., OneDrive / antivirus).
- **Safe templating**: Uses `StrictUndefined` to catch missing fields early; custom LaTeX-escaping filter to avoid compilation errors.

---

## Project Structure

At a glance:

```text
cv_generator/
├─ awesome-cv.cls           # Awesome-CV LaTeX class (upstream)
├─ generate_cv.py           # Main script: JSON → LaTeX (Jinja2) → PDF
├─ README.md                # This file
├─ data/
│  ├─ cvs/                  # Input JSON CVs (one file per person)
│  │  ├─ mahsa.json
│  │  └─ ramin.json
│  └─ pics/                 # Optional profile photos
│     ├─ mahsa.jpg
│     └─ ramin.jpg
├─ output/                  # Final generated PDFs (e.g. mahsa.pdf, ramin.pdf)
├─ templates/               # Jinja2+LaTeX section templates
│  ├─ layout.tex            # Main document layout; includes sections inline
│  ├─ header.tex            # Personal info & social links
│  ├─ education.tex
│  ├─ experience.tex
│  ├─ skills.tex
│  ├─ language.tex
│  ├─ projects.tex
│  ├─ certificates.tex
│  ├─ publications.tex
│  ├─ references.tex
│  └─ ... (extendable)
└─ (generated at runtime)
   └─ result/               # Per-person intermediate .tex sections (auto‑cleaned)
      └─ <name>/sections/
         ├─ header.tex
         ├─ education.tex
         └─ ...
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

From the project root (`cv_generator`):

```bash
python generate_cv.py
```

What this does:

1. Loops over every JSON file in `data/cvs/` (e.g. `mahsa.json`, `ramin.json`).
2. For each person:
   - **Checks if the file has changed** since the last PDF generation (using hash-based caching).
   - If unchanged, skips PDF generation for that file.
   - If changed, creates `result/<name>/sections/`.
   - Renders each template in `templates/` with that person’s data into `result/<name>/sections/*.tex`.
   - Embeds all section content into `templates/layout.tex` and produces a combined LaTeX file `rendered.tex` in the same sections folder.
   - Runs `xelatex` to compile the LaTeX to a PDF in `output/`.
   - Cleans up non-PDF files in `output/`.
   - Renames the compiled `rendered.pdf` to `<name>.pdf` (e.g. `ramin.pdf`).
3. After processing all people, removes the `result/` directory using a Windows‑friendly cleanup helper.

Final PDFs are written to:

```text
output/<name>.pdf
```

For example:

- `output/mahsa.pdf`
- `output/ramin.pdf`


### Command-line options

The generator supports several command-line options:

```bash
# Process all JSON files (default behavior)
python generate_cv.py

# Process specific file(s) only
python generate_cv.py file1.json file2.json

# Enable verbose output for detailed processing information
python generate_cv.py --verbose
python generate_cv.py -v

# Combine options
python generate_cv.py --verbose file1.json file2.json
```

To see all available options:

```bash
python generate_cv.py --help
```

### Change detection and caching

The generator uses a **hash-based caching mechanism** to avoid regenerating PDFs for unchanged files:

- File hashes are stored in `.cvgen_cache.json` in the project root.
- Before processing each JSON file, the script compares its current hash with the cached hash.
- If the file hasn't changed, PDF generation is skipped.
- This significantly speeds up subsequent runs when only a few files have been modified.

To **force regeneration** of all PDFs:
1. Delete the `.cvgen_cache.json` file, or
2. Modify the JSON files you want to regenerate

### Verbose mode

Use the `--verbose` (or `-v`) flag to see detailed processing information:

```bash
python generate_cv.py --verbose
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
data/cvs/jane_doe.json
```

2. Follow the existing structure in `mahsa.json` or `ramin.json` (see [Data Format](#data-format-json-schema-overview) below).
3. Optionally add a matching photo (`data/pics/jane_doe.jpg`).
4. Run:

```bash
python generate_cv.py
```

You should get:

```text
output/jane_doe.pdf
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

The JSON schema is loosely based on [JSON Resume](https://jsonresume.org/) with some customizations. Look at `data/cvs/mahsa.json` and `data/cvs/ramin.json` for complete examples.

Below is a conceptual overview of key fields used by existing templates.

### Basics

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

### Profiles / Social links

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

### Education

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

### Experience

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

### Skills

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

### Other Sections

There are templates for:

- `language.tex` – language skills.
- `projects.tex` – projects overview.
- `certificates.tex` – certifications and awards.
- `publications.tex` – academic or professional publications.
- `references.tex` – references.

Their expected JSON structure follows the examples in `mahsa.json` and `ramin.json`. You can open each template under `templates/` to see exactly which keys are referenced and in what shape.

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

### Main LaTeX layout

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

---

## Output and Intermediate Files

- **Intermediate**:
  - `result/<name>/sections/*.tex` – one file per template.
  - `result/<name>/sections/rendered.tex` – final combined LaTeX document for that person.

- **Final**:
  - `output/<name>.pdf` – compiled PDF CV.

After generation completes, the script:

1. Cleans up non-PDF files in `output/`.
2. Renames `rendered.pdf` to `<name>.pdf`.
3. Recursively removes `result/` with a custom, retrying `rmtree_reliable()` function that:
   - Removes the read-only attribute on Windows.
   - Retries on `PermissionError` / certain `OSError` cases.
   - Works better around OneDrive / Explorer / antivirus file locks.

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

### Windows “Access is denied” when deleting `result/`

The script already includes robust cleanup logic (`rmtree_reliable`) with:

- Read-only flag clearing via `attrib`.
- Multiple retries with exponential backoff.

If you still hit issues, ensure:

- You’re not keeping `result/` open in an editor that locks files.
- OneDrive (or similar) isn’t aggressively syncing mid‑delete; pausing sync temporarily can help.

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

- **Adding a new section**:
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

- **Debugging template data**:
  - Use `|debug` or `|types` filters in templates to understand what’s being passed in.
  - Example:

    ```latex
    <VAR> basics | debug </VAR>
    ```

- **Commenting in templates**:
  - Use LaTeX comments (`%`) or the `cmt` / `cblock` filters.
  - Toggle `SHOW_COMMENTS` in `generate_cv.py` to control whether these get emitted.

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

