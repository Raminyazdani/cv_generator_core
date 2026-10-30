# CV generator core — separate local variant

Preserved code includes `generate_cv.py`, Jinja/LaTeX source templates, language-key tooling and scripts. Original CV records, translation-data JSON and generated PDFs are excluded. Use explicit owner-provided CV input files: `python generate_cv.py PATH --output-path NEW_LOCAL_OUTPUT`. The CLI no longer implicitly scans every private CV when no positional input is supplied.

The generator needs Jinja2, a suitable LaTeX engine/fonts, and an owner-supplied language map (`CVGEN_LANGUAGE_MAP` overrides the historical local map path). Source templates are code; no generated CV/PDF is included. Language-key tools under `Lang_engine/` remain available for explicit local inputs. PDF rendering and language resources were not exercised here. This is usable code with explicit external-input requirements, not a claim that the historic complete data environment was restored.

## Publication boundary and history

This is a current-tree, code-only publication copy prepared at the time recorded in `PUBLICATION_PROVENANCE.md`. Original local data and Git repositories are unchanged. Real CVs, contacts, databases, `.env` files, outreach results, browser profiles, personal fixtures and logs were excluded. Synthetic configuration examples contain no real credentials or CV facts.

For owned-repository variants, the proposed branch starts from the recorded existing remote parent. **Old remote Git history may still contain CV/private/runtime data. This change only replaces the new current tree; it does not purge history, rotate credentials, change visibility or make old data safe.** No local source-history commits are imported. Source HEAD and per-file SHA-256 document this code import; no historical commit dates or fake development history are created.

No sender, browser, login, production database or network API was executed during preparation. Validation scope is recorded in the external receipt. Dependencies and full runtime behavior are not claimed verified. Ignore rules do not protect already tracked or historical secrets.

## Dependency metadata audit

See [DEPENDENCY_AUDIT.md](DEPENDENCY_AUDIT.md) and `constraints-audited-py312-windows.txt` for the actual2026-10-30 resolver/advisory scope. This is a Python3.12/Windows package-metadata snapshot, not proof of complete runtime compatibility or coverage of LaTeX/browser/system tools.
