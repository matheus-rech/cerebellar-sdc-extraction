#!/usr/bin/env python3
"""
Marker-based PDF Extractor with Enhanced Provenance

Replaces pdfplumber with Marker for better structure preservation
and automatic section-level bounding boxes.
"""

import os
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class BoundingBox:
    """Bounding box coordinates with page reference"""
    x0: float
    y0: float
    x1: float
    y1: float
    page: int

    def to_dict(self) -> Dict:
        return {
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
            "page": self.page
        }

    def to_svg_rect(self, page_height: float) -> str:
        """Convert to SVG rect for visualization"""
        # Convert from PDF coords (bottom-left origin) to SVG (top-left origin)
        y = page_height - self.y1
        height = self.y1 - self.y0
        return f'<rect x="{self.x0}" y="{y}" width="{self.x1 - self.x0}" height="{height}" />'


class MarkerProvenanceExtractor:
    """
    Extract text from PDF using Marker with automatic section detection
    and bounding box tracking.

    Advantages over pdfplumber:
    - Automatic section detection (headers, lists, paragraphs)
    - Section-level bounding boxes (polygons)
    - Better structure preservation (markdown)
    - Rich metadata (page statistics, table of contents)
    """

    def __init__(self, pdf_path: str, output_dir: Optional[str] = None):
        self.pdf_path = pdf_path
        self.output_dir = output_dir or tempfile.mkdtemp(prefix="marker_extract_")
        self.base_name = Path(pdf_path).stem

        # Storage for extracted data
        self.full_text = None
        self.markdown_text = None
        self.metadata = None
        self.pages_text = {}  # page_num -> text
        self.sections = {}  # section_name -> {text, bbox, page}

        # Extract on initialization
        self._extract_with_marker()

    def _extract_with_marker(self):
        """Run Marker extraction"""
        cmd = [
            "marker_single",
            self.pdf_path,
            "--output_dir", self.output_dir,
            "--output_format", "markdown"
        ]

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Load markdown
            markdown_path = Path(self.output_dir) / self.base_name / f"{self.base_name}.md"
            with open(markdown_path, 'r', encoding='utf-8') as f:
                self.markdown_text = f.read()

            # Load metadata
            meta_path = Path(self.output_dir) / self.base_name / f"{self.base_name}_meta.json"
            with open(meta_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)

            # Build page text index
            self._build_page_index()

            # Build section index with bounding boxes
            self._build_section_index()

        except Exception as e:
            raise RuntimeError(f"Marker extraction failed: {e}")

    def _build_page_index(self):
        """Split markdown text by page"""
        # Simple approach: split by page markers if present
        # For now, just store the full text for page 1
        # This can be enhanced based on Marker's output format
        self.pages_text[1] = self.markdown_text
        self.full_text = self.markdown_text

    def _build_section_index(self):
        """Build index of sections with bounding boxes from table of contents"""
        if not self.metadata or 'table_of_contents' not in self.metadata:
            return

        for section in self.metadata['table_of_contents']:
            title = section['title']
            page_id = section['page_id']
            polygon = section['polygon']

            # Convert polygon to bounding box
            # Polygon is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            x_coords = [p[0] for p in polygon]
            y_coords = [p[1] for p in polygon]

            bbox = BoundingBox(
                x0=min(x_coords),
                y0=min(y_coords),
                x1=max(x_coords),
                y1=max(y_coords),
                page=page_id + 1  # Convert 0-indexed to 1-indexed
            )

            self.sections[title] = {
                'text': title,
                'bbox': bbox,
                'page': page_id + 1
            }

    def extract_all_text(self) -> str:
        """Extract all text from PDF (markdown format)"""
        if self.full_text is None:
            return self.markdown_text
        return self.full_text

    def extract_text_with_coords(self, page_num: int) -> List[Dict]:
        """
        Get text with coordinates for a page.

        Note: Marker provides section-level coordinates, not word-level.
        Returns section information for the specified page.
        """
        sections_on_page = []
        for title, info in self.sections.items():
            if info['page'] == page_num:
                sections_on_page.append({
                    'text': title,
                    'bbox': info['bbox'],
                    'page': page_num
                })
        return sections_on_page

    def find_text_location(self, search_text: str, page_num: int = None) -> Optional[BoundingBox]:
        """
        Find bounding box for specific text.

        Marker provides section-level boxes, so this searches for the
        section that contains the search text.
        """
        search_lower = search_text.lower()

        # Search through sections
        for title, info in self.sections.items():
            if page_num and info['page'] != page_num:
                continue

            # Check if search text is in section title
            if search_lower in title.lower():
                return info['bbox']

            # Also search in full markdown text for the section
            # This is a simplified approach - could be enhanced
            if search_lower in self.markdown_text.lower():
                # If found in text, return the nearest section box
                return info['bbox']

        return None

    def find_text_in_section(self, search_text: str) -> List[Tuple[str, BoundingBox]]:
        """
        Find which section(s) contain the search text.

        Returns list of (section_name, bounding_box) tuples.
        """
        results = []
        search_lower = search_text.lower()

        for title, info in self.sections.items():
            if search_lower in title.lower():
                results.append((title, info['bbox']))

        return results

    def search_text(self, query: str) -> List[Tuple[int, str, BoundingBox]]:
        """
        Search for text across all pages with locations.

        Returns list of (page_num, context, bounding_box) tuples.
        """
        results = []
        query_lower = query.lower()

        # Search in markdown text
        if query_lower in self.markdown_text.lower():
            # Find context
            idx = self.markdown_text.lower().index(query_lower)
            context_start = max(0, idx - 100)
            context_end = min(len(self.markdown_text), idx + len(query) + 100)
            context = self.markdown_text[context_start:context_end]

            # Try to find which section this belongs to
            for title, info in self.sections.items():
                if query_lower in title.lower():
                    results.append((info['page'], context, info['bbox']))
                    break
            else:
                # If not in any section title, just return first section's bbox
                if self.sections:
                    first_section = list(self.sections.values())[0]
                    results.append((first_section['page'], context, first_section['bbox']))

        return results

    def get_section_by_name(self, section_name: str) -> Optional[Dict]:
        """Get section information by name (fuzzy match)"""
        section_lower = section_name.lower()
        for title, info in self.sections.items():
            if section_lower in title.lower():
                return {
                    'title': title,
                    'page': info['page'],
                    'bbox': info['bbox'],
                    'text': title
                }
        return None

    def get_all_sections(self) -> List[Dict]:
        """Get all detected sections with their bounding boxes"""
        return [
            {
                'title': title,
                'page': info['page'],
                'bbox': info['bbox'],
                'text': info['text']
            }
            for title, info in self.sections.items()
        ]

    def get_metadata(self) -> Dict:
        """Get full Marker metadata"""
        return self.metadata or {}

    def get_page_stats(self) -> List[Dict]:
        """Get page-level statistics"""
        if self.metadata and 'page_stats' in self.metadata:
            return self.metadata['page_stats']
        return []

    def get_search_results(self, enable_citations: bool = True, context: str = None) -> List[Dict]:
        """
        Convert Marker sections to Claude search_result blocks.

        Returns search results compatible with Claude's API for RAG applications
        with automatic citations. Each section becomes a search_result block
        with its title, content, and source attribution.

        Args:
            enable_citations: Enable citation tracking for these results
            context: Optional context string with metadata (e.g., publication date,
                    study type, quality notes). This information helps Claude but
                    won't be directly cited. Follows Anthropic's official pattern.

        Returns:
            List of search_result dict blocks ready for Claude API

        Example:
            # Basic usage
            search_results = extractor.get_search_results()

            # With context for paper quality metadata
            context = "Publication: JAMA 2016. Study Type: Retrospective cohort. Sample: n=23"
            search_results = extractor.get_search_results(context=context)

            response = client.messages.create(
                model="claude-sonnet-4-5",
                messages=[{
                    "role": "user",
                    "content": search_results + [{
                        "type": "text",
                        "text": "Extract mortality data"
                    }]
                }]
            )
        """
        sections = self.get_all_sections()

        if not sections:
            # Fallback: create single search result with full text
            result = {
                "type": "search_result",
                "source": f"file://{self.pdf_path}",
                "title": "Full Document",
                "content": [{
                    "type": "text",
                    "text": self.full_text or self.markdown_text
                }],
                "citations": {"enabled": enable_citations}
            }
            if context:
                result["context"] = context
            return [result]

        # Convert each section to search_result block
        search_results = []
        for section in sections:
            # Get section text from markdown by searching for title
            section_text = section.get('text', '')

            # If section text is just the title, try to extract more context
            if section_text == section['title'] and self.markdown_text:
                # Find the section in markdown and extract surrounding text
                title_idx = self.markdown_text.find(section['title'])
                if title_idx != -1:
                    # Extract up to 2000 chars after title
                    end_idx = min(title_idx + 2000, len(self.markdown_text))
                    section_text = self.markdown_text[title_idx:end_idx]

            result = {
                "type": "search_result",
                "source": f"file://{self.pdf_path}#page={section['page']}",
                "title": section['title'],
                "content": [{
                    "type": "text",
                    "text": section_text
                }],
                "citations": {"enabled": enable_citations}
            }
            if context:
                result["context"] = context
            search_results.append(result)

        return search_results

    def close(self):
        """Clean up resources"""
        # Marker output is in temp directory, can be cleaned up if needed
        pass


# Convenience function to maintain compatibility with existing code
def ProvenancePDFExtractor(pdf_path: str) -> MarkerProvenanceExtractor:
    """
    Compatibility wrapper - returns Marker-based extractor.

    This allows existing code to work without modification:
    extractor = ProvenancePDFExtractor("paper.pdf")
    """
    return MarkerProvenanceExtractor(pdf_path)
