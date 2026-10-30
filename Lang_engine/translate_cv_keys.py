"""
translate_cv_keys.py - Translate CV JSON keys using a language mapping file.

This script transforms CV JSON files by translating dictionary keys (field names)
to the target language using a key translation mapping file (lang.json).
Values are preserved exactly as-is.

Usage:
    python translate_cv_keys.py --in-dir data/cvs --out-dir output/translated
    python translate_cv_keys.py --in-file data/cvs/example_de.json --out-dir output/
    python translate_cv_keys.py --in-file data/cvs/example.json --out-dir output/ --lang de
    python translate_cv_keys.py --in-dir data/cvs --out-dir output/ --on-collision suffix

Options:
    --in-dir:      Input directory containing CV JSON files (default: data/cvs)
    --in-file:     Single input CV JSON file (alternative to --in-dir)
    --out-dir:     Output directory for translated files (required)
    --lang-map:    Path to lang.json mapping file (default: Lang_engine/lang.json)
    --lang:        Force a specific language for all files (overrides auto-detection)
    --on-collision: How to handle key collisions: error (default), suffix, keep-first

Language Detection:
    - If filename ends with -<lang>.json or _<lang>.json, use <lang>
    - Otherwise, default to 'en'
    - Use --lang to force a specific language for all files

Key Translation Rules:
    - Only keys are translated, never values
    - If a key exists in LANG_MAP and has a non-empty translation, use it
    - If no mapping exists or translation is empty, keep the original key
    - Already-translated keys (not found in LANG_MAP) are kept as-is

Skills Special Handling:
    - The 'skills' key itself is translated if mapping exists
    - Category label keys (depth 1 under skills) are NOT translated
    - Subcategory label keys (depth 2 under skills) are NOT translated
    - Keys inside skill item objects (depth 3+) ARE translated
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent

def detect_language_from_filename(filename: str) -> str:
    """
    Detect target language from filename.
    
    Patterns:
        - example-de.json -> de
        - example_fa.json -> fa
        - example.json -> en (default)
    
    Returns the detected language code (2-3 lowercase chars).
    """
    stem = Path(filename).stem
    match = re.search('[-_]([a-z]{2,3})$', stem, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return 'en'

def load_lang_map(lang_map_path: Path) -> dict[str, dict[str, str]]:
    """
    Load the language mapping file.
    
    Returns a dict where keys are original field names and values are
    dicts mapping language codes to translations.
    """
    if not lang_map_path.exists():
        raise FileNotFoundError(f'Language map not found: {lang_map_path}')
    try:
        return json.loads(lang_map_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid JSON in language map: {e}')

def translate_key(key: str, lang: str, lang_map: dict[str, dict[str, str]]) -> str:
    """
    Translate a single key to the target language.
    
    Rules:
        1. If key exists in lang_map and lang_map[key][lang] is non-empty, use it
        2. Otherwise, keep the original key
    
    Returns the translated key (or original if no translation).
    """
    if key in lang_map:
        translations = lang_map[key]
        if isinstance(translations, dict) and lang in translations:
            translated = translations[lang]
            if isinstance(translated, str) and translated.strip():
                return translated
    return key

def translate_dict_keys(obj: dict[str, Any], lang: str, lang_map: dict[str, dict[str, str]], on_collision: str, path: str='', in_skills_subtree: bool=False, skills_depth: int=0) -> dict[str, Any]:
    """
    Recursively translate dictionary keys.
    
    Args:
        obj: The dictionary to translate
        lang: Target language code
        lang_map: The translation mapping
        on_collision: Collision handling strategy
        path: Current JSON path (for error reporting)
        in_skills_subtree: Whether we're inside the skills tree
        skills_depth: Depth within skills (0 = skills itself, 1 = category, 2 = subcategory)
    
    Returns a new dictionary with translated keys.
    """
    result: dict[str, Any] = {}
    collisions: dict[str, list[str]] = {}
    for original_key, value in obj.items():
        current_path = f'{path}.{original_key}' if path else original_key
        should_translate = True
        if in_skills_subtree and skills_depth in (1, 2):
            should_translate = False
        if should_translate:
            translated_key = translate_key(original_key, lang, lang_map)
        else:
            translated_key = original_key
        collisions.setdefault(translated_key, []).append(original_key)
        new_in_skills = in_skills_subtree or original_key == 'skills'
        new_skills_depth = skills_depth + 1 if in_skills_subtree else 1 if original_key == 'skills' else 0
        translated_value = translate_value(value, lang, lang_map, on_collision, current_path, new_in_skills, new_skills_depth)
        if translated_key in result:
            if on_collision == 'error':
                existing_originals = collisions[translated_key]
                raise ValueError(f"Key collision at {path}: keys {existing_originals} both translate to '{translated_key}'")
            elif on_collision == 'suffix':
                suffix = 2
                while f'{translated_key}_{suffix}' in result:
                    suffix += 1
                translated_key = f'{translated_key}_{suffix}'
            elif on_collision == 'keep-first':
                print(f"Warning: Collision at {current_path}: '{original_key}' -> '{translated_key}' (dropping, keeping first)")
                continue
        result[translated_key] = translated_value
    return result

def translate_value(value: Any, lang: str, lang_map: dict[str, dict[str, str]], on_collision: str, path: str, in_skills_subtree: bool, skills_depth: int) -> Any:
    """
    Recursively translate keys within a value.
    
    Values themselves are never modified - only dictionary keys are translated.
    """
    if isinstance(value, dict):
        return translate_dict_keys(value, lang, lang_map, on_collision, path, in_skills_subtree, skills_depth)
    elif isinstance(value, list):
        return [translate_value(item, lang, lang_map, on_collision, f'{path}[{i}]', in_skills_subtree, skills_depth) for i, item in enumerate(value)]
    else:
        return value

def translate_cv(cv_data: dict[str, Any], lang: str, lang_map: dict[str, dict[str, str]], on_collision: str='error') -> dict[str, Any]:
    """
    Translate all keys in a CV JSON structure.
    
    Args:
        cv_data: The CV data to translate
        lang: Target language code
        lang_map: The translation mapping
        on_collision: Collision handling strategy
    
    Returns the translated CV data.
    """
    return translate_dict_keys(cv_data, lang, lang_map, on_collision)

def process_cv_file(in_path: Path, out_path: Path, lang_map: dict[str, dict[str, str]], lang: str | None=None, on_collision: str='error') -> dict[str, Any]:
    """
    Process a single CV file.
    
    Args:
        in_path: Input CV JSON file path
        out_path: Output file path
        lang_map: The translation mapping
        lang: Target language (None = auto-detect from filename)
        on_collision: Collision handling strategy
    
    Returns stats dict.
    """
    stats = {'input': str(in_path), 'output': str(out_path), 'lang': None, 'success': False, 'error': None}
    try:
        cv_data = json.loads(in_path.read_text(encoding='utf-8'))
        target_lang = lang if lang else detect_language_from_filename(in_path.name)
        stats['lang'] = target_lang
        translated = translate_cv(cv_data, target_lang, lang_map, on_collision)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(translated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        stats['success'] = True
    except Exception as e:
        stats['error'] = str(e)
        raise
    return stats

def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Translate CV JSON keys using a language mapping file.', formatter_class=argparse.RawDescriptionHelpFormatter, epilog="\nExamples:\n    python translate_cv_keys.py --in-dir data/cvs --out-dir output/translated\n    python translate_cv_keys.py --in-file data/cvs/example_de.json --out-dir output/\n    python translate_cv_keys.py --in-file data/cvs/example.json --out-dir output/ --lang de\n    python translate_cv_keys.py --in-dir data/cvs --out-dir output/ --on-collision suffix\n\nNotes:\n    - Original files are never modified; output goes to --out-dir\n    - Language is auto-detected from filename suffix (-de, _fa) or defaults to 'en'\n    - Use --lang to force a specific language for all files\n        ")
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument('--in-dir', type=Path, default=None, help='Input directory containing CV JSON files')
    input_group.add_argument('--in-file', type=Path, default=None, help='Single input CV JSON file')
    parser.add_argument('--out-dir', type=Path, required=True, help='Output directory for translated files')
    parser.add_argument('--lang-map', type=Path, default=_HERE / 'lang.json', help='Path to lang.json mapping file (default: Lang_engine/lang.json)')
    parser.add_argument('--lang', type=str, default=None, metavar='LANG', help='Force a specific target language for all files')
    parser.add_argument('--on-collision', type=str, choices=['error', 'suffix', 'keep-first'], default='error', help='How to handle key collisions (default: error)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    args = parser.parse_args()
    if args.in_file:
        if not args.in_file.exists():
            print(f'Error: Input file not found: {args.in_file}', file=sys.stderr)
            return 1
        input_files = [args.in_file]
    elif args.in_dir:
        if not args.in_dir.exists():
            print(f'Error: Input directory not found: {args.in_dir}', file=sys.stderr)
            return 1
        input_files = sorted(args.in_dir.glob('*.json'))
        if not input_files:
            print(f'Error: No JSON files found in {args.in_dir}', file=sys.stderr)
            return 1
    else:
        default_in_dir = _PROJECT_ROOT / 'data' / 'cvs'
        if not default_in_dir.exists():
            print(f'Error: Default input directory not found: {default_in_dir}', file=sys.stderr)
            return 1
        input_files = sorted(default_in_dir.glob('*.json'))
        if not input_files:
            print(f'Error: No JSON files found in {default_in_dir}', file=sys.stderr)
            return 1
    try:
        lang_map = load_lang_map(args.lang_map)
    except (FileNotFoundError, ValueError) as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1
    if args.verbose:
        print(f'Loaded language map with {len(lang_map)} keys')
        print(f'Output directory: {args.out_dir}')
        if args.lang:
            print(f'Forcing language: {args.lang}')
        print()
    success_count = 0
    error_count = 0
    print(f'\n📋 Translating {len(input_files)} CV file(s)...\n')
    for in_path in input_files:
        out_path = args.out_dir / in_path.name
        try:
            stats = process_cv_file(in_path=in_path, out_path=out_path, lang_map=lang_map, lang=args.lang, on_collision=args.on_collision)
            print(f"  ✅ {in_path.name} -> {out_path.name} (lang: {stats['lang']})")
            success_count += 1
        except Exception as e:
            print(f'  ❌ {in_path.name}: {e}')
            error_count += 1
    print('\n' + '=' * 60)
    print(f'📊 Results: {success_count}/{len(input_files)} translated successfully')
    print('=' * 60)
    if error_count > 0:
        print('\n❌ Some files failed to translate')
        return 1
    else:
        print('\n✅ All files translated successfully')
        return 0
if __name__ == '__main__':
    sys.exit(main())
