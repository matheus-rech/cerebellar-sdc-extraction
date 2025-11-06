#!/usr/bin/env python3
"""
Compare Legacy vs Search Result Extraction Approaches

Runs OutcomesAgent with both methods on the same PDF and provides:
- Side-by-side extraction results
- Citation quality analysis
- Performance metrics comparison
"""

import os
import sys
from pathlib import Path
from typing import Dict, List
import json
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import extraction system
from cerebellar_extractor_pro import OutcomesAgent, ExtractionResult
from marker_provenance_extractor import MarkerProvenanceExtractor


class SearchResultComparison:
    """Compare legacy and search_result extraction approaches"""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.marker_extractor = MarkerProvenanceExtractor(pdf_path)

        # Initialize Anthropic client and OutcomesAgent
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        client = Anthropic(api_key=api_key)
        self.outcomes_agent = OutcomesAgent(name="Outcomes Agent", client=client)

        # Storage for results
        self.legacy_result = None
        self.search_result_result = None

    def run_comparison(self):
        """Run both extraction approaches"""
        print("\n" + "=" * 80)
        print("🔬 Cerebellar Extraction: Legacy vs Search Result Comparison")
        print("=" * 80)
        print(f"PDF: {Path(self.pdf_path).name}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("=" * 80 + "\n")

        # Get PDF text for legacy mode
        pdf_text = self.marker_extractor.extract_all_text()

        # Run legacy extraction
        print("⏳ Running LEGACY extraction (plain text)...")
        self.legacy_result = self.outcomes_agent.extract(
            pdf_text=pdf_text,
            pdf_extractor=self.marker_extractor,
            use_search_results=False
        )
        print(f"   ✅ Completed in {self.legacy_result.processing_time:.2f}s")
        print(f"   📊 Tokens: {self.legacy_result.tokens_used}")
        print(f"   📝 Fields: {len(self.legacy_result.fields_extracted)}")
        if not self.legacy_result.success and hasattr(self.legacy_result, 'error'):
            print(f"   ❌ Error: {self.legacy_result.error}")

        # Run search_result extraction
        print("\n⏳ Running SEARCH_RESULT extraction (with citations)...")
        self.search_result_result = self.outcomes_agent.extract(
            pdf_text=pdf_text,  # Not used in search_result mode
            pdf_extractor=self.marker_extractor,
            use_search_results=True
        )
        print(f"   ✅ Completed in {self.search_result_result.processing_time:.2f}s")
        print(f"   📊 Tokens: {self.search_result_result.tokens_used}")
        print(f"   📝 Fields: {len(self.search_result_result.fields_extracted)}")
        if not self.search_result_result.success and hasattr(self.search_result_result, 'error'):
            print(f"   ❌ Error: {self.search_result_result.error}")

        print("\n" + "=" * 80)

    def display_comparison(self):
        """Display side-by-side comparison"""
        if not self.legacy_result or not self.search_result_result:
            print("❌ No results to compare. Run comparison first.")
            return

        print("\n📊 EXTRACTION RESULTS COMPARISON")
        print("=" * 80)

        # Build field mapping
        legacy_fields = {f.field: f for f in self.legacy_result.fields_extracted}
        search_fields = {f.field: f for f in self.search_result_result.fields_extracted}

        all_fields = set(legacy_fields.keys()) | set(search_fields.keys())

        for field in sorted(all_fields):
            legacy = legacy_fields.get(field)
            search = search_fields.get(field)

            print(f"\n{'─' * 80}")
            print(f"📌 Field: {field}")
            print(f"{'─' * 80}")

            # Legacy result
            print("\n🔹 LEGACY MODE:")
            if legacy:
                print(f"   Value:      {legacy.value}")
                print(f"   Confidence: {legacy.confidence:.2f}")
                print(f"   Source:     {legacy.source_text[:100]}...")
            else:
                print("   ❌ Not extracted")

            # Search result
            print("\n🔹 SEARCH_RESULT MODE:")
            if search:
                print(f"   Value:      {search.value}")
                print(f"   Confidence: {search.confidence:.2f}")
                print(f"   Source:     {search.source_text[:100]}...")

                # Show enhanced citation data if available
                if search.cited_sections:
                    print(f"   📚 Cited Sections: {', '.join(search.cited_sections)}")
                if search.cited_text_snippets:
                    print(f"   📖 Quoted Text: {search.cited_text_snippets[0][:100]}...")
                if search.citation_confidence:
                    print(f"   ✨ Citation Quality: {search.citation_confidence:.2f}")

                # Show PDF location data if available
                if search.claude_citations:
                    bbox_count = sum(1 for c in search.claude_citations if c.get('pdf_bounding_box'))
                    if bbox_count > 0:
                        print(f"   📍 PDF Locations Found: {bbox_count}/{len(search.claude_citations)} citations")
            else:
                print("   ❌ Not extracted")

            # Comparison
            if legacy and search:
                value_match = str(legacy.value) == str(search.value)
                conf_diff = abs(legacy.confidence - search.confidence)

                print(f"\n   {'✅' if value_match else '⚠️'} Values Match: {value_match}")
                print(f"   📊 Confidence Δ: {conf_diff:+.2f}")

        print("\n" + "=" * 80)

    def display_metrics(self):
        """Display performance and quality metrics"""
        print("\n📈 PERFORMANCE METRICS")
        print("=" * 80)

        metrics = [
            ["Metric", "Legacy", "Search Result", "Difference"],
            ["─" * 20, "─" * 15, "─" * 15, "─" * 15],
        ]

        # Processing time
        time_diff = self.search_result_result.processing_time - self.legacy_result.processing_time
        metrics.append([
            "Processing Time",
            f"{self.legacy_result.processing_time:.2f}s",
            f"{self.search_result_result.processing_time:.2f}s",
            f"{time_diff:+.2f}s"
        ])

        # Tokens
        token_diff = self.search_result_result.tokens_used - self.legacy_result.tokens_used
        metrics.append([
            "Tokens Used",
            f"{self.legacy_result.tokens_used}",
            f"{self.search_result_result.tokens_used}",
            f"{token_diff:+d}"
        ])

        # Fields extracted
        fields_diff = len(self.search_result_result.fields_extracted) - len(self.legacy_result.fields_extracted)
        metrics.append([
            "Fields Extracted",
            f"{len(self.legacy_result.fields_extracted)}",
            f"{len(self.search_result_result.fields_extracted)}",
            f"{fields_diff:+d}"
        ])

        # Average confidence
        if len(self.legacy_result.fields_extracted) > 0:
            legacy_conf = sum(f.confidence for f in self.legacy_result.fields_extracted) / len(self.legacy_result.fields_extracted)
        else:
            legacy_conf = 0.0

        if len(self.search_result_result.fields_extracted) > 0:
            search_conf = sum(f.confidence for f in self.search_result_result.fields_extracted) / len(self.search_result_result.fields_extracted)
        else:
            search_conf = 0.0

        conf_diff = search_conf - legacy_conf

        metrics.append([
            "Avg Confidence",
            f"{legacy_conf:.3f}" if legacy_conf > 0 else "N/A",
            f"{search_conf:.3f}" if search_conf > 0 else "N/A",
            f"{conf_diff:+.3f}" if (legacy_conf > 0 or search_conf > 0) else "N/A"
        ])

        # Print table
        for row in metrics:
            print(f"{row[0]:<20} {row[1]:<15} {row[2]:<15} {row[3]:<15}")

        print("=" * 80)

    def analyze_citations(self):
        """Analyze citation quality for search_result mode"""
        print("\n📚 CITATION QUALITY ANALYSIS (Search Result Mode)")
        print("=" * 80)

        search_fields = self.search_result_result.fields_extracted

        has_citations = sum(1 for f in search_fields if f.claude_citations)
        has_sections = sum(1 for f in search_fields if f.cited_sections)
        has_snippets = sum(1 for f in search_fields if f.cited_text_snippets)

        total = len(search_fields)

        if total > 0:
            print(f"\n✅ Fields with Claude Citations:  {has_citations}/{total} ({has_citations/total*100:.1f}%)")
            print(f"✅ Fields with Cited Sections:    {has_sections}/{total} ({has_sections/total*100:.1f}%)")
            print(f"✅ Fields with Quoted Text:       {has_snippets}/{total} ({has_snippets/total*100:.1f}%)")
        else:
            print(f"\n⚠️  No fields extracted - cannot analyze citations")

        if has_citations > 0 or has_sections > 0:
            print("\n🎯 Citation Details:")
            for field in search_fields:
                if field.cited_sections or field.claude_citations:
                    print(f"\n   📌 {field.field}:")
                    if field.cited_sections:
                        print(f"      Sections: {', '.join(field.cited_sections)}")
                    if field.citation_confidence:
                        print(f"      Quality: {field.citation_confidence:.2f}")
        else:
            print("\n⚠️  No citations found in this extraction")

        # Show PDF location integration stats
        if has_citations > 0:
            total_citations = sum(len(f.claude_citations) for f in search_fields if f.claude_citations)
            citations_with_bbox = sum(
                sum(1 for c in f.claude_citations if c.get('pdf_bounding_box'))
                for f in search_fields if f.claude_citations
            )

            print(f"\n📍 PDF Location Integration:")
            print(f"   Total Citations: {total_citations}")
            print(f"   Located in PDF: {citations_with_bbox}/{total_citations} ({citations_with_bbox/total_citations*100:.1f}%)")

            if citations_with_bbox > 0:
                print(f"\n   ✅ Citations successfully integrated with search_text()")
                print(f"   ✅ Bounding boxes available for highlighting and tagging")

        print("\n" + "=" * 80)

    def export_comparison(self, output_path: str = None):
        """Export comparison to JSON"""
        if not output_path:
            output_path = f"comparison_{Path(self.pdf_path).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        comparison_data = {
            "pdf_path": self.pdf_path,
            "timestamp": datetime.now().isoformat(),
            "legacy": {
                "agent": self.legacy_result.agent_name,
                "processing_time": self.legacy_result.processing_time,
                "tokens": self.legacy_result.tokens_used,
                "fields": [f.to_dict() for f in self.legacy_result.fields_extracted]
            },
            "search_result": {
                "agent": self.search_result_result.agent_name,
                "processing_time": self.search_result_result.processing_time,
                "tokens": self.search_result_result.tokens_used,
                "fields": [f.to_dict() for f in self.search_result_result.fields_extracted]
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(comparison_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Comparison exported to: {output_path}")
        return output_path


def main():
    """Run comparison"""
    if len(sys.argv) < 2:
        print("Usage: python compare_search_results.py <pdf_path>")
        print("\nExample:")
        print("  python compare_search_results.py test_cerebellar_paper.pdf")
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

    # Run comparison
    comparison = SearchResultComparison(pdf_path)

    try:
        comparison.run_comparison()
        comparison.display_comparison()
        comparison.display_metrics()
        comparison.analyze_citations()
        comparison.export_comparison()

        print("\n✅ Comparison complete!")

    except Exception as e:
        print(f"\n❌ Error during comparison: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
