from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class LatexCompileError(RuntimeError):
    def __init__(self, message: str, log_excerpt: str = ""):
        super().__init__(message)
        self.log_excerpt = log_excerpt


def compile_latex(latex: str, workdir: Path | None = None) -> Path:
    if shutil.which("pdflatex") is None:
        raise LatexCompileError(
            "pdflatex not found on PATH; install a TeX distribution (e.g. MacTeX, TeX Live)."
        )

    if workdir is None:
        workdir = Path(tempfile.mkdtemp(prefix="resume_"))
    workdir.mkdir(parents=True, exist_ok=True)

    tex_path = workdir / "resume.tex"
    tex_path.write_text(latex, encoding="utf-8")

    last_stdout = ""
    for pass_idx in (1, 2):
        try:
            proc = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-output-directory",
                    str(workdir),
                    str(tex_path),
                ],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            raise LatexCompileError("pdflatex timed out after 60s.")

        last_stdout = proc.stdout or ""
        if proc.returncode != 0:
            log_path = workdir / "resume.log"
            log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else last_stdout
            excerpt = _extract_error_excerpt(log_text)
            logger.error("compile_latex — pass %d failed rc=%d", pass_idx, proc.returncode)
            raise LatexCompileError(
                f"pdflatex failed (pass {pass_idx}, rc={proc.returncode}).",
                log_excerpt=excerpt,
            )

    pdf_path = workdir / "resume.pdf"
    if not pdf_path.exists():
        raise LatexCompileError("pdflatex returned 0 but resume.pdf was not produced.")

    logger.info("compile_latex — success: %s", pdf_path)
    return pdf_path


def pdf_page_count(pdf: Path) -> int:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf))
    return len(reader.pages)


def _extract_error_excerpt(log_text: str, max_chars: int = 1500) -> str:
    lines = log_text.splitlines()
    err_idx = next((i for i, ln in enumerate(lines) if ln.startswith("!")), None)
    if err_idx is None:
        return log_text[-max_chars:]
    start = max(0, err_idx - 2)
    end = min(len(lines), err_idx + 15)
    return "\n".join(lines[start:end])[:max_chars]
