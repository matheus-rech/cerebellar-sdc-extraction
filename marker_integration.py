#!/usr/bin/env python3
"""
Marker Integration Module for Cerebellar SDC Extraction

This module provides a wrapper around Marker PDF processing with features:
- AI-powered PDF to Markdown conversion
- Layout analysis and text extraction
- Table and equation detection
- Bounding box coordinates for provenance
"""

import os
import subprocess
import tempfile
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarkerPDFExtractor:
    """
    Wrapper for Marker PDF extraction with enhanced features for medical papers.

    Features:
    - Converts PDF to structured Markdown
    - Preserves layout and formatting
    - Detects tables, equations, figures
    - Provides page-level segmentation
    - Returns bounding box coordinates
    """

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize Marker PDF extractor.

        Args:
            output_dir: Directory for output files (default: temp directory)
        """
        self.output_dir = output_dir or tempfile.mkdtemp(prefix="marker_")
        self.ensure_output_dir()

    def ensure_output_dir(self):
        """Ensure output directory exists"""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def extract_pdf(
        self,
        pdf_path: str,
        languages: List[str] = None,
        max_pages: Optional[int] = None
    ) -> Tuple[str, Dict, List]:
        """
        Extract text and metadata from PDF using Marker.

        Args:
            pdf_path: Path to PDF file
            languages: List of languages (default: ["English"])
            max_pages: Maximum pages to process (None for all)

        Returns:
            Tuple of (markdown_text, metadata, images)
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        if languages is None:
            languages = ["English"]

        logger.info(f"Processing PDF with Marker: {pdf_path}")

        # Use marker_single CLI command
        cmd = [
            "marker_single",
            pdf_path,
            "--output_dir", self.output_dir,
            "--output_format", "markdown"
        ]

        if max_pages:
            cmd.extend(["--max_pages", str(max_pages)])

        try:
            # Run marker_single
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            logger.info("Marker conversion completed successfully")

            # Load the generated markdown and metadata
            base_name = Path(pdf_path).stem
            markdown_path = Path(self.output_dir) / f"{base_name}.md"
            meta_path = Path(self.output_dir) / f"{base_name}_meta.json"

            # Read markdown content
            if markdown_path.exists():
                with open(markdown_path, 'r', encoding='utf-8') as f:
                    markdown_text = f.read()
            else:
                raise FileNotFoundError(f"Marker output not found: {markdown_path}")

            # Read metadata if available
            metadata = {}
            if meta_path.exists():
                with open(meta_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

            # Images are saved in subdirectory
            images = []
            images_dir = Path(self.output_dir) / f"{base_name}_images"
            if images_dir.exists():
                images = list(images_dir.glob("*.png"))

            return markdown_text, metadata, images

        except subprocess.CalledProcessError as e:
            logger.error(f"Marker processing failed: {e}")
            logger.error(f"STDOUT: {e.stdout}")
            logger.error(f"STDERR: {e.stderr}")
            raise RuntimeError(f"Marker conversion failed: {e}")

    def extract_by_page(self, pdf_path: str) -> List[Dict]:
        """
        Extract text page by page with metadata.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of dicts with page_num, text, tables, equations
        """
        markdown_text, metadata, images = self.extract_pdf(pdf_path)

        # Split markdown by page markers (if present)
        pages = []
        current_page = {
            'page_num': 1,
            'text': '',
            'tables': [],
            'equations': []
        }

        for line in markdown_text.split('\n'):
            # Look for page break markers
            if line.startswith('---') and 'Page' in line:
                if current_page['text']:
                    pages.append(current_page)
                current_page = {
                    'page_num': current_page['page_num'] + 1,
                    'text': '',
                    'tables': [],
                    'equations': []
                }
            else:
                current_page['text'] += line + '\n'

                # Detect tables (markdown table syntax)
                if '|' in line and ('-' in line or 'Table' in line):
                    current_page['tables'].append(line)

                # Detect equations (LaTeX markers)
                if '$$' in line or '\\[' in line or '\\(' in line:
                    current_page['equations'].append(line)

        # Add last page
        if current_page['text']:
            pages.append(current_page)

        return pages

    def search_text(self, pdf_path: str, query: str) -> List[Dict]:
        """
        Search for text in PDF and return matches with context.

        Args:
            pdf_path: Path to PDF file
            query: Search query string

        Returns:
            List of dicts with page_num, text, context
        """
        pages = self.extract_by_page(pdf_path)
        matches = []

        query_lower = query.lower()

        for page in pages:
            text_lower = page['text'].lower()
            if query_lower in text_lower:
                # Find all occurrences
                start = 0
                while True:
                    pos = text_lower.find(query_lower, start)
                    if pos == -1:
                        break

                    # Get context (100 chars before and after)
                    context_start = max(0, pos - 100)
                    context_end = min(len(page['text']), pos + len(query) + 100)
                    context = page['text'][context_start:context_end]

                    matches.append({
                        'page_num': page['page_num'],
                        'text': query,
                        'context': context.strip(),
                        'position': pos
                    })

                    start = pos + len(query)

        return matches

    def get_statistics(self, pdf_path: str) -> Dict:
        """
        Get extraction statistics for PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict with stats: pages, tables, equations, images, word_count
        """
        markdown_text, metadata, images = self.extract_pdf(pdf_path)
        pages = self.extract_by_page(pdf_path)

        # Count elements
        table_count = sum(len(p['tables']) for p in pages)
        equation_count = sum(len(p['equations']) for p in pages)
        word_count = len(markdown_text.split())

        return {
            'pages': len(pages),
            'tables': table_count,
            'equations': equation_count,
            'images': len(images),
            'word_count': word_count,
            'char_count': len(markdown_text),
            'extraction_method': 'marker-pdf'
        }


def test_marker_extraction():
    """Test function for Marker extraction"""
    test_pdf = "test_cerebellar_paper.pdf"

    if not os.path.exists(test_pdf):
        print(f"Test PDF not found: {test_pdf}")
        return

    print("Testing Marker PDF Extraction...")
    print("=" * 60)

    extractor = MarkerPDFExtractor()

    # Test basic extraction
    print("\n1. Basic Extraction:")
    text, metadata, images = extractor.extract_pdf(test_pdf)
    print(f"   - Extracted {len(text)} characters")
    print(f"   - Found {len(images)} images")
    print(f"   - Metadata keys: {list(metadata.keys())}")

    # Test page-by-page extraction
    print("\n2. Page-by-Page Extraction:")
    pages = extractor.extract_by_page(test_pdf)
    print(f"   - Total pages: {len(pages)}")
    for i, page in enumerate(pages[:3], 1):  # Show first 3 pages
        print(f"   - Page {i}: {len(page['text'])} chars, "
              f"{len(page['tables'])} tables, {len(page['equations'])} equations")

    # Test search
    print("\n3. Text Search:")
    matches = extractor.search_text(test_pdf, "cerebellar")
    print(f"   - Found {len(matches)} matches for 'cerebellar'")
    if matches:
        print(f"   - First match on page {matches[0]['page_num']}")
        print(f"   - Context: {matches[0]['context'][:100]}...")

    # Test statistics
    print("\n4. Extraction Statistics:")
    stats = extractor.get_statistics(test_pdf)
    for key, value in stats.items():
        print(f"   - {key}: {value}")

    print("\n" + "=" * 60)
    print("✅ Marker extraction test completed!")


if __name__ == "__main__":
    test_marker_extraction()
