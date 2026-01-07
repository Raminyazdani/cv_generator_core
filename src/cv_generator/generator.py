"""
CV Generator orchestration module.

Provides the main functions for:
- Rendering individual CVs from JSON to LaTeX
- Compiling LaTeX to PDF
- Orchestrating the full CV generation pipeline
"""

import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any

from jinja2.exceptions import TemplateError as JinjaTemplateError

from .io import (
    discover_cv_files,
    load_cv_json,
    load_lang_map,
    parse_cv_filename,
    validate_cv_data
)
from .jinja_env import create_jinja_env, RTL_LANGUAGES
from .latex import compile_latex, cleanup_latex_artifacts, rename_pdf
from .cleanup import cleanup_result_dir
from .paths import (
    get_default_cvs_path,
    get_default_templates_path,
    get_default_output_path,
    get_default_result_path,
    get_repo_root
)
from .errors import TemplateError, ConfigurationError

logger = logging.getLogger(__name__)


class CVGenerationResult:
    """Result of generating a single CV."""
    
    def __init__(
        self,
        name: str,
        lang: str,
        success: bool,
        pdf_path: Optional[Path] = None,
        tex_path: Optional[Path] = None,
        error: Optional[str] = None
    ):
        self.name = name
        self.lang = lang
        self.success = success
        self.pdf_path = pdf_path
        self.tex_path = tex_path
        self.error = error
    
    def __repr__(self) -> str:
        status = "✅" if self.success else "❌"
        return f"CVGenerationResult({status} {self.name}_{self.lang})"


def render_sections(
    env,
    template_dir: Path,
    data: Dict[str, Any],
    output_dir: Path
) -> Dict[str, str]:
    """
    Render all section templates.
    
    Args:
        env: Jinja2 environment.
        template_dir: Path to templates directory.
        data: CV data dictionary.
        output_dir: Directory to write section .tex files.
        
    Returns:
        Dictionary mapping section names to rendered content.
        
    Raises:
        TemplateError: If a template fails to render.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    rendered_sections = {}
    template_files = list(template_dir.glob('*.tex'))
    
    for tmpl_path in template_files:
        tmpl_file = tmpl_path.name
        try:
            template = env.get_template(tmpl_file)
            rendered = template.render(data)
        except JinjaTemplateError as e:
            raise TemplateError(f"[Jinja error in {tmpl_file}] {e}") from e
        
        # Write section file
        section_name = tmpl_path.stem
        output_path = output_dir / f"{section_name}.tex"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rendered)
        
        # Store for inline embedding in layout
        rendered_sections[section_name] = rendered
        
    logger.debug(f"Rendered {len(rendered_sections)} section templates")
    return rendered_sections


def render_layout(
    env,
    data: Dict[str, Any],
    output_path: Path
) -> str:
    """
    Render the main layout template with embedded sections.
    
    Args:
        env: Jinja2 environment.
        data: CV data dictionary (should include *_section keys).
        output_path: Path to write the combined .tex file.
        
    Returns:
        The rendered layout content.
        
    Raises:
        TemplateError: If the layout template fails to render.
    """
    try:
        layout_template = env.get_template("layout.tex")
        rendered_layout = layout_template.render(data)
    except JinjaTemplateError as e:
        raise TemplateError(f"[Jinja error in layout.tex] {e}") from e
    
    # Collapse accidental double blank lines
    rendered_layout = rendered_layout.replace("\n\n\n", "\n\n")
    
    # Write the combined file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered_layout)
    
    logger.debug(f"Written combined layout to {output_path}")
    return rendered_layout


def generate_cv(
    cv_file: Path,
    *,
    templates_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    result_dir: Optional[Path] = None,
    lang_map: Optional[Dict[str, Dict[str, str]]] = None,
    dry_run: bool = False,
    keep_intermediate: bool = False
) -> CVGenerationResult:
    """
    Generate a PDF CV from a JSON file.
    
    Args:
        cv_file: Path to the CV JSON file.
        templates_dir: Path to templates directory.
        output_dir: Path to output directory for PDFs.
        result_dir: Path to intermediate result directory.
        lang_map: Language translation map (will be loaded if not provided).
        dry_run: If True, render LaTeX but don't compile to PDF.
        keep_intermediate: If True, don't clean up intermediate files.
        
    Returns:
        CVGenerationResult with status and paths.
    """
    if templates_dir is None:
        templates_dir = get_default_templates_path()
    if output_dir is None:
        output_dir = get_default_output_path()
    if result_dir is None:
        result_dir = get_default_result_path()
    
    # Parse filename
    base_name, lang = parse_cv_filename(cv_file.name)
    is_rtl = lang in RTL_LANGUAGES
    
    logger.info(f"Processing CV: {base_name} ({lang})")
    
    # Load CV data
    try:
        data = load_cv_json(cv_file)
    except Exception as e:
        return CVGenerationResult(base_name, lang, False, error=str(e))
    
    # Validate required structure
    if not validate_cv_data(data, cv_file.name):
        return CVGenerationResult(
            base_name, lang, False,
            error=f"Missing 'basics' key (incompatible schema)"
        )
    
    # Load language map if needed
    if lang_map is None:
        lang_map = load_lang_map()
    
    # Create Jinja environment
    env = create_jinja_env(templates_dir, lang_map, lang)
    
    # Set up output paths
    people_output_dir = result_dir / base_name / lang
    sections_dir = people_output_dir / "sections"
    rendered_tex_path = people_output_dir / "rendered.tex"
    
    # Prepare template variables
    data["OPT_NAME"] = base_name
    env.globals["BASE_NAME"] = base_name
    env.globals["IS_RTL"] = is_rtl
    
    env_vars = {**data}
    env_vars["LANG_MAP"] = lang_map
    env_vars["LANG"] = lang
    env_vars["BASE_NAME"] = base_name
    env_vars["IS_RTL"] = is_rtl
    
    # Render sections
    try:
        rendered_sections = render_sections(env, templates_dir, env_vars, sections_dir)
    except TemplateError as e:
        return CVGenerationResult(base_name, lang, False, error=str(e))
    
    # Add sections to env_vars for layout
    for section_name, content in rendered_sections.items():
        env_vars[f"{section_name}_section"] = content
    
    logger.info(f"✅ Sections rendered to '{sections_dir}'.")
    
    # Render layout
    try:
        render_layout(env, env_vars, rendered_tex_path)
    except TemplateError as e:
        return CVGenerationResult(base_name, lang, False, error=str(e))
    
    logger.info(f"✅ Final rendered.tex generated for {base_name} ({lang}).")
    
    if dry_run:
        logger.info(f"➡️  Dry run: would compile with xelatex {rendered_tex_path}")
        return CVGenerationResult(
            base_name, lang, True,
            tex_path=rendered_tex_path
        )
    
    # Copy awesome-cv.cls to the tex file directory.
    # The layout.tex template uses \documentclass[...]{./awesome-cv}, which tells
    # LaTeX to look for awesome-cv.cls in the same directory as the .tex file.
    # Since xelatex runs with cwd=tex_file.parent, we must ensure the class file
    # is present there. Without this copy, LaTeX fails with:
    #   "! LaTeX Error: File `./awesome-cv.cls' not found."
    repo_root = get_repo_root()
    cls_source = repo_root / "awesome-cv.cls"
    cls_dest = rendered_tex_path.parent / "awesome-cv.cls"
    if cls_source.exists() and not cls_dest.exists():
        try:
            shutil.copy2(cls_source, cls_dest)
            logger.debug(f"Copied awesome-cv.cls to {cls_dest}")
        except OSError as e:
            logger.warning(f"Could not copy awesome-cv.cls: {e}")
    
    # Compile LaTeX
    logger.info(f"➡️  Compile with: xelatex {rendered_tex_path}")
    
    try:
        pdf_path = compile_latex(rendered_tex_path, output_dir)
    except Exception as e:
        logger.error(f"LaTeX compilation failed: {e}")
        pdf_path = None
    
    if pdf_path is not None:
        # Rename to final name
        pdf_name = f"{base_name}_{lang}"
        final_pdf = rename_pdf(pdf_path, pdf_name, output_dir)
        
        # Clean up LaTeX artifacts
        cleanup_latex_artifacts(output_dir)
        
        result = CVGenerationResult(
            base_name, lang, True,
            pdf_path=final_pdf,
            tex_path=rendered_tex_path
        )
    else:
        result = CVGenerationResult(
            base_name, lang, False,
            tex_path=rendered_tex_path,
            error="LaTeX compilation failed"
        )
    
    # Clean up intermediate files
    if not keep_intermediate:
        cleanup_result_dir(people_output_dir)
    
    return result


def generate_all_cvs(
    *,
    cvs_dir: Optional[Path] = None,
    templates_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    result_dir: Optional[Path] = None,
    name_filter: Optional[str] = None,
    dry_run: bool = False,
    keep_intermediate: bool = False
) -> List[CVGenerationResult]:
    """
    Generate PDFs for all CV files in a directory.
    
    Args:
        cvs_dir: Path to directory containing CV JSON files.
        templates_dir: Path to templates directory.
        output_dir: Path to output directory for PDFs.
        result_dir: Path to intermediate result directory.
        name_filter: If provided, only generate CVs matching this base name.
        dry_run: If True, render LaTeX but don't compile to PDF.
        keep_intermediate: If True, don't clean up intermediate files.
        
    Returns:
        List of CVGenerationResult objects.
    """
    if cvs_dir is None:
        cvs_dir = get_default_cvs_path()
    if result_dir is None:
        result_dir = get_default_result_path()
    
    # Ensure result directory exists
    result_dir.mkdir(parents=True, exist_ok=True)
    
    # Load language map once for all CVs
    lang_map = load_lang_map()
    
    # Discover CV files
    cv_files = discover_cv_files(cvs_dir, name_filter)
    
    if not cv_files:
        if name_filter:
            logger.warning(f"No CV files found matching '{name_filter}'")
        else:
            logger.warning(f"No CV files found in {cvs_dir}")
        return []
    
    logger.info(f"Found {len(cv_files)} CV file(s) to process")
    
    results = []
    for cv_file in cv_files:
        result = generate_cv(
            cv_file,
            templates_dir=templates_dir,
            output_dir=output_dir,
            result_dir=result_dir,
            lang_map=lang_map,
            dry_run=dry_run,
            keep_intermediate=keep_intermediate
        )
        results.append(result)
    
    # Summary
    successful = sum(1 for r in results if r.success)
    logger.info(f"Generated {successful}/{len(results)} CVs successfully")
    
    return results
