#!/usr/bin/env python3
"""
PDF Enhancements Module - Advanced PDF Processing Capabilities

Adds high-quality PDF processing features inspired by Anthropic's PDF skills:
- PDF rendering to images for visual analysis
- Enhanced table extraction with custom strategies
- Image extraction from PDFs
- OCR fallback for scanned PDFs
- Character-level coordinate precision
- Bounding box validation utilities

Author: Dr. Matheus Rech
Date: November 6, 2025
"""

import os
import io
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from PIL import Image
import pdfplumber
from pdf2image import convert_from_path
import pytesseract

# Optional imports with fallbacks
try:
    import pypdfium2 as pdfium
    PYPDFIUM_AVAILABLE = True
except ImportError:
    PYPDFIUM_AVAILABLE = False


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

    def area(self) -> float:
        """Calculate bounding box area"""
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    def intersects(self, other: 'BoundingBox') -> bool:
        """Check if this box intersects with another"""
        if self.page != other.page:
            return False
        return not (self.x1 < other.x0 or
                   self.x0 > other.x1 or
                   self.y1 < other.y0 or
                   self.y0 > other.y1)

    def union(self, other: 'BoundingBox') -> 'BoundingBox':
        """Return union (smallest box containing both boxes)"""
        if self.page != other.page:
            raise ValueError("Cannot union boxes from different pages")
        return BoundingBox(
            x0=min(self.x0, other.x0),
            y0=min(self.y0, other.y0),
            x1=max(self.x1, other.x1),
            y1=max(self.y1, other.y1),
            page=self.page
        )


class PDFEnhancer:
    """
    Advanced PDF processing capabilities following Anthropic's best practices.

    Features:
    - Visual rendering with configurable DPI
    - Advanced table extraction with custom pdfplumber settings
    - Image extraction from PDFs
    - OCR fallback for scanned documents
    - Character-level coordinate precision
    - Bounding box validation and optimization
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # Cache for lazy loading
        self._pdfplumber_pdf = None
        self._rendered_pages = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Clean up resources"""
        if self._pdfplumber_pdf:
            self._pdfplumber_pdf.close()
            self._pdfplumber_pdf = None
        self._rendered_pages.clear()

    @property
    def plumber_pdf(self):
        """Lazy load pdfplumber PDF object"""
        if self._pdfplumber_pdf is None:
            self._pdfplumber_pdf = pdfplumber.open(str(self.pdf_path))
        return self._pdfplumber_pdf

    # =========================================================================
    # PDF Rendering for Visual Analysis
    # =========================================================================

    def render_pages_to_images(
        self,
        pages: Optional[List[int]] = None,
        dpi: int = 200,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None
    ) -> List[Tuple[int, Image.Image]]:
        """
        Render PDF pages to images for visual analysis with Claude.

        Args:
            pages: List of page numbers (1-indexed). If None, renders all pages.
            dpi: Rendering DPI (default 200 for good quality/size balance)
            max_width: Maximum image width in pixels
            max_height: Maximum image height in pixels

        Returns:
            List of (page_number, PIL.Image) tuples

        Example:
            enhancer = PDFEnhancer("paper.pdf")
            images = enhancer.render_pages_to_images(pages=[1, 2], dpi=150)
            for page_num, img in images:
                # Send img to Claude for analysis
                pass
        """
        # Use pdf2image for reliable rendering
        page_range = None if pages is None else [(p, p) for p in pages]

        images = convert_from_path(
            str(self.pdf_path),
            dpi=dpi,
            first_page=pages[0] if pages else None,
            last_page=pages[-1] if pages else None
        )

        result = []
        start_page = pages[0] if pages else 1

        for i, img in enumerate(images):
            page_num = start_page + i

            # Resize if needed
            if max_width or max_height:
                img.thumbnail((max_width or img.width, max_height or img.height), Image.Resampling.LANCZOS)

            result.append((page_num, img))
            self._rendered_pages[page_num] = img

        return result

    def render_page_to_bytes(
        self,
        page_num: int,
        dpi: int = 200,
        format: str = "PNG"
    ) -> bytes:
        """
        Render single page to bytes for API transmission.

        Args:
            page_num: Page number (1-indexed)
            dpi: Rendering DPI
            format: Image format (PNG, JPEG, etc.)

        Returns:
            Image bytes ready for API transmission
        """
        images = self.render_pages_to_images(pages=[page_num], dpi=dpi)
        if not images:
            raise ValueError(f"Could not render page {page_num}")

        _, img = images[0]
        buf = io.BytesIO()
        img.save(buf, format=format)
        return buf.getvalue()

    # =========================================================================
    # Enhanced Table Extraction
    # =========================================================================

    def extract_tables_advanced(
        self,
        page_num: int,
        table_settings: Optional[Dict] = None,
        return_debug_images: bool = False
    ) -> List[Dict]:
        """
        Extract tables with advanced pdfplumber settings for complex layouts.

        Args:
            page_num: Page number (1-indexed)
            table_settings: Custom table settings. If None, uses optimized defaults.
            return_debug_images: Include debug images showing detected table structure

        Returns:
            List of table dictionaries with:
                - data: 2D list of cell values
                - bbox: BoundingBox of the table
                - debug_image: PIL.Image (if return_debug_images=True)

        Default settings are optimized for medical research papers:
            - vertical_strategy: "lines" (strict line detection)
            - horizontal_strategy: "lines"
            - snap_tolerance: 3 (px tolerance for line alignment)
            - intersection_tolerance: 15 (px tolerance for intersections)
        """
        # Optimized defaults for medical research papers
        default_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
            "intersection_tolerance": 15,
            "min_words_vertical": 3,
            "min_words_horizontal": 1
        }

        settings = table_settings or default_settings

        page = self.plumber_pdf.pages[page_num - 1]
        tables = page.find_tables(table_settings=settings)

        result = []
        for table in tables:
            table_data = table.extract()
            bbox = BoundingBox(
                x0=table.bbox[0],
                y0=table.bbox[1],
                x1=table.bbox[2],
                y1=table.bbox[3],
                page=page_num
            )

            table_dict = {
                "data": table_data,
                "bbox": bbox,
                "rows": len(table_data),
                "cols": len(table_data[0]) if table_data else 0
            }

            if return_debug_images:
                # Create debug image showing table structure
                im = page.to_image(resolution=150)
                im.debug_tablefinder(table_settings=settings)
                table_dict["debug_image"] = im.original

            result.append(table_dict)

        return result

    def extract_all_tables(self, table_settings: Optional[Dict] = None) -> Dict[int, List[Dict]]:
        """
        Extract tables from all pages.

        Returns:
            Dictionary mapping page_num -> list of tables
        """
        tables_by_page = {}
        for i, page in enumerate(self.plumber_pdf.pages):
            page_num = i + 1
            tables = self.extract_tables_advanced(
                page_num,
                table_settings=table_settings,
                return_debug_images=False
            )
            if tables:
                tables_by_page[page_num] = tables

        return tables_by_page

    # =========================================================================
    # Image Extraction
    # =========================================================================

    def extract_images(
        self,
        page_num: Optional[int] = None,
        min_width: int = 50,
        min_height: int = 50
    ) -> List[Dict]:
        """
        Extract embedded images from PDF pages.

        Args:
            page_num: Specific page (1-indexed), or None for all pages
            min_width: Minimum image width to include
            min_height: Minimum image height to include

        Returns:
            List of image dictionaries with:
                - image: PIL.Image object
                - page: Page number
                - bbox: BoundingBox of image location
                - width: Image width
                - height: Image height
        """
        images = []

        pages_to_process = [page_num] if page_num else range(1, len(self.plumber_pdf.pages) + 1)

        for pnum in pages_to_process:
            page = self.plumber_pdf.pages[pnum - 1]

            # Extract images using pdfplumber
            for img_obj in page.images:
                width = img_obj.get('width', 0)
                height = img_obj.get('height', 0)

                if width >= min_width and height >= min_height:
                    bbox = BoundingBox(
                        x0=img_obj['x0'],
                        y0=img_obj['top'],
                        x1=img_obj['x1'],
                        y1=img_obj['bottom'],
                        page=pnum
                    )

                    # Try to extract actual image data
                    try:
                        # Crop image from page
                        im = page.to_image(resolution=150)
                        cropped = im.original.crop((
                            int(bbox.x0 * 150/72),
                            int(bbox.y0 * 150/72),
                            int(bbox.x1 * 150/72),
                            int(bbox.y1 * 150/72)
                        ))

                        images.append({
                            'image': cropped,
                            'page': pnum,
                            'bbox': bbox,
                            'width': width,
                            'height': height
                        })
                    except Exception as e:
                        print(f"Warning: Could not extract image on page {pnum}: {e}")
                        continue

        return images

    # =========================================================================
    # OCR Fallback for Scanned PDFs
    # =========================================================================

    def is_scanned_pdf(self, sample_pages: int = 3) -> bool:
        """
        Detect if PDF is scanned (low text content).

        Args:
            sample_pages: Number of pages to sample for detection

        Returns:
            True if appears to be scanned/image-based
        """
        total_chars = 0
        pages_checked = min(sample_pages, len(self.plumber_pdf.pages))

        for i in range(pages_checked):
            page = self.plumber_pdf.pages[i]
            text = page.extract_text()
            if text:
                total_chars += len(text.strip())

        avg_chars_per_page = total_chars / pages_checked if pages_checked > 0 else 0

        # Heuristic: if less than 100 chars per page, likely scanned
        return avg_chars_per_page < 100

    def extract_text_with_ocr_fallback(
        self,
        page_num: int,
        force_ocr: bool = False
    ) -> Tuple[str, bool]:
        """
        Extract text with automatic OCR fallback for scanned pages.

        Args:
            page_num: Page number (1-indexed)
            force_ocr: Force OCR even if text extraction works

        Returns:
            Tuple of (text, used_ocr)
        """
        page = self.plumber_pdf.pages[page_num - 1]

        # Try normal text extraction first
        if not force_ocr:
            text = page.extract_text()
            if text and len(text.strip()) > 50:
                return text, False

        # Fallback to OCR
        try:
            # Render page to image
            images = self.render_pages_to_images(pages=[page_num], dpi=300)
            if not images:
                return "", False

            _, img = images[0]

            # Run OCR
            text = pytesseract.image_to_string(img, lang='eng')
            return text, True

        except Exception as e:
            print(f"Warning: OCR failed for page {page_num}: {e}")
            return "", False

    # =========================================================================
    # Character-Level Coordinate Precision
    # =========================================================================

    def get_character_level_coords(
        self,
        page_num: int,
        search_text: Optional[str] = None
    ) -> List[Dict]:
        """
        Get character-level coordinates for precise highlighting.

        Args:
            page_num: Page number (1-indexed)
            search_text: If provided, only return chars matching this text

        Returns:
            List of character dictionaries with:
                - char: The character
                - x0, y0, x1, y1: Precise coordinates
                - font: Font name
                - size: Font size
        """
        page = self.plumber_pdf.pages[page_num - 1]
        chars = page.chars

        if search_text:
            # Find characters that match search text
            search_lower = search_text.lower()
            page_text = ''.join(c['text'] for c in chars).lower()

            if search_lower not in page_text:
                return []

            # Find start index
            start_idx = page_text.index(search_lower)
            end_idx = start_idx + len(search_text)

            return chars[start_idx:end_idx]

        return chars

    def find_text_precise_bbox(
        self,
        page_num: int,
        search_text: str
    ) -> Optional[BoundingBox]:
        """
        Find precise bounding box for text using character-level coordinates.

        More accurate than word-level or line-level bounding boxes.

        Args:
            page_num: Page number (1-indexed)
            search_text: Text to find

        Returns:
            BoundingBox with precise coordinates, or None if not found
        """
        chars = self.get_character_level_coords(page_num, search_text)

        if not chars:
            return None

        # Calculate tight bounding box around all characters
        x0 = min(c['x0'] for c in chars)
        y0 = min(c['top'] for c in chars)
        x1 = max(c['x1'] for c in chars)
        y1 = max(c['bottom'] for c in chars)

        return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1, page=page_num)

    # =========================================================================
    # Bounding Box Validation and Utilities
    # =========================================================================

    @staticmethod
    def validate_bounding_boxes(
        boxes: List[BoundingBox],
        page_width: float,
        page_height: float,
        allow_intersections: bool = False,
        min_area: float = 10.0
    ) -> Tuple[List[BoundingBox], List[str]]:
        """
        Validate bounding boxes for quality and correctness.

        Args:
            boxes: List of BoundingBox objects to validate
            page_width: Page width for bounds checking
            page_height: Page height for bounds checking
            allow_intersections: Whether to allow overlapping boxes
            min_area: Minimum box area (reject very small boxes)

        Returns:
            Tuple of (valid_boxes, error_messages)
        """
        valid_boxes = []
        errors = []

        for i, box in enumerate(boxes):
            # Check bounds
            if box.x0 < 0 or box.y0 < 0 or box.x1 > page_width or box.y1 > page_height:
                errors.append(f"Box {i} out of page bounds")
                continue

            # Check ordering
            if box.x0 >= box.x1 or box.y0 >= box.y1:
                errors.append(f"Box {i} has invalid coordinates (x0 >= x1 or y0 >= y1)")
                continue

            # Check minimum area
            if box.area() < min_area:
                errors.append(f"Box {i} area {box.area():.1f} < minimum {min_area}")
                continue

            # Check intersections with previously validated boxes
            if not allow_intersections:
                for j, valid_box in enumerate(valid_boxes):
                    if box.intersects(valid_box):
                        errors.append(f"Box {i} intersects with box {j}")
                        break
                else:
                    valid_boxes.append(box)
            else:
                valid_boxes.append(box)

        return valid_boxes, errors

    @staticmethod
    def merge_overlapping_boxes(
        boxes: List[BoundingBox],
        same_page_only: bool = True
    ) -> List[BoundingBox]:
        """
        Merge overlapping bounding boxes into larger boxes.

        Useful for consolidating fragmented text regions.

        Args:
            boxes: List of BoundingBox objects
            same_page_only: Only merge boxes from the same page

        Returns:
            List of merged BoundingBox objects
        """
        if not boxes:
            return []

        # Sort by page and x0
        sorted_boxes = sorted(boxes, key=lambda b: (b.page, b.x0))

        merged = []
        current = sorted_boxes[0]

        for next_box in sorted_boxes[1:]:
            # Check if should merge
            if same_page_only and current.page != next_box.page:
                merged.append(current)
                current = next_box
            elif current.intersects(next_box):
                # Merge
                current = current.union(next_box)
            else:
                merged.append(current)
                current = next_box

        merged.append(current)
        return merged

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def get_page_info(self, page_num: int) -> Dict:
        """
        Get comprehensive page information.

        Returns:
            Dictionary with page metadata including:
                - dimensions, text_length, char_count, image_count, table_count
        """
        page = self.plumber_pdf.pages[page_num - 1]
        text = page.extract_text() or ""

        return {
            'page_num': page_num,
            'width': page.width,
            'height': page.height,
            'text_length': len(text),
            'char_count': len(page.chars),
            'image_count': len(page.images),
            'table_count': len(page.find_tables())
        }

    def get_all_page_info(self) -> List[Dict]:
        """Get information for all pages"""
        return [self.get_page_info(i+1) for i in range(len(self.plumber_pdf.pages))]


# =============================================================================
# Convenience Functions
# =============================================================================

def validate_pdf_bboxes(
    pdf_path: str,
    boxes: List[BoundingBox],
    page_num: int
) -> Tuple[List[BoundingBox], List[str]]:
    """
    Convenience function to validate bounding boxes against actual PDF dimensions.

    Args:
        pdf_path: Path to PDF
        boxes: List of bounding boxes to validate
        page_num: Page number for dimension lookup

    Returns:
        Tuple of (valid_boxes, error_messages)
    """
    with PDFEnhancer(pdf_path) as enhancer:
        page_info = enhancer.get_page_info(page_num)
        return PDFEnhancer.validate_bounding_boxes(
            boxes,
            page_width=page_info['width'],
            page_height=page_info['height']
        )


def extract_tables_with_images(
    pdf_path: str,
    page_num: int,
    output_dir: str = "table_debug"
) -> List[Dict]:
    """
    Extract tables and save debug images showing detection.

    Args:
        pdf_path: Path to PDF
        page_num: Page number
        output_dir: Directory to save debug images

    Returns:
        List of table dictionaries with saved debug image paths
    """
    os.makedirs(output_dir, exist_ok=True)

    with PDFEnhancer(pdf_path) as enhancer:
        tables = enhancer.extract_tables_advanced(
            page_num,
            return_debug_images=True
        )

        for i, table in enumerate(tables):
            if 'debug_image' in table:
                img = table['debug_image']
                img_path = os.path.join(output_dir, f"page{page_num}_table{i}.png")
                img.save(img_path)
                table['debug_image_path'] = img_path
                del table['debug_image']  # Remove PIL object from dict

        return tables


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_enhancements.py <pdf_path>")
        print("\nThis module provides advanced PDF processing capabilities.")
        print("Import it in your code to use the PDFEnhancer class.")
        sys.exit(1)

    pdf_path = sys.argv[1]

    print(f"🔍 Analyzing {pdf_path}...\n")

    with PDFEnhancer(pdf_path) as enhancer:
        # Check if scanned
        is_scanned = enhancer.is_scanned_pdf()
        print(f"Scanned PDF: {is_scanned}")

        # Get page info
        pages = enhancer.get_all_page_info()
        print(f"\nTotal pages: {len(pages)}")

        for page in pages[:3]:  # Show first 3 pages
            print(f"\nPage {page['page_num']}:")
            print(f"  Dimensions: {page['width']:.1f} x {page['height']:.1f}")
            print(f"  Text length: {page['text_length']} chars")
            print(f"  Images: {page['image_count']}")
            print(f"  Tables: {page['table_count']}")

        # Extract tables from first page
        if pages and pages[0]['table_count'] > 0:
            print(f"\n📊 Extracting tables from page 1...")
            tables = enhancer.extract_tables_advanced(1)
            for i, table in enumerate(tables):
                print(f"  Table {i+1}: {table['rows']} rows x {table['cols']} cols")

        # Extract images
        print(f"\n🖼️  Extracting images...")
        images = enhancer.extract_images()
        print(f"  Found {len(images)} images")

        if images:
            for i, img_info in enumerate(images[:3]):
                print(f"  Image {i+1}: {img_info['width']}x{img_info['height']} on page {img_info['page']}")

    print("\n✅ Analysis complete!")
