#!/usr/bin/env python3
"""Install script for InternApplier (macOS)."""
from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VENV_PY = VENV / "bin" / "python"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
REQUIREMENTS = ROOT / "requirements.txt"


def phase(title: str) -> None:
    print(f"\n=== {title} ===")


def run(cmd: list[str], *, check: bool = True) -> int:
    print(f"About to run: {' '.join(cmd)}")
    if not prompt_yes_no("Proceed?", default_no=False):
        print("Skipped by user.")
        if check:
            print("Aborting install.", file=sys.stderr)
            sys.exit(1)
        return 1
    proc = subprocess.run(cmd)
    if check and proc.returncode != 0:
        print(f"Command failed (exit {proc.returncode}): {' '.join(cmd)}", file=sys.stderr)
        sys.exit(1)
    return proc.returncode


def prompt_yes_no(question: str, default_no: bool = True) -> bool:
    suffix = " [y/N] " if default_no else " [Y/n] "
    try:
        ans = input(question + suffix).strip().lower()
    except EOFError:
        return False
    if not ans:
        return not default_no
    return ans in ("y", "yes")


def check_python() -> None:
    phase("Python version")
    if sys.version_info < (3, 10):
        print(f"Python 3.10+ required; found {sys.version.split()[0]}.", file=sys.stderr)
        sys.exit(1)
    print(f"OK — {sys.version.split()[0]}")


def create_venv() -> None:
    phase("Virtual environment")
    if VENV_PY.exists():
        print(f"Reusing existing venv at {VENV}")
        return
    run([sys.executable, "-m", "venv", str(VENV)])


def install_requirements() -> None:
    phase("Python requirements")
    run([str(VENV_PY), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(VENV_PY), "-m", "pip", "install", "-r", str(REQUIREMENTS)])


def install_playwright() -> None:
    phase("Playwright Chromium")
    run([str(VENV_PY), "-m", "playwright", "install", "chromium"])


def ensure_pdflatex() -> None:
    phase("LaTeX (pdflatex)")
    if shutil.which("pdflatex"):
        print("pdflatex already installed.")
        return

    brew = shutil.which("brew")
    if brew:
        if prompt_yes_no("Install MacTeX (scheme-full, ~5 GB) via 'brew install --cask mactex'?"):
            rc = run([brew, "install", "--cask", "mactex"], check=False)
            if rc != 0:
                print("WARNING: MacTeX install failed. Install manually from https://www.tug.org/mactex/")
                return
            if not shutil.which("pdflatex"):
                print("WARNING: pdflatex still not on PATH. Open a new shell and re-run `which pdflatex`.")
            else:
                print("pdflatex installed.")
        else:
            print("Skipping LaTeX install. See https://www.tug.org/mactex/ to install manually later.")
    else:
        print("Homebrew not found. Install MacTeX manually from https://www.tug.org/mactex/")
        print("(LaTeX is required for resume PDF compilation.)")


def write_env_key(key: str) -> None:
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text().splitlines()
    elif ENV_EXAMPLE.exists():
        lines = ENV_EXAMPLE.read_text().splitlines()
    else:
        lines = []

    new_line = f"OPENROUTER_API_KEY={key}"
    found = False
    for i, line in enumerate(lines):
        if line.startswith("OPENROUTER_API_KEY="):
            lines[i] = new_line
            found = True
            break
    if not found:
        lines.append(new_line)
    ENV_FILE.write_text("\n".join(lines) + "\n")


def existing_key() -> str | None:
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            value = line.split("=", 1)[1].strip()
            return value or None
    return None


def configure_api_key() -> None:
    phase("OpenRouter API key")
    if existing_key():
        if not prompt_yes_no("Existing OPENROUTER_API_KEY found. Replace?"):
            print("Keeping existing key.")
            return

    try:
        key = getpass.getpass("Enter your OpenRouter API key (input hidden, leave blank to skip): ").strip()
    except EOFError:
        key = ""

    if not key:
        print("No key entered. The app will not make AI calls until OPENROUTER_API_KEY is set in .env.")
        # Still ensure .env exists with an empty placeholder
        if not ENV_FILE.exists():
            write_env_key("")
        return

    write_env_key(key)
    print("API key written to .env")


def done_summary() -> None:
    phase("Done")
    print("To run the app:")
    print(f"  source {VENV.relative_to(ROOT)}/bin/activate")
    print("  python main.py")


def main() -> None:
    os.chdir(ROOT)
    check_python()
    create_venv()
    install_requirements()
    install_playwright()
    ensure_pdflatex()
    configure_api_key()
    done_summary()


if __name__ == "__main__":
    main()
