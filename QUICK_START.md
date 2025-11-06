# Quick Start Guide - Citation System

## 🚀 Start Server (30 seconds)

```bash
cd /Users/matheusrech/Downloads/SUB

# Method 1: Use start script
export ANTHROPIC_API_KEY="your-key"
./start_server.sh

# Method 2: Manual
source venv/bin/activate
export ANTHROPIC_API_KEY="your-key"
python3 api_server.py
```

## 🌐 Enable Frontend

Edit `cerebellar_extraction_pro.html` line 1661:
```javascript
const USE_MOCK_DATA = false;  // Change from true
```

Then open:
```bash
open cerebellar_extraction_pro.html
```

## ✅ Test Workflow (2 minutes)

1. **Upload PDF**: Click "📂 Upload PDF" → Select `Kim2016.pdf`
   - ✅ Should see: "PDF uploaded! Ready for extraction"

2. **Extract Field**: Click "AI Extract" next to "Title"
   - ✅ Field populates in ~3-5 seconds
   - ✅ Citation badge appears: "📚 N citations"

3. **View Citation**: Hover badge
   - ✅ Tooltip shows with preview

4. **Open Panel**: Click badge
   - ✅ Panel slides in from right
   - ✅ Shows all citations

5. **Navigate**: Click any citation card
   - ✅ PDF jumps to location
   - ✅ Blue highlight appears

## 🔍 Quick Debug

**Server not starting?**
```bash
lsof -i :5000  # Check if port in use
kill -9 <PID>  # Kill if needed
```

**API key not working?**
```bash
echo $ANTHROPIC_API_KEY  # Verify it's set
```

**Dependencies missing?**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**Citations not showing?**
- Check browser console (F12)
- Verify USE_MOCK_DATA=false
- Check server logs for errors

## 📚 Full Documentation

- **PRODUCTION_SETUP.md** - Complete setup guide
- **IMPLEMENTATION_STATUS.md** - Technical details
- **IMPLEMENTATION_COMPLETE.md** - Original specs

## 🎯 Key Endpoints

- `http://localhost:5000/api/health` - Health check
- `http://localhost:5000/api/upload` - Upload PDF
- `http://localhost:5000/api/extract/field` - Extract with citations

## 💡 Tips

- Use Kim2016.pdf for testing (in lector-review/public)
- Citations work best with "title", "mortality_30day_surgical", "surgical_type"
- Extraction takes 2-5 seconds per field
- Check server terminal for real-time logs
- Browser console shows API requests/responses

## 🎉 Success Indicators

- ✅ Server shows "Running on http://127.0.0.1:5000"
- ✅ Health endpoint returns 200 OK
- ✅ Upload shows success toast
- ✅ Extraction completes in 2-5s
- ✅ Citation badge appears
- ✅ Panel opens smoothly
- ✅ PDF navigation works

---

**Ready to go!** Start the server and open the HTML file.
