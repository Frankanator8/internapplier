from __future__ import annotations

import os
import shutil
import subprocess
import tempfile


def compile_latex_to_pdf(tex_source: str, out_path: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tex_path = os.path.join(tmp, "resume.tex")
        with open(tex_path, "w", encoding="utf-8") as fh:
            fh.write(tex_source)

        try:
            result = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-output-directory", tmp,
                    tex_path,
                ],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "pdflatex not found. Please install a LaTeX distribution "
                "(e.g. MacTeX or BasicTeX) and ensure pdflatex is on PATH."
            )

        pdf_path = os.path.join(tmp, "resume.pdf")
        if result.returncode != 0 or not os.path.exists(pdf_path):
            log_tail = (result.stdout or "")[-2000:]
            raise RuntimeError(
                "pdflatex failed to compile the resume.\n\n"
                f"Last log output:\n{log_tail}"
            )

        shutil.copyfile(pdf_path, out_path)
