"""
create_lang.py - Generate and merge lang.json from CV JSON keys.

This script extracts all unique JSON key names from a CV JSON file
and produces/updates a language dictionary file (lang.json) with
translation slots for each discovered key.

Usage:
    python create_lang.py --cv data/cvs/example.json --out Lang_engine/lang.json --langs de,en,fa
    python create_lang.py --dry-run --verbose
    python create_lang.py --cv data/cvs/example.json --out lang.json --langs de,en,fa --from-lang en

Options:
    --from-lang <lang>: Auto-populate the specified language slot with the key name itself
                        for any empty/missing translation slot. E.g., --from-lang en will set
                        "en": "fname" for key "fname" if the en slot is empty.
                        The specified language is automatically added to the languages list.

Notes:
    - For the top-level "skills" object, we apply special handling:
      - The "skills" key itself is included.
      - Category label keys (immediate children of skills) are EXCLUDED.
      - Subcategory label keys (children of categories) are EXCLUDED.
      - Skill item object keys (e.g., long_name, short_name, type_key) ARE INCLUDED.
    - This allows translation of skill item fields while avoiding dynamic category/subcategory names.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any
_HERE = Path(__file__).resolve().parent

def collect_keys(obj: Any, exclude_skills_descendants: bool=True) -> set[str]:
    """
    Recursively traverse the CV JSON and collect all unique key names.
    
    Rules:
    - If node is a dict: add each key to the set and recurse into values
    - If node is a list: recurse into every element
    - If node is a scalar (str/int/float/bool/null): stop (don't add values)
    
    Key names are case-sensitive ("Pictures" != "pictures").
    
    Special handling for "skills" (when exclude_skills_descendants=True):
    - The "skills" key itself is included.
    - Category label keys (immediate children of skills dict) are EXCLUDED.
    - Subcategory label keys (children of categories) are EXCLUDED.
    - Skill item object keys (e.g., long_name, short_name, type_key) ARE INCLUDED.
    
    The skills structure is expected to be:
        skills -> category(dict) -> subcategory(dict) -> list[skill_item_dicts]
    """
    out_set: set[str] = set()
    _collect_keys_recursive(obj, out_set, exclude_skills_descendants)
    return out_set

def _collect_skills_items(obj: Any, out_set: set[str]) -> None:
    """
    Collect keys from skill item objects within the skills subtree.
    
    This function is called for lists at the subcategory level of skills.
    It collects keys from dict items in those lists (skill items).
    """
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                for key, value in item.items():
                    out_set.add(key)
                    _collect_keys_recursive(value, out_set, exclude_skills_descendants=False)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            out_set.add(key)
            _collect_keys_recursive(value, out_set, exclude_skills_descendants=False)

def _collect_keys_recursive(obj: Any, out_set: set[str], exclude_skills_descendants: bool=True) -> None:
    """Internal recursive helper for collect_keys."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            out_set.add(key)
            if key == 'skills' and exclude_skills_descendants:
                _handle_skills_subtree(value, out_set)
            else:
                _collect_keys_recursive(value, out_set, exclude_skills_descendants)
    elif isinstance(obj, list):
        for item in obj:
            _collect_keys_recursive(item, out_set, exclude_skills_descendants)

def _handle_skills_subtree(skills_value: Any, out_set: set[str]) -> None:
    """
    Handle the skills subtree with special traversal rules.
    
    Structure expected:
        skills_value (dict of categories) ->
            category_value (dict of subcategories) ->
                subcategory_value (list of skill item dicts)
    
    We skip category and subcategory KEYS but descend into their values
    to find and collect skill item dict keys.
    """
    if isinstance(skills_value, dict):
        for category_key, category_value in skills_value.items():
            if isinstance(category_value, dict):
                for subcategory_key, subcategory_value in category_value.items():
                    _collect_skills_items(subcategory_value, out_set)
            elif isinstance(category_value, list):
                _collect_skills_items(category_value, out_set)
    elif isinstance(skills_value, list):
        _collect_skills_items(skills_value, out_set)

def _is_translation_dict(d: dict[str, Any]) -> bool:
    """
    Detect a dict that looks like a translation leaf.
    
    A translation dict has only string values and all keys look like language codes
    (2-3 character lowercase strings).
    """
    if not isinstance(d, dict) or len(d) == 0:
        return False
    if not all((isinstance(v, str) for v in d.values())):
        return False
    for k in d.keys():
        if not isinstance(k, str) or not 2 <= len(k) <= 3 or (not k.islower()):
            return False
    return True

def merge_lang_data(existing: dict[str, Any], discovered_keys: set[str], languages: list[str], from_lang: str | None=None) -> tuple[dict[str, dict[str, str]], dict[str, int]]:
    """
    Merge discovered keys into existing lang data without overwriting non-empty translations.
    
    Behavior:
    - If key exists and has non-empty translation for a language: keep it
    - If key exists but language is missing: add the language with ""
    - If key is new: add it with all languages set to ""
    - If existing file has extra languages not in requested list: keep them
    - Do not delete keys from existing lang.json just because they're not in CV
    - If from_lang is specified and that language slot is empty/missing,
      set it to the key name itself (auto-populate source language)
    
    Returns:
        (merged_dict, stats) where stats has counts for reporting
    """
    merged: dict[str, dict[str, str]] = {}
    stats = {'keys_discovered': len(discovered_keys), 'keys_added': 0, 'lang_slots_filled': 0, 'translations_preserved': 0, 'from_lang_populated': 0}
    all_keys = set(existing.keys()) | discovered_keys
    requested_langs = set(languages)
    for key in all_keys:
        existing_entry = existing.get(key, {})
        is_new_key = key not in existing
        if is_new_key:
            stats['keys_added'] += 1
        new_entry: dict[str, str] = {}
        if isinstance(existing_entry, dict) and _is_translation_dict(existing_entry):
            all_langs_for_key = set(existing_entry.keys()) | requested_langs
        else:
            all_langs_for_key = requested_langs
        for lang in all_langs_for_key:
            if isinstance(existing_entry, dict):
                existing_value = existing_entry.get(lang)
            else:
                existing_value = None
            if isinstance(existing_value, str) and existing_value.strip():
                new_entry[lang] = existing_value
                stats['translations_preserved'] += 1
            elif from_lang and lang == from_lang:
                new_entry[lang] = key
                stats['from_lang_populated'] += 1
            else:
                new_entry[lang] = ''
                if lang in requested_langs and (not is_new_key):
                    if isinstance(existing_entry, dict) and lang not in existing_entry:
                        stats['lang_slots_filled'] += 1
        merged[key] = new_entry
    return (merged, stats)

def update_lang_json(cv_path: Path, lang_path: Path, languages: list[str], dry_run: bool=False, verbose: bool=False, from_lang: str | None=None) -> dict[str, int]:
    """
    Main function to update lang.json from a CV JSON file.
    
    Args:
        cv_path: Path to the CV JSON file
        lang_path: Path to the lang.json output file
        languages: List of language codes (e.g., ["de", "en", "fa"])
        dry_run: If True, don't write file, just print summary
        verbose: If True, print detailed output
        from_lang: If specified, auto-populate this language slot with the key name
                   for any empty/missing translation slot
    
    Returns:
        Statistics dict with counts
    """
    if not cv_path.exists():
        raise FileNotFoundError(f'CV file not found: {cv_path}')
    try:
        cv_data = json.loads(cv_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid JSON in CV file: {e}')
    discovered_keys = collect_keys(cv_data, exclude_skills_descendants=True)
    if verbose:
        print(f'Discovered {len(discovered_keys)} unique keys from CV')
        sample_keys = sorted(discovered_keys)[:10]
        print(f'Sample keys: {sample_keys}')
    existing: dict[str, Any] = {}
    if lang_path.exists():
        try:
            raw = lang_path.read_text(encoding='utf-8').strip()
            if raw:
                existing = json.loads(raw)
        except json.JSONDecodeError:
            if verbose:
                print(f'Warning: Could not parse existing {lang_path}, starting fresh')
            existing = {}
    merged, stats = merge_lang_data(existing, discovered_keys, languages, from_lang=from_lang)
    sorted_merged = dict(sorted(merged.items()))
    for key in sorted_merged:
        sorted_merged[key] = dict(sorted(sorted_merged[key].items()))
    if dry_run:
        print('\n[DRY RUN] Would write to:', lang_path)
        print(f'Total keys: {len(sorted_merged)}')
    else:
        lang_path.parent.mkdir(parents=True, exist_ok=True)
        lang_path.write_text(json.dumps(sorted_merged, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if verbose:
            print(f'Written to: {lang_path}')
    print('\n--- Summary ---')
    print(f"Keys discovered in CV:    {stats['keys_discovered']}")
    print(f"Keys newly added:         {stats['keys_added']}")
    print(f"Language slots filled:    {stats['lang_slots_filled']}")
    print(f"Translations preserved:   {stats['translations_preserved']}")
    if from_lang:
        print(f"From-lang populated:      {stats['from_lang_populated']}")
    print(f'Total keys in output:     {len(sorted_merged)}')
    return stats

def parse_languages(langs_str: str) -> list[str]:
    """Parse comma-separated language string into a list."""
    return [lang.strip() for lang in langs_str.split(',') if lang.strip()]

def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Generate and merge lang.json from CV JSON keys.', formatter_class=argparse.RawDescriptionHelpFormatter, epilog='\nExamples:\n    python create_lang.py --cv data/cvs/example.json --out Lang_engine/lang.json --langs de,en,fa\n    python create_lang.py --dry-run --verbose\n    python create_lang.py --langs de,en,fa,it  # Add Italian language slots\n    python create_lang.py --cv data/cvs/example.json --out lang.json --langs de,en,fa --from-lang en\n\nNotes:\n    - Keys inside the top-level "skills" object are excluded from key discovery.\n    - The --from-lang option auto-populates empty translation slots with the key name.\n        ')
    parser.add_argument('--cv', type=Path, default=_HERE.parent / 'data' / 'cvs' / 'example.json', help='Path to CV JSON file (default: data/cvs/example.json)')
    parser.add_argument('--out', type=Path, default=_HERE / 'lang.json', help='Path to output lang.json file (default: Lang_engine/lang.json)')
    parser.add_argument('--langs', type=str, default='de,en,fa', help='Comma-separated list of language codes (default: de,en,fa)')
    parser.add_argument('--from-lang', type=str, default=None, metavar='LANG', help="Auto-populate empty slots for this language with the key name itself. E.g., --from-lang en sets 'en': 'fname' for key 'fname' if empty. The specified language is automatically added to the languages list.")
    parser.add_argument('--dry-run', action='store_true', help='Print summary without writing file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output including sample keys')
    args = parser.parse_args()
    languages = parse_languages(args.langs)
    if not languages:
        print('Error: No valid languages specified', file=sys.stderr)
        return 1
    from_lang = args.from_lang
    if from_lang:
        from_lang = from_lang.strip()
        if from_lang and from_lang not in languages:
            languages.append(from_lang)
            if args.verbose:
                print(f"Note: Added '{from_lang}' to languages list (from --from-lang)")
    if args.verbose:
        print(f'CV file:    {args.cv}')
        print(f'Output:     {args.out}')
        print(f'Languages:  {languages}')
        if from_lang:
            print(f'From-lang:  {from_lang}')
        print()
    try:
        update_lang_json(cv_path=args.cv, lang_path=args.out, languages=languages, dry_run=args.dry_run, verbose=args.verbose, from_lang=from_lang)
        return 0
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1
    except Exception as e:
        print(f'Unexpected error: {e}', file=sys.stderr)
        return 1
if __name__ == '__main__':
    sys.exit(main())
