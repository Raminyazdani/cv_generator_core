"""
Integration tests for cv_generator.generator module.

Tests the full CV generation pipeline with dry-run mode.
"""

import json
import tempfile
from pathlib import Path

import pytest

from cv_generator.generator import (
    render_sections,
    render_layout,
    generate_cv,
    generate_all_cvs,
    CVGenerationResult
)
from cv_generator.jinja_env import create_jinja_env
from cv_generator.io import load_lang_map
from cv_generator.paths import get_default_templates_path


class TestRenderSections:
    """Tests for render_sections function."""
    
    def test_render_sections(self, tmp_path):
        """Test rendering section templates."""
        # Create a simple template
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "header.tex").write_text(
            r"% Header for <VAR> name | latex_escape </VAR>"
        )
        (templates_dir / "layout.tex").write_text(
            r"\documentclass{article}"
        )
        
        output_dir = tmp_path / "output"
        data = {"name": "Test User"}
        
        env = create_jinja_env(template_dir=templates_dir)
        sections = render_sections(env, templates_dir, data, output_dir)
        
        assert "header" in sections
        assert "Test User" in sections["header"]
        assert (output_dir / "header.tex").exists()


class TestGenerateCV:
    """Tests for generate_cv function with dry-run mode."""
    
    @pytest.fixture
    def sample_cv(self, tmp_path):
        """Create a sample CV JSON file with all required fields."""
        cv_data = {
            "basics": [{
                "fname": "Test",
                "lname": "User",
                "email": "test@example.com",
                "label": ["Software Engineer"],
                "location": [{
                    "city": "Berlin",
                    "country": "Germany"
                }],
                "phone": {"formatted": "+49 123 456789"}
            }],
            "profiles": [],
            "education": [],
            "experiences": [],
            "skills": {},
            "languages": [],
            "projects": [],
            "publications": [],
            "references": [],
            "workshop_and_certifications": []
        }
        cv_file = tmp_path / "test.json"
        cv_file.write_text(json.dumps(cv_data))
        return cv_file
    
    @pytest.fixture
    def lang_map_dir(self, tmp_path):
        """Create a language map directory."""
        lang_dir = tmp_path / "Lang_engine"
        lang_dir.mkdir()
        lang_data = {
            "education": {"en": "Education", "de": "Ausbildung"},
            "experiences": {"en": "Experience", "de": "Berufserfahrung"},
            "skills": {"en": "Skills", "de": "Fähigkeiten"},
            "curriculum_vitae": {"en": "Curriculum Vitae", "de": "Lebenslauf"}
        }
        (lang_dir / "lang.json").write_text(json.dumps(lang_data))
        return lang_dir
    
    def test_generate_cv_dry_run(self, sample_cv, lang_map_dir, tmp_path):
        """Test generating a CV in dry-run mode."""
        result_dir = tmp_path / "result"
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Load language map
        lang_map = load_lang_map(lang_map_dir)
        
        result = generate_cv(
            sample_cv,
            templates_dir=get_default_templates_path(),
            output_dir=output_dir,
            result_dir=result_dir,
            lang_map=lang_map,
            dry_run=True,
            keep_intermediate=True
        )
        
        assert result.success is True
        assert result.name == "test"
        assert result.lang == "en"
        assert result.tex_path is not None
        assert result.tex_path.exists()
        # In dry-run mode, no PDF should be generated
        assert result.pdf_path is None
    
    def test_generate_cv_missing_basics(self, tmp_path, lang_map_dir):
        """Test that CV without basics is skipped."""
        cv_data = {"education": []}
        cv_file = tmp_path / "incomplete.json"
        cv_file.write_text(json.dumps(cv_data))
        
        result_dir = tmp_path / "result"
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        lang_map = load_lang_map(lang_map_dir)
        
        result = generate_cv(
            cv_file,
            templates_dir=get_default_templates_path(),
            output_dir=output_dir,
            result_dir=result_dir,
            lang_map=lang_map,
            dry_run=True
        )
        
        assert result.success is False
        assert "basics" in result.error.lower()
    
    def test_generate_cv_copies_cls_file(self, sample_cv, lang_map_dir, tmp_path):
        """Test that awesome-cv.cls is copied to result directory for compilation."""
        from unittest.mock import patch
        from cv_generator.paths import get_repo_root
        
        result_dir = tmp_path / "result"
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Load language map
        lang_map = load_lang_map(lang_map_dir)
        
        # Mock compile_latex to skip actual xelatex execution,
        # while still triggering the cls file copy logic (which runs before compilation)
        with patch('cv_generator.generator.compile_latex') as mock_compile:
            mock_compile.return_value = None  # Skip actual compilation
            
            result = generate_cv(
                sample_cv,
                templates_dir=get_default_templates_path(),
                output_dir=output_dir,
                result_dir=result_dir,
                lang_map=lang_map,
                dry_run=False,  # Not dry run - triggers the copy
                keep_intermediate=True
            )
        
        # The awesome-cv.cls file should be copied to the tex file's directory
        repo_root = get_repo_root()
        cls_source = repo_root / "awesome-cv.cls"
        expected_cls = result_dir / "test" / "en" / "awesome-cv.cls"
        
        # Only verify if the source cls file exists (it should in the real repo)
        if cls_source.exists():
            assert expected_cls.exists(), \
                f"awesome-cv.cls should be copied to {expected_cls}"
            # Verify it's the same content
            assert expected_cls.read_bytes() == cls_source.read_bytes()


class TestGenerateAllCVs:
    """Tests for generate_all_cvs function."""
    
    def test_generate_all_with_filter(self, tmp_path):
        """Test generating CVs with name filter."""
        # Create CV files
        cvs_dir = tmp_path / "cvs"
        cvs_dir.mkdir()
        
        cv1 = {
            "basics": [{"fname": "User", "lname": "One", "email": "one@example.com"}]
        }
        cv2 = {
            "basics": [{"fname": "User", "lname": "Two", "email": "two@example.com"}]
        }
        
        (cvs_dir / "user1.json").write_text(json.dumps(cv1))
        (cvs_dir / "user2.json").write_text(json.dumps(cv2))
        
        # Create lang map
        lang_dir = tmp_path / "Lang_engine"
        lang_dir.mkdir()
        (lang_dir / "lang.json").write_text(json.dumps({}))
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Use mock.patch for clean patching with automatic cleanup
        from unittest.mock import patch
        with patch('cv_generator.paths.get_lang_engine_path', return_value=lang_dir):
            results = generate_all_cvs(
                cvs_dir=cvs_dir,
                templates_dir=get_default_templates_path(),
                output_dir=output_dir,
                name_filter="user1",
                dry_run=True,
                keep_intermediate=True
            )
        
        assert len(results) == 1
        assert results[0].name == "user1"


class TestCVGenerationResult:
    """Tests for CVGenerationResult class."""
    
    def test_successful_result(self):
        """Test creating a successful result."""
        result = CVGenerationResult(
            name="test",
            lang="en",
            success=True,
            pdf_path=Path("/output/test.pdf")
        )
        
        assert result.success is True
        assert "✅" in repr(result)
    
    def test_failed_result(self):
        """Test creating a failed result."""
        result = CVGenerationResult(
            name="test",
            lang="en",
            success=False,
            error="Template error"
        )
        
        assert result.success is False
        assert "❌" in repr(result)
