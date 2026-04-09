"""
attachment_extractor.py — PDF/text attachment → .md converter

Usage:
    python attachment_extractor.py <input_path> <output_path>

Extracts text from a local file and writes it as a Markdown document.
Supported: .pdf (text-only), .txt, .csv, .md
Refuses: executable/script/macro-enabled files (raises ValueError)

Exit codes:
    0 — success, output file written
    1 — unsupported or dangerous file type
    2 — extraction failed (scanned/image-only PDF, corrupt file)
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone


SAFE_EXTENSIONS = {".pdf", ".txt", ".csv", ".md"}
DANGEROUS_EXTENSIONS = {
    ".bat", ".exe", ".ps1", ".sh", ".cmd", ".vbs", ".js", ".py", ".msi",
    ".dll", ".docm", ".xlsm", ".pptm", ".scr", ".hta", ".jar",
}


def _extract_pdf(path: Path) -> str:
    """Extract text from PDF using pdfplumber (preferred) or pypdf fallback."""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = []
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"### Page {i}\n\n{text.strip()}")
            if not pages:
                raise ValueError("PDF appears to be image-only (no extractable text)")
            return "\n\n".join(pages)
    except ImportError:
        pass

    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        pages = []
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"### Page {i}\n\n{text.strip()}")
        if not pages:
            raise ValueError("PDF appears to be image-only (no extractable text)")
        return "\n\n".join(pages)
    except ImportError:
        raise RuntimeError(
            "No PDF library found. Install one: uv add pdfplumber  OR  uv add pypdf"
        )


def _extract_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract(input_path: str, output_path: str) -> None:
    src = Path(input_path)
    dst = Path(output_path)

    ext = src.suffix.lower()

    if ext in DANGEROUS_EXTENSIONS:
        raise ValueError(
            f"SECURITY: Refused to process dangerous file type '{ext}'. "
            f"File: {src.name}"
        )

    if ext not in SAFE_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SAFE_EXTENSIONS))}"
        )

    if ext == ".pdf":
        content = _extract_pdf(src)
    else:
        content = _extract_text(src)

    now = datetime.now(timezone.utc).isoformat()
    word_count = len(content.split())

    md = f"""---
type: extracted_attachment
source_file: {src.name}
source_path: {str(src)}
extracted_at: {now}
word_count: {word_count}
status: extracted
---

# Extracted: {src.name}

> Extracted at {now} | {word_count} words

---

{content}
"""

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(md, encoding="utf-8")
    print(f"OK: extracted {word_count} words from '{src.name}' -> '{dst}'")


def main():
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <input_path> <output_path>", file=sys.stderr)
        sys.exit(1)

    try:
        extract(sys.argv[1], sys.argv[2])
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"EXTRACTION FAILED: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
