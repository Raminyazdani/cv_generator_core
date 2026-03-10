import os
import shutil
import subprocess
from pathlib import Path

from core.settings import log_verbose


def compile_latex(rendered_tex_path, output_dir: Path):
    """
    Compile a rendered .tex file to PDF using XeLaTeX.

    Args:
        rendered_tex_path: Path to the rendered .tex file
        output_dir: Directory for generated output

    Returns:
        The subprocess.CompletedProcess result
    """
    command = [
        "xelatex",
        "-enable-etex",
        "-enable-installer",
        "-enable-mltex",
        "-interaction=nonstopmode",
        "-file-line-error",
        "-synctex=1",
        f"-output-directory={output_dir}",
        str(rendered_tex_path),
    ]

    log_verbose(f"    🔧 Running: {' '.join(command)}")
    return subprocess.run(command, check=False)


def finalize_pdf(output_dir: Path, output_pdf_path: Path):
    """
    Clean up auxiliary files from LaTeX compilation and move the rendered PDF.

    Removes all non-PDF files from the output directory and renames
    'rendered.pdf' to the target PDF filename.

    Args:
        output_dir: Directory containing compilation output
        output_pdf_path: Final desired path for the PDF

    Returns:
        True if PDF was successfully finalized, False otherwise
    """
    if output_dir.exists():
        for file in os.listdir(output_dir):
            file_path = output_dir / file
            if file.endswith("rendered.pdf"):
                shutil.move(file_path, output_pdf_path)
                log_verbose(f"    📄 PDF generated: {output_pdf_path.name}")
            elif not file.endswith(".pdf"):
                os.remove(file_path)

    return output_pdf_path.exists()
