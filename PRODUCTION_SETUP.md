# Production Setup Guide - Citation System with API

## ✅ Prerequisites Completed

- ✅ Virtual environment with anthropic 0.72.0
- ✅ All backend agents with citation support
- ✅ Frontend with citation UI and panel
- ✅ API server with proper response format
- ✅ Start script created

## 🚀 Quick Start (3 Steps)

### Step 1: Set API Key
```bash
cd /Users/matheusrech/Downloads/SUB
export ANTHROPIC_API_KEY="your-key-here"
```

Or create a `.env` file:
```bash
echo 'ANTHROPIC_API_KEY=your-key-here' > .env
```

### Step 2: Start API Server
```bash
./start_server.sh
```

Or manually:
```bash
source venv/bin/activate
python3 api_server.py
```

You should see:
```
🧠 Cerebellar SDC Extraction API Server
============================================================
Starting server on http://localhost:5000

Endpoints:
  POST /api/upload - Upload PDF
  POST /api/extract/field - Extract single field
  POST /api/extract/all - Extract all fields
  POST /api/search - Search in PDF
  POST /api/export - Export data
============================================================
 * Running on http://127.0.0.1:5000
```

### Step 3: Enable API Mode in Frontend

Open `cerebellar_extraction_pro.html` and change line 1661:
```javascript
const USE_MOCK_DATA = false;  // Changed from true
```

Then open the HTML file in your browser:
```bash
open cerebellar_extraction_pro.html
```

## 📋 Testing the Complete System

### 1. Health Check
```bash
curl http://localhost:5000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "2.0.0-pro",
  "model": "claude-sonnet-4-20250514"
}
```

### 2. Upload PDF
```bash
curl -X POST http://localhost:5000/api/upload \
  -F "pdf=@Kim2016.pdf"
```

Expected response:
```json
{
  "success": true,
  "session_id": "abc123...",
  "filename": "Kim2016.pdf",
  "page_count": 10,
  "status": "ready"
}
```

Save the `session_id` for next step.

### 3. Extract Field with Citations
```bash
curl -X POST http://localhost:5000/api/extract/field \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "field_name": "title"
  }'
```

Expected response:
```json
{
  "success": true,
  "extraction": {
    "field": "title",
    "value": "Suboccipital Decompressive Craniectomy...",
    "confidence": 0.98,
    "page_number": 1,
    "timestamp": "2025-01-06T...",
    "agent": "Metadata Agent",
    "bounding_box": {...},
    "claude_citations": [
      {
        "type": "search_result_location",
        "cited_text": "...",
        "source": "...",
        ...
      }
    ],
    "cited_sections": ["Title", "Abstract"],
    "cited_text_snippets": ["..."],
    "citation_confidence": 0.98
  },
  "mode": "search_result"
}
```

### 4. Test in Browser

1. Open `cerebellar_extraction_pro.html` in Chrome/Edge
2. Upload `Kim2016.pdf` from `/Users/matheusrech/Documents/lector-review/public/`
3. You should see: "✅ PDF uploaded! Ready for extraction"
4. Click "AI Extract" on any field (e.g., "title")
5. Wait ~2-5 seconds
6. Field should populate with value
7. **Citation badge** should appear next to field label
8. **Hover badge** → See tooltip with preview
9. **Click badge** → Citation panel slides in from right
10. **Click citation card** → PDF jumps to location with highlight

## 🔧 API Server Configuration

### Port Configuration
Default: `http://localhost:5000`

To change port, edit `api_server.py` line ~last:
```python
app.run(debug=True, port=8080)  # Change to desired port
```

And update frontend `cerebellar_extraction_pro.html` line ~1662:
```javascript
const API_BASE_URL = 'http://localhost:8080';  // Match server port
```

### Debug Mode
For production, disable debug mode in `api_server.py`:
```python
app.run(debug=False, port=5000)
```

### CORS Configuration
Currently allows all origins. For production, restrict CORS in `api_server.py`:
```python
CORS(app, origins=['https://yourdomain.com'])
```

## 📊 API Endpoints Documentation

### GET /api/health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0-pro",
  "model": "claude-sonnet-4-20250514"
}
```

### POST /api/upload
Upload PDF and create extraction session.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `pdf` file field

**Response:**
```json
{
  "success": true,
  "session_id": "unique-session-id",
  "filename": "paper.pdf",
  "page_count": 10,
  "status": "ready"
}
```

### POST /api/extract/field
Extract single field with citations (default: search_result mode enabled).

**Request:**
```json
{
  "session_id": "session-id-from-upload",
  "field_name": "title",
  "use_search_results": true  // Optional, default true
}
```

**Response:**
```json
{
  "success": true,
  "extraction": {
    "field": "title",
    "value": "Paper Title",
    "confidence": 0.95,
    "page_number": 1,
    "timestamp": "2025-01-06T14:30:00",
    "agent": "Metadata Agent",
    "bounding_box": {
      "x0": 72, "y0": 150, "x1": 523, "y1": 180, "page": 1
    },
    "claude_citations": [...],
    "cited_sections": ["Title", "Abstract"],
    "cited_text_snippets": ["..."],
    "citation_confidence": 0.98
  },
  "mode": "search_result"
}
```

### POST /api/extract/all
Extract all fields with all agents.

**Request:**
```json
{
  "session_id": "session-id",
  "use_search_results": false  // Optional
}
```

**Response:**
```json
{
  "success": true,
  "extractions": [
    {
      "field": "title",
      "value": "...",
      "confidence": 0.95,
      ...
    },
    // ... more fields
  ],
  "metadata": {
    "total_fields": 19,
    "extraction_time": 36.5,
    "total_tokens": 42620
  }
}
```

## 🎯 Available Fields

### Metadata Agent
- `title` - Paper title
- `doi` - Digital Object Identifier
- `pmid` - PubMed ID
- `journal` - Journal name
- `publication_date` - Publication date
- `study_design` - Study type (RETROSPECTIVE_COHORT, etc.)

### Population Agent
- `total_sample_size` - Total patients
- `surgical_group_size` - Surgery group size
- `control_group_size` - Control group size
- `inclusion_criteria` - Patient inclusion criteria
- `exclusion_criteria` - Patient exclusion criteria

### Intervention Agent
- `surgical_type` - Type of surgery (SDC_ALONE, SDC_WITH_RESECTION, etc.)
- `timing_category` - Surgery timing category (<24h, 24-48h, >48h)
- `timing_hours` - Exact timing in hours
- `surgical_technique` - Technique details

### Outcomes Agent
- `mortality_30day_surgical` - 30-day mortality in surgery group (%)
- `mortality_30day_control` - 30-day mortality in control group (%)
- `mrs_favorable_surgical` - Favorable mRS in surgery group (%)
- `mrs_favorable_control` - Favorable mRS in control group (%)

## 🐛 Troubleshooting

### Server won't start
```bash
# Check if port 5000 is already in use
lsof -i :5000

# Kill existing process
kill -9 <PID>

# Or use different port (see Port Configuration above)
```

### API Key not recognized
```bash
# Verify key is set
echo $ANTHROPIC_API_KEY

# If empty, set it
export ANTHROPIC_API_KEY="your-key"

# Or load from .env
source venv/bin/activate
python3 -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('ANTHROPIC_API_KEY'))"
```

### Dependencies missing
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### CORS errors in browser
If you see CORS errors in browser console:
1. Verify API server is running
2. Check API_BASE_URL matches server address
3. Try Chrome/Edge (better CORS handling)
4. Check api_server.py has `CORS(app)` line

### Citations not showing
1. Check extraction response includes `claude_citations` array
2. Verify `use_search_results=true` (default)
3. Check browser console for JavaScript errors
4. Verify citation badge CSS is loaded (line 749-1113)

### Upload fails
1. Check file is actually a PDF
2. Verify file size < 10MB (increase in api_server.py if needed)
3. Check server logs for error messages
4. Verify temp directory has write permissions

## 📈 Performance Expectations

### Single Field Extraction
- **Time**: 2-5 seconds
- **Tokens**: ~2,000-3,000
- **Citations**: 1-3 per field

### Full Extraction (19 fields)
- **Time**: 30-40 seconds
- **Tokens**: 40,000-45,000
- **Citations**: 10-20 total
- **Success Rate**: 100%

### Memory Usage
- **Server**: ~500MB with one active session
- **Per Session**: ~50-100MB (PDF + extractors)
- **Recommended**: 2GB RAM minimum

## 🔒 Security Considerations

### For Production Deployment:

1. **API Key Management**
   - Never commit API key to git
   - Use environment variables
   - Rotate keys periodically

2. **CORS Restrictions**
   ```python
   CORS(app, origins=['https://yourdomain.com'])
   ```

3. **Rate Limiting**
   ```python
   from flask_limiter import Limiter
   limiter = Limiter(app, key_func=lambda: request.remote_addr)

   @limiter.limit("10 per minute")
   @app.route('/api/extract/field', methods=['POST'])
   def extract_field():
       ...
   ```

4. **File Size Limits**
   ```python
   app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
   ```

5. **Session Cleanup**
   ```python
   # Implement session expiration
   # Clean up temp files regularly
   # Monitor disk usage
   ```

6. **HTTPS**
   - Use reverse proxy (nginx/Apache)
   - SSL/TLS certificates
   - Secure headers

## 📝 Production Checklist

- [ ] Set ANTHROPIC_API_KEY
- [ ] Start API server
- [ ] Enable API mode in frontend (USE_MOCK_DATA=false)
- [ ] Test health endpoint
- [ ] Test upload endpoint
- [ ] Test extraction with citations
- [ ] Verify citation UI displays correctly
- [ ] Test citation panel navigation
- [ ] Test PDF highlighting
- [ ] Check browser console for errors
- [ ] Monitor server logs
- [ ] Set up error monitoring
- [ ] Configure backups
- [ ] Document deployment process

## 🎉 Success Metrics

When everything is working:
- ✅ Server runs on http://localhost:5000
- ✅ Health endpoint returns 200 OK
- ✅ PDF uploads successfully
- ✅ Fields extract with citations
- ✅ Citation badges appear
- ✅ Tooltips show on hover
- ✅ Panel opens on click
- ✅ PDF navigation works
- ✅ Highlights display correctly

## 📞 Support

For issues:
1. Check IMPLEMENTATION_STATUS.md
2. Review browser console (F12)
3. Check server logs
4. Verify all dependencies installed
5. Test with Kim2016.pdf (known working)

---

**Status**: Ready for Production Testing
**Last Updated**: 2025-01-06
**Next Step**: Start server and test end-to-end workflow
