import hashlib
import json
import os
from pathlib import Path

from core.settings import CACHE_FILE


def load_cache():
    """Load the hash cache from the cache file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_cache(cache):
    """Save the hash cache to the cache file."""
    cache_path = Path(CACHE_FILE)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_suffix(".tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        os.replace(temp_path, cache_path)
    except IOError as e:
        print(f"⚠️  Warning: Could not save cache: {e}")
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def compute_file_hash(filepath: Path):
    """Compute SHA-256 hash of a file's contents."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except IOError:
        return None


def normalize_path_for_cache(path: Path) -> str:
    """Normalize a path for cache key stability across platforms."""
    resolved = path.expanduser().resolve()
    normalized = os.path.normcase(str(resolved))
    return normalized


def cache_key_for_path(path: Path) -> str:
    """Return a canonical cache key for a given input file path."""
    return normalize_path_for_cache(path)


def has_file_changed(filepath: Path, cache, output_pdf_path: Path):
    """
    Check if a file has changed since last processing.

    Returns (changed: bool, current_hash: str)
    """
    current_hash = compute_file_hash(filepath)
    if current_hash is None:
        return True, None

    cache_key = cache_key_for_path(filepath)
    cached_hash = cache.get(cache_key)
    if cached_hash == current_hash and output_pdf_path.exists():
        return False, current_hash
    return True, current_hash
