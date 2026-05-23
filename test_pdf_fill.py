"""Quick script to run pdf_page_metrics on a PDF of your choosing.

Usage:
    python test_pdf_fill.py path/to/file.pdf
"""

import json
import sys
from pathlib import Path

from api.generate_resume.compile import pdf_page_metrics


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python test_pdf_fill.py <path-to-pdf>")
        sys.exit(1)

    pdf = Path(sys.argv[1]).expanduser().resolve()
    if not pdf.is_file():
        print(f"Not a file: {pdf}")
        sys.exit(1)

    metrics = pdf_page_metrics(pdf)
    fill = metrics["fill"]
    lines = metrics["lines"]

    print(f"PDF: {pdf}")
    print(f"Pages: {len(lines)}")
    print(f"Fill: {fill:.4f}")
    print()
    for i, page in enumerate(lines, 1):
        print(f"--- Page {i} ({len(page)} lines) ---")
        for ln in page:
            print(
                f"  y={ln['y']:7.2f}  "
                f"width_ratio={ln['width_ratio']:.2f}  "
                f"last={ln['is_last_on_page']!s:5}  "
                f"{ln['text'][:80]}"
            )

    # Also dump the raw structure for piping into jq, etc.
    if "--json" in sys.argv:
        print()
        print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
