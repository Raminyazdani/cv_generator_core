from pathlib import Path

import pytest

import generate_cv


def _write_json(path: Path, content: str = "{\"basics\": []}") -> None:
    path.write_text(content, encoding="utf-8")


def test_folder_expansion_collects_json_only(tmp_path: Path) -> None:
    folder = tmp_path / "cvs"
    folder.mkdir()
    _write_json(folder / "first.json")
    _write_json(folder / "second.JSON")
    (folder / "notes.txt").write_text("ignore", encoding="utf-8")
    nested = folder / "nested"
    nested.mkdir()
    _write_json(nested / "nested.json")

    files = generate_cv.gather_input_files([str(folder)], folder)

    names = sorted(path.name for path in files)
    assert names == ["first.json", "second.JSON"]


def test_mixed_inputs_dedupes_and_expands(tmp_path: Path) -> None:
    folder = tmp_path / "cvs"
    folder.mkdir()
    single = tmp_path / "single.json"
    _write_json(single)
    _write_json(folder / "a.json")
    _write_json(folder / "b.json")

    files = generate_cv.gather_input_files([str(folder), str(single), str(folder / "a.json")], folder)

    names = sorted(path.name for path in files)
    assert names == ["a.json", "b.json", "single.json"]


def test_cache_key_avoids_basename_collisions(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "resume.json"
    second = second_dir / "resume.json"
    _write_json(first)
    _write_json(second)

    key_one = generate_cv.cache_key_for_path(first)
    key_two = generate_cv.cache_key_for_path(second)

    assert key_one != key_two


def test_has_file_changed_requires_output(tmp_path: Path) -> None:
    json_path = tmp_path / "resume.json"
    _write_json(json_path)
    output_pdf = tmp_path / "resume.pdf"
    cache = {}

    changed, current_hash = generate_cv.has_file_changed(json_path, cache, output_pdf)
    assert changed is True
    cache[generate_cv.cache_key_for_path(json_path)] = current_hash

    output_pdf.write_text("pdf", encoding="utf-8")
    changed_again, _ = generate_cv.has_file_changed(json_path, cache, output_pdf)
    assert changed_again is False

    output_pdf.unlink()
    changed_missing, _ = generate_cv.has_file_changed(json_path, cache, output_pdf)
    assert changed_missing is True


def test_resolve_output_target_pdf_requires_single_input(tmp_path: Path) -> None:
    json_one = tmp_path / "one.json"
    json_two = tmp_path / "two.json"
    _write_json(json_one)
    _write_json(json_two)

    output_dir, output_file = generate_cv.resolve_output_target(str(tmp_path / "out.pdf"), [json_one])
    assert output_file == tmp_path / "out.pdf"
    assert output_dir == tmp_path

    with pytest.raises(SystemExit):
        generate_cv.resolve_output_target(str(tmp_path / "out.pdf"), [json_one, json_two])


def test_resolve_output_target_rejects_existing_file(tmp_path: Path) -> None:
    existing = tmp_path / "output"
    existing.write_text("not a dir", encoding="utf-8")

    with pytest.raises(SystemExit):
        generate_cv.resolve_output_target(str(existing), [tmp_path / "one.json"])


def test_paths_with_spaces_and_unicode(tmp_path: Path) -> None:
    space_dir = tmp_path / "space folder"
    space_dir.mkdir()
    spaced_file = space_dir / "spaced.json"
    _write_json(spaced_file)

    files = generate_cv.gather_input_files([str(space_dir)], space_dir)
    assert files == [spaced_file]

    unicode_file = space_dir / "résumé.json"
    try:
        _write_json(unicode_file)
    except OSError:
        pytest.skip("Unicode filenames are not supported on this filesystem.")

    files_with_unicode = generate_cv.gather_input_files([str(space_dir)], space_dir)
    names = sorted(path.name for path in files_with_unicode)
    assert names == ["résumé.json", "spaced.json"]
