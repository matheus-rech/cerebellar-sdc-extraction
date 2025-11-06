# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Cerebellar SDC Extraction System v2.0.0 Pro** - A medical research data extraction system for cerebellar stroke papers using multi-agent AI with provenance tracking. Extracts structured clinical data from PDF research papers using specialized AI agents (Metadata, Population, Intervention, Outcomes, Validator).

## Architecture

### Three-Tier System

```
Frontend (cerebellar_extraction_pro.html)
├── PDF.js rendering engine
├── Interactive annotation layer
└── API client (configurable: mock or real)
    ↓
Backend (api_server.py)
├── Flask REST API with CORS
├── Session management
└── Routes extraction requests
    ↓
Multi-Agent Engine (cerebellar_extractor_pro.py)
├── ProvenancePDFExtractor (pdfplumber)
├── MetadataAgent (title, DOI, journal, study design)
├── PopulationAgent (sample sizes, criteria)
├── InterventionAgent (surgical procedures, timing)
├── OutcomesAgent (mortality, mRS scores)
└── ValidatorAgent (conflict resolution, consensus)
```

### Key Design Patterns

**Multi-Agent Consensus**: Each specialized agent extracts its domain fields independently. The ValidatorAgent consolidates results and resolves conflicts, providing final confidence scores.

**Provenance Tracking**: Every extracted value includes:
- `bounding_box`: Exact PDF coordinates (x0, y0, x1, y1, page)
- `source_text`: Surrounding context from PDF
- `confidence`: 0-1 score from AI agent
- `page_number`: Source page reference
- `timestamp`: Extraction time

**Dual-Mode Frontend**:
- Standalone mode (USE_MOCK_DATA=true): No backend required, demo with mock data
- API mode (USE_MOCK_DATA=false): Full AI extraction via Flask server

## Commands

### Quick Start (Recommended)

```bash
# Start complete system (API server + opens browser)
./start.sh
```

This checks Python, installs dependencies, validates API key, starts Flask server, and opens HTML interface.

### Manual Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY="your-key-here"
# Or create .env file
echo "ANTHROPIC_API_KEY=your-key-here" > .env

# Start API server only
python3 api_server.py
# Server runs on http://localhost:5000

# Open frontend in browser
open cerebellar_extraction_pro.html  # macOS
xdg-open cerebellar_extraction_pro.html  # Linux
```

### CLI Extraction (Python Direct)

```bash
# Extract from PDF directly (bypasses web UI)
python3 cerebellar_extractor_pro.py path/to/paper.pdf
# Outputs: paper_extraction.json
```

### Testing & Development

```bash
# Health check API
curl http://localhost:5000/api/health

# Test single field extraction
curl -X POST http://localhost:5000/api/extract/field \
  -H "Content-Type: application/json" \
  -d '{"session_id":"SESSION_ID","field_name":"title"}'

# Check Python environment
python3 -c "import flask, anthropic, pdfplumber; print('All imports OK')"

# Validate schema (if schema file exists)
python3 -c "import json; json.load(open('cerebellar_sdc_schema.json'))"
```

## Development Workflow

### Adding New Extraction Fields

1. **Update Schema** (if cerebellar_sdc_schema.json exists):
   ```json
   {
     "properties": {
       "new_field": {
         "type": "string",
         "description": "Field description"
       }
     }
   }
   ```

2. **Add Agent Logic** (cerebellar_extractor_pro.py):
   - Extend existing agent's prompt to include new field
   - Or create new specialized agent class inheriting from `ExtractionAgent`
   - Implement `extract()` method with Claude API call

3. **Update HTML Form** (cerebellar_extraction_pro.html):
   ```html
   <div class="field-group">
     <label>New Field</label>
     <button onclick="extractField('new_field')">AI Extract</button>
     <input type="text" id="new_field">
   </div>
   ```

4. **Map to Agent** (api_server.py, line ~94):
   ```python
   agent_map = {
       'new_field': 'Appropriate Agent Name',
       # ...
   }
   ```

### Modifying Agent Behavior

Agents are in `cerebellar_extractor_pro.py`:
- **MetadataAgent** (line ~197): Title, DOI, PMID, journal, publication date, study design
- **PopulationAgent** (line ~283): Sample sizes, inclusion/exclusion criteria
- **InterventionAgent** (line ~370): Surgical type, timing, technique details
- **OutcomesAgent** (line ~456): Mortality rates, mRS scores, predictors
- **ValidatorAgent** (line ~549): Consolidates and validates all agent results

To modify: Edit the agent's `prompt` variable in its `extract()` method. The prompt guides Claude's extraction behavior.

### Frontend Configuration

**Switch between mock and real API** (cerebellar_extraction_pro.html):
```javascript
// Near line 1050 (search for "USE_MOCK_DATA")
const USE_MOCK_DATA = false;  // Set to true for standalone demo
const API_BASE_URL = 'http://localhost:5000';  // Change for different server
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check, returns version/model info |
| `/api/upload` | POST | Upload PDF, returns session_id |
| `/api/extract/field` | POST | Extract single field (body: `{session_id, field_name}`) |
| `/api/extract/all` | POST | Extract all fields with all agents (body: `{session_id}`) |
| `/api/search` | POST | Search text in PDF (body: `{session_id, query}`) |
| `/api/export` | POST | Export extraction results (body: `{session_id}`) |

**Session Management**: Each uploaded PDF gets unique `session_id`. Store in global dicts:
- `pdf_extractors[session_id]` → ProvenancePDFExtractor instance
- `extraction_systems[session_id]` → CerebellarExtractionSystem instance

## Key Classes & Methods

### ProvenancePDFExtractor
```python
extractor = ProvenancePDFExtractor(pdf_path)
text = extractor.extract_all_text()  # Full PDF text with page markers
words = extractor.extract_text_with_coords(page_num)  # Word-level bounding boxes
bbox = extractor.find_text_location(search_text, page_num)  # Returns BoundingBox
results = extractor.search_text(query)  # Returns [(page, context, bbox), ...]
extractor.close()  # Always close when done
```

### CerebellarExtractionSystem
```python
system = CerebellarExtractionSystem()
results = system.extract_from_pdf(pdf_path)  # Full extraction with all agents
# Returns dict with: metadata, agent_results, extractions, data
```

### ExtractionResult
```python
@dataclass
class ExtractionResult:
    field: str
    value: Any
    confidence: float
    page_number: int
    bounding_box: Optional[BoundingBox]
    source_text: str
    citations: List[str]
    agent: str
    timestamp: str
    validation_status: str
```

## Configuration

### Environment Variables
- `ANTHROPIC_API_KEY`: Required for real AI extraction (can use .env file)

### Model Configuration
- Model: `claude-sonnet-4-20250514` (defined in cerebellar_extractor_pro.py line 25)
- Change by editing `MODEL` constant

### Dependencies
All defined in `requirements.txt`:
- **Flask 3.0.0** + flask-cors: Web server
- **anthropic 0.25.0**: Claude API client
- **pdfplumber 0.11.0**: PDF text extraction with coordinates
- **PyPDF2, pdf2image, Pillow**: PDF processing utilities
- **jsonschema**: Schema validation (if schema file exists)
- **python-dotenv**: Environment variable loading

## Troubleshooting

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
pip list | grep -E "(flask|anthropic|pdfplumber)"

# Reinstall if missing
pip install -r requirements.txt
```

### Extraction Returns Mock Data
- Check `USE_MOCK_DATA` flag in HTML file (should be `false`)
- Verify API server is running: `curl http://localhost:5000/api/health`
- Check browser console (F12) for API connection errors

### Low Confidence Scores
- Confidence < 0.8 often indicates ambiguous or missing data in PDF
- Review `source_text` in extraction results to see what Claude found
- May need to adjust agent prompts to better guide extraction

### PDF Not Loading in Browser
- Check file size (very large PDFs >50MB may timeout)
- Verify PDF is not corrupted: `pdfinfo <file.pdf>`
- Try different browser (Chrome/Edge recommended for PDF.js)

## Output Format

Extraction results are JSON with structure:
```json
{
  "metadata": {
    "pdf_path": "...",
    "extraction_date": "2025-11-06T...",
    "model": "claude-sonnet-4-20250514",
    "total_fields": 15,
    "total_tokens": 12450,
    "total_time": 23.5
  },
  "agent_results": [
    {
      "agent": "Metadata Agent",
      "success": true,
      "fields": 6,
      "processing_time": 4.2,
      "tokens": 2340
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
      "timestamp": "2025-11-06T..."
    }
  ],
  "data": {
    "title": "...",
    "doi": "10.xxxx/xxxxx"
  }
}
```

## Related Systems

This system is related to the Medical Research Multi-Agent System in the global CLAUDE.md:
- Uses similar multi-agent pattern with specialized extractors
- Differs in focus: This is cerebellar-specific vs general medical extraction
- Can be integrated as a specialized module in broader medical extraction pipelines
