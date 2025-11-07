#!/usr/bin/env python3
"""
PDF Information Utility

Get comprehensive information about PDF structure and content.

Usage:
    python pdf_info.py input.pdf [--check-scanned] [--output info.json]
"""

import sys
import json
import argparse
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from pdf_enhancements import PDFEnhancer


def main():
    parser = argparse.ArgumentParser(description='Get PDF information')
    parser.add_argument('pdf_path', help='Path to PDF file')
    parser.add_argument('--check-scanned', action='store_true', help='Check if PDF is scanned')
    parser.add_argument('--output', help='Save information as JSON to this file')

    args = parser.parse_args()

    print(f"📄 Analyzing {args.pdf_path}...\n")

    with PDFEnhancer(args.pdf_path) as enhancer:
        # Get page information
        pages = enhancer.get_all_page_info()

        print(f"📊 General Information:")
        print(f"   Total pages: {len(pages)}")

        if pages:
            total_chars = sum(p['char_count'] for p in pages)
            total_images = sum(p['image_count'] for p in pages)
            total_tables = sum(p['table_count'] for p in pages)

            print(f"   Total characters: {total_chars:,}")
            print(f"   Total images: {total_images}")
            print(f"   Total tables: {total_tables}")

            # Average page dimensions
            avg_width = sum(p['width'] for p in pages) / len(pages)
            avg_height = sum(p['height'] for p in pages) / len(pages)
            print(f"   Average page size: {avg_width:.1f} x {avg_height:.1f} points")

        # Check if scanned
        if args.check_scanned:
            is_scanned = enhancer.is_scanned_pdf()
            print(f"\n🔍 Scanned PDF Detection:")
            print(f"   Is scanned: {'Yes' if is_scanned else 'No'}")
            if is_scanned:
                print(f"   ⚠️  This PDF appears to be scanned. OCR may be needed for text extraction.")

        # Per-page details
        print(f"\n📑 Page Details:")
        for page in pages[:10]:  # Show first 10 pages
            print(f"\n   Page {page['page_num']}:")
            print(f"     Dimensions: {page['width']:.1f} x {page['height']:.1f}")
            print(f"     Text: {page['text_length']:,} chars ({page['char_count']} detailed)")
            print(f"     Images: {page['image_count']}")
            print(f"     Tables: {page['table_count']}")

        if len(pages) > 10:
            print(f"\n   ... and {len(pages) - 10} more pages")

        # Save as JSON if requested
        if args.output:
            output_data = {
                'pdf_path': str(args.pdf_path),
                'total_pages': len(pages),
                'total_characters': sum(p['char_count'] for p in pages) if pages else 0,
                'total_images': sum(p['image_count'] for p in pages) if pages else 0,
                'total_tables': sum(p['table_count'] for p in pages) if pages else 0,
                'pages': pages
            }

            if args.check_scanned:
                output_data['is_scanned'] = enhancer.is_scanned_pdf()

            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"\n💾 Information saved to: {args.output}")

    print("\n✅ Analysis complete!")


if __name__ == '__main__':
    main()
