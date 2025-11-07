# PDF Utilities

Command-line utilities for advanced PDF processing, following Anthropic's best practices.

## Available Tools

### 1. pdf_to_images.py - Convert PDFs to Images

Convert PDF pages to high-quality images for visual analysis with Claude.

**Usage:**
```bash
# Convert all pages at 200 DPI
python pdf_to_images.py input.pdf output_images/

# Convert specific pages at higher DPI
python pdf_to_images.py input.pdf output_images/ --pages 1,2,3 --dpi 300

# Limit image dimensions
python pdf_to_images.py input.pdf output_images/ --max-width 1920 --max-height 1080

# Save as JPEG instead of PNG
python pdf_to_images.py input.pdf output_images/ --format JPEG
```

**Options:**
- `--dpi`: Rendering DPI (default: 200)
- `--pages`: Comma-separated page numbers (e.g., 1,2,3)
- `--format`: Image format (PNG or JPEG)
- `--max-width`: Maximum image width
- `--max-height`: Maximum image height

### 2. extract_tables.py - Extract Tables from PDFs

Extract tables with advanced detection and debug visualizations.

**Usage:**
```bash
# Extract all tables from PDF
python extract_tables.py input.pdf

# Extract from specific page with debug images
python extract_tables.py input.pdf --page 1 --show-debug

# Save tables as JSON
python extract_tables.py input.pdf --json-output tables.json

# Custom output directory
python extract_tables.py input.pdf --output-dir my_tables/
```

**Options:**
- `--page`: Specific page number (if omitted, extracts from all pages)
- `--output-dir`: Output directory for CSV files and debug images
- `--show-debug`: Generate debug images showing table detection
- `--json-output`: Save all tables as JSON

**Output:**
- CSV files: `pageN_tableM.csv` - Table data
- Debug images: `pageN_tableM_debug.png` - Visual table structure
- JSON: All tables with metadata

### 3. pdf_info.py - PDF Analysis

Get comprehensive information about PDF structure and content.

**Usage:**
```bash
# Basic analysis
python pdf_info.py input.pdf

# Check if PDF is scanned (needs OCR)
python pdf_info.py input.pdf --check-scanned

# Save analysis as JSON
python pdf_info.py input.pdf --output info.json
```

**Options:**
- `--check-scanned`: Detect if PDF is scanned/image-based
- `--output`: Save analysis as JSON

**Output Information:**
- Total pages, characters, images, tables
- Per-page dimensions and content statistics
- Scanned PDF detection (when --check-scanned used)

## Installation

These utilities require the main project dependencies:

```bash
cd /Users/matheusrech/Downloads/SUB
pip install -r requirements.txt
```

## Integration with Main System

These utilities use the `PDFEnhancer` class from `pdf_enhancements.py`, which provides:

- **PDF Rendering**: Convert pages to images (pdf2image)
- **Table Extraction**: Advanced pdfplumber with custom settings
- **Image Extraction**: Extract embedded images
- **OCR Fallback**: Handle scanned PDFs with pytesseract
- **Character-Level Coords**: Precise text highlighting
- **Bounding Box Validation**: Quality checks and merging

## Examples

### Extract Tables for Medical Research Paper

```bash
# Extract outcome tables from Kim2016.pdf
python extract_tables.py ../Kim2016.pdf --page 5 --show-debug --output-dir kim_tables/

# Result: CSV files with mortality and mRS scores + debug images
```

### Prepare PDF Pages for Claude Analysis

```bash
# Convert first 3 pages to images for Claude
python pdf_to_images.py ../paper.pdf claude_images/ --pages 1,2,3 --dpi 150

# Claude can now analyze these images for figures, diagrams, etc.
```

### Check if PDF Needs OCR

```bash
# Detect scanned PDFs that need OCR processing
python pdf_info.py ../unknown.pdf --check-scanned

# If scanned: use pdf_enhancements.extract_text_with_ocr_fallback()
```

## Performance Tips

1. **DPI Selection**:
   - 150 DPI: Fast, good for text-heavy pages
   - 200 DPI: Balanced quality/performance (default)
   - 300 DPI: High quality for figures/diagrams
   - 600 DPI: Maximum quality, slow

2. **Table Extraction**:
   - Use `--show-debug` to verify detection quality
   - Adjust table settings in code if needed (see pdf_enhancements.py)
   - Complex tables may need custom settings

3. **Batch Processing**:
   - Process multiple PDFs with shell loops:
     ```bash
     for pdf in *.pdf; do
         python pdf_to_images.py "$pdf" "images/${pdf%.pdf}/"
     done
     ```

## Troubleshooting

**Import errors:**
```bash
# Make sure you're in the right directory
cd /Users/matheusrech/Downloads/SUB/pdf_utils
python pdf_info.py ../test.pdf
```

**Missing dependencies:**
```bash
# Install from parent directory
cd ..
pip install pdfplumber pdf2image pytesseract
```

**OCR not working:**
```bash
# Install tesseract system package
# macOS:
brew install tesseract

# Ubuntu/Debian:
sudo apt-get install tesseract-ocr
```

**pdf2image errors:**
```bash
# Install poppler system package
# macOS:
brew install poppler

# Ubuntu/Debian:
sudo apt-get install poppler-utils
```

## See Also

- `pdf_enhancements.py` - Main PDF enhancement module
- `marker_provenance_extractor.py` - Marker-based extraction
- `cerebellar_extractor_pro.py` - Multi-agent extraction system
