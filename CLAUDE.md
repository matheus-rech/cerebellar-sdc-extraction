# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Cerebellar SDC Extraction System v2.0.0 Pro** - A production-ready medical research data extraction system for cerebellar stroke papers using multi-agent AI with Claude Citations API. Extracts structured clinical data from PDF research papers using specialized AI agents with full provenance tracking and citation support.

**GitHub Repository**: https://github.com/matheus-rech/cerebellar-sdc-extraction

**Status**: ✅ Production Ready (2025-11-06)

## Key Features

### 🎯 Core Capabilities
- **Multi-Agent AI Extraction**: 4 specialized agents (Metadata, Population, Intervention, Outcomes) + Validator
- **Claude Citations API**: Native citation support with search_result mode
- **Citation Panel UI**: Slideable panel showing all citations with PDF navigation
- **Interactive PDF Viewer**: PDF.js with highlighting and jump-to-citation
- **Dual-Mode Operation**: Standalone demo (mock data) or full API integration
- **Provenance Tracking**: Every field includes bounding boxes, confidence scores, and source text

### 📚 Citation System Features
- **Citation Badges**: Color-coded by confidence (green ≥0.9, blue 0.7-0.9, yellow <0.7)
- **Citation Tooltips**: Hover to see citation preview with page and section
- **Citation Panel**: Right-side slideable panel with all citations for a field
- **PDF Navigation**: Click citation to jump to exact location in PDF
- **PDF Highlighting**: Animated blue highlights at citation locations
- **Citation Correlation**: Automatic matching of Claude citations to PDF coordinates

## Architecture

### Three-Tier System with Citations

```
Frontend (cerebellar_extraction_pro.html - 2,600+ lines)
├── PDF.js rendering engine with citation highlights
├── Citation panel with glassmorphic design
├── Citation badges, tooltips, and confidence bars
└── API client (configurable: mock or real)
    ↓
Backend (api_server.py)
├── Flask REST API with CORS
├── Session management for PDF uploads
├── Citation-enhanced response format
└── Routes extraction requests to agents
    ↓
Multi-Agent Engine (cerebellar_extractor_pro.py - 1,800+ lines)
├── ProvenancePDFExtractor (Marker-based PDF processing)
├── MetadataAgent (title, DOI, journal, study design) with citations
├── PopulationAgent (sample sizes, criteria) with citations
├── InterventionAgent (surgical procedures, timing) with citations
├── OutcomesAgent (mortality, mRS scores) with citations
└── ValidatorAgent (conflict resolution, consensus)
```

### Key Design Patterns

**Multi-Agent Consensus**: Each specialized agent extracts its domain fields independently. The ValidatorAgent consolidates results and resolves conflicts, providing final confidence scores.

**Claude Citations Integration**: All agents use search_result mode:
```python
{
    "type": "text",
    "text": pdf_text,
    "cache_control": {"type": "ephemeral"}
}
```
Citations are automatically extracted from Claude's response and correlated with PDF locations using Marker's search capabilities.

**Provenance Tracking with Citations**: Every extracted value includes:
- `value`: Extracted data
- `confidence`: 0-1 score from AI agent
- `page_number`: Source page reference
- `bounding_box`: Exact PDF coordinates (x0, y0, x1, y1, page)
- `source_text`: Surrounding context from PDF
- `claude_citations`: Array of citation objects from Claude API
- `cited_sections`: Section names where citations found
- `cited_text_snippets`: Text excerpts from citations
- `citation_confidence`: Overall citation quality score
- `timestamp`: Extraction time

**Dual-Mode Frontend**:
- Standalone mode (USE_MOCK_DATA=true): No backend required, demo with mock data
- API mode (USE_MOCK_DATA=false): Full AI extraction via Flask server with real citations

## Quick Start

### GitHub Clone & Setup
```bash
# Clone the repository
git clone https://github.com/matheus-rech/cerebellar-sdc-extraction.git
cd cerebellar-sdc-extraction

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY="your-key-here"
# Or create .env file
echo "ANTHROPIC_API_KEY=your-key-here" > .env
```

### Start System (Two Options)

**Option 1: Quick Start Script**
```bash
./start_server.sh
# Opens browser automatically when ready
```

**Option 2: Manual Start**
```bash
# Terminal 1: Start API server
source venv/bin/activate
python3 api_server.py
# Server runs on http://localhost:5000

# Terminal 2: Open UI
open cerebellar_extraction_pro.html  # macOS
xdg-open cerebellar_extraction_pro.html  # Linux
```

### Enable API Mode (for real citations)

Edit `cerebellar_extraction_pro.html` line 1661:
```javascript
const USE_MOCK_DATA = false;  // Change from true
```

Then reload the page in your browser.

## Using the Citation System

### Workflow
1. **Upload PDF**: Click "📂 Upload PDF" → Select research paper
2. **Extract Field**: Click "AI Extract" next to any field (e.g., "Title")
3. **View Citations**:
   - See badge appear: "📚 N citations"
   - Hover badge for tooltip preview
   - Click badge to open citation panel
4. **Navigate to Citations**: Click any citation card in panel
   - PDF jumps to exact location
   - Blue highlight appears at citation
   - Multiple citations show multiple highlights

### Test Papers
- `test_cerebellar_paper.pdf` - Included in repository
- `Kim2016.pdf` - Known working example (19 fields, 15 citations)

## API Endpoints

| Endpoint | Method | Purpose | Returns |
|----------|--------|---------|---------|
| `/api/health` | GET | Health check | `{status, version, model}` |
| `/api/upload` | POST | Upload PDF | `{success, session_id, filename, page_count}` |
| `/api/extract/field` | POST | Extract single field with citations | `{success, extraction{...}, mode}` |
| `/api/extract/all` | POST | Extract all fields | `{success, extractions[], agents[]}` |
| `/api/search` | POST | Search text in PDF | `{success, results[]}` |
| `/api/export` | POST | Export results | `{ArticleMetadata, StudyPopulation, ...}` |
| `/api/export/annotated-pdf` | POST | Export PDF with citation highlights | PDF file download |

### Citation-Enhanced Response Format

**POST `/api/extract/field`**
```json
{
  "session_id": "abc123...",
  "field_name": "title",
  "use_search_results": true  // Default: citations enabled
}
```

**Response**:
```json
{
  "success": true,
  "extraction": {
    "field": "title",
    "value": "Suboccipital Decompressive Craniectomy...",
    "confidence": 0.98,
    "page_number": 1,
    "timestamp": "2025-11-06T...",
    "agent": "Metadata Agent",
    "bounding_box": {
      "x0": 72, "y0": 150, "x1": 523, "y1": 180, "page": 1
    },
    "claude_citations": [
      {
        "type": "search_result_location",
        "cited_text": "Suboccipital Decompressive Craniectomy for Cerebellar Infarction...",
        "source": "document",
        "pdf_bounding_box": {
          "x0": 72, "y0": 150, "x1": 523, "y1": 180, "page": 1
        }
      }
    ],
    "cited_sections": ["Title", "Abstract"],
    "cited_text_snippets": ["Suboccipital Decompressive Craniectomy..."],
    "citation_confidence": 0.98
  },
  "mode": "search_result"
}
```

## PDF Enhancement Features (v2.0.1)

### Context Field Support

The extraction system now supports the `context` field as per Anthropic's official citation patterns. This allows you to provide metadata that helps Claude understand the research paper but won't be directly cited.

**Usage in marker_provenance_extractor.py**:
```python
extractor = MarkerProvenanceExtractor(pdf_path)

# Add context for paper quality metadata
context = "Publication: JAMA 2016. Study Type: Retrospective cohort. Sample: n=23. Quality: Newcastle-Ottawa Scale 7/9"

search_results = extractor.get_search_results(
    enable_citations=True,
    context=context  # Optional context field
)
```

**When to use context**:
- Publication venue and date (e.g., "JAMA 2016")
- Study type (e.g., "Randomized controlled trial")
- Quality assessment scores (e.g., "Newcastle-Ottawa Scale 8/9")
- Sample size warnings (e.g., "Small sample: n=15")
- Data completeness notes (e.g., "Missing outcomes for 3 patients")

The context field informs Claude's extraction but won't appear in citations, keeping citation text clean while improving extraction accuracy.

### Annotated PDF Export

Export PDFs with permanent yellow highlights at citation locations using PyMuPDF. This creates a downloadable PDF with visual markers showing exactly where each extracted field was found.

**API Endpoint**: `POST /api/export/annotated-pdf`

**Request**:
```json
{
  "session_id": "abc123...",
  "extractions": [
    {
      "field": "title",
      "value": "...",
      "bounding_box": {
        "x0": 72, "y0": 150, "x1": 523, "y1": 180, "page": 1
      }
    }
  ]
}
```

**Response**: PDF file download with yellow highlights

**Implementation** (api_server.py:335-411):
- Opens PDF with PyMuPDF (fitz)
- Iterates through extractions with bounding boxes
- Adds yellow highlight annotations at each location
- Saves and returns annotated PDF

**Use Cases**:
- Share extraction provenance with collaborators
- Verify extraction accuracy visually
- Create annotated datasets for training
- Documentation and audit trails

### Advanced PDF Processing

The system includes comprehensive PDF processing capabilities via `pdf_enhancements.py` (634 lines) following Anthropic's best practices.

#### PDFEnhancer Class

**PDF Rendering for Visual Analysis**:
```python
from pdf_enhancements import PDFEnhancer

with PDFEnhancer(pdf_path) as enhancer:
    # Render pages to images for Claude visual analysis
    images = enhancer.render_pages_to_images(
        pages=[1, 2, 3],  # Specific pages
        dpi=200,  # Quality (150-600)
        max_width=1920,   # Optional size limits
        max_height=1080
    )
    # Returns list of PIL Image objects
```

**Advanced Table Extraction**:
```python
# Extract tables with custom pdfplumber settings
tables = enhancer.extract_tables_advanced(
    page_num=5,
    table_settings={
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 3
    },
    return_debug_images=True  # Visual debugging
)
# Returns: (table_data, debug_images) if debug enabled
```

**Image Extraction**:
```python
# Extract embedded images from PDF
images = enhancer.extract_images(
    page_num=2,  # Specific page or None for all
    min_width=50,
    min_height=50
)
# Returns list of PIL Image objects
```

**OCR Fallback for Scanned PDFs**:
```python
# Detect if PDF is scanned
is_scanned = enhancer.is_scanned_pdf()

# Extract text with automatic OCR fallback
text = enhancer.extract_text_with_ocr_fallback(
    page_num=1,
    force_ocr=False  # Auto-detect if OCR needed
)
```

**Character-Level Coordinates**:
```python
# Get precise character-level coordinates
chars = enhancer.get_character_level_coords(
    page_num=1,
    search_text="mortality rate"  # Optional filter
)
# Returns list of dicts with 'char', 'x0', 'y0', 'x1', 'y1'
```

**Bounding Box Validation**:
```python
# Validate and merge bounding boxes
validated = PDFEnhancer.validate_bounding_boxes(
    boxes=[bbox1, bbox2, bbox3],
    page_width=612,
    page_height=792,
    allow_intersections=False,
    min_area=10.0
)
# Returns: (valid_boxes, invalid_boxes, warnings)
```

### Command-Line PDF Utilities

The `pdf_utils/` directory provides three command-line utilities:

#### 1. pdf_to_images.py - Convert PDFs to Images

```bash
# Convert all pages at 200 DPI
python pdf_utils/pdf_to_images.py input.pdf output_images/

# Convert specific pages at higher DPI
python pdf_utils/pdf_to_images.py input.pdf output_images/ --pages 1,2,3 --dpi 300

# Limit image dimensions
python pdf_utils/pdf_to_images.py input.pdf output_images/ --max-width 1920 --max-height 1080

# Save as JPEG instead of PNG
python pdf_utils/pdf_to_images.py input.pdf output_images/ --format JPEG
```

#### 2. extract_tables.py - Extract Tables from PDFs

```bash
# Extract all tables from PDF
python pdf_utils/extract_tables.py input.pdf

# Extract from specific page with debug images
python pdf_utils/extract_tables.py input.pdf --page 1 --show-debug

# Save tables as JSON
python pdf_utils/extract_tables.py input.pdf --json-output tables.json

# Custom output directory
python pdf_utils/extract_tables.py input.pdf --output-dir my_tables/
```

**Output**:
- CSV files: `pageN_tableM.csv` - Table data
- Debug images: `pageN_tableM_debug.png` - Visual table structure
- JSON: All tables with metadata

#### 3. pdf_info.py - PDF Analysis

```bash
# Basic analysis
python pdf_utils/pdf_info.py input.pdf

# Check if PDF is scanned (needs OCR)
python pdf_utils/pdf_info.py input.pdf --check-scanned

# Save analysis as JSON
python pdf_utils/pdf_info.py input.pdf --output info.json
```

**Output Information**:
- Total pages, characters, images, tables
- Per-page dimensions and content statistics
- Scanned PDF detection (when --check-scanned used)

### DPI Selection Guidelines

- **150 DPI**: Fast, good for text-heavy pages
- **200 DPI**: Balanced quality/performance (default)
- **300 DPI**: High quality for figures/diagrams
- **600 DPI**: Maximum quality, slow

### Integration Examples

**Extract and Render Tables**:
```bash
# Extract outcome tables from medical paper
python pdf_utils/extract_tables.py Kim2016.pdf --page 5 --show-debug --output-dir kim_tables/
# Result: CSV files with mortality and mRS scores + debug images
```

**Prepare Pages for Claude Visual Analysis**:
```bash
# Convert first 3 pages to images
python pdf_utils/pdf_to_images.py paper.pdf claude_images/ --pages 1,2,3 --dpi 150
# Claude can now analyze these images for figures, diagrams, etc.
```

**Check if PDF Needs OCR**:
```bash
# Detect scanned PDFs
python pdf_utils/pdf_info.py unknown.pdf --check-scanned
# If scanned: use enhancer.extract_text_with_ocr_fallback()
```

## Development Workflow

### Adding New Extraction Fields

1. **Update Agent Logic** (cerebellar_extractor_pro.py):
   - Extend existing agent's prompt to include new field
   - Or create new specialized agent class inheriting from `ExtractionAgent`
   - Ensure `_extract_with_search_results()` method is implemented

2. **Update HTML Form** (cerebellar_extraction_pro.html):
   ```html
   <div class="field-group">
     <label>New Field</label>
     <button onclick="extractField('new_field')">AI Extract</button>
     <input type="text" id="new_field">
   </div>
   ```

3. **Map to Agent** (api_server.py, line ~97):
   ```python
   agent_map = {
       'new_field': 'Appropriate Agent Name',
       # ...
   }
   ```

### Modifying Agent Behavior

Agents in `cerebellar_extractor_pro.py`:
- **MetadataAgent** (line ~197): Title, DOI, PMID, journal, publication date, study design
- **PopulationAgent** (line ~1079): Sample sizes, inclusion/exclusion criteria
- **InterventionAgent** (line ~1297): Surgical type, timing, technique details
- **OutcomesAgent** (line ~1512): Mortality rates, mRS scores, predictors
- **ValidatorAgent** (line ~1715): Consolidates and validates all agent results

Each agent has two extraction methods:
- `_extract_with_search_results()`: Current working method (search_result mode with citations)
- `_extract_with_files_api()`: Ready for when Files API is available in SDK

To modify: Edit the agent's `prompt` variable in its `_extract_with_search_results()` method.

### Frontend Configuration

**Toggle between mock and real API** (cerebellar_extraction_pro.html, line 1661):
```javascript
const USE_MOCK_DATA = false;  // false = API mode, true = standalone demo
const API_BASE_URL = 'http://localhost:5000';  // Change for different server
```

### Citation Panel Customization

**CSS Styling** (lines 1114-1310):
- Glassmorphic design with backdrop-filter
- Smooth animations (0.3s cubic-bezier)
- Responsive width (400px default)

**JavaScript Functions** (lines 1919-2011):
- `openCitationPanel(fieldName)` - Shows panel with all citations
- `closeCitationPanel()` - Hides panel and overlay
- `jumpToCitation(fieldName, citationIndex)` - Navigates to citation in PDF

## Key Classes & Methods

### ProvenancePDFExtractor (Marker-based)
```python
extractor = ProvenancePDFExtractor(pdf_path)
text = extractor.extract_all_text()  # Full PDF text with page markers
words = extractor.extract_text_with_coords(page_num)  # Word-level bounding boxes
bbox = extractor.find_text_location(search_text, page_num)  # Returns BoundingBox
results = extractor.search_text(query)  # Returns [(page, context, bbox), ...]
page_stats = extractor.get_page_stats()  # Get page count and statistics
extractor.close()  # Always close when done
```

### CerebellarExtractionSystem
```python
system = CerebellarExtractionSystem()
results = system.extract_from_pdf(pdf_path, use_search_results=True)
# Returns dict with: metadata, agent_results, extractions, data
# All extractions include claude_citations when use_search_results=True
```

### ExtractionResult (with Citations)
```python
@dataclass
class ExtractionResult:
    field: str
    value: Any
    confidence: float
    page_number: int
    bounding_box: Optional[BoundingBox]
    source_text: str
    citations: List[str]  # Legacy
    agent: str
    timestamp: str
    validation_status: str
    # Citation fields (new)
    claude_citations: List[Dict] = None
    cited_sections: List[str] = None
    cited_text_snippets: List[str] = None
    citation_confidence: float = None
```

## Configuration

### Environment Variables
- `ANTHROPIC_API_KEY`: Required for real AI extraction (can use .env file)

### Model Configuration
- Model: `claude-sonnet-4-20250514` (defined in cerebellar_extractor_pro.py line 25)
- Citations: Enabled by default with search_result mode
- Change by editing `MODEL` constant

### Dependencies
All defined in `requirements.txt`:
- **Flask 3.0.0** + flask-cors: Web server
- **anthropic 0.72.0**: Claude API client with citation support
- **marker-pdf 1.10.1**: Privacy-preserving PDF extraction with section detection
- **pypdfium2 4.30.0**: PDF rendering
- **PyPDF2 3.0.1**: PDF manipulation utilities
- **pdf2image 1.16.3**: PDF to image conversion
- **Pillow 10.2.0**: Image processing
- **pdfplumber 0.11.0**: Advanced table extraction and character-level coordinates
- **pytesseract 0.3.10**: OCR fallback for scanned PDFs
- **PyMuPDF 1.24.0**: Annotated PDF export with highlights
- **jsonschema 4.20.0**: Schema validation
- **python-dotenv 1.0.0**: Environment variable loading

## Performance Metrics

### Citation System Performance (Kim2016.pdf Test)
- **Extraction Time**: 36.72s for 19 fields
- **Token Usage**: 42,620 tokens
- **Citations Found**: 15 total across fields
  - Population: 3/5 fields (10 citations)
  - Intervention: 3/4 fields (5 citations)
- **Success Rate**: 100%
- **Confidence**: 0.85-1.0 range
- **Citation Accuracy**: High (verified against source PDF)

### Single Field Extraction
- **Time**: 2-5 seconds
- **Tokens**: 2,000-3,000
- **Citations**: 1-3 per field typically
- **Success Rate**: 100%

## Troubleshooting

### Citations Not Showing
1. Check `USE_MOCK_DATA = false` in HTML (line 1661)
2. Verify API server is running: `curl http://localhost:5000/api/health`
3. Check browser console (F12) for JavaScript errors
4. Verify extraction includes `claude_citations` array in response
5. Test with known working PDF (test_cerebellar_paper.pdf)

### Citation Panel Not Opening
1. Ensure extraction completed successfully
2. Check citation badge is visible
3. Verify `extractedData[fieldName]` has citations
4. Check browser console for errors

### PDF Highlights Not Appearing
1. Verify bounding_box coordinates are present
2. Check page number matches current PDF page
3. Try navigating to different page and back
4. Verify PDF.js canvas is rendered

### API Key Issues
```bash
# Check if set
echo $ANTHROPIC_API_KEY

# If empty, set it
export ANTHROPIC_API_KEY="your-key"

# Or use .env file (api_server.py loads automatically)
echo "ANTHROPIC_API_KEY=your-key" > .env
```

### Server Won't Start
```bash
# Check if port 5000 in use
lsof -i :5000
# Kill if needed: kill -9 <PID>

# Check dependencies installed
pip list | grep -E "(flask|anthropic|marker-pdf)"

# Reinstall if missing
pip install -r requirements.txt
```

### Extraction Returns Mock Data
- Check `USE_MOCK_DATA` flag in HTML file (should be `false`)
- Verify API server is running: `curl http://localhost:5000/api/health`
- Check browser console (F12) for API connection errors
- Verify `currentSessionId` is set after upload

### Low Confidence Scores
- Confidence < 0.8 often indicates ambiguous or missing data in PDF
- Review `source_text` in extraction results to see what Claude found
- Check `citation_confidence` vs field `confidence` for validation
- May need to adjust agent prompts to better guide extraction

## Documentation Files

### Quick Reference
- **QUICK_START.md** (2,512 bytes): 30-second setup guide with minimal commands
- **README.md**: Original project documentation

### Production Deployment
- **PRODUCTION_SETUP.md** (10,449 bytes): Complete deployment guide with:
  - API endpoints documentation
  - Security considerations
  - Testing procedures
  - Troubleshooting guide
  - Production checklist

### Technical Details
- **IMPLEMENTATION_STATUS.md** (11,144 bytes): System architecture and implementation details
- **IMPLEMENTATION_COMPLETE.md** (12,861 bytes): Original implementation guide
- **SEARCH_RESULT_MIGRATION.md** (16,906 bytes): Migration to search_result mode

### Testing & Validation
- **E2E_DEMO_SUMMARY.md**: End-to-end testing summary
- **HIGHLIGHT_FIX_SUMMARY.md**: PDF highlighting implementation
- **HARDCODED_VALUES_FIX.md**: Mock data cleanup

## Output Format (with Citations)

Extraction results are JSON with citation structure:
```json
{
  "metadata": {
    "pdf_path": "Kim2016.pdf",
    "extraction_date": "2025-11-06T...",
    "model": "claude-sonnet-4-20250514",
    "total_fields": 19,
    "total_tokens": 42620,
    "total_time": 36.72,
    "total_citations": 15
  },
  "agent_results": [
    {
      "agent": "Metadata Agent",
      "success": true,
      "fields": 6,
      "processing_time": 4.2,
      "tokens": 2340,
      "citations": 2
    }
  ],
  "extractions": [
    {
      "field": "title",
      "value": "Suboccipital decompressive craniectomy...",
      "confidence": 0.95,
      "page_number": 1,
      "bounding_box": {"x0": 72, "y0": 150, "x1": 523, "y1": 180, "page": 1},
      "source_text": "...surrounding context...",
      "agent": "Metadata Agent",
      "timestamp": "2025-11-06T...",
      "claude_citations": [
        {
          "type": "search_result_location",
          "cited_text": "Suboccipital Decompressive Craniectomy for Cerebellar Infarction",
          "source": "document",
          "pdf_bounding_box": {
            "x0": 72, "y0": 150, "x1": 523, "y1": 180, "page": 1
          }
        }
      ],
      "cited_sections": ["Title"],
      "cited_text_snippets": ["Suboccipital Decompressive Craniectomy for Cerebellar Infarction"],
      "citation_confidence": 0.98
    }
  ],
  "data": {
    "title": "Suboccipital decompressive craniectomy...",
    "doi": "10.xxxx/xxxxx"
  }
}
```

## Production Deployment

### Checklist
- [ ] Set `ANTHROPIC_API_KEY` environment variable
- [ ] Change `USE_MOCK_DATA = false` in HTML
- [ ] Configure CORS restrictions in `api_server.py`
- [ ] Set up HTTPS with reverse proxy (nginx/Apache)
- [ ] Enable rate limiting for API endpoints
- [ ] Configure session cleanup for temp files
- [ ] Set up error monitoring and logging
- [ ] Configure file size limits (default: 16MB max)
- [ ] Test with known working PDFs
- [ ] Verify citation system end-to-end
- [ ] Document API endpoints for users
- [ ] Set up backups for extraction results

### Security Considerations
1. **API Key**: Never commit to git, use environment variables
2. **CORS**: Restrict to specific domains in production
3. **Rate Limiting**: Implement to prevent abuse
4. **File Validation**: Verify PDF files before processing
5. **Session Management**: Auto-expire old sessions
6. **HTTPS**: Required for production deployment

## Related Systems

This system is related to the Medical Research Multi-Agent System in the global CLAUDE.md:
- Uses similar multi-agent pattern with specialized extractors
- Differs in focus: This is cerebellar-specific vs general medical extraction
- Can be integrated as a specialized module in broader medical extraction pipelines
- Demonstrates production-ready citation integration that can be adopted by other extraction systems

## Version History

- **v2.0.1** (2025-11-06): PDF Enhancement Update
  - Context field support for non-citable metadata (Anthropic official pattern)
  - PyMuPDF annotated PDF export with yellow highlights
  - Advanced PDF processing module (pdf_enhancements.py, 634 lines)
  - PDF to image conversion for visual analysis
  - Enhanced table extraction with pdfplumber
  - OCR fallback for scanned PDFs
  - Character-level coordinate precision
  - Bounding box validation utilities
  - Three command-line utilities (pdf_to_images, extract_tables, pdf_info)
  - Complete alignment with Anthropic PDF best practices

- **v2.0.0 Pro** (2025-11-06): Production-ready with full citation system
  - Claude Citations API integration
  - Citation panel with PDF navigation
  - Dual-mode operation (mock + API)
  - Complete documentation suite
  - GitHub repository published

## Support & Contributing

- **GitHub Issues**: https://github.com/matheus-rech/cerebellar-sdc-extraction/issues
- **Documentation**: See `/docs` directory or individual `.md` files
- **API Reference**: PRODUCTION_SETUP.md
- **Quick Start**: QUICK_START.md
- **Technical Details**: IMPLEMENTATION_STATUS.md

## License

See LICENSE file in repository.
