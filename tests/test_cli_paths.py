import json
import sys
from pathlib import Path
import types

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

jinja2_stub = types.ModuleType("jinja2")
jinja2_exceptions_stub = types.ModuleType("jinja2.exceptions")


class StubEnvironment:
    def __init__(self, **kwargs):
        self.filters = {}
        self.globals = {}

    def get_template(self, name):
        class Template:
            def render(self, _):
                return "rendered"

        return Template()


class StubFileSystemLoader:
    def __init__(self, path):
        self.path = path


class StubStrictUndefined:
    pass


class StubTemplateError(Exception):
    pass


jinja2_stub.Environment = StubEnvironment
jinja2_stub.FileSystemLoader = StubFileSystemLoader
jinja2_stub.StrictUndefined = StubStrictUndefined
jinja2_exceptions_stub.TemplateError = StubTemplateError

sys.modules["jinja2"] = jinja2_stub
sys.modules["jinja2.exceptions"] = jinja2_exceptions_stub

import generate_cv


def setup_test_env(tmp_path, monkeypatch):
    base_dir = tmp_path / "repo"
    cvs_dir = base_dir / "data" / "cvs"
    template_dir = base_dir / "templates"
    lang_dir = base_dir / "Lang_engine"
    result_dir = base_dir / "result"
    cache_file = base_dir / ".cvgen_cache.json"

    cvs_dir.mkdir(parents=True)
    template_dir.mkdir(parents=True)
    lang_dir.mkdir(parents=True)
    result_dir.mkdir(parents=True)

    (lang_dir / "lang.json").write_text(json.dumps({"dummy": {"en": "Dummy"}}))
    (template_dir / "layout.tex").write_text("Test layout")
    (template_dir / "header.tex").write_text("Header section")

    monkeypatch.setattr(generate_cv, "BASE_DIR", str(base_dir))
    monkeypatch.setattr(generate_cv, "CVS_PATH", str(cvs_dir))
    monkeypatch.setattr(generate_cv, "TEMPLATE_DIR", str(template_dir))
    monkeypatch.setattr(generate_cv, "LANG_ENGINE_DIR", str(lang_dir))
    monkeypatch.setattr(generate_cv, "RESULT_DIR", str(result_dir))
    monkeypatch.setattr(generate_cv, "CACHE_FILE", str(cache_file))
    monkeypatch.setattr(generate_cv, "VERBOSE", False)

    return {
        "base_dir": base_dir,
        "cvs_dir": cvs_dir,
        "template_dir": template_dir,
        "lang_dir": lang_dir,
        "result_dir": result_dir,
        "cache_file": cache_file,
    }


def fake_latex_runner(command):
    output_arg = next(arg for arg in command if arg.startswith("-output-directory="))
    output_dir = Path(output_arg.split("=", 1)[1])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rendered.pdf").write_bytes(b"%PDF-1.4")
    return generate_cv.subprocess.CompletedProcess(command, 0, stdout="", stderr="")


def create_cv_json(path: Path, name="Alice"):
    data = {"basics": [{"fname": name, "lname": "Tester", "label": ["Engineer"]}]}
    path.write_text(json.dumps(data))


def test_folder_expansion_processes_json_only(tmp_path, monkeypatch):
    env = setup_test_env(tmp_path, monkeypatch)
    folder = env["base_dir"] / "inputs"
    folder.mkdir()
    create_cv_json(folder / "alice.json")
    create_cv_json(folder / "bob.JSON")
    (folder / "notes.txt").write_text("ignore")

    output_dir = env["base_dir"] / "out"

    monkeypatch.setattr(generate_cv, "_run_latex", fake_latex_runner)
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_cv.py", str(folder), "--output-path", str(output_dir)],
    )

    generate_cv.main()

    assert (output_dir / "alice_en.pdf").exists()
    assert (output_dir / "bob_en.pdf").exists()
    assert not (output_dir / "notes.pdf").exists()


def test_output_path_file_requires_single_input(tmp_path, monkeypatch):
    env = setup_test_env(tmp_path, monkeypatch)
    create_cv_json(env["cvs_dir"] / "one.json")
    create_cv_json(env["cvs_dir"] / "two.json")
    output_file = env["base_dir"] / "output.pdf"

    monkeypatch.setattr(generate_cv, "_run_latex", fake_latex_runner)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_cv.py",
            str(env["cvs_dir"] / "one.json"),
            str(env["cvs_dir"] / "two.json"),
            "--output-path",
            str(output_file),
        ],
    )

    with pytest.raises(SystemExit):
        generate_cv.main()


def test_output_path_pdf_for_single_input(tmp_path, monkeypatch):
    env = setup_test_env(tmp_path, monkeypatch)
    cv_path = env["cvs_dir"] / "single.json"
    create_cv_json(cv_path)
    output_file = env["base_dir"] / "custom.pdf"

    monkeypatch.setattr(generate_cv, "_run_latex", fake_latex_runner)
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_cv.py", str(cv_path), "--output-path", str(output_file)],
    )

    generate_cv.main()

    assert output_file.exists()


def test_cache_skip_and_regenerate_when_output_missing(tmp_path, monkeypatch):
    env = setup_test_env(tmp_path, monkeypatch)
    cv_path = env["cvs_dir"] / "skip.json"
    create_cv_json(cv_path)

    output_dir = env["base_dir"] / "out"
    output_dir.mkdir()
    cache = {}

    run_count = {"value": 0}

    def counting_runner(command):
        run_count["value"] += 1
        return fake_latex_runner(command)

    monkeypatch.setattr(generate_cv, "_run_latex", counting_runner)

    lang_map = generate_cv.load_lang_map()
    section_templates = ["header.tex"]

    processed, skipped, current_hash = generate_cv.process_cv_file(
        cv_path, lang_map, section_templates, cache, output_dir
    )
    assert processed is True
    cache[generate_cv.normalize_cache_key(cv_path)] = current_hash

    processed, skipped, _ = generate_cv.process_cv_file(
        cv_path, lang_map, section_templates, cache, output_dir
    )
    assert processed is False
    assert skipped is True
    assert run_count["value"] == 1

    (output_dir / "skip_en.pdf").unlink()

    processed, skipped, _ = generate_cv.process_cv_file(
        cv_path, lang_map, section_templates, cache, output_dir
    )
    assert processed is True
    assert skipped is False
    assert run_count["value"] == 2


def test_cache_key_dedupes_by_full_path(tmp_path, monkeypatch):
    env = setup_test_env(tmp_path, monkeypatch)
    dir_one = env["base_dir"] / "set1"
    dir_two = env["base_dir"] / "set2"
    dir_one.mkdir()
    dir_two.mkdir()

    file_one = dir_one / "shared.json"
    file_two = dir_two / "shared.json"
    create_cv_json(file_one)
    create_cv_json(file_two)

    key_one = generate_cv.normalize_cache_key(file_one)
    key_two = generate_cv.normalize_cache_key(file_two)

    assert key_one != key_two
