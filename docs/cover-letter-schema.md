# Cover Letter JSON Schema

This document defines the JSON schema for cover letter data files used by the CV Generator Core project.
Cover letter JSON files are stored in `data/cover_letter_datas/` and follow a structure distinct from the CV schema.

Each JSON file represents **one cover letter** for a specific job application.

---

## Overview

A cover letter JSON file has the following top-level keys:

| Key | Required | Description |
|-----|----------|-------------|
| `meta` | **Yes** | Document metadata; identifies the file as a cover letter |
| `sender` | **Yes** | Sender (applicant) information |
| `recipient` | **Yes** | Recipient / addressee information |
| `job` | No | Job and application metadata |
| `letter` | **Yes** | Letter metadata (date, salutation, closing, etc.) |
| `sections` | **Yes** | Ordered body content blocks |
| `options` | No | Rendering and layout options |

---

## 1  `meta` — Document Metadata

Identifies the document type and provides optional bookkeeping fields.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | **Yes** | Must be `"cover_letter"`. Used for auto-detection when `--type` is omitted. |
| `version` | string | No | Schema version for forward compatibility (e.g. `"1.0"`). |

```json
{
  "meta": {
    "type": "cover_letter",
    "version": "1.0"
  }
}
```

---

## 2  `sender` — Sender / Applicant Data

The sender section describes the person writing the cover letter.

It supports two modes:

1. **Inline sender data** — all fields provided directly in the cover letter JSON.
2. **CV reference with overrides** — a `cv_data_path` points to an existing CV JSON file; any inline fields override the corresponding CV values.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `cv_data_path` | string | No | Relative path to a CV JSON file (e.g. `"../cvs/ramin_en.json"`). When present, sender fields are populated from the CV `basics` section first, then overridden by any inline fields below. |
| `first_name` | string | **Yes**\* | Sender's first name. |
| `last_name` | string | **Yes**\* | Sender's last name. |
| `position` | string | No | Sender's current position / professional title. |
| `address` | string | No | Sender's postal address (single line or multiline with `\n`). |
| `mobile` | string | No | Phone number. |
| `email` | string | No | Email address. |
| `homepage` | string | No | Personal website URL. |
| `github` | string | No | GitHub username or URL. |
| `linkedin` | string | No | LinkedIn URL or username. |
| `photo` | string or object | No | Photo configuration. Can be a simple filename string (e.g. `"ramin.jpg"`) or a rich object (see below). |
| `quote` | string | No | A personal motto or tagline. Rendered as `\quote{...}` in the header. |

\* `first_name` and `last_name` are required unless `cv_data_path` is provided and the referenced CV contains `basics[0].fname` / `basics[0].lname`.

### Rich photo configuration

The `photo` field supports a rich object form for fine-grained control over photo rendering:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enabled` | boolean | **Yes** | Whether to include the photo. |
| `path` | string | **Yes** | Photo filename (without extension) or path. |
| `style` | array of strings | No | Awesome-CV photo style options (e.g. `["circle", "noedge", "left"]`). |

```json
{
  "photo": {
    "enabled": true,
    "path": "profile",
    "style": ["circle", "noedge", "left"]
  }
}
```

When a rich `photo` object is provided, it takes precedence over `options.show_photo`. If the rich object is absent, the legacy `options.show_photo` boolean is used as a fallback.

### Override / Fallback Rules

When `cv_data_path` is present:

1. Load the referenced CV JSON and read the first element of `basics`.
2. Map CV fields to sender fields:
   - `basics[0].fname` → `first_name`
   - `basics[0].lname` → `last_name`
   - `basics[0].label[0]` → `position`
   - `basics[0].phone` → `mobile`
   - `basics[0].email` → `email`
   - `basics[0].location[0]` → `address` (formatted from city, region, country)
   - `profiles` → `github`, `linkedin`, `homepage` (matched by `network` field)
   - `basics[0].Pictures[0].URL` → `photo`
3. Any inline sender field in the cover letter JSON **overrides** the corresponding CV value.
4. If neither the CV nor the inline field provides a value, the field is absent (treated as empty).

```json
{
  "sender": {
    "cv_data_path": "../cvs/ramin_en.json",
    "position": "Bioinformatics Researcher"
  }
}
```

In the example above, `first_name`, `last_name`, `email`, etc. come from the CV file, but `position` is overridden to `"Bioinformatics Researcher"`.

### Fully inline example

```json
{
  "sender": {
    "first_name": "Ramin",
    "last_name": "Yazdani",
    "position": "Bioinformatics Researcher",
    "address": "Saarbrücken, Germany",
    "mobile": "+49 123 456 789",
    "email": "ramin@example.com",
    "github": "Raminyazdani",
    "linkedin": "https://linkedin.com/in/raminyazdani"
  }
}
```

---

## 3  `recipient` — Recipient / Addressee Data

Supports both company-level addressing ("Dear Hiring Committee") and named-person addressing ("Dear Dr. Smith").

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `company` | string | **Yes**\* | Company or organization name. |
| `department` | string | No | Department or team within the company. |
| `person_name` | string | No | Full name of the recipient (e.g. `"Dr. Jane Smith"`). |
| `person_title` | string | No | Title or role of the recipient (e.g. `"Hiring Manager"`). |
| `address_lines` | array of strings | No | Street address lines (e.g. `["123 Main St", "Building A"]`). |
| `city` | string | No | City and postal code (e.g. `"80331 Munich"`). |
| `country` | string | No | Country name. |

\* At least one of `company` or `person_name` must be provided.

### Company-only example (no named person)

```json
{
  "recipient": {
    "company": "TechCorp GmbH",
    "department": "Engineering",
    "address_lines": ["Musterstraße 10"],
    "city": "10115 Berlin",
    "country": "Germany"
  }
}
```

### Named-person example

```json
{
  "recipient": {
    "company": "Google",
    "department": "Cloud AI Research",
    "person_name": "Dr. Jane Smith",
    "person_title": "Senior Hiring Manager",
    "address_lines": ["Erika-Mann-Straße 33"],
    "city": "80636 Munich",
    "country": "Germany"
  }
}
```

---

## 4  `job` — Job / Application Metadata

Optional section describing the target position. All fields are optional.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | No | Job title (e.g. `"Bioinformatics Research Engineer"`). |
| `reference` | string | No | Job posting reference number (e.g. `"REF-2026-1234"`). |
| `location` | string | No | Job location (e.g. `"Munich, Germany"`). |
| `posting_url` | string | No | URL of the job posting. |
| `team` | string | No | Team or group name within the company. |
| `start_date` | string | No | Expected or preferred start date (ISO 8601 or free text). |
| `employment_type` | string | No | Employment type (e.g. `"Full-time"`, `"Part-time"`, `"Contract"`). |

```json
{
  "job": {
    "title": "Bioinformatics Research Engineer",
    "reference": "REF-2026-1234",
    "location": "Munich, Germany",
    "posting_url": "https://careers.google.com/jobs/12345",
    "team": "Cloud AI Research",
    "start_date": "2026-06-01",
    "employment_type": "Full-time"
  }
}
```

---

## 5  `letter` — Letter Metadata

Controls the letter's date, salutation, closing, and output settings.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `date` | string | **Yes** | Letter date (ISO 8601 preferred, e.g. `"2026-03-10"`). |
| `title` | string | No | Optional letter title / subject line (e.g. `"Application for …"`). |
| `opening` | string | **Yes** | Salutation / greeting (e.g. `"Dear Dr. Smith,"` or `"Dear Hiring Committee,"`). |
| `closing` | string | **Yes** | Valediction / sign-off (e.g. `"Sincerely,"`, `"Best regards,"`). |
| `enclosures` | array of strings | No | List of enclosed documents (e.g. `["Curriculum Vitae", "Certificates"]`). |
| `signature_name` | string | No | Name printed below the closing. Defaults to `sender.first_name sender.last_name` when absent. |
| `language` | string | No | BCP 47 language code override (e.g. `"en"`, `"de"`). When absent, language is parsed from the filename. |
| `output_name` | string | No | Custom output PDF filename (without extension). When absent, follows the standard naming convention `<base_name>_<lang>_cover_letter`. |

```json
{
  "letter": {
    "date": "2026-03-10",
    "title": "Application for Bioinformatics Research Engineer",
    "opening": "Dear Dr. Smith,",
    "closing": "Sincerely,",
    "enclosures": ["Curriculum Vitae", "Academic Transcripts"],
    "signature_name": "Ramin Yazdani",
    "language": "en"
  }
}
```

---

## 6  `sections` — Body Content Model

The body of the cover letter is modeled as an **ordered array of content blocks**. Each block represents one logical section of the letter body.

### Block structure

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | **Yes** | Unique identifier for the section (e.g. `"motivation"`, `"experience"`, `"closing_remarks"`). Used for template targeting and CSS/class hooks. |
| `title` | string | No | Optional visible heading for the section. When absent, the section renders without a heading (typical for cover letters). |
| `content` | string or array | **Yes** | Section content. Can be a single paragraph string or an array of paragraph strings. |

### Content formats

**Simple string** — a single paragraph:

```json
{
  "id": "motivation",
  "content": "I am writing to express my strong interest in the Bioinformatics Research Engineer position."
}
```

**Array of paragraphs** — multiple paragraphs rendered in order:

```json
{
  "id": "experience",
  "content": [
    "In my current role as a researcher at Saarland University, I developed computational pipelines for multi-omics data integration.",
    "My work on single-cell RNA-seq analysis using Seurat and DESeq2 has been published in peer-reviewed journals."
  ]
}
```

### Full sections example

```json
{
  "sections": [
    {
      "id": "motivation",
      "content": "I am writing to express my interest in the open position."
    },
    {
      "id": "experience",
      "title": "Relevant Experience",
      "content": [
        "At Saarland University, I developed bioinformatics pipelines.",
        "I also contributed to open-source genomics tools."
      ]
    },
    {
      "id": "skills",
      "content": "My technical skills include Python, R, and cloud computing."
    },
    {
      "id": "closing_remarks",
      "content": "I would welcome the opportunity to discuss my qualifications further."
    }
  ]
}
```

### Design rationale

- **Ordered array** rather than a fixed-key object allows users to structure letters differently per application (e.g., some letters may lead with skills, others with motivation).
- **`id` field** enables template-level styling per section and serves as a stable reference for automation.
- **Optional `title`** supports both headed and unheaded sections; most cover letters do not use internal headings, but the option is available for formal or structured applications.
- **String or array `content`** keeps simple letters concise while supporting multi-paragraph sections.

---

## 7  `options` — Rendering Options

Optional settings that control how the cover letter is rendered.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `template` | string | No | `"default"` | Template/layout name. Supported values: `"default"`, `"compact"`, `"awesomecv_sectioned"`. |
| `layout_variant` | string | No | `"standard"` | Layout variant within the template (e.g. `"standard"`, `"compact"`, `"academic"`). |
| `color_theme` | string | No | Template default | Awesome-CV color theme (e.g. `"blue"`, `"red"`, `"darkgray"`). |
| `show_photo` | boolean | No | `false` | Whether to include the sender's photo (legacy; see `sender.photo` for rich config). |
| `rtl` | boolean | No | Auto-detected | Force RTL layout. When absent, RTL is auto-detected from the language. |
| `compile` | object | No | `{}` | Additional compilation options (passed through to the build pipeline). |
| `header_alignment` | string | No | Layout default | Header alignment for `\makecvheader`. Values: `"L"` (left), `"C"` (center), `"R"` (right). Used by `awesomecv_sectioned`. |
| `font_dir` | string | No | — | Font directory path (e.g. `"fonts/"`). Rendered as `\fontdir[...]`. Used by `awesomecv_sectioned`. |
| `geometry` | object | No | Layout default | Custom page geometry. Fields: `left`, `top`, `right`, `bottom`, `footskip` (all strings with LaTeX units). |
| `footer` | object | No | `{}` | Footer configuration. Supports `show_page_number` (boolean, default `true`). |

```json
{
  "options": {
    "template": "default",
    "color_theme": "blue",
    "show_photo": false
  }
}
```

### `awesomecv_sectioned` template example

```json
{
  "options": {
    "template": "awesomecv_sectioned",
    "color_theme": "red",
    "header_alignment": "R",
    "font_dir": "fonts/",
    "geometry": {
      "left": "1.0cm",
      "top": ".5cm",
      "right": "1.0cm",
      "bottom": "1.0cm",
      "footskip": ".25cm"
    },
    "footer": {
      "show_page_number": false
    }
  }
}
```

---

## 8  Validation Rules

### Required fields

The following fields **must** be present for a valid cover letter:

| Path | Rule |
|------|------|
| `meta.type` | Must equal `"cover_letter"` |
| `sender.first_name` | Required (or provided via `cv_data_path`) |
| `sender.last_name` | Required (or provided via `cv_data_path`) |
| `recipient.company` OR `recipient.person_name` | At least one must be present |
| `letter.date` | Required |
| `letter.opening` | Required |
| `letter.closing` | Required |
| `sections` | Must be a non-empty array with at least one section |
| `sections[*].id` | Required for each section |
| `sections[*].content` | Required for each section (string or non-empty array) |

### Optional fields — allowed empty

The following fields may be absent or empty without causing errors:

- `sender.position`, `sender.address`, `sender.mobile`, `sender.email`, `sender.homepage`, `sender.github`, `sender.linkedin`, `sender.photo`, `sender.quote`
- `recipient.department`, `recipient.person_name`, `recipient.person_title`, `recipient.address_lines`, `recipient.city`, `recipient.country`
- All `job.*` fields
- `letter.title`, `letter.enclosures`, `letter.signature_name`, `letter.language`, `letter.output_name`
- `sections[*].title`
- All `options.*` fields

### Fallback behavior

| Scenario | Behavior |
|----------|----------|
| `sender.cv_data_path` provided but file not found | Warning; use inline sender fields only |
| `sender.cv_data_path` provided but CV lacks a field | Field is treated as absent; inline override wins if present |
| `letter.signature_name` absent | Defaults to `"<sender.first_name> <sender.last_name>"` |
| `letter.language` absent | Parsed from filename (e.g. `ramin_google_en.json` → `"en"`) |
| `letter.output_name` absent | Uses `<base_name>_<lang>_cover_letter` |
| `options.rtl` absent | Auto-detected from language |
| `options.color_theme` absent | Uses template default |
| `options.show_photo` absent | Defaults to `false` |
| `options.template` absent | Defaults to `"default"` |

---

## Complete Example

```json
{
  "meta": {
    "type": "cover_letter",
    "version": "1.0"
  },
  "sender": {
    "first_name": "Ramin",
    "last_name": "Yazdani",
    "position": "Bioinformatics Researcher",
    "address": "Saarbrücken, Germany",
    "mobile": "+49 123 456 789",
    "email": "ramin@example.com",
    "github": "Raminyazdani",
    "linkedin": "https://linkedin.com/in/raminyazdani"
  },
  "recipient": {
    "company": "Google",
    "department": "Cloud AI Research",
    "person_name": "Dr. Jane Smith",
    "person_title": "Senior Hiring Manager",
    "address_lines": ["Erika-Mann-Straße 33"],
    "city": "80636 Munich",
    "country": "Germany"
  },
  "job": {
    "title": "Bioinformatics Research Engineer",
    "reference": "REF-2026-1234",
    "location": "Munich, Germany",
    "posting_url": "https://careers.google.com/jobs/12345",
    "team": "Cloud AI Research",
    "start_date": "2026-06-01",
    "employment_type": "Full-time"
  },
  "letter": {
    "date": "2026-03-10",
    "title": "Application for Bioinformatics Research Engineer",
    "opening": "Dear Dr. Smith,",
    "closing": "Sincerely,",
    "enclosures": ["Curriculum Vitae", "Academic Transcripts"],
    "signature_name": "Ramin Yazdani"
  },
  "sections": [
    {
      "id": "motivation",
      "content": "I am writing to express my strong interest in the Bioinformatics Research Engineer position at Google Cloud AI Research."
    },
    {
      "id": "experience",
      "content": [
        "During my Master's studies in Bioinformatics at Saarland University, I developed computational pipelines for multi-omics data integration.",
        "My hands-on experience with single-cell RNA-seq analysis using Seurat and DESeq2 directly aligns with the requirements of this role."
      ]
    },
    {
      "id": "skills",
      "content": "I bring strong proficiency in Python, R, and cloud-based pipeline orchestration, complemented by practical experience with Docker, Kubernetes, and CI/CD workflows."
    },
    {
      "id": "closing_remarks",
      "content": "I would welcome the opportunity to discuss how my background in bioinformatics and software development can contribute to your team's goals."
    }
  ],
  "options": {
    "template": "default",
    "color_theme": "blue",
    "show_photo": false
  }
}
```

---

## Compatibility with ADR-001

This schema extends the structure proposed in [ADR-001](ADR-001-cover-letter-architecture.md) with the following additions:

| ADR-001 field | Schema equivalent | Notes |
|---------------|-------------------|-------|
| `basics` (single object) | `sender` | Renamed for clarity; `cv_data_path` adds reuse support |
| `recipient` | `recipient` | Extended with `person_name`, `person_title`, `address_lines` |
| `letter.subject` | `letter.title` | Renamed to `title` for consistency |
| `letter.greeting` | `letter.opening` | Renamed per issue specification |
| `letter.body` (array of strings) | `sections` (array of block objects) | Upgraded to structured blocks with `id` and optional `title` |
| `letter.sign_off` | `letter.closing` | Consolidated; `sign_off` was redundant with `closing` |
| — | `job` | New; not in ADR-001 |
| — | `options` | New; not in ADR-001 |
| — | `meta.version` | New; not in ADR-001 |

The `meta.type = "cover_letter"` marker is preserved exactly as specified in ADR-001 for auto-detection compatibility.

---

## Schema Extensibility

The schema is designed to support future needs without breaking changes:

- **New top-level keys** can be added alongside existing ones (e.g. `attachments`, `tracking`).
- **New section block types** can be introduced by adding a `type` field to section objects (default: `"paragraph"`).
- **New rendering options** can be added to the `options` object.
- **Localization** is supported via `letter.language`, filename-based detection, and the existing `Lang_engine/` translation infrastructure.
- **Multiple template families** are supported via `options.template`.
