# CV JSON Configuration Keys

| Key | Type | Required | Allowed / default | Purpose |
|---|---:|---:|---|---|
| `basics` | array | yes | min 1 item | Only code-required CV key. First item drives header/footer. |
| `config` | object | no | `{}` | Rendering/config values used by templates. |
| `profiles` | array | no | — | Social/profile links. |
| `education` | array | no | rendered only if length > 1 | Education entries. |
| `experiences` | array | no | rendered only if length > 1 | Work/research experience entries. |
| `skills` | object | no | rendered only if object length > 1 | Nested skill groups. |
| `languages` | array | no | rendered only if length > 1 | Language proficiency entries. |
| `workshop_and_certifications` | array | no | rendered only if length > 1 | Certificate/workshop groups. |
| `projects` | array | no | rendered only if length > 1 | Project entries. |
| `publications` | array | no | rendered only if length > 1 | Publication entries. |
| `references` | array | no | rendered only if length > 1 | Reference entries. |

| CV subkey | Type | Required | Allowed / default | Purpose |
|---|---:|---:|---|---|
| `config.lang` | string | no | filename is source of truth; examples: `en`, `de`, `fa`, `ar`, `he` | Stored language marker. |
| `config.ID` | string | no | — | Person/config identifier. |
| `config.color` | string | no | default `awesome-nephritis`; examples: `awesome-emerald`, `awesome-skyblue`, `awesome-red`, `awesome-pink`, `awesome-orange`, `awesome-nephritis`, `awesome-concrete`, `awesome-darknight` | Passed to `\colorlet{awesome}{...}`. |
| `config.no_cert` | boolean | no | `false` | Hides Certification/Workshop text in certificates. |
| `basics[0].fname` | string | template-required | — | First name. |
| `basics[0].lname` | string | template-required | — | Last name. |
| `basics[0].label` | string[] | template-required | — | Position line. |
| `basics[0].email` | string | template-required | — | Header email. |
| `basics[0].phone.formatted` | string | template-required if `phone` exists | — | Header phone. |
| `basics[0].location[0].city/region/postalCode/country` | string | template-used | — | Header address parts. |
| `basics[0].Pictures` | array | no | — | Used by cover-letter CV fallback, not by CV header photo lookup. |
| `profiles[].network` | string | yes per profile | rendered exact values: `GitHub`, `Google Scholar`, `LinkedIn`, `Website`; other values are ignored by current header template | Selects profile renderer. |
| `profiles[].username` | string | profile-dependent | — | GitHub/LinkedIn/Google Scholar display value. |
| `profiles[].uuid` | string | for `Google Scholar` | — | Scholar ID. |
| `profiles[].url` | string | for `Website` | — | Website URL. |
| `education[]` | object | no | keys: `studyType`, `area`, `institution`, `location`, `startDate`, `endDate`, optional `gpa`, `logo_url`, `type_key` | Education row. |
| `experiences[]` | object | no | keys: `role`, `duration`, optional `institution`, `location`, `primaryFocus`, `description`, `type_key` | Experience row and bullets. |
| `skills` | object | no | shape: `{sectionName: {categoryName: [{short_name, long_name?, type_key?}]}}` | `short_name` is rendered. |
| `languages[]` | object | no | keys: `language`, `proficiency`, `certifications` | Language row. |
| `proficiency.CEFR/level/status` | string/null | template-used | — | Rendered language level/status. |
| `certifications[0]` under language | object | no | `test`, `overall`, `maxScore`, `reading`, `listening`, `writing`, `speaking`, `examDate`, `URL` | Only first language certification is rendered. |
| `workshop_and_certifications[].issuer` | string | yes per group | — | Certificate group heading. |
| `certifications[].certificate` | boolean | no | `true` => Certification, `false` => Workshop | Certificate label. |
| `projects[].type_key` | string[] | template-required | exact filtered values: `Full CV`, `Academic` are removed before rendering | Project type labels. |
| `projects[].title/description/url` | string | `title`, `description` template-required; `url` optional | — | Project entry. |
| `publications[].type` | string | template-required | special branches: `Book Chapter`, `Master Thesis`, `Bachelor Thesis`, `PhD Thesis`, `Thesis`, `Dissertation`; other strings use journal/publisher branch | Publication type/status line. |
| `publications[].identifiers.doi` | string | no | — | DOI link. |
| `references[]` | object | no | keys: `name`, `position`, `department`, `institution`, `location`, `email[]`, `phone[]`, `URL` | Reference entry. |

# Cover Letter JSON Configuration Keys

| Key | Type | Required | Allowed / default | Purpose |
|---|---:|---:|---|---|
| `meta` | object | yes | `meta.type` must be `cover_letter` | Document marker; files are skipped if wrong/missing. |
| `sender` | object | yes | inline fields or `cv_data_path` | Applicant data. |
| `recipient` | object | yes | at least one of `company`, `person_name` in documented schema | Addressee block. |
| `job` | object | no | — | Application metadata; not directly rendered by fetched default templates. |
| `letter` | object | yes | — | Date, subject, salutation, closing, output name. |
| `sections` | array | yes | min 1 item | Ordered body paragraphs. |
| `options` | object | no | `{}` | Layout/rendering options. |

| Cover-letter subkey | Type | Required | Allowed / default | Purpose |
|---|---:|---:|---|---|
| `meta.type` | string | yes | exact `cover_letter` | Build validation. |
| `meta.version` | string | no | example `1.0` | Schema/version marker. |
| `sender.cv_data_path` | string | no | resolved relative to cover-letter JSON first | Load sender defaults from CV JSON. |
| `sender.first_name`, `sender.last_name` | string | required unless provided through CV fallback | — | Sender name. |
| `sender.position` | string or string[] | no | — | Professional title. |
| `sender.address`, `sender.mobile`, `sender.email` | string | no | — | Contact details. |
| `sender.homepage`, `sender.github`, `sender.linkedin` | string | no | — | Social/contact links. |
| `sender.photo` | string or object | no | string, or `{enabled, path, style}` | Photo config. String form depends on `options.show_photo`. |
| `sender.photo.enabled` | boolean | rich photo required | fallback `options.show_photo` if omitted by normalizer | Include photo. |
| `sender.photo.path` / `sender.photo.url` | string | rich photo required | checked with extensions: none, `.png`, `.jpg`, `.jpeg`, `.pdf`, `.webp` | Photo path. |
| `sender.photo.style` | string or string[] | no | examples: `circle`, `rectangle`, `edge`, `noedge`, `left`, `right` | Awesome-CV photo style options; not code-enforced. |
| `sender.quote` | string | no | — | Documented/tested for sectioned header; fetched template conflict noted below. |
| `recipient.company` | string | conditionally required | — | Company/organization. |
| `recipient.person_name` | string | conditionally required | — | Named recipient. |
| `recipient.person_title`, `department`, `address_lines`, `city`, `country` | string / string[] | no | `address_lines` default `[]` | Recipient address block. |
| `job.title`, `reference`, `location`, `posting_url`, `team`, `start_date`, `employment_type` | string | no | no enum | Job metadata. |
| `letter.date` | string | documented required | template fallback `\today` | Letter date. |
| `letter.title` | string | no | — | Subject/title. |
| `letter.opening` | string | documented required | — | Salutation. |
| `letter.closing` | string | documented required | — | Sign-off. |
| `letter.enclosures` | string[] | no | — | Joined as comma-separated enclosure list. |
| `letter.signature_name` | string | no | default `<sender.first_name> <sender.last_name>` | Signature override. |
| `letter.language` | string | no | filename-derived; RTL auto for `fa`, `ar`, `he` | Language override. |
| `letter.output_name` | string | no | default `<base_name>_<lang>_cover_letter`; `.pdf` appended if missing | Output filename. |
| `sections[].id` | string | yes | no enum | Stable section identifier. |
| `sections[].title` | string | no | — | Renders `\lettersection{...}`. |
| `sections[].content` | string or string[] | yes | — | Body paragraph(s). |
| `options.template` | string | no | default `default`; exact values: `default`, `compact`, `rtl`, `awesomecv_sectioned` | Layout selector. RTL mode overrides to RTL layout. |
| `options.layout_variant` | string | no | documented default `standard` | Documented but no direct use found in fetched code/templates. |
| `options.color_theme` | string | no | exact template branches: `blue`, `red`, `orange`, `pink`, `emerald`, `darkgray`, `concrete`; otherwise templates fall back | Theme color. |
| `options.show_photo` | boolean | no | `false` | Legacy photo toggle. |
| `options.rtl` | boolean | no | auto from language | Force RTL/LTR. |
| `options.compile.runs` | integer | no | `1`, min `1` | Number of XeLaTeX runs for cover letters. |
| `options.header_alignment` | string | no | `R` in `awesomecv_sectioned`; exact values `L`, `C`, `R` | Header alignment for sectioned layout. |
| `options.font_dir` | string | no | — | Emits `\fontdir[...]` in sectioned layout. |
| `options.geometry.left/top/right/bottom/footskip` | string | no | sectioned default `left=1.0cm, top=.5cm, right=1.0cm, bottom=1.0cm, footskip=.25cm` | Page geometry for sectioned layout. |
| `options.footer.show_page_number` | boolean | no | `true` | Sectioned layout page-number toggle. |

Conflict/uncertain:
- Docs/tests expect inline `sender.first_name`, `sender.last_name`, contact fields, `sender.quote`, and rich `sender.photo` rendering. The fetched `templates/cover_letter/sender_header.tex` still primarily reads `basics`/`profiles` like the CV header. Safest current mode is `sender.cv_data_path` plus inline overrides, unless the sender header template is updated.

# CV Generation Commands

| Command | Purpose | Required args | Optional args | Output |
|---|---|---|---|---|
| `python generate_cv.py` | Generate all CVs from `data/cvs/` | none | none | `output/<base_name>_<lang>.pdf` or `output/<base_name>_<lang>_<extra>.pdf` |
| `python generate_cv.py --type cv` | Same as default CV generation | none | `--type cv` | same as above |
| `python generate_cv.py <file1.json> [file2.json ...]` | Generate selected CV JSON files | one or more JSON paths/names/directories | `--verbose`, `-v`, `--output-path <dir-or-pdf>` | directory output or single custom PDF |
| `python generate_cv.py --output-path ./pdfs` | Generate CVs to a custom directory | none | `--type cv`, files | `./pdfs/<generated-name>.pdf` |
| `python generate_cv.py <file.json> --output-path ./cv.pdf` | Generate one CV to an exact PDF path | exactly one input JSON | `--verbose`, `-v` | `./cv.pdf` |
| `python generate_cv.py --verbose` / `python generate_cv.py -v` | Generate CVs with detailed logs | none | files, `--output-path` | standard or custom output |

Rules:
- `files` is optional. If omitted, every `.json` file in `data/cvs/` is processed.
- A directory passed as `files` expands to its `.json` files.
- A relative filename not found in the current directory is tried under `data/cvs/`.
- `--output-path` default: `./output`.
- `--output-path <something>.pdf` is valid only with exactly one input file.
- Language and output base name are parsed from the filename.
- RTL CV layout is auto-selected for filename languages `fa`, `ar`, `he`.
- Cache file: `.cvgen_cache.json`; unchanged inputs with existing PDFs are skipped.

Examples:
```bash
python generate_cv.py
python generate_cv.py --type cv
python generate_cv.py ramin_en.json
python generate_cv.py data/cvs/ramin_en.json --output-path ./pdfs
python generate_cv.py data/cvs/ramin_en.json --output-path ./ramin_cv.pdf -v
```

# Cover Letter Generation Commands

| Command | Purpose | Required args | Optional args | Output |
|---|---|---|---|---|
| `python generate_cv.py --type cover-letter` | Generate all cover letters from `data/cover_letter_datas/` | `--type cover-letter` | `--verbose`, `-v`, `--output-path <dir>` | `output/<base_name>_<lang>_cover_letter.pdf` unless `letter.output_name` overrides |
| `python generate_cv.py --type cover-letter <file.json>` | Generate one cover letter | `--type cover-letter`, one JSON | `--verbose`, `-v`, `--output-path <dir-or-pdf>` | generated name or exact PDF path |
| `python generate_cv.py --type cover-letter --output-path ./letters` | Generate cover letters to a custom directory | `--type cover-letter` | files, `--verbose` | `./letters/<generated-name>.pdf` |
| `python generate_cv.py --type cover-letter <file.json> --output-path ./application.pdf` | Generate one cover letter to an exact PDF path | `--type cover-letter`, exactly one JSON | `--verbose`, `-v` | `./application.pdf` |

Rules:
- Cover-letter input directory: `data/cover_letter_datas/`.
- `meta.type` must be exactly `cover_letter`.
- Required top-level keys: `meta`, `sender`, `recipient`, `letter`, `sections`.
- `files` can be paths, names, or directories; directories expand to `.json`.
- A relative filename not found in the current directory is tried under `data/cover_letter_datas/`.
- `--output-path` default: `./output`.
- `--output-path <something>.pdf` is valid only with exactly one input file.
- Layout options: `options.template = default | compact | rtl | awesomecv_sectioned`.
- RTL layout is auto-selected for `fa`, `ar`, `he` unless `options.rtl` overrides.
- Cover-letter cache hashes the JSON, all `templates/cover_letter/*.tex`, and linked CV data if present.

Examples:
```bash
python generate_cv.py --type cover-letter
python generate_cv.py --type cover-letter ramin_google_en.json
python generate_cv.py --type cover-letter data/cover_letter_datas/ramin_google_en.json --output-path ./letters
python generate_cv.py --type cover-letter data/cover_letter_datas/ramin_google_en.json --output-path ./application.pdf -v
```
