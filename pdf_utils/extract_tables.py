#!/usr/bin/env python3
"""
Table Extraction Utility

Extract tables from PDFs with debug visualizations.
Uses advanced pdfplumber settings optimized for complex table layouts.

Usage:
    python extract_tables.py input.pdf [--page 1] [--output-dir tables/] [--show-debug]
"""

import sys
import json
import argparse
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from pdf_enhancements import PDFEnhancer, extract_tables_with_images


def main():
    parser = argparse.ArgumentParser(description='Extract tables from PDF')
    parser.add_argument('pdf_path', help='Path to PDF file')
    parser.add_argument('--page', type=int, help='Specific page number (1-indexed). If omitted, extracts from all pages.')
    parser.add_argument('--output-dir', default='table_output', help='Output directory for debug images')
    parser.add_argument('--show-debug', action='store_true', help='Generate debug images showing table detection')
    parser.add_argument('--json-output', help='Save tables as JSON to this file')

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📊 Extracting tables from {args.pdf_path}...")
    if args.page:
        print(f"   Page: {args.page}")
    else:
        print(f"   Pages: all")
    print(f"   Debug images: {args.show_debug}")
    print(f"   Output: {output_dir}/\n")

    with PDFEnhancer(args.pdf_path) as enhancer:
        if args.page:
            # Extract from specific page
            tables = enhancer.extract_tables_advanced(
                args.page,
                return_debug_images=args.show_debug
            )

            print(f"Page {args.page}: Found {len(tables)} table(s)")
            for i, table in enumerate(tables):
                print(f"\n  Table {i+1}:")
                print(f"    Dimensions: {table['rows']} rows x {table['cols']} columns")
                print(f"    Location: {table['bbox'].to_dict()}")

                # Save debug image if requested
                if args.show_debug and 'debug_image' in table:
                    img_path = output_dir / f"page{args.page}_table{i+1}_debug.png"
                    table['debug_image'].save(img_path)
                    print(f"    Debug image: {img_path}")

                # Save table data as CSV
                csv_path = output_dir / f"page{args.page}_table{i+1}.csv"
                with open(csv_path, 'w') as f:
                    for row in table['data']:
                        f.write(','.join(str(cell or '') for cell in row) + '\n')
                print(f"    Data: {csv_path}")

            all_tables = {args.page: tables} if tables else {}

        else:
            # Extract from all pages
            all_tables = enhancer.extract_all_tables()

            total_tables = sum(len(tables) for tables in all_tables.values())
            print(f"Found {total_tables} table(s) across {len(all_tables)} page(s)\n")

            for page_num, tables in all_tables.items():
                print(f"Page {page_num}: {len(tables)} table(s)")
                for i, table in enumerate(tables):
                    print(f"  Table {i+1}: {table['rows']}x{table['cols']}")

                    # Save as CSV
                    csv_path = output_dir / f"page{page_num}_table{i+1}.csv"
                    with open(csv_path, 'w') as f:
                        for row in table['data']:
                            f.write(','.join(str(cell or '') for cell in row) + '\n')

        # Save as JSON if requested
        if args.json_output:
            # Convert tables to JSON-serializable format
            json_data = {}
            for page_num, tables in all_tables.items():
                json_data[page_num] = []
                for table in tables:
                    json_data[page_num].append({
                        'data': table['data'],
                        'rows': table['rows'],
                        'cols': table['cols'],
                        'bbox': table['bbox'].to_dict()
                    })

            with open(args.json_output, 'w') as f:
                json.dump(json_data, f, indent=2)
            print(f"\n💾 Tables saved to JSON: {args.json_output}")

    print("\n✅ Table extraction complete!")


if __name__ == '__main__':
    main()
