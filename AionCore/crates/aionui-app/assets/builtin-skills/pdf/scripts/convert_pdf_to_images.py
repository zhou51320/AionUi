#!/usr/bin/env python3
"""
Convert PDF pages to PNG images.

Usage: python convert_pdf_to_images.py <input.pdf> <output_directory>

Creates one PNG image per page: page_1.png, page_2.png, etc.

Dependencies are provided by AionUI's offline runtime on Win7. When running
outside AionUI, install pdf2image and Poppler separately.
"""

import os
import sys


def convert_pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 150) -> None:
    """Convert PDF pages to PNG images."""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        print("Error: pdf2image is required. Install with: pip install pdf2image")
        print("Also requires poppler: brew install poppler (macOS) or apt-get install poppler-utils (Linux)")
        sys.exit(1)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    print(f"Converting {pdf_path} to images...")

    # Prefer the Poppler shipped with AionUI. This keeps Win7 portable builds
    # independent of PATH and avoids an accidental online package install.
    poppler_path = os.environ.get("AIONUI_PDF_POPPLER")
    convert_kwargs = {"dpi": dpi}
    if poppler_path:
        convert_kwargs["poppler_path"] = poppler_path

    try:
        images = convert_from_path(pdf_path, **convert_kwargs)
    except Exception as exc:
        print(
            "Error: Poppler is unavailable. In the AionUI offline package, "
            "check AIONUI_PDF_POPPLER and the bundled PDF runtime. "
            f"Details: {exc}"
        )
        sys.exit(1)

    for i, image in enumerate(images, start=1):
        output_path = os.path.join(output_dir, f"page_{i}.png")
        image.save(output_path, "PNG")
        print(f"  Created: {output_path} ({image.width}x{image.height})")

    print(f"\nConverted {len(images)} page(s) to {output_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python convert_pdf_to_images.py <input.pdf> <output_directory> [dpi]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_dir = sys.argv[2]
    dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 150

    convert_pdf_to_images(pdf_path, output_dir, dpi)
