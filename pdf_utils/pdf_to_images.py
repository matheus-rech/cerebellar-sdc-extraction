#!/usr/bin/env python3
"""
PDF to Images Utility

Convert PDF pages to images for visual analysis with Claude.
Follows Anthropic's best practices for PDF rendering.

Usage:
    python pdf_to_images.py input.pdf output_dir/ [--dpi 200] [--pages 1,2,3]
"""

import sys
import argparse
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from pdf_enhancements import PDFEnhancer


def main():
    parser = argparse.ArgumentParser(description='Convert PDF pages to images')
    parser.add_argument('pdf_path', help='Path to PDF file')
    parser.add_argument('output_dir', help='Output directory for images')
    parser.add_argument('--dpi', type=int, default=200, help='Rendering DPI (default: 200)')
    parser.add_argument('--pages', help='Comma-separated page numbers (e.g., 1,2,3). If omitted, converts all pages.')
    parser.add_argument('--format', default='PNG', choices=['PNG', 'JPEG'], help='Image format')
    parser.add_argument('--max-width', type=int, help='Maximum image width')
    parser.add_argument('--max-height', type=int, help='Maximum image height')

    args = parser.parse_args()

    # Parse pages
    pages = None
    if args.pages:
        pages = [int(p.strip()) for p in args.pages.split(',')]

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📄 Converting {args.pdf_path} to {args.format} images...")
    print(f"   DPI: {args.dpi}")
    print(f"   Pages: {pages or 'all'}")
    print(f"   Output: {output_dir}/\n")

    with PDFEnhancer(args.pdf_path) as enhancer:
        images = enhancer.render_pages_to_images(
            pages=pages,
            dpi=args.dpi,
            max_width=args.max_width,
            max_height=args.max_height
        )

        for page_num, img in images:
            output_path = output_dir / f"page_{page_num:03d}.{args.format.lower()}"
            img.save(output_path, format=args.format)
            print(f"✅ Page {page_num} -> {output_path}")

    print(f"\n✨ Converted {len(images)} pages successfully!")


if __name__ == '__main__':
    main()
