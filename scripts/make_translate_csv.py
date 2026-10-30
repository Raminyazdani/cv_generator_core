import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
SENSITIVE_KEY_RX = re.compile('(url|uri|email|phone|doi|issn|isbn)', re.IGNORECASE)
SENSITIVE_VALUE_RX = re.compile('(https?://|www\\.|@|cloudinary\\.com|github\\.com|taylorfrancis\\.com)', re.IGNORECASE)

def _blank_leaf(value: Any) -> Any:
    """Blank a leaf while preserving the intent of the type."""
    if value is None:
        return None
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0
    if isinstance(value, float):
        return 0.0
    if isinstance(value, str):
        return ''
    return ''

def _looks_like_skill_item(x: Any) -> bool:
    """Heuristic: a skill entry is usually a dict with long_name/short_name/type_key."""
    return isinstance(x, dict) and ('short_name' in x or 'long_name' in x or 'type_key' in x)

def _trim_lists(obj: Any, max_items: int, path: tuple[str, ...]=()) -> Any:
    """
    Trim lists but preserve the intended *skills* shape:
    - Under `skills`: keep all group/subheading dict keys.
    - Only trim the leaf lists that contain skill items.
    """
    if isinstance(obj, dict):
        return {k: _trim_lists(v, max_items, path + (str(k),)) for k, v in obj.items()}
    if isinstance(obj, list):
        in_skills = 'skills' in path
        if in_skills and obj and _looks_like_skill_item(obj[0]):
            items = obj[:max_items]
        else:
            items = obj[:max_items] if not in_skills else obj
        return [_trim_lists(v, max_items, path) for v in items]
    return obj

def _anonymize_keep_shape(obj: Any) -> Any:
    """Blank all leaves, keep full structure."""
    if isinstance(obj, dict):
        return {k: _anonymize_keep_shape(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_anonymize_keep_shape(v) for v in obj]
    return _blank_leaf(obj)

def _override_sensitive(obj: Any) -> Any:
    """
    Force blanking for sensitive keys and values even if they appear as non-leaves.
    - If key looks sensitive => blank it (preserve None vs non-None intent loosely).
    - If string value looks like a link/email => blank it.
    """
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if SENSITIVE_KEY_RX.search(k or ''):
                out[k] = None if v is None else ''
            else:
                out[k] = _override_sensitive(v)
        return out
    if isinstance(obj, list):
        return [_override_sensitive(v) for v in obj]
    if isinstance(obj, str) and SENSITIVE_VALUE_RX.search(obj):
        return ''
    return obj

def make_empty_example(src_path: Path=Path('../data/cvs/example.json'), dst_path: Path=Path('../example/empty.json'), max_list_items: int=1) -> None:
    data = json.loads(src_path.read_text(encoding='utf-8'))
    trimmed = _trim_lists(deepcopy(data), max_items=max_list_items)
    empty = _anonymize_keep_shape(trimmed)
    empty = _override_sensitive(empty)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(json.dumps(empty, ensure_ascii=False, indent=2), encoding='utf-8')

def make_minimal_example(src_path: Path=Path('../data/cvs/example.json'), dst_path: Path=Path('../example/minimal.json'), max_list_items: int=1) -> None:
    """
    Write a minimal-but-real example:
    - Keep original values (do not blank content)
    - Trim repeated list entries to `max_list_items`
    - Blank sensitive fields/values
    """
    data = json.loads(src_path.read_text(encoding='utf-8'))
    minimal = _trim_lists(deepcopy(data), max_items=max_list_items)
    minimal = _override_sensitive(minimal)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(json.dumps(minimal, ensure_ascii=False, indent=2), encoding='utf-8')
if __name__ == '__main__':
    make_empty_example()
    make_minimal_example()
