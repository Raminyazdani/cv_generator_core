from __future__ import annotations

"""Cover-letter-specific document build orchestration.

Handles the cover-letter rendering pipeline: JSON loading, schema validation,
partial rendering, layout selection, and PDF compilation.

This module keeps the same public surface expected by the manager/import site
while adding the missing normalization required for cover-letter sender/header
features such as CV fallback mapping, photo resolution, language/RTL overrides,
and safer output naming.
"""

import json
import os
import re
from copy import deepcopy
from pathlib import Path

from jinja2.exceptions import TemplateError

from core.cache import DOC_PREFIX_CL, cache_key_for_path, compute_composite_hash
from core.compile import compile_latex, finalize_pdf
from core.jinja_env import create_jinja_env
from core.language import parse_cv_filename
from core.settings import RTL_LANGUAGES, RESULT_DIR, TEMPLATE_DIR, log_verbose

# ── Document-type constants ─────────────────────────────────────────────────
CL_DOC_TYPE = "cover_letter"
CL_TEMPLATE_NAMESPACE = "cover_letter"

CL_PARTIAL_TEMPLATES = [
    "sender_header.tex",
    "recipient.tex",
    "letter_meta.tex",
    "body_sections.tex",
    "signature.tex",
    "enclosures.tex",
]

CL_LAYOUTS = {
    "default": "layout.tex",
    "compact": "layout_compact.tex",
    "rtl": "layout_rtl.tex",
    "awesomecv_sectioned": "layout_awesomecv_sectioned.tex",
}

CL_REQUIRED_KEYS = ("sender", "recipient", "letter", "sections")

_IMAGE_EXTENSIONS = ("", ".png", ".jpg", ".jpeg", ".pdf", ".webp")


def get_cl_layout(options, is_rtl):
    """Select the appropriate cover-letter layout template."""
    if is_rtl:
        return CL_LAYOUTS["rtl"]

    template_choice = (options or {}).get("template", "default")
    if template_choice not in CL_LAYOUTS:
        allowed = ", ".join(sorted(CL_LAYOUTS.keys()))
        raise SystemExit(
            f"❌ Invalid cover-letter layout '{template_choice}'. "
            f"Allowed choices: {allowed}"
        )
    return CL_LAYOUTS[template_choice]


def _first_list_item(value, default=None):
    if isinstance(value, list) and value:
        return value[0]
    return default


def _coerce_str(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return str(value).strip() or None


def _normalize_bool(value, default=None):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _resolve_linked_cv_path(input_path: Path, raw_cv_path: str) -> Path:
    """Resolve sender.cv_data_path relative to the cover-letter JSON file first.

    Resolution order:
    1) Absolute path as-is
    2) Relative to the cover-letter JSON directory
    3) Relative to current working directory
    """
    candidate = Path(raw_cv_path).expanduser()

    if candidate.is_absolute():
        return candidate

    rel_to_cover_letter = (input_path.parent / candidate).resolve()
    if rel_to_cover_letter.exists():
        return rel_to_cover_letter

    return candidate.resolve()


def _load_linked_cv_data(input_path: Path, data: dict) -> tuple[dict, list, list, Path | None]:
    """Load CV JSON referenced by sender.cv_data_path, if present.

    Returns:
        tuple: (cv_data, basics, profiles, cv_path)
    """
    sender = data.get("sender", {})
    if not isinstance(sender, dict):
        return {}, [], [], None

    raw_cv_path = sender.get("cv_data_path")
    if not raw_cv_path:
        return {}, [], [], None

    cv_path = _resolve_linked_cv_path(input_path, raw_cv_path)

    if not cv_path.exists():
        print(
            f"⚠️  Linked CV file not found for sender.cv_data_path: {raw_cv_path}\n"
            f"    Resolved path tried: {cv_path}"
        )
        return {}, [], [], cv_path

    try:
        with open(cv_path, encoding="utf-8") as cf:
            cv_data = json.load(cf)
    except Exception as exc:
        print(f"⚠️  Failed to read linked CV file '{cv_path}': {exc}")
        return {}, [], [], cv_path

    if not isinstance(cv_data, dict):
        print(f"⚠️  Linked CV file '{cv_path}' is not a JSON object.")
        return {}, [], [], cv_path

    basics = cv_data.get("basics", [])
    profiles = cv_data.get("profiles", cv_data.get("profile", []))

    if basics is None:
        basics = []
    if profiles is None:
        profiles = []

    if not isinstance(basics, list):
        basics = []
    if not isinstance(profiles, list):
        profiles = []

    return cv_data, basics, profiles, cv_path


def _extract_location_string(raw_location) -> str | None:
    location = raw_location
    if isinstance(location, list):
        location = _first_list_item(location)

    if isinstance(location, dict):
        parts = [
            _coerce_str(location.get("city")),
            _coerce_str(location.get("region")),
            _coerce_str(location.get("country")),
        ]
        joined = ", ".join(part for part in parts if part)
        return joined or None

    return _coerce_str(location)


def _extract_profile_map(profiles: list) -> dict[str, str]:
    profile_map: dict[str, str] = {}
    for item in profiles:
        if not isinstance(item, dict):
            continue
        network = _coerce_str(item.get("network") or item.get("type") or item.get("name"))
        if not network:
            continue
        value = (
            _coerce_str(item.get("url"))
            or _coerce_str(item.get("username"))
            or _coerce_str(item.get("handle"))
            or _coerce_str(item.get("value"))
            or _coerce_str(item.get("link"))
        )
        if value:
            profile_map.setdefault(network.strip().lower(), value)
    return profile_map


def _extract_cv_photo(basic0: dict) -> str | None:
    pictures = basic0.get("Pictures") or basic0.get("pictures") or basic0.get("photo")

    if isinstance(pictures, str):
        return _coerce_str(pictures)

    if isinstance(pictures, dict):
        return (
            _coerce_str(pictures.get("URL"))
            or _coerce_str(pictures.get("url"))
            or _coerce_str(pictures.get("path"))
        )

    if isinstance(pictures, list) and pictures:
        first_pic = pictures[0]
        if isinstance(first_pic, str):
            return _coerce_str(first_pic)
        if isinstance(first_pic, dict):
            return (
                _coerce_str(first_pic.get("URL"))
                or _coerce_str(first_pic.get("url"))
                or _coerce_str(first_pic.get("path"))
            )

    return None


def _resolve_existing_image(raw_path: str | None, roots: list[Path]) -> str | None:
    raw = _coerce_str(raw_path)
    if not raw:
        return None

    candidate = Path(raw).expanduser()
    probes: list[Path] = []

    if candidate.is_absolute():
        base_candidates = [candidate]
    else:
        base_candidates = [(root / candidate) for root in roots if root is not None]
        base_candidates.append(candidate)

    seen: set[str] = set()
    for base in base_candidates:
        for ext in _IMAGE_EXTENSIONS:
            probe = base if ext == "" else Path(f"{base}{ext}")
            key = str(probe)
            if key in seen:
                continue
            seen.add(key)
            probes.append(probe)

    for probe in probes:
        if probe.exists() and probe.is_file():
            return probe.resolve().as_posix()

    return None


def _strip_image_extension(path_str: str | None) -> str | None:
    if not path_str:
        return None
    p = Path(path_str)
    if p.suffix.lower() in _IMAGE_EXTENSIONS[1:]:
        return p.with_suffix("").as_posix()
    return p.as_posix()


def _extract_username_from_url(value: str | None, domain_pattern: str) -> str | None:
    raw = _coerce_str(value)
    if not raw:
        return None
    match = re.search(domain_pattern, raw, flags=re.IGNORECASE)
    if not match:
        return raw
    username = match.group(1).strip("/")
    return username or raw


def _clean_homepage_display(value: str | None) -> str | None:
    raw = _coerce_str(value)
    if not raw:
        return None
    cleaned = re.sub(r"^https?://", "", raw, flags=re.IGNORECASE).rstrip("/")
    return cleaned or raw


def _merge_sender_from_cv(sender: dict, basics: list, profiles: list) -> dict:
    sender_data = deepcopy(sender) if isinstance(sender, dict) else {}
    basic0 = basics[0] if basics and isinstance(basics[0], dict) else {}
    profile_map = _extract_profile_map(profiles)

    defaults = {
        "first_name": _coerce_str(basic0.get("fname") or basic0.get("first_name") or basic0.get("firstName")),
        "last_name": _coerce_str(basic0.get("lname") or basic0.get("last_name") or basic0.get("lastName")),
        "position": _coerce_str(_first_list_item(basic0.get("label"))) or _coerce_str(basic0.get("position")),
        "address": _extract_location_string(basic0.get("location")),
        "mobile": _coerce_str(basic0.get("phone") or basic0.get("mobile")),
        "email": _coerce_str(basic0.get("email")),
        "homepage": profile_map.get("homepage") or profile_map.get("website") or _coerce_str(basic0.get("url")),
        "github": profile_map.get("github"),
        "linkedin": profile_map.get("linkedin"),
        "quote": _coerce_str(basic0.get("quote") or basic0.get("summary")),
    }

    for key, value in defaults.items():
        if not _coerce_str(sender_data.get(key)) and value:
            sender_data[key] = value

    if "photo" not in sender_data or sender_data.get("photo") in (None, "", {}):
        cv_photo = _extract_cv_photo(basic0)
        if cv_photo:
            sender_data["photo"] = cv_photo

    sender_data["_address_single_line"] = _coerce_str(sender_data.get("address", ""))
    sender_data["_homepage_display"] = _clean_homepage_display(sender_data.get("homepage"))
    sender_data["_github_handle"] = _extract_username_from_url(
        sender_data.get("github"), r"github\.com/([^/?#]+)"
    )
    sender_data["_linkedin_handle"] = _extract_username_from_url(
        sender_data.get("linkedin"), r"linkedin\.com/(?:in|company)/([^/?#]+)"
    )

    return sender_data


def _normalize_photo_config(
    sender_data: dict,
    options_data: dict,
    input_path: Path,
    linked_cv_path: Path | None,
) -> dict:
    photo_cfg = sender_data.get("photo")
    result = {
        "enabled": False,
        "path": None,
        "resolved_path": None,
        "style": [],
        "style_csv": "",
    }

    legacy_show = _normalize_bool(options_data.get("show_photo"), False)

    if isinstance(photo_cfg, str):
        result["enabled"] = legacy_show
        result["path"] = _coerce_str(photo_cfg)
    elif isinstance(photo_cfg, dict):
        result["enabled"] = _normalize_bool(photo_cfg.get("enabled"), legacy_show)
        result["path"] = _coerce_str(photo_cfg.get("path")) or _coerce_str(photo_cfg.get("url"))
        style = photo_cfg.get("style", [])
        if isinstance(style, str):
            style = [part.strip() for part in style.split(",") if part.strip()]
        elif not isinstance(style, list):
            style = []
        result["style"] = [str(item).strip() for item in style if _coerce_str(item)]
        result["style_csv"] = ",".join(result["style"])
    else:
        result["enabled"] = False

    roots = [input_path.parent]
    if linked_cv_path is not None:
        roots.append(linked_cv_path.parent)
    roots.append(Path.cwd())

    resolved = _resolve_existing_image(result["path"], roots)
    if resolved:
        result["resolved_path"] = _strip_image_extension(resolved)
    elif result["path"]:
        result["resolved_path"] = _strip_image_extension(_coerce_str(result["path"]))

    if result["enabled"] and result["path"] and not resolved:
        print(
            f"⚠️  Cover-letter photo could not be resolved: {result['path']}\n"
            f"    Checked relative to: {input_path.parent}"
            + (f" and {linked_cv_path.parent}" if linked_cv_path else "")
        )

    return result


def _normalize_letter(letter: dict, sender_data: dict, base_name: str, filename_lang: str) -> tuple[dict, str]:
    letter_data = deepcopy(letter) if isinstance(letter, dict) else {}
    lang = _coerce_str(letter_data.get("language")) or filename_lang
    signature_name = _coerce_str(letter_data.get("signature_name"))
    if not signature_name:
        full_name = " ".join(
            part for part in [sender_data.get("first_name"), sender_data.get("last_name")] if _coerce_str(part)
        )
        if full_name:
            letter_data["signature_name"] = full_name
    output_name = _coerce_str(letter_data.get("output_name"))
    if not output_name:
        letter_data["output_name"] = f"{base_name}_{lang}_{CL_DOC_TYPE}"
    return letter_data, lang


def _normalize_recipient(recipient: dict) -> dict:
    recipient_data = deepcopy(recipient) if isinstance(recipient, dict) else {}
    address_lines = recipient_data.get("address_lines")
    if address_lines is None:
        recipient_data["address_lines"] = []
    elif not isinstance(address_lines, list):
        recipient_data["address_lines"] = [str(address_lines)]
    return recipient_data


def _normalize_sections(sections) -> list:
    if not isinstance(sections, list):
        return []
    normalized = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        content = section.get("content")
        if isinstance(content, str):
            pass
        elif isinstance(content, list):
            content = [str(item) for item in content if item is not None and str(item).strip()]
        else:
            content = "" if content is None else str(content)
        normalized.append({**section, "content": content})
    return normalized


def _normalize_options(options: dict | None, lang: str) -> tuple[dict, bool]:
    options_data = deepcopy(options) if isinstance(options, dict) else {}
    rtl_override = _normalize_bool(options_data.get("rtl"), None)
    is_rtl = rtl_override if rtl_override is not None else lang in RTL_LANGUAGES
    return options_data, bool(is_rtl)


def _normalize_cover_letter_context(
    input_path: Path,
    raw_data: dict,
    base_name: str,
    filename_lang: str,
    linked_cv_path: Path | None,
    cv_data: dict,
    basics: list,
    profiles: list,
) -> tuple[dict, str, bool]:
    normalized = deepcopy(raw_data)

    sender_data = _merge_sender_from_cv(normalized.get("sender", {}), basics, profiles)
    letter_data, lang = _normalize_letter(normalized.get("letter", {}), sender_data, base_name, filename_lang)
    options_data, is_rtl = _normalize_options(normalized.get("options"), lang)
    sender_data["_photo"] = _normalize_photo_config(sender_data, options_data, input_path, linked_cv_path)

    normalized["sender"] = sender_data
    normalized["recipient"] = _normalize_recipient(normalized.get("recipient", {}))
    normalized["letter"] = letter_data
    normalized["options"] = options_data
    normalized["sections"] = _normalize_sections(normalized.get("sections", []))
    normalized["CV_DATA"] = cv_data
    normalized["basics"] = basics
    normalized["profiles"] = profiles
    normalized["OPT_NAME"] = base_name

    return normalized, lang, is_rtl


def process_cover_letter_file(
    input_path: Path,
    lang_map,
    cache,
    output_dir: Path,
    output_file: Path | None,
):
    """Process a single cover-letter JSON file and generate PDF.

    Returns:
        tuple: (processed, skipped, current_hash)
    """

    if input_path.suffix.lower() != ".json":
        log_verbose(f"  ⏭️  Skipping {input_path}: not a JSON file")
        return False, True, None

    base_name, filename_lang,extra = parse_cv_filename(input_path.stem + input_path.suffix)

    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        return False, False, None

    # -------------------------
    # Load cover-letter JSON
    # -------------------------
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    # ── Validate cover-letter schema ────────────────────────────────────
    meta = data.get("meta")
    if not isinstance(meta, dict) or meta.get("type") != "cover_letter":
        actual = meta.get("type") if isinstance(meta, dict) else None
        detail = "the 'meta' key is missing" if meta is None else f"meta.type is '{actual}'"
        print(
            f"⚠️  Skipping {input_path}: {detail}, expected 'cover_letter'. "
            f'Set "meta": {{"type": "cover_letter"}} in your JSON file.'
        )
        return False, True, None

    missing_keys = [k for k in CL_REQUIRED_KEYS if k not in data]
    if missing_keys:
        print(
            f"⚠️  Skipping {input_path}: missing required field(s): "
            f"{', '.join(repr(k) for k in missing_keys)}. "
            f"A valid cover letter must contain: "
            f"{', '.join(repr(k) for k in CL_REQUIRED_KEYS)}."
        )
        return False, True, None

    # -------------------------
    # Load linked CV data, if any
    # -------------------------
    cv_data, basics, profiles, linked_cv_path = _load_linked_cv_data(input_path, data)

    normalized_data, lang, is_rtl = _normalize_cover_letter_context(
        input_path=input_path,
        raw_data=data,
        base_name=base_name,
        filename_lang=filename_lang,
        linked_cv_path=linked_cv_path,
        cv_data=cv_data,
        basics=basics,
        profiles=profiles,
    )

    output_name = normalized_data["letter"].get("output_name") or f"{base_name}_{lang}_{CL_DOC_TYPE}"
    output_name = f"{output_name}.pdf" if not str(output_name).lower().endswith(".pdf") else str(output_name)
    output_pdf_path = output_file or (output_dir / output_name)

    # ── Cache-aware skip: composite hash of JSON + all template files + linked CV ──
    cl_template_dir = Path(TEMPLATE_DIR) / CL_TEMPLATE_NAMESPACE
    template_files = sorted(cl_template_dir.glob("*.tex"))
    all_inputs = [input_path] + template_files
    if linked_cv_path is not None and linked_cv_path.exists():
        all_inputs.append(linked_cv_path)

    current_hash = compute_composite_hash(all_inputs)
    cache_key = cache_key_for_path(input_path, prefix=DOC_PREFIX_CL)

    if current_hash is not None:
        cached_hash = cache.get(cache_key)
        if cached_hash == current_hash and output_pdf_path.exists():
            log_verbose(f"  ⏭️  Skipping {input_path}: file unchanged (cached)")
            print(f"⏭️  Skipping {input_path}: no changes detected")
            return False, True, current_hash

    log_verbose(
        f"  📄 Processing cover letter {input_path} "
        f"(base: {base_name}, lang: {lang}, RTL: {is_rtl})"
    )

    # Create output directory structure
    cl_output_dir = os.path.join(RESULT_DIR, base_name, lang, CL_DOC_TYPE)
    os.makedirs(cl_output_dir, exist_ok=True)

    sections_dir = os.path.join(cl_output_dir, "sections")
    rendered_output = os.path.join(cl_output_dir, "rendered.tex")

    # -------------------------
    # Jinja environment
    # -------------------------
    env = create_jinja_env(lang_map, lang, base_name, is_rtl)

    # Context variables
    env_vars = {**normalized_data}
    env_vars["LANG_MAP"] = lang_map
    env_vars["LANG"] = lang
    env_vars["BASE_NAME"] = base_name
    env_vars["IS_RTL"] = is_rtl

    # -------------------------
    # Ensure output folder exists
    # -------------------------
    os.makedirs(sections_dir, exist_ok=True)

    # -------------------------
    # Render partial templates
    # -------------------------
    for tmpl_file in CL_PARTIAL_TEMPLATES:
        tmpl_path = f"{CL_TEMPLATE_NAMESPACE}/{tmpl_file}"
        try:
            template = env.get_template(tmpl_path)
            rendered = template.render(env_vars)
        except TemplateError as e:
            raise SystemExit(f"[Jinja error in {tmpl_path}] {e}") from e

        section_name = os.path.splitext(tmpl_file)[0]
        section_output_path = os.path.join(sections_dir, f"{section_name}.tex")
        with open(section_output_path, "w", encoding="utf-8") as f:
            f.write(rendered)

        env_vars[f"{section_name}_section"] = rendered
        log_verbose(f"    ✓ Rendered partial: {section_name}")

    print(f"✅ Cover letter sections rendered to '{sections_dir}'.")

    # -------------------------
    # Render layout with embedded sections
    # -------------------------
    layout_name = get_cl_layout(normalized_data.get("options"), is_rtl)
    layout_path = f"{CL_TEMPLATE_NAMESPACE}/{layout_name}"
    try:
        layout_template = env.get_template(layout_path)
        rendered_layout = layout_template.render(env_vars)
    except TemplateError as e:
        raise SystemExit(f"[Jinja error in {layout_path}] {e}") from e

    rendered_layout = rendered_layout.replace("\n\n\n", "\n\n")

    with open(rendered_output, "w", encoding="utf-8") as f:
        f.write(rendered_layout)

    rtl_info = " (RTL mode)" if is_rtl else ""
    print(f"✅ Cover letter rendered.tex generated for {base_name} ({lang}){rtl_info}.")
    print(f"➡️  Compile with: xelatex {rendered_output}")

    # -------------------------
    # Generate PDF
    # -------------------------
    compile_runs = 1
    compile_opts = normalized_data.get("options", {}).get("compile")
    if isinstance(compile_opts, dict):
        try:
            compile_runs = max(1, int(compile_opts.get("runs", 1)))
        except (TypeError, ValueError):
            compile_runs = 1

    for _ in range(compile_runs):
        compile_latex(rendered_output, output_dir)

    if not finalize_pdf(output_dir, output_pdf_path):
        print(f"❌ PDF generation failed for {input_path}")
        return False, False, None

    return True, False, current_hash
