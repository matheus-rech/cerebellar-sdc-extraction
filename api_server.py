#!/usr/bin/env python3
"""
Flask API Server for Cerebellar SDC Extraction
Provides REST API for real-time field extraction
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import json
import tempfile
from pathlib import Path
from cerebellar_extractor_pro import (
    CerebellarExtractionSystem,
    ProvenancePDFExtractor
)

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Global state
pdf_extractors = {}  # session_id -> PDF extractor
extraction_systems = {}  # session_id -> Extraction system

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "version": "2.0.0-pro",
        "model": "claude-sonnet-4-20250514"
    })

@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    """Upload and initialize PDF for extraction"""
    if 'pdf' not in request.files:
        return jsonify({"error": "No PDF file provided"}), 400
    
    file = request.files['pdf']
    if not file.filename.endswith('.pdf'):
        return jsonify({"error": "File must be a PDF"}), 400
    
    # Save temporarily
    session_id = os.urandom(16).hex()
    temp_dir = Path(tempfile.gettempdir()) / "cerebellar_extraction" / session_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_path = temp_dir / file.filename
    file.save(str(pdf_path))
    
    # Initialize extractor
    try:
        extractor = ProvenancePDFExtractor(str(pdf_path))
        system = CerebellarExtractionSystem()
        
        pdf_extractors[session_id] = extractor
        extraction_systems[session_id] = system

        # Get basic info (Marker-based)
        page_stats = extractor.get_page_stats()
        page_count = len(page_stats) if page_stats else 1
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "filename": file.filename,
            "page_count": page_count,
            "status": "ready"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/extract/field', methods=['POST'])
def extract_field():
    """Extract a single field with search_result mode (citations enabled by default)"""
    data = request.json
    session_id = data.get('session_id')
    field_name = data.get('field_name')
    use_search_results = data.get('use_search_results', True)  # DEFAULT: Citations enabled

    if not session_id or session_id not in pdf_extractors:
        return jsonify({"error": "Invalid session"}), 400

    if not field_name:
        return jsonify({"error": "Field name required"}), 400

    extractor = pdf_extractors[session_id]
    system = extraction_systems[session_id]

    try:
        # Get PDF text
        pdf_text = extractor.extract_all_text()

        # Determine which agent to use based on field
        agent_map = {
            'title': 'Metadata Agent',
            'doi': 'Metadata Agent',
            'pmid': 'Metadata Agent',
            'journal': 'Metadata Agent',
            'publication_date': 'Metadata Agent',
            'study_design': 'Metadata Agent',
            'total_sample_size': 'Population Agent',
            'surgical_group_size': 'Population Agent',
            'control_group_size': 'Population Agent',
            'inclusion_criteria': 'Population Agent',
            'exclusion_criteria': 'Population Agent',
            'surgical_type': 'Intervention Agent',
            'timing_category': 'Intervention Agent',
            'timing_hours': 'Intervention Agent',
            'surgical_technique': 'Intervention Agent',
            'mortality_30day_surgical': 'Outcomes Agent',
            'mortality_30day_control': 'Outcomes Agent',
            'mrs_favorable_surgical': 'Outcomes Agent',
            'mrs_favorable_control': 'Outcomes Agent',
        }

        agent_name = agent_map.get(field_name, 'Metadata Agent')
        agent = next((a for a in system.agents if a.name == agent_name), system.agents[0])

        # Run extraction - pass use_search_results if agent supports it
        if hasattr(agent.extract, '__code__') and 'use_search_results' in agent.extract.__code__.co_varnames:
            result = agent.extract(pdf_text, extractor, use_search_results=use_search_results)
        else:
            result = agent.extract(pdf_text, extractor)

        # Find the specific field
        field_result = next((e for e in result.fields_extracted if e.field == field_name), None)

        if field_result:
            # Build extraction object matching frontend expectations
            extraction = {
                "field": field_name,
                "value": field_result.value,
                "confidence": field_result.confidence,
                "page_number": field_result.page_number,
                "timestamp": field_result.timestamp,
                "source_text": field_result.source_text,
                "agent": agent_name,
                "bounding_box": field_result.bounding_box.__dict__ if field_result.bounding_box else None,
                # Citation data (always included, empty arrays if none)
                "claude_citations": field_result.claude_citations or [],
                "cited_sections": field_result.cited_sections or [],
                "cited_text_snippets": field_result.cited_text_snippets or [],
                "citation_confidence": field_result.citation_confidence if field_result.citation_confidence is not None else field_result.confidence
            }

            return jsonify({
                "success": True,
                "extraction": extraction,
                "mode": "search_result" if use_search_results else "legacy"
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Could not extract {field_name}"
            }), 404

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/extract/all', methods=['POST'])
def extract_all():
    """Extract all fields with optional search_result mode"""
    data = request.json
    session_id = data.get('session_id')
    use_search_results = data.get('use_search_results', False)  # NEW: Optional parameter

    if not session_id or session_id not in pdf_extractors:
        return jsonify({"error": "Invalid session"}), 400

    extractor = pdf_extractors[session_id]
    system = extraction_systems[session_id]

    try:
        # Get PDF text
        pdf_text = extractor.extract_all_text()

        # Run all agents
        all_results = []
        all_extractions = []

        for agent in system.agents:
            # Pass use_search_results if agent supports it
            if hasattr(agent.extract, '__code__') and 'use_search_results' in agent.extract.__code__.co_varnames:
                result = agent.extract(pdf_text, extractor, use_search_results=use_search_results)
            else:
                result = agent.extract(pdf_text, extractor)

            all_results.append(result)
            all_extractions.extend(result.fields_extracted)

        # Validate
        validation_result = system.validator.validate(all_extractions)
        validated = validation_result.fields_extracted

        # Format response with enhanced citation data
        extractions_data = []
        for e in validated:
            extraction_dict = {
                "field": e.field,
                "value": e.value,
                "confidence": e.confidence,
                "page": e.page_number,
                "source_text": e.source_text,
                "agent": e.agent,
                "validation_status": e.validation_status
            }

            # Include enhanced citation data if available
            if e.claude_citations:
                extraction_dict["claude_citations"] = e.claude_citations
            if e.cited_sections:
                extraction_dict["cited_sections"] = e.cited_sections
            if e.cited_text_snippets:
                extraction_dict["cited_text_snippets"] = e.cited_text_snippets
            if e.citation_confidence is not None:
                extraction_dict["citation_confidence"] = e.citation_confidence

            extractions_data.append(extraction_dict)

        # Format response
        return jsonify({
            "success": True,
            "mode": "search_result" if use_search_results else "legacy",
            "total_fields": len(validated),
            "extractions": extractions_data,
            "agents": [
                {
                    "name": r.agent_name,
                    "success": r.success,
                    "fields": len(r.fields_extracted),
                    "time": r.processing_time
                }
                for r in all_results
            ]
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/search', methods=['POST'])
def search_pdf():
    """Search text in PDF"""
    data = request.json
    session_id = data.get('session_id')
    query = data.get('query')
    
    if not session_id or session_id not in pdf_extractors:
        return jsonify({"error": "Invalid session"}), 400
    
    if not query:
        return jsonify({"error": "Query required"}), 400
    
    extractor = pdf_extractors[session_id]
    
    try:
        results = extractor.search_text(query)
        
        return jsonify({
            "success": True,
            "query": query,
            "total_results": len(results),
            "results": [
                {
                    "page": page_num,
                    "context": context,
                    "bbox": bbox.to_dict() if bbox else None
                }
                for page_num, context, bbox in results
            ]
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/export', methods=['POST'])
def export_data():
    """Export extracted data as JSON"""
    data = request.json
    session_id = data.get('session_id')
    extracted_data = data.get('data', {})
    
    if not session_id:
        return jsonify({"error": "Session ID required"}), 400
    
    # Create export object matching schema
    export_obj = {
        "ArticleMetadata": {
            "title": extracted_data.get('title', ''),
            "doi": extracted_data.get('doi', ''),
            "pmid": extracted_data.get('pmid', ''),
            "journal": extracted_data.get('journal', ''),
            "publicationDate": extracted_data.get('publication_date', ''),
            "studyDesign": extracted_data.get('study_design', '')
        },
        "StudyPopulation": {
            "totalSampleSize": extracted_data.get('total_sample_size', 0),
            "surgicalGroupSize": extracted_data.get('surgical_group_size', 0),
            "controlGroupSize": extracted_data.get('control_group_size', 0),
            "inclusionCriteria": extracted_data.get('inclusion_criteria', ''),
            "exclusionCriteria": extracted_data.get('exclusion_criteria', '')
        },
        "Interventions": {
            "surgicalType": extracted_data.get('surgical_type', ''),
            "timingCategory": extracted_data.get('timing_category', ''),
            "timingHours": extracted_data.get('timing_hours'),
            "surgicalTechnique": extracted_data.get('surgical_technique', '')
        },
        "Outcomes": {
            "mortality30daySurgical": extracted_data.get('mortality_30day_surgical'),
            "mortality30dayControl": extracted_data.get('mortality_30day_control'),
            "mrsFavorableSurgical": extracted_data.get('mrs_favorable_surgical'),
            "mrsFavorableControl": extracted_data.get('mrs_favorable_control')
        },
        "Metadata": {
            "exportDate": "2025-11-06T00:00:00Z",
            "extractorVersion": "2.0.0-pro",
            "model": "claude-sonnet-4-20250514"
        }
    }
    
    return jsonify(export_obj)

@app.route('/api/export/annotated-pdf', methods=['POST'])
def export_annotated_pdf():
    """Export PDF with citation highlights using PyMuPDF"""
    import fitz  # PyMuPDF

    data = request.json
    session_id = data.get('session_id')
    extractions = data.get('extractions', [])

    if not session_id or session_id not in pdf_extractors:
        return jsonify({"error": "Invalid session"}), 400

    extractor = pdf_extractors[session_id]

    try:
        # Get original PDF path
        pdf_path = extractor.pdf_path

        # Open PDF with PyMuPDF
        doc = fitz.open(pdf_path)

        # Track statistics
        highlights_added = 0

        # Add highlights for each extraction with bounding box
        for extraction in extractions:
            bbox_data = extraction.get('bounding_box')
            if not bbox_data:
                continue

            page_num = bbox_data.get('page', 1) - 1  # Convert to 0-indexed

            # Validate page number
            if page_num < 0 or page_num >= len(doc):
                continue

            page = doc[page_num]

            # Create fitz.Rect from bounding box coordinates
            # PDF coordinates: (x0, y0, x1, y1)
            rect = fitz.Rect(
                bbox_data['x0'],
                bbox_data['y0'],
                bbox_data['x1'],
                bbox_data['y1']
            )

            # Add yellow highlight annotation
            highlight = page.add_highlight_annot(rect)
            highlight.set_colors({"stroke": (1, 1, 0)})  # Yellow (RGB)
            highlight.update()

            highlights_added += 1

        # Save annotated PDF to temporary file
        temp_dir = Path(tempfile.gettempdir()) / "cerebellar_extraction" / session_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        output_filename = f"annotated_{Path(pdf_path).name}"
        output_path = temp_dir / output_filename

        doc.save(str(output_path))
        doc.close()

        # Return the annotated PDF file
        return send_file(
            str(output_path),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=output_filename
        )

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to create annotated PDF: {str(e)}"
        }), 500

@app.route('/api/cleanup', methods=['POST'])
def cleanup():
    """Clean up session resources"""
    data = request.json
    session_id = data.get('session_id')

    if session_id in pdf_extractors:
        pdf_extractors[session_id].close()
        del pdf_extractors[session_id]
        del extraction_systems[session_id]

    return jsonify({"success": True})

if __name__ == '__main__':
    print("🧠 Cerebellar SDC Extraction API Server")
    print("=" * 60)
    print("Starting server on http://localhost:5000")
    print("\nEndpoints:")
    print("  POST /api/upload - Upload PDF")
    print("  POST /api/extract/field - Extract single field")
    print("  POST /api/extract/all - Extract all fields")
    print("  POST /api/search - Search in PDF")
    print("  POST /api/export - Export data")
    print("  POST /api/export/annotated-pdf - Export PDF with highlights")
    print("=" * 60)

    app.run(debug=True, port=5000)
