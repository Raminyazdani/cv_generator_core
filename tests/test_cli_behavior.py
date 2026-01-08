import json
from pathlib import Path

import pytest

import generate_cv


def test_expand_input_paths_directory_only_json(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "b.JSON").write_text("{}", encoding="utf-8")
    (tmp_path / "c.txt").write_text("nope", encoding="utf-8")

    results = generate_cv.expand_input_paths([str(tmp_path)])

    assert {p.name for p in results} == {"a.json", "b.JSON"}


def test_expand_input_paths_mixed_file_and_dir(tmp_path: Path) -> None:
    direct_file = tmp_path / "direct.json"
    direct_file.write_text("{}", encoding="utf-8")
    nested_dir = tmp_path / "folder"
    nested_dir.mkdir()
    (nested_dir / "inside.json").write_text("{}", encoding="utf-8")

    results = generate_cv.expand_input_paths([str(direct_file), str(nested_dir)])

    assert {p.name for p in results} == {"direct.json", "inside.json"}


def test_resolve_output_config_pdf_requires_single_input(tmp_path: Path) -> None:
    input_one = tmp_path / "one.json"
    input_two = tmp_path / "two.json"

    with pytest.raises(SystemExit):
        generate_cv.resolve_output_config(str(tmp_path / "out.pdf"), [input_one, input_two])


def test_resolve_output_config_pdf_for_single_input(tmp_path: Path) -> None:
    input_one = tmp_path / "one.json"
    config = generate_cv.resolve_output_config(str(tmp_path / "out.pdf"), [input_one])

    assert config.explicit_pdf_path == tmp_path / "out.pdf"
    assert config.output_dir == tmp_path


def test_cache_identity_no_collision(tmp_path: Path) -> None:
    dir_one = tmp_path / "a"
    dir_two = tmp_path / "b"
    dir_one.mkdir()
    dir_two.mkdir()
    file_one = dir_one / "same.json"
    file_two = dir_two / "same.json"
    file_one.write_text("{}", encoding="utf-8")
    file_two.write_text("{}", encoding="utf-8")

    key_one = generate_cv.canonicalize_path(file_one)
    key_two = generate_cv.canonicalize_path(file_two)

    assert key_one != key_two


def test_has_file_changed_requires_output(tmp_path: Path) -> None:
    json_file = tmp_path / "test.json"
    json_file.write_text("{}", encoding="utf-8")
    output_pdf = tmp_path / "test.pdf"
    cache_key = generate_cv.canonicalize_path(json_file)
    cache = {cache_key: generate_cv.compute_file_hash(json_file)}

    changed, _ = generate_cv.has_file_changed(cache_key, cache, output_pdf, json_file)
    assert changed is True

    output_pdf.write_text("pdf", encoding="utf-8")
    changed, _ = generate_cv.has_file_changed(cache_key, cache, output_pdf, json_file)
    assert changed is False


def test_process_cv_file_skips_when_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "data" / "cvs" / "ramin_en.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    temp_json = tmp_path / "ramin_en.json"
    temp_json.write_text(json.dumps(data), encoding="utf-8")

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    def fake_run_xelatex(command: list[str]) -> bool:
        output_arg = next(arg for arg in command if arg.startswith("-output-directory="))
        output_path = Path(output_arg.split("=", 1)[1])
        (output_path / "rendered.pdf").write_text("pdf", encoding="utf-8")
        return True

    monkeypatch.setattr(generate_cv, "run_xelatex", fake_run_xelatex)
    monkeypatch.setattr(generate_cv, "RESULT_DIR", str(tmp_path / "result"))

    output_config = generate_cv.OutputConfig(output_dir=output_dir)
    lang_map = generate_cv.load_lang_map()
    section_templates = [
        x for x in Path(generate_cv.TEMPLATE_DIR).iterdir()
        if not x.name.startswith("layout")
    ]
    section_templates = [x.name for x in section_templates]

    cache: dict[str, str] = {}
    processed, skipped, current_hash = generate_cv.process_cv_file(
        temp_json, lang_map, section_templates, cache, output_config
    )
    assert processed is True
    assert skipped is False
    assert current_hash is not None

    cache[generate_cv.canonicalize_path(temp_json)] = current_hash
    processed, skipped, _ = generate_cv.process_cv_file(
        temp_json, lang_map, section_templates, cache, output_config
    )
    assert processed is False
    assert skipped is True
