import os
from pathlib import Path

from core.cache import normalize_path_for_cache
from core.settings import log_verbose


def gather_input_files(files, default_dir: Path) -> list[Path]:
    """Resolve file and directory arguments into a list of JSON files."""
    if not files:
        candidates = [p for p in default_dir.iterdir() if p.is_file()]
    else:
        candidates = []
        for entry in files:
            path = Path(entry).expanduser()
            if not path.is_absolute() and not path.exists():
                candidate = default_dir / entry
                if candidate.exists():
                    path = candidate
            candidates.append(path)

    resolved_files = []
    for candidate in candidates:
        if candidate.is_dir():
            for item in candidate.iterdir():
                if item.is_file() and item.suffix.lower() == ".json":
                    resolved_files.append(item)
            continue
        if candidate.is_file():
            if candidate.suffix.lower() == ".json":
                resolved_files.append(candidate)
            else:
                log_verbose(f"  ⏭️  Skipping {candidate}: not a JSON file")
            continue
        resolved_files.append(candidate)

    deduped = []
    seen = set()
    for item in resolved_files:
        try:
            key = normalize_path_for_cache(item)
        except FileNotFoundError:
            key = os.path.normcase(str(item))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def resolve_output_target(output_path: str, input_files: list[Path]) -> tuple[Path, Path | None]:
    """Resolve output path configuration and validate constraints."""
    output_target = Path(output_path).expanduser()
    if output_target.suffix.lower() == ".pdf":
        if len(input_files) != 1:
            raise SystemExit("❌ --output-path may be a PDF file only when processing a single input file.")
        return output_target.parent, output_target
    if output_target.exists() and output_target.is_file():
        raise SystemExit("❌ --output-path must be a directory when processing multiple outputs.")
    return output_target, None
