#!/usr/bin/env python3
"""Uninstall script for InternApplier (macOS)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
ENV_FILE = ROOT / ".env"
APP_SUPPORT = Path.home() / "Library" / "Application Support" / "InternApplier"


def phase(title: str) -> None:
    print(f"\n=== {title} ===")


def prompt_yes_no(question: str, default_no: bool = True) -> bool:
    suffix = " [y/N] " if default_no else " [Y/n] "
    try:
        ans = input(question + suffix).strip().lower()
    except EOFError:
        return False
    if not ans:
        return not default_no
    return ans in ("y", "yes")


def remove_path(path: Path, label: str, removed: list[str], skipped: list[str]) -> None:
    if not path.exists():
        print(f"{label}: not present, skipping.")
        skipped.append(label)
        return
    action = "recursively delete directory" if path.is_dir() else "delete file"
    print(f"About to {action}: {path}")
    if not prompt_yes_no("Proceed?", default_no=False):
        print(f"{label}: skipped by user.")
        skipped.append(f"{label} (declined)")
        return
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"{label}: removed ({path})")
        removed.append(label)
    except OSError as exc:
        print(f"WARNING: failed to remove {label} ({path}): {exc}", file=sys.stderr)
        skipped.append(f"{label} (error)")


def maybe_uninstall_mactex(removed: list[str], skipped: list[str]) -> None:
    if not shutil.which("pdflatex"):
        return
    if not prompt_yes_no(
        "Also uninstall MacTeX (LaTeX)? This affects other apps that use LaTeX."
    ):
        skipped.append("MacTeX (declined)")
        return

    brew = shutil.which("brew")
    if not brew:
        print("Homebrew not found. See https://www.tug.org/mactex/faq/uninstalling.html to remove MacTeX manually.")
        skipped.append("MacTeX (manual)")
        return

    check = subprocess.run([brew, "list", "--cask", "mactex"], capture_output=True)
    if check.returncode != 0:
        print("MacTeX not installed via Homebrew. See https://www.tug.org/mactex/faq/uninstalling.html to remove manually.")
        skipped.append("MacTeX (not brew-managed)")
        return

    print(f"About to run: {brew} uninstall --cask mactex")
    if not prompt_yes_no("Proceed?", default_no=False):
        print("Skipped by user.")
        skipped.append("MacTeX (declined)")
        return
    proc = subprocess.run([brew, "uninstall", "--cask", "mactex"])
    if proc.returncode == 0:
        removed.append("MacTeX")
    else:
        print(f"WARNING: brew uninstall returned {proc.returncode}", file=sys.stderr)
        skipped.append("MacTeX (error)")


def main() -> None:
    os.chdir(ROOT)
    print("This will remove:")
    print(f"  - virtual env:        {VENV}")
    print(f"  - application data:   {APP_SUPPORT}")
    print(f"  - env file:           {ENV_FILE}")
    print("You will also be asked whether to uninstall MacTeX.")
    if not prompt_yes_no("Proceed with uninstall?"):
        print("Aborted.")
        return

    removed: list[str] = []
    skipped: list[str] = []

    phase("Removing virtual environment")
    remove_path(VENV, "virtual env", removed, skipped)

    phase("Removing application support directory")
    remove_path(APP_SUPPORT, "application data", removed, skipped)

    phase("Removing .env file")
    remove_path(ENV_FILE, ".env file", removed, skipped)

    phase("MacTeX")
    maybe_uninstall_mactex(removed, skipped)

    phase("Done")
    if removed:
        print("Removed:")
        for item in removed:
            print(f"  - {item}")
    if skipped:
        print("Skipped:")
        for item in skipped:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
