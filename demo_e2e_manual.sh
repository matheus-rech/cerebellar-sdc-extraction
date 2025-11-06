#!/bin/bash
##############################################################################
# Manual E2E Demo Script
# This script opens the UI in your browser so you can interact with it manually
##############################################################################

echo "========================================================================"
echo "🎬 CEREBELLAR EXTRACTION E2E DEMO"
echo "========================================================================"
echo ""

# Check if server is running
echo "🔍 Checking if API server is running..."
if nc -z localhost 5000 2>/dev/null; then
    echo "✅ Server is already running on port 5000"
else
    echo "❌ Server is not running"
    echo ""
    echo "Starting server..."
    echo "Note: Server logs will be in server.log"

    # Start server in background
    source venv/bin/activate
    python3 api_server.py > server.log 2>&1 &
    SERVER_PID=$!
    echo "Server PID: $SERVER_PID"

    # Wait for server to start
    echo "⏳ Waiting for server to initialize..."
    sleep 5

    if nc -z localhost 5000 2>/dev/null; then
        echo "✅ Server started successfully!"
    else
        echo "❌ Server failed to start. Check server.log for details"
        exit 1
    fi
fi

echo ""
echo "========================================================================"
echo "📄 Opening Frontend in Browser"
echo "========================================================================"
echo ""

# Get absolute path to HTML file
HTML_PATH="$(pwd)/cerebellar_extraction_pro.html"

echo "Frontend: file://$HTML_PATH"
echo ""
echo "========================================================================"
echo "🎯 DEMO INSTRUCTIONS"
echo "========================================================================"
echo ""
echo "The browser will open with the Cerebellar Extraction Interface."
echo ""
echo "To see the E2E workflow:"
echo ""
echo "1️⃣  UPLOAD PDF"
echo "   - Click 'Choose File' button"
echo "   - Select 'test_cerebellar_paper.pdf'"
echo "   - PDF will render in the viewer"
echo ""
echo "2️⃣  EXTRACT SINGLE FIELD (Quick Test)"
echo "   - Find the 'Title' field"
echo "   - Click 'AI Extract' button next to it"
echo "   - Watch as Marker extracts text and AI fills the field"
echo "   - You'll see: 'Suboccipital Decompressive Craniectomy for Cerebellar Infarction'"
echo ""
echo "3️⃣  EXTRACT ALL FIELDS (Full Multi-Agent System)"
echo "   - Scroll down and click 'Extract All Fields' button"
echo "   - This triggers the complete multi-agent workflow:"
echo "     • Metadata Agent → title, DOI, journal, study design"
echo "     • Population Agent → sample sizes, criteria"
echo "     • Intervention Agent → surgical procedures"
echo "     • Outcomes Agent → mortality, mRS scores"
echo "     • Validator Agent → consolidation and validation"
echo "   - All fields will be automatically populated"
echo ""
echo "4️⃣  VIEW PROVENANCE"
echo "   - Each extracted value has bounding box coordinates"
echo "   - These link back to specific PDF locations"
echo "   - Marker provides section-level polygon coordinates"
echo ""
echo "5️⃣  EXPORT RESULTS"
echo "   - Click 'Export JSON' to download the complete extraction"
echo "   - Includes all values, confidence scores, and provenance data"
echo ""
echo "========================================================================"
echo "🔬 WHAT YOU'RE SEEING"
echo "========================================================================"
echo ""
echo "✨ Marker-PDF Integration:"
echo "   - PDF → Markdown with structure preservation"
echo "   - Automatic section detection with bounding boxes"
echo "   - Superior to old pdfplumber approach"
echo ""
echo "🤖 Multi-Agent AI System:"
echo "   - 5 specialized Claude agents working together"
echo "   - Each agent extracts its domain fields"
echo "   - Validator agent consolidates and resolves conflicts"
echo ""
echo "📍 Full Provenance Tracking:"
echo "   - Every value has source text and coordinates"
echo "   - Can trace back to exact PDF location"
echo "   - Enables 'Show in PDF' functionality"
echo ""
echo "========================================================================"
echo ""

# Open in default browser
echo "Opening browser..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open "$HTML_PATH"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    xdg-open "$HTML_PATH"
else
    echo "Please open this URL manually: file://$HTML_PATH"
fi

echo ""
echo "✅ Demo ready! Follow the instructions above to test the system."
echo ""
echo "Press Ctrl+C to stop the server when done."
echo ""

# Keep script running to maintain server
if [ ! -z "$SERVER_PID" ]; then
    wait $SERVER_PID
fi
