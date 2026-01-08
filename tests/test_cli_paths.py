import json
from pathlib import Path

import pytest

import generate_cv


def _write_json(path: Path, payload=None):
    payload = payload or {"basics": [{"fname": "Test", "lname": "User"}]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_templates(template_dir: Path):
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "header.tex").write_text("Header", encoding="utf-8")
    (template_dir / "layout.tex").write_text("<VAR>header_section</VAR>", encoding="utf-8")


def test_expand_folder_inputs(tmp_path):
    data_dir = tmp_path / "cvs"
    _write_json(data_dir / "one.json")
    _write_json(data_dir / "two.JSON")
    (data_dir / "notes.txt").write_text("ignore", encoding="utf-8")

    files = generate_cv.expand_input_paths([str(data_dir)], data_dir)

    assert sorted([p.name for p in files]) == ["one.json", "two.JSON"]


def test_expand_mixed_inputs_and_dedupes(tmp_path):
    dir_one = tmp_path / "dir_one"
    dir_two = tmp_path / "dir_two"
    file_one = dir_one / "alpha.json"
    file_two = dir_two / "beta.json"
    _write_json(file_one)
    _write_json(file_two)

    inputs = [str(dir_one), str(file_two), str(dir_two), str(file_one)]
    files = generate_cv.expand_input_paths(inputs, dir_one)

    assert sorted([p.name for p in files]) == ["alpha.json", "beta.json"]


def test_cache_key_avoids_basename_collision(tmp_path):
    first = tmp_path / "a" / "resume.json"
    second = tmp_path / "b" / "resume.json"
    _write_json(first)
    _write_json(second)

    key_one = generate_cv.normalize_cache_key(first)
    key_two = generate_cv.normalize_cache_key(second)

    assert key_one != key_two


def test_skip_and_regenerate_when_output_missing(tmp_path, monkeypatch):
    cvs_dir = tmp_path / "cvs"
    template_dir = tmp_path / "templates"
    result_dir = tmp_path / "result"
    output_dir = tmp_path / "output"
    json_path = cvs_dir / "person_en.json"
    _write_json(json_path)
    _write_templates(template_dir)

    monkeypatch.setattr(generate_cv, "TEMPLATE_DIR", str(template_dir))
    monkeypatch.setattr(generate_cv, "RESULT_DIR", str(result_dir))

    def fake_run_xelatex(rendered_output: Path, output_dir: Path) -> bool:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "rendered.pdf").write_bytes(b"pdf")
        return True

    monkeypatch.setattr(generate_cv, "run_xelatex", fake_run_xelatex)

    cache = {}
    section_templates = ["header.tex"]
    output_config = generate_cv.OutputConfig(output_dir=output_dir, explicit_pdf_path=None)

    processed, skipped, current_hash, cache_key = generate_cv.process_cv_file(
        json_path, {}, section_templates, cache, output_config
    )
    assert processed is True
    assert skipped is False
    assert current_hash
    cache[cache_key] = current_hash

    processed, skipped, _, _ = generate_cv.process_cv_file(
        json_path, {}, section_templates, cache, output_config
    )
    assert processed is False
    assert skipped is True

    output_pdf = output_dir / "person_en.pdf"
    output_pdf.unlink()

    processed, skipped, _, _ = generate_cv.process_cv_file(
        json_path, {}, section_templates, cache, output_config
    )
    assert processed is True
    assert skipped is False


def test_output_path_pdf_requires_single_input(tmp_path):
    with pytest.raises(ValueError):
        generate_cv.resolve_output_config(str(tmp_path / "output.pdf"), 2)


def test_output_path_pdf_single_input(tmp_path):
    config = generate_cv.resolve_output_config(str(tmp_path / "custom name.pdf"), 1)
    assert config.explicit_pdf_path == tmp_path / "custom name.pdf"
    assert config.output_dir == tmp_path


def test_unicode_input_path(tmp_path):
    unicode_dir = tmp_path / "unicodé"
    unicode_file = unicode_dir / "réšumé.json"
    try:
        _write_json(unicode_file)
    except OSError:
        pytest.skip("Unicode filenames not supported by filesystem")

    files = generate_cv.expand_input_paths([str(unicode_dir)], unicode_dir)
    assert files == [unicode_file]
