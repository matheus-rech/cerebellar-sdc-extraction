#!/usr/bin/env python3
"""
Comparison Demo: pdfplumber vs Marker PDF Extraction

This script demonstrates the quality difference between
pdfplumber and Marker for medical research paper extraction.
"""

import os
import json
from pathlib import Path
import pdfplumber


def extract_with_pdfplumber(pdf_path):
    """Extract text using pdfplumber (current method)"""
    print("\n" + "=" * 60)
    print("🔹 PDFPLUMBER EXTRACTION")
    print("=" * 60)

    with pdfplumber.open(pdf_path) as pdf:
        all_text = ""
        for i, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text()
            all_text += page_text + "\n\n"
            print(f"\nPage {i} extracted: {len(page_text)} characters")

    print(f"\nTotal text length: {len(all_text)} characters")
    print("\n📄 Sample output (first 500 chars):")
    print("-" * 60)
    print(all_text[:500])
    print("-" * 60)

    # Try to get bounding boxes (limited in pdfplumber)
    print("\n📍 Provenance capability:")
    print("   - Bounding boxes: ❌ Limited (word/character level only)")
    print("   - Section detection: ❌ None")
    print("   - Structure preservation: ⚠️  Minimal")

    return {
        'text': all_text,
        'length': len(all_text),
        'metadata': {
            'pages': len(pdf.pages),
            'method': 'pdfplumber'
        }
    }


def extract_with_marker(pdf_path, output_dir="marker_output"):
    """Extract text using Marker (new method)"""
    print("\n" + "=" * 60)
    print("✨ MARKER EXTRACTION")
    print("=" * 60)

    # Check if already extracted
    base_name = Path(pdf_path).stem
    markdown_path = Path(output_dir) / base_name / f"{base_name}.md"
    meta_path = Path(output_dir) / base_name / f"{base_name}_meta.json"

    if not markdown_path.exists():
        print("⚠️  Marker output not found. Run marker_single first.")
        return None

    # Read markdown
    with open(markdown_path, 'r', encoding='utf-8') as f:
        markdown_text = f.read()

    # Read metadata
    with open(meta_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    print(f"\nMarkdown length: {len(markdown_text)} characters")
    print(f"Pages processed: {len(metadata['page_stats'])}")

    print("\n📄 Sample output (first 500 chars):")
    print("-" * 60)
    print(markdown_text[:500])
    print("-" * 60)

    # Show provenance capabilities
    print("\n📍 Provenance capability:")
    print("   - Bounding boxes: ✅ Section-level polygons")
    print("   - Section detection: ✅ Headers, lists, text blocks")
    print("   - Structure preservation: ✅ Markdown formatting")

    # Show table of contents with coordinates
    if 'table_of_contents' in metadata:
        toc = metadata['table_of_contents']
        print(f"\n📑 Table of Contents detected: {len(toc)} sections")
        for i, section in enumerate(toc[:3], 1):  # Show first 3
            print(f"   {i}. {section['title'][:50]}")
            print(f"      Page: {section['page_id']}")
            print(f"      Coords: {section['polygon'][0][:2]}")

    # Show page statistics
    if 'page_stats' in metadata:
        print(f"\n📊 Page Statistics:")
        for stat in metadata['page_stats']:
            page_id = stat['page_id']
            blocks = dict(stat['block_counts'])
            print(f"   Page {page_id + 1}:")
            for block_type, count in list(blocks.items())[:5]:
                print(f"      - {block_type}: {count}")

    return {
        'text': markdown_text,
        'length': len(markdown_text),
        'metadata': metadata
    }


def compare_provenance_tracking(marker_result):
    """Demonstrate provenance tracking capabilities"""
    print("\n" + "=" * 60)
    print("🎯 PROVENANCE TRACKING COMPARISON")
    print("=" * 60)

    print("\n❌ pdfplumber limitations:")
    print("   - No section-level bounding boxes")
    print("   - Manual coordinate extraction needed")
    print("   - No structural metadata")
    print("   - Difficult to trace text back to PDF location")

    print("\n✅ Marker advantages:")
    print("   - Automatic section detection with coordinates")
    print("   - Polygon bounding boxes for each section")
    print("   - Rich structural metadata")
    print("   - Easy to implement 'Show in PDF' feature")

    if marker_result and 'table_of_contents' in marker_result['metadata']:
        print("\n📍 Example: Tracing 'Results' section:")
        toc = marker_result['metadata']['table_of_contents']
        for section in toc:
            if 'Results' in section['title']:
                polygon = section['polygon']
                print(f"   Section: {section['title']}")
                print(f"   Page: {section['page_id'] + 1}")
                print(f"   Bounding box (polygon):")
                for i, point in enumerate(polygon):
                    print(f"      Point {i + 1}: x={point[0]:.1f}, y={point[1]:.1f}")
                print("\n   ✨ With these coordinates, we can:")
                print("      1. Highlight the exact section in PDF viewer")
                print("      2. Implement 'Show source' functionality")
                print("      3. Validate extracted data location")
                break


def compare_extraction_quality():
    """Main comparison function"""
    pdf_path = "test_cerebellar_paper.pdf"

    if not os.path.exists(pdf_path):
        print(f"❌ Test PDF not found: {pdf_path}")
        return

    print("\n" + "=" * 70)
    print("🔬 PDF EXTRACTION COMPARISON: pdfplumber vs Marker")
    print("=" * 70)

    # Extract with both methods
    pdfplumber_result = extract_with_pdfplumber(pdf_path)
    marker_result = extract_with_marker(pdf_path)

    if marker_result:
        # Compare results
        print("\n" + "=" * 60)
        print("📊 COMPARISON SUMMARY")
        print("=" * 60)

        print("\n📏 Text Length:")
        print(f"   pdfplumber: {pdfplumber_result['length']} chars")
        print(f"   Marker:     {marker_result['length']} chars")

        print("\n📐 Structure:")
        print("   pdfplumber: Plain text, no structure")
        print("   Marker:     Markdown with headers, lists, formatting")

        print("\n📍 Provenance:")
        print("   pdfplumber: ⚠️  Limited word-level boxes")
        print("   Marker:     ✅ Section-level polygons")

        print("\n🎯 Use Case Fit:")
        print("   pdfplumber: ⚠️  Requires extensive post-processing")
        print("   Marker:     ✅ Ready for AI extraction with provenance")

        # Demonstrate provenance tracking
        compare_provenance_tracking(marker_result)

        print("\n" + "=" * 60)
        print("✅ RECOMMENDATION: Use Marker for cerebellar extraction")
        print("=" * 60)
        print("\nKey advantages:")
        print("  1. ✅ Better structure preservation")
        print("  2. ✅ Automatic section detection")
        print("  3. ✅ Bounding box coordinates for provenance")
        print("  4. ✅ Richer metadata for validation")
        print("  5. ✅ Easier integration with multi-agent system")


if __name__ == "__main__":
    compare_extraction_quality()
