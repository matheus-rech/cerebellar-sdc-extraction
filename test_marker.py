#!/usr/bin/env python3
"""
Test Marker PDF extraction on the sample cerebellar paper
"""

import pypdfium2  # Import at top to avoid warnings
import os
from marker.convert import convert_single_pdf
from marker.models import load_all_models
from marker.output import save_markdown

def test_marker():
    print("🧪 Testing Marker PDF Extraction...")
    print("=" * 60)

    # Check if test PDF exists
    pdf_path = "test_cerebellar_paper.pdf"
    if not os.path.exists(pdf_path):
        print(f"❌ Test PDF not found: {pdf_path}")
        return

    print(f"📄 Loading PDF: {pdf_path}")
    print("⏳ Loading Marker models (this may take a moment on first run)...")

    try:
        # Load models
        model_lst = load_all_models()
        print("✅ Models loaded successfully")

        # Convert PDF to markdown
        print("\n🔄 Converting PDF to markdown...")
        full_text, images, out_meta = convert_single_pdf(
            pdf_path,
            model_lst,
            max_pages=None,
            langs=["English"]
        )

        print("✅ Conversion complete!")
        print("\n" + "=" * 60)
        print("📊 EXTRACTION RESULTS")
        print("=" * 60)

        # Show metadata
        print(f"\n📈 Metadata:")
        print(f"  - Pages: {out_meta.get('pages', 'N/A')}")
        print(f"  - Tables detected: {out_meta.get('table_count', 0)}")
        print(f"  - Equations detected: {out_meta.get('equation_count', 0)}")

        # Show extracted text (first 1000 chars)
        print(f"\n📝 Extracted Text (first 1000 characters):")
        print("-" * 60)
        print(full_text[:1000])
        if len(full_text) > 1000:
            print(f"\n... ({len(full_text) - 1000} more characters)")

        # Save full markdown
        output_path = "test_cerebellar_paper_marker.md"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"\n💾 Full markdown saved to: {output_path}")

        # Save metadata
        import json
        meta_path = "test_cerebellar_paper_marker_meta.json"
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(out_meta, f, indent=2)
        print(f"💾 Metadata saved to: {meta_path}")

        print("\n✅ Marker test completed successfully!")
        return full_text, out_meta

    except Exception as e:
        print(f"\n❌ Error during Marker test: {e}")
        import traceback
        traceback.print_exc()
        return None, None

if __name__ == "__main__":
    test_marker()
