#!/usr/bin/env python3
"""
Smoke Validation Script for CV Generator

This script validates CV and cover-letter JSON files to prevent regressions
that cause:
- Empty sections
- undefined/null values appearing in output
- Wrong data types (arrays becoming objects, etc.)

Usage:
    python scripts/smoke_validate.py                     # Validate all CVs
    python scripts/smoke_validate.py --all               # Same as above
    python scripts/smoke_validate.py --cover-letters      # Validate cover letters
    python scripts/smoke_validate.py --all --cover-letters # Validate both
    python scripts/smoke_validate.py -v                  # Verbose output
"""

import json
import os
import sys
import argparse
from pathlib import Path

# Script directory and project root
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CVS_PATH = PROJECT_ROOT / "data" / "cvs"
COVER_LETTER_PATH = PROJECT_ROOT / "data" / "cover_letter_datas"

# Required top-level keys for a valid CV
REQUIRED_KEYS = ["basics"]

# Keys that should be arrays (not objects or other types)
# Note: This list is intentionally explicit rather than auto-derived to:
# 1. Catch cases where a new section is accidentally defined as wrong type
# 2. Serve as documentation of expected CV structure
# Add new section types here when extending the CV schema
ARRAY_KEYS = ["basics", "profiles", "education", "experiences", "languages", 
              "projects", "publications", "references", "workshop_and_certifications"]

# Keys within basics that are critical
REQUIRED_BASICS_KEYS = ["fname", "lname"]


def validate_json_structure(data: dict, filename: str, verbose: bool = False) -> list:
    """
    Validate the JSON structure of a CV file.
    
    Returns a list of error messages (empty if valid).
    """
    errors = []
    
    # Check required top-level keys
    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"Missing required key: '{key}'")
    
    # Check array keys are actually arrays
    for key in ARRAY_KEYS:
        if key in data and not isinstance(data[key], list):
            errors.append(f"Key '{key}' should be an array, got {type(data[key]).__name__}")
    
    # Check basics structure
    if "basics" in data:
        basics = data["basics"]
        if isinstance(basics, list) and len(basics) > 0:
            first_basic = basics[0]
            for key in REQUIRED_BASICS_KEYS:
                if key not in first_basic:
                    errors.append(f"Missing required basics key: '{key}'")
                elif first_basic[key] is None:
                    errors.append(f"basics.{key} is null")
                elif not isinstance(first_basic[key], str):
                    errors.append(f"basics.{key} should be a string")
        elif isinstance(basics, list) and len(basics) == 0:
            errors.append("basics array is empty")
    
    # Check for null values that would render as "undefined" or empty
    null_fields = find_null_fields(data)
    if verbose and null_fields:
        print(f"  Warning: Found null fields in {filename}: {null_fields[:5]}...")
    
    return errors


def find_null_fields(obj, path="") -> list:
    """
    Recursively find fields with null values.
    Returns a list of paths to null fields.
    """
    null_paths = []
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path else key
            if value is None:
                null_paths.append(current_path)
            else:
                null_paths.extend(find_null_fields(value, current_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            current_path = f"{path}[{i}]"
            null_paths.extend(find_null_fields(item, current_path))
    
    return null_paths


def check_for_undefined_strings(data: dict) -> list:
    """
    Check for literal 'undefined' or 'null' strings in data.
    Returns a list of paths where these values are found.
    """
    issues = []
    
    def check_recursive(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                check_recursive(value, current_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                check_recursive(item, f"{path}[{i}]")
        elif isinstance(obj, str):
            lower_val = obj.lower().strip()
            if lower_val == "undefined":
                issues.append(f"{path}: contains 'undefined'")
            # Note: 'null' as a string might be valid in some contexts
    
    check_recursive(data)
    return issues


def validate_cv_file(filepath: Path, verbose: bool = False) -> tuple:
    """
    Validate a single CV JSON file.
    
    Returns (success: bool, errors: list)
    """
    errors = []
    
    # Check file exists
    if not filepath.exists():
        return False, [f"File not found: {filepath}"]
    
    # Try to parse JSON
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    except Exception as e:
        return False, [f"Error reading file: {e}"]
    
    # Validate structure
    structure_errors = validate_json_structure(data, filepath.name, verbose)
    errors.extend(structure_errors)
    
    # Check for undefined strings
    undefined_issues = check_for_undefined_strings(data)
    errors.extend(undefined_issues)
    
    return len(errors) == 0, errors


# ── Cover-letter validation ──────────────────────────────────────────────────

# Required top-level keys for a valid cover letter
CL_REQUIRED_KEYS = ["meta", "sender", "recipient", "letter", "sections"]

# Keys within sender that are critical
CL_REQUIRED_SENDER_KEYS = ["first_name", "last_name"]


def validate_cl_json_structure(data: dict, filename: str, verbose: bool = False) -> list:
    """
    Validate the JSON structure of a cover-letter file.

    Returns a list of error messages (empty if valid).
    """
    errors = []

    # Meta type must be cover_letter
    meta_type = data.get("meta", {}).get("type")
    if meta_type != "cover_letter":
        errors.append(f"meta.type must be 'cover_letter', got '{meta_type}'")

    # Check required top-level keys
    for key in CL_REQUIRED_KEYS:
        if key not in data:
            errors.append(f"Missing required key: '{key}'")

    # Check sender structure
    sender = data.get("sender", {})
    if isinstance(sender, dict):
        for key in CL_REQUIRED_SENDER_KEYS:
            if key not in sender:
                if verbose:
                    print(f"  Warning: sender missing '{key}' in {filename}")

    # Check sections is a non-empty list
    sections = data.get("sections")
    if sections is not None:
        if not isinstance(sections, list):
            errors.append(f"'sections' should be an array, got {type(sections).__name__}")
        elif len(sections) == 0:
            errors.append("'sections' array is empty (cover letter has no body content)")

    # Check for null values
    null_fields = find_null_fields(data)
    if verbose and null_fields:
        print(f"  Warning: Found null fields in {filename}: {null_fields[:5]}...")

    return errors


def validate_cover_letter_file(filepath: Path, verbose: bool = False) -> tuple:
    """
    Validate a single cover-letter JSON file.

    Returns (success: bool, errors: list)
    """
    errors = []

    if not filepath.exists():
        return False, [f"File not found: {filepath}"]

    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    except Exception as e:
        return False, [f"Error reading file: {e}"]

    structure_errors = validate_cl_json_structure(data, filepath.name, verbose)
    errors.extend(structure_errors)

    undefined_issues = check_for_undefined_strings(data)
    errors.extend(undefined_issues)

    return len(errors) == 0, errors


def validate_all_cover_letters(verbose: bool = False) -> dict:
    """
    Validate all cover-letter JSON files in data/cover_letter_datas/.

    Returns a dict with validation results.
    """
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "files": {}
    }

    if not COVER_LETTER_PATH.exists():
        print(f"❌ Cover-letter directory not found: {COVER_LETTER_PATH}")
        return results

    json_files = list(COVER_LETTER_PATH.glob("*.json"))

    if not json_files:
        print(f"⚠️  No JSON files found in {COVER_LETTER_PATH}")
        return results

    results["total"] = len(json_files)

    print(f"\n📋 Validating {len(json_files)} cover-letter file(s)...\n")

    for filepath in sorted(json_files):
        filename = filepath.name
        success, errors = validate_cover_letter_file(filepath, verbose)

        results["files"][filename] = {
            "success": success,
            "errors": errors
        }

        if success:
            results["passed"] += 1
            print(f"  ✅ {filename}")
        else:
            results["failed"] += 1
            print(f"  ❌ {filename}")
            for error in errors:
                print(f"      - {error}")

    return results


def validate_all_cvs(verbose: bool = False) -> dict:
    """
    Validate all CV JSON files in the data/cvs directory.
    
    Returns a dict with validation results.
    """
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "files": {}
    }
    
    if not CVS_PATH.exists():
        print(f"❌ CVs directory not found: {CVS_PATH}")
        sys.exit(1)
    
    json_files = list(CVS_PATH.glob("*.json"))
    
    if not json_files:
        print(f"❌ No JSON files found in {CVS_PATH}")
        sys.exit(1)
    
    results["total"] = len(json_files)
    
    print(f"\n📋 Validating {len(json_files)} CV file(s)...\n")
    
    for filepath in sorted(json_files):
        filename = filepath.name
        success, errors = validate_cv_file(filepath, verbose)
        
        results["files"][filename] = {
            "success": success,
            "errors": errors
        }
        
        if success:
            results["passed"] += 1
            print(f"  ✅ {filename}")
        else:
            results["failed"] += 1
            print(f"  ❌ {filename}")
            for error in errors:
                print(f"      - {error}")
    
    return results


def generate_report(results: dict) -> None:
    """Generate a JSON report of validation results."""
    report_path = PROJECT_ROOT / "validation-report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n📄 Report saved to: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Smoke validation for CV Generator")
    parser.add_argument("--all", action="store_true", help="Validate all CV files")
    parser.add_argument("--cover-letters", action="store_true",
                        help="Also validate cover-letter files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔍 CV Generator Smoke Validation")
    print("=" * 60)
    
    cv_results = validate_all_cvs(verbose=args.verbose)
    
    cl_results = None
    if args.cover_letters:
        print("\n" + "-" * 60)
        print("📨 Cover-Letter Validation")
        print("-" * 60)
        cl_results = validate_all_cover_letters(verbose=args.verbose)
    
    # Combined summary
    total_passed = cv_results["passed"]
    total_total = cv_results["total"]
    total_failed = cv_results["failed"]
    if cl_results:
        total_passed += cl_results["passed"]
        total_total += cl_results["total"]
        total_failed += cl_results["failed"]

    print("\n" + "=" * 60)
    print(f"📊 Results: {total_passed}/{total_total} passed")
    print("=" * 60)
    
    # Generate report
    combined = {"cv": cv_results}
    if cl_results:
        combined["cover_letter"] = cl_results
    generate_report(combined)
    
    # Exit with appropriate code
    if total_failed > 0:
        print("\n❌ Validation FAILED")
        sys.exit(1)
    else:
        print("\n✅ All validations PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
