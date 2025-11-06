#!/usr/bin/env python3
"""
Test Files API Hybrid Mode

Tests the new Files API hybrid approach:
1. Upload PDF to Files API
2. Extract with MetadataAgent using document content blocks
3. Use local Marker for bounding boxes
4. Compare speed vs search_result mode
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from cerebellar_extractor_pro import MetadataAgent, CerebellarExtractionSystem
from marker_provenance_extractor import MarkerProvenanceExtractor
from anthropic import Anthropic

def test_hybrid_mode(pdf_path: str):
    """Test Files API hybrid extraction with MetadataAgent"""
    print("\n" + "=" * 80)
    print("🚀 Testing Files API Hybrid Mode (MetadataAgent)")
    print("=" * 80)
    print(f"PDF: {Path(pdf_path).name}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 80 + "\n")

    # Initialize components
    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = Anthropic(api_key=api_key)
    agent = MetadataAgent("Metadata Agent", client)
    pdf_extractor = MarkerProvenanceExtractor(pdf_path)
    pdf_text = pdf_extractor.extract_all_text()

    # Test 1: search_result mode (baseline)
    print("📊 Test 1: SEARCH_RESULT Mode (Baseline)")
    print("-" * 80)
    start = datetime.now()
    result_search = agent.extract(pdf_text, pdf_extractor, use_search_results=True, file_id=None)
    time_search = (datetime.now() - start).total_seconds()
    print(f"✅ Completed in {time_search:.2f}s")
    print(f"   Fields: {len(result_search.fields_extracted)}")
    print(f"   Tokens: {result_search.tokens_used}")
    if not result_search.success:
        print(f"   ❌ Error: {result_search.error}")

    # Test 2: Files API hybrid mode
    print("\n📊 Test 2: FILES API Hybrid Mode")
    print("-" * 80)

    # Upload PDF to Files API
    print("   📤 Uploading PDF...")
    start_upload = datetime.now()
    with open(pdf_path, 'rb') as f:
        file_response = client.files.create(
            file=f,
            purpose="extractive_qa"
        )
    file_id = file_response.id
    upload_time = (datetime.now() - start_upload).total_seconds()
    print(f"   ✅ Upload complete: {file_id} ({upload_time:.2f}s)")

    # Extract with Files API
    print("   🔍 Extracting metadata...")
    start_extract = datetime.now()
    result_files = agent.extract(pdf_text, pdf_extractor, use_search_results=False, file_id=file_id)
    time_extract = (datetime.now() - start_extract).total_seconds()
    time_files_total = upload_time + time_extract

    print(f"✅ Completed in {time_extract:.2f}s (extraction only)")
    print(f"   Total time: {time_files_total:.2f}s (including upload)")
    print(f"   Fields: {len(result_files.fields_extracted)}")
    print(f"   Tokens: {result_files.tokens_used}")
    if not result_files.success:
        print(f"   ❌ Error: {result_files.error}")

    # Cleanup
    print("   🗑️  Cleaning up...")
    try:
        client.files.delete(file_id)
        print("   ✅ File deleted")
    except Exception as e:
        print(f"   ⚠️  Could not delete file: {e}")

    pdf_extractor.close()

    # Comparison
    print("\n" + "=" * 80)
    print("📊 PERFORMANCE COMPARISON")
    print("=" * 80)
    speedup = time_search / time_files_total if time_files_total > 0 else 0
    print(f"\nSearch Result Mode:  {time_search:.2f}s")
    print(f"Files API Hybrid:    {time_files_total:.2f}s ({upload_time:.2f}s upload + {time_extract:.2f}s extract)")
    print(f"Speedup:             {speedup:.2f}x")

    token_diff = result_files.tokens_used - result_search.tokens_used
    print(f"\nToken Usage:")
    print(f"  Search Result: {result_search.tokens_used}")
    print(f"  Files API:     {result_files.tokens_used}")
    print(f"  Difference:    {token_diff:+d}")

    # Quality comparison
    print("\n" + "=" * 80)
    print("📊 QUALITY COMPARISON")
    print("=" * 80)

    search_extractions = {e.field: e for e in result_search.fields_extracted}
    files_extractions = {e.field: e for e in result_files.fields_extracted}

    all_fields = set(search_extractions.keys()) | set(files_extractions.keys())

    print(f"\nExtracted Fields: {len(all_fields)}")
    for field in sorted(all_fields):
        search_ex = search_extractions.get(field)
        files_ex = files_extractions.get(field)

        print(f"\n📌 {field}:")
        if search_ex:
            print(f"   Search: {search_ex.value} (conf: {search_ex.confidence:.2f})")
            if search_ex.claude_citations:
                print(f"   📚 Citations: {len(search_ex.claude_citations)}")
        else:
            print(f"   Search: ❌ Not extracted")

        if files_ex:
            print(f"   Files:  {files_ex.value} (conf: {files_ex.confidence:.2f})")
            if files_ex.claude_citations:
                print(f"   📚 Citations: {len(files_ex.claude_citations)}")
        else:
            print(f"   Files:  ❌ Not extracted")

        if search_ex and files_ex:
            match = str(search_ex.value) == str(files_ex.value)
            print(f"   Match:  {'✅' if match else '⚠️'}")

    print("\n" + "=" * 80)
    print("✅ Test Complete!")
    print("=" * 80)

    return {
        'search_result': result_search,
        'files_api': result_files,
        'speedup': speedup,
        'time_search': time_search,
        'time_files_total': time_files_total,
        'upload_time': upload_time,
        'extract_time': time_extract
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_files_api_hybrid.py <pdf_path>")
        print("\nExample:")
        print("  python test_files_api_hybrid.py Kim2016.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]

    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        sys.exit(1)

    # Check for API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("❌ ANTHROPIC_API_KEY not set")
        print("   Run: export ANTHROPIC_API_KEY='your-key'")
        sys.exit(1)

    try:
        results = test_hybrid_mode(pdf_path)
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
