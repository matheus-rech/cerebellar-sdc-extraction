#!/usr/bin/env python3
"""
Cerebellar SDC Extraction System - Professional Edition
Enhanced multi-agent extraction with full provenance tracking
Author: Dr. Matheus Rech
Date: November 6, 2025
"""

import os
import json
from anthropic import Anthropic
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
import re
from pathlib import Path
import hashlib

# Import Marker-based extractor (replaces pdfplumber)
from marker_provenance_extractor import MarkerProvenanceExtractor, BoundingBox as MarkerBoundingBox

# ============================================================================
# Configuration
# ============================================================================

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"

# Load schema
SCHEMA_PATH = Path(__file__).parent / "cerebellar_sdc_schema.json"
with open(SCHEMA_PATH) as f:
    SCHEMA = json.load(f)

# ============================================================================
# Data Structures
# ============================================================================

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

@dataclass
class ExtractionResult:
    """Single field extraction with full provenance"""
    field: str
    value: Any
    confidence: float
    page_number: int
    bounding_box: Optional[BoundingBox]
    source_text: str
    citations: List[str]
    agent: str
    timestamp: str
    validation_status: str = "PENDING"

    # Enhanced citation data from search_result blocks (Claude's built-in citation system)
    claude_citations: Optional[List[Dict]] = None  # Raw citation objects from Claude response
    cited_sections: Optional[List[str]] = None  # Section titles that were cited
    cited_text_snippets: Optional[List[str]] = None  # Exact quoted text from citations
    citation_confidence: Optional[float] = None  # Quality metric derived from citation data

    def to_dict(self) -> Dict:
        result = {
            "field": self.field,
            "value": self.value,
            "confidence": self.confidence,
            "page_number": self.page_number,
            "bounding_box": self.bounding_box.to_dict() if self.bounding_box else None,
            "source_text": self.source_text,
            "citations": self.citations,
            "agent": self.agent,
            "timestamp": self.timestamp,
            "validation_status": self.validation_status
        }

        # Include enhanced citation data if available
        if self.claude_citations:
            result["claude_citations"] = self.claude_citations
        if self.cited_sections:
            result["cited_sections"] = self.cited_sections
        if self.cited_text_snippets:
            result["cited_text_snippets"] = self.cited_text_snippets
        if self.citation_confidence is not None:
            result["citation_confidence"] = self.citation_confidence

        return result

@dataclass
class AgentResult:
    """Result from a single extraction agent"""
    agent_name: str
    fields_extracted: List[ExtractionResult]
    processing_time: float
    tokens_used: int
    success: bool
    error: Optional[str] = None

# ============================================================================
# PDF Text Extraction with Provenance
# ============================================================================

# Use Marker-based extractor (superior to pdfplumber)
# Provides automatic section detection and section-level bounding boxes
ProvenancePDFExtractor = MarkerProvenanceExtractor

# ============================================================================
# Multi-Agent Extraction System
# ============================================================================

class ExtractionAgent:
    """Base class for specialized extraction agents"""

    def __init__(self, name: str, client: Anthropic):
        self.name = name
        self.client = client

    def extract(self, pdf_text: str, pdf_extractor: ProvenancePDFExtractor) -> AgentResult:
        """Override this method in subclasses"""
        raise NotImplementedError

    # ========================================================================
    # JSON Extraction Helper (shared by all agents)
    # ========================================================================

    def _extract_json_from_response(self, response_text: str) -> Dict:
        """
        Robustly extract JSON from Claude's response.

        Handles:
        - Plain JSON
        - JSON wrapped in markdown code blocks
        - JSON with explanatory text before/after
        - Empty responses
        - Multiple paragraphs with JSON embedded
        """
        if not response_text or not response_text.strip():
            raise ValueError("Empty response from Claude - check if prompt is too complex or PDF too large")

        original_text = response_text
        text = response_text.strip()

        # Strategy 1: Look for JSON: label (common in structured responses)
        json_label_match = re.search(r'JSON:\s*\n(.+)', text, re.DOTALL | re.IGNORECASE)
        if json_label_match:
            text = json_label_match.group(1).strip()

        # Strategy 2: Remove markdown code blocks (```json ... ```)
        code_block_match = re.search(r'```json\s*\n(.+?)\n```', text, re.DOTALL)
        if code_block_match:
            text = code_block_match.group(1).strip()
        else:
            # Remove any ``` markers without json label
            text = re.sub(r'```\s*|\s*```', '', text).strip()

        # Strategy 3: Find the largest {...} block (most likely the JSON)
        # This handles cases where there's explanatory text before or after
        json_objects = []
        for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL):
            try:
                obj = json.loads(match.group(0))
                json_objects.append((len(match.group(0)), obj))
            except json.JSONDecodeError:
                continue

        # Return the largest valid JSON object found
        if json_objects:
            json_objects.sort(key=lambda x: x[0], reverse=True)
            return json_objects[0][1]

        # Strategy 4: Try to parse the entire cleaned text as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 5: Look for JSON arrays [...]
        array_match = re.search(r'(\[.*\])', text, re.DOTALL)
        if array_match:
            try:
                return json.loads(array_match.group(1))
            except json.JSONDecodeError:
                pass

        # If all strategies fail, provide detailed error
        preview = original_text[:500] if len(original_text) > 500 else original_text
        raise ValueError(
            f"Could not extract valid JSON from response.\n"
            f"Response preview (first 500 chars):\n{preview}\n"
            f"Response length: {len(original_text)} chars"
        )

    # ========================================================================
    # Citation Helper Methods (shared by all agents)
    # ========================================================================

    def _parse_citations(self, response) -> Dict:
        """
        Parse citation data from Claude's response.

        Returns dict mapping field names to citation info:
        {
            "field_name": {
                "raw_citations": [...],
                "sections": [...],
                "snippets": [...],
                "confidence": 0.0-1.0
            }
        }
        """
        citations_by_text = {}

        # Extract all text blocks with citations from response
        for content_block in response.content:
            if content_block.type == "text":
                text = content_block.text

                # Check if block has citations
                if hasattr(content_block, 'citations') and content_block.citations:
                    citations = content_block.citations
                    citations_by_text[text] = citations

        # If no citations found, return empty dict
        if not citations_by_text:
            return {}

        # Parse citations and extract metadata
        parsed_citations = {}

        for text, citations in citations_by_text.items():
            raw_citations = []
            sections = set()
            snippets = []

            for citation in citations:
                # Extract citation metadata
                citation_dict = {
                    "type": citation.type if hasattr(citation, 'type') else "unknown",
                    "cited_text": citation.cited_text if hasattr(citation, 'cited_text') else text,
                    "document_index": getattr(citation, 'document_index', None),
                    "document_title": getattr(citation, 'document_title', None) or getattr(citation, 'title', None),
                    "source": getattr(citation, 'source', None),
                }

                # Add type-specific location fields
                citation_dict.update(self._get_location_fields(citation))

                raw_citations.append(citation_dict)

                # Extract section titles
                if citation_dict['document_title']:
                    sections.add(citation_dict['document_title'])

                # Extract cited text snippets
                if citation_dict['cited_text']:
                    snippets.append(citation_dict['cited_text'])

            # Calculate citation confidence score
            confidence = self._calculate_citation_confidence(raw_citations)

            parsed_citations[text] = {
                "raw_citations": raw_citations,
                "sections": list(sections),
                "snippets": snippets,
                "confidence": confidence
            }

        return parsed_citations

    def _get_location_fields(self, citation) -> Dict:
        """Extract location fields based on citation type."""
        location_fields = {}

        # Page location (for PDFs)
        if hasattr(citation, 'start_page_number'):
            location_fields['start_page_number'] = citation.start_page_number
        if hasattr(citation, 'end_page_number'):
            location_fields['end_page_number'] = citation.end_page_number

        # Character location (for plain text)
        if hasattr(citation, 'start_char_index'):
            location_fields['start_char_index'] = citation.start_char_index
        if hasattr(citation, 'end_char_index'):
            location_fields['end_char_index'] = citation.end_char_index

        # Content block location (for custom content)
        if hasattr(citation, 'start_block_index'):
            location_fields['start_block_index'] = citation.start_block_index
        if hasattr(citation, 'end_block_index'):
            location_fields['end_block_index'] = citation.end_block_index

        # Search result location (for RAG)
        if hasattr(citation, 'search_result_index'):
            location_fields['search_result_index'] = citation.search_result_index

        return location_fields

    def _calculate_citation_confidence(self, raw_citations: List[Dict]) -> float:
        """
        Calculate confidence score for citations.

        Factors:
        - Number of citations (more = higher confidence)
        - Citation specificity (page/char locations = higher)
        - Cited text length (longer = more context)
        """
        if not raw_citations:
            return 0.0

        # Base score from number of citations
        num_citations = len(raw_citations)
        base_score = min(0.5 + (num_citations * 0.1), 0.9)

        # Bonus for location specificity
        specificity_bonus = 0.0
        for cit in raw_citations:
            if cit['type'] == 'page_location':
                specificity_bonus += 0.05
            elif cit['type'] in ['char_location', 'search_result_location']:
                specificity_bonus += 0.10

        # Bonus for longer cited text (more context)
        text_length_bonus = 0.0
        for cit in raw_citations:
            cited_text = cit.get('cited_text', '')
            if len(cited_text) > 50:
                text_length_bonus += 0.05
            if len(cited_text) > 100:
                text_length_bonus += 0.05

        final_score = min(1.0, base_score + specificity_bonus + text_length_bonus)
        return round(final_score, 2)

    def _correlate_citations_to_fields(self, result_data: Dict, citations_data: Dict) -> Dict:
        """
        Map citations to specific fields based on text content matching.

        Strategy: Match field values to citation text to determine which
        citations support which extracted fields.
        """
        field_citation_map = {}

        for field, data in result_data.items():
            value = str(data.get('value', ''))

            if not value or value == 'None':
                continue

            # Find citations containing this value
            matching_citations = []
            for text, cit_info in citations_data.items():
                # Check if the value appears in the cited text or snippets
                if value in text or any(value in snippet for snippet in cit_info.get('snippets', [])):
                    matching_citations.append(cit_info)

            if matching_citations:
                # Merge all matching citations (keep all per user preference)
                all_raw_citations = []
                all_sections = set()
                all_snippets = []
                max_confidence = 0.0

                for cit_info in matching_citations:
                    all_raw_citations.extend(cit_info['raw_citations'])
                    all_sections.update(cit_info['sections'])
                    all_snippets.extend(cit_info['snippets'])
                    max_confidence = max(max_confidence, cit_info['confidence'])

                field_citation_map[field] = {
                    "raw_citations": all_raw_citations,
                    "sections": list(all_sections),
                    "snippets": all_snippets,
                    "confidence": max_confidence
                }

        return field_citation_map

    def _locate_citations_in_pdf(self, field_citations_map: Dict, pdf_extractor) -> None:
        """
        Locate cited text in the PDF to get exact bounding boxes for highlighting.

        Uses pdf_extractor.search_text() to find the exact location of each
        cited text snippet. Modifies field_citations_map in place to add
        bounding box information.

        Args:
            field_citations_map: Dict mapping fields to their citation data
            pdf_extractor: PDF extractor instance with search_text() method
        """
        for field, citation_data in field_citations_map.items():
            raw_citations = citation_data.get('raw_citations', [])

            # Add bounding boxes to each raw citation
            for citation in raw_citations:
                cited_text = citation.get('cited_text', '')

                # Skip if no cited text or too long to search efficiently
                if not cited_text or len(cited_text) > 500:
                    continue

                try:
                    # Search for the cited text in the PDF
                    # Take first 100 chars for more reliable matching
                    search_query = cited_text[:100].strip()

                    if len(search_query) < 10:
                        # Too short to search reliably
                        continue

                    # Search in PDF
                    search_results = pdf_extractor.search_text(search_query)

                    if search_results:
                        # Take the first match
                        page_num, context, bbox = search_results[0]

                        # Add bounding box to citation
                        citation['pdf_bounding_box'] = bbox.to_dict() if bbox else None
                        citation['pdf_page'] = page_num
                        citation['pdf_context'] = context

                except Exception as e:
                    # Silently continue if search fails
                    continue

class MetadataAgent(ExtractionAgent):
    """Extract article metadata"""

    def extract(self, pdf_text: str, pdf_extractor: ProvenancePDFExtractor, use_search_results: bool = True, file_id: str = None) -> AgentResult:
        """
        Extract metadata with optional citation support.

        Args:
            pdf_text: Full PDF text (used in legacy mode)
            pdf_extractor: PDF extractor for search_result blocks and location finding
            use_search_results: If True, use search_result blocks with citations (default)
                               If False, use legacy plain text mode
            file_id: If provided, use Files API hybrid mode (fastest)
        """
        if file_id:
            return self._extract_with_files_api(file_id, pdf_extractor)
        elif use_search_results:
            return self._extract_with_search_results(pdf_extractor)
        else:
            return self._extract_legacy(pdf_text, pdf_extractor)

    def _extract_with_search_results(self, pdf_extractor: ProvenancePDFExtractor) -> AgentResult:
        """Extract metadata using search_result blocks with citation support."""
        start_time = datetime.now()

        # Get search_result blocks from PDF
        search_results = pdf_extractor.get_search_results(enable_citations=True)

        prompt = f"""Extract the following metadata from this medical research paper.

REQUIRED FIELDS:
- title: Full article title
- doi: Digital Object Identifier (format: 10.xxxx/xxxxx)
- pmid: PubMed ID if available
- journal: Journal name
- publication_date: Publication date (YYYY-MM-DD format)
- study_design: One of: RCT, PROSPECTIVE_COHORT, RETROSPECTIVE_COHORT, CASE_CONTROL, CASE_SERIES

CRITICAL INSTRUCTIONS:
1. Quote the EXACT text from the PDF for each value
2. Do NOT paraphrase or summarize
3. Extract ONLY what is present in the document
4. If a field is not found, set value to null

Return ONLY a valid JSON object with these fields. For each field, include your confidence (0-1).

Format:
{{
  "title": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "doi": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "pmid": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "journal": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "publication_date": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "study_design": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}}
}}

IMPORTANT: Quote exact text from the PDF. This enables citation tracking."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": [*search_results, {"type": "text", "text": prompt}]
                    }
                ]
            )

            # Parse JSON response using robust extraction
            result_text = response.content[0].text
            result_data = self._extract_json_from_response(result_text)

            # Extract citations from response metadata
            citations_by_text = self._parse_citations(response)

            # Correlate citations to specific fields
            field_citations_map = self._correlate_citations_to_fields(result_data, citations_by_text)

            # Locate cited text in PDF to get bounding boxes
            self._locate_citations_in_pdf(field_citations_map, pdf_extractor)

            # Create extraction results with citation data
            extractions = []
            for field, data in result_data.items():
                value = data.get('value')
                confidence = data.get('confidence', 0.8)

                # Get citation data for this field
                citation_info = field_citations_map.get(field, {})
                claude_citations = citation_info.get('raw_citations', [])
                cited_sections = citation_info.get('sections', [])
                cited_snippets = citation_info.get('snippets', [])
                citation_confidence = citation_info.get('confidence')

                # Try to find text location (fallback if citations don't have bounding boxes)
                search_results_fallback = pdf_extractor.search_text(str(value)[:50])
                page_num = search_results_fallback[0][0] if search_results_fallback else 1
                bbox = search_results_fallback[0][2] if search_results_fallback else None
                source_text = search_results_fallback[0][1] if search_results_fallback else str(value)

                extractions.append(ExtractionResult(
                    field=field,
                    value=value,
                    confidence=confidence,
                    page_number=page_num,
                    bounding_box=bbox,
                    source_text=source_text,
                    citations=[],
                    agent=self.name,
                    timestamp=datetime.now().isoformat(),
                    claude_citations=claude_citations,
                    cited_sections=cited_sections,
                    cited_text_snippets=cited_snippets,
                    citation_confidence=citation_confidence
                ))

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                fields_extracted=extractions,
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                fields_extracted=[],
                processing_time=processing_time,
                tokens_used=0,
                success=False,
                error=str(e)
            )

    def _extract_with_files_api(self, file_id: str, pdf_extractor: ProvenancePDFExtractor) -> AgentResult:
        """Extract metadata using Files API with hybrid bounding box lookup."""
        start_time = datetime.now()

        prompt = f"""Extract the following metadata from this medical research paper.

REQUIRED FIELDS:
- title: Full article title
- doi: Digital Object Identifier (format: 10.xxxx/xxxxx)
- pmid: PubMed ID if available
- journal: Journal name
- publication_date: Publication date (YYYY-MM-DD format)
- study_design: One of: RCT, PROSPECTIVE_COHORT, RETROSPECTIVE_COHORT, CASE_CONTROL, CASE_SERIES

CRITICAL INSTRUCTIONS:
1. Quote the EXACT text from the PDF for each value
2. Do NOT paraphrase or summarize
3. Extract ONLY what is present in the document
4. If a field is not found, set value to null

Return ONLY a valid JSON object with these fields. For each field, include your confidence (0-1).

Format:
{{
  "title": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "doi": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "pmid": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "journal": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "publication_date": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "study_design": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}}
}}

IMPORTANT: Quote exact text from the PDF. This enables citation tracking."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "file",
                                    "file_id": file_id
                                },
                                "citations": {"enabled": True}
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            # Parse JSON response using robust extraction
            result_text = response.content[0].text
            result_data = self._extract_json_from_response(result_text)

            # Extract citations from response metadata
            citations_by_text = self._parse_citations(response)

            # Correlate citations to specific fields
            field_citations_map = self._correlate_citations_to_fields(result_data, citations_by_text)

            # Locate cited text in PDF using local Marker to get bounding boxes
            self._locate_citations_in_pdf(field_citations_map, pdf_extractor)

            # Create extraction results with citation data
            extractions = []
            for field, data in result_data.items():
                value = data.get('value')
                confidence = data.get('confidence', 0.8)

                # Get citation data for this field
                citation_info = field_citations_map.get(field, {})
                claude_citations = citation_info.get('raw_citations', [])
                cited_sections = citation_info.get('sections', [])
                cited_snippets = citation_info.get('snippets', [])
                citation_confidence = citation_info.get('confidence')

                # Try to find text location (fallback if citations don't have bounding boxes)
                search_results_fallback = pdf_extractor.search_text(str(value)[:50])
                page_num = search_results_fallback[0][0] if search_results_fallback else 1
                bbox = search_results_fallback[0][2] if search_results_fallback else None
                source_text = search_results_fallback[0][1] if search_results_fallback else str(value)

                extractions.append(ExtractionResult(
                    field=field,
                    value=value,
                    confidence=confidence,
                    page_number=page_num,
                    bounding_box=bbox,
                    source_text=source_text,
                    citations=[],
                    agent=self.name,
                    timestamp=datetime.now().isoformat(),
                    claude_citations=claude_citations,
                    cited_sections=cited_sections,
                    cited_text_snippets=cited_snippets,
                    citation_confidence=citation_confidence
                ))

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                fields_extracted=extractions,
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                fields_extracted=[],
                processing_time=processing_time,
                tokens_used=0,
                success=False,
                error=str(e)
            )

    def _extract_legacy(self, pdf_text: str, pdf_extractor: ProvenancePDFExtractor) -> AgentResult:
        """Legacy extraction using plain text (no citations)."""
        start_time = datetime.now()

        prompt = f"""Extract the following metadata from this medical research paper:

REQUIRED FIELDS:
- title: Full article title
- doi: Digital Object Identifier (format: 10.xxxx/xxxxx)
- pmid: PubMed ID if available
- journal: Journal name
- publication_date: Publication date (YYYY-MM-DD format)
- study_design: One of: RCT, PROSPECTIVE_COHORT, RETROSPECTIVE_COHORT, CASE_CONTROL, CASE_SERIES

PDF TEXT:
{pdf_text[:3000]}

Extract ONLY from the PDF text above. Do NOT use placeholder or example values.

Return ONLY a valid JSON object with these fields. For each field, include your confidence (0-1).

Format:
{{
  "title": {{"value": "<extracted_from_pdf>", "confidence": 0.0-1.0}},
  "doi": {{"value": "<extracted_from_pdf>", "confidence": 0.0-1.0}},
  ...
}}

IMPORTANT: Extract actual values from the PDF text, not placeholders."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            result_text = response.content[0].text
            result_text = re.sub(r'```json\s*|\s*```', '', result_text).strip()
            result_data = json.loads(result_text)

            # Create extraction results with provenance
            extractions = []
            for field, data in result_data.items():
                value = data.get('value')
                confidence = data.get('confidence', 0.8)

                # Try to find text location
                search_results = pdf_extractor.search_text(str(value)[:50])
                page_num = search_results[0][0] if search_results else 1
                bbox = search_results[0][2] if search_results else None
                source_text = search_results[0][1] if search_results else str(value)

                extractions.append(ExtractionResult(
                    field=field,
                    value=value,
                    confidence=confidence,
                    page_number=page_num,
                    bounding_box=bbox,
                    source_text=source_text,
                    citations=[],
                    agent=self.name,
                    timestamp=datetime.now().isoformat()
                ))

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                fields_extracted=extractions,
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                fields_extracted=[],
                processing_time=processing_time,
                tokens_used=0,
                success=False,
                error=str(e)
            )

class PopulationAgent(ExtractionAgent):
    """Extract study population data"""

    def extract(self, pdf_text: str, pdf_extractor: ProvenancePDFExtractor, use_search_results: bool = True, file_id: str = None) -> AgentResult:
        """
        Extract population data with optional citation support.

        Args:
            pdf_text: Full PDF text (used in legacy mode)
            pdf_extractor: PDF extractor for search_result blocks and location finding
            use_search_results: If True, use search_result blocks with citations (default)
                               If False, use legacy plain text mode
            file_id: If provided, use Files API hybrid mode (fastest)
        """
        if file_id:
            return self._extract_with_files_api(file_id, pdf_extractor)
        elif use_search_results:
            return self._extract_with_search_results(pdf_extractor)
        else:
            return self._extract_legacy(pdf_text, pdf_extractor)

    def _extract_with_search_results(self, pdf_extractor: ProvenancePDFExtractor) -> AgentResult:
        """Extract population data using search_result blocks with citation support."""
        start_time = datetime.now()

        # Get search_result blocks from PDF
        search_results = pdf_extractor.get_search_results(enable_citations=True)

        prompt = f"""Extract study population data from this cerebellar stroke paper.

REQUIRED FIELDS:
- total_sample_size: Total number of patients (integer)
- surgical_group_size: Number in surgical group (integer)
- control_group_size: Number in control group (integer)
- inclusion_criteria: Patient inclusion criteria (text)
- exclusion_criteria: Patient exclusion criteria (text)

SEARCH FOR:
- "patients", "subjects", "n =", "N ="
- "Methods" or "Patients and Methods" section
- Tables showing patient demographics

CRITICAL INSTRUCTIONS:
1. Quote the EXACT text from the PDF for each value
2. Do NOT paraphrase or summarize
3. Extract ONLY what is present in the document
4. If a field is not found, set value to null

Return ONLY valid JSON with confidence scores for each field.

Format:
{{
  "total_sample_size": {{"value": <exact_quoted_integer>, "confidence": 0.0-1.0}},
  "surgical_group_size": {{"value": <exact_quoted_integer>, "confidence": 0.0-1.0}},
  "control_group_size": {{"value": <exact_quoted_integer>, "confidence": 0.0-1.0}},
  "inclusion_criteria": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "exclusion_criteria": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}}
}}

IMPORTANT: Quote exact text from the PDF. This enables citation tracking."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2500,
                messages=[
                    {
                        "role": "user",
                        "content": [*search_results, {"type": "text", "text": prompt}]
                    }
                ]
            )

            # Parse JSON response using robust extraction
            result_text = response.content[0].text
            result_data = self._extract_json_from_response(result_text)

            # Extract citations from response metadata
            citations_by_text = self._parse_citations(response)

            # Correlate citations to specific fields
            field_citations_map = self._correlate_citations_to_fields(result_data, citations_by_text)

            # Locate cited text in PDF to get bounding boxes
            self._locate_citations_in_pdf(field_citations_map, pdf_extractor)

            # Create extraction results with citation data
            extractions = []
            for field, data in result_data.items():
                value = data.get('value')
                confidence = data.get('confidence', 0.8)

                # Get citation data for this field
                citation_info = field_citations_map.get(field, {})
                claude_citations = citation_info.get('raw_citations', [])
                cited_sections = citation_info.get('sections', [])
                cited_snippets = citation_info.get('snippets', [])
                citation_confidence = citation_info.get('confidence')

                # Try to find text location (fallback if citations don't have bounding boxes)
                search_results_fallback = pdf_extractor.search_text(str(value)[:50])
                page_num = search_results_fallback[0][0] if search_results_fallback else 1
                bbox = search_results_fallback[0][2] if search_results_fallback else None
                source_text = search_results_fallback[0][1] if search_results_fallback else str(value)

                extractions.append(ExtractionResult(
                    field=field,
                    value=value,
                    confidence=confidence,
                    page_number=page_num,
                    bounding_box=bbox,
                    source_text=source_text,
                    citations=[],
                    agent=self.name,
                    timestamp=datetime.now().isoformat(),
                    claude_citations=claude_citations,
                    cited_sections=cited_sections,
                    cited_text_snippets=cited_snippets,
                    citation_confidence=citation_confidence
                ))

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                fields_extracted=extractions,
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                fields_extracted=[],
                processing_time=processing_time,
                tokens_used=0,
                success=False,
                error=str(e)
            )

    def _extract_with_files_api(self, file_id: str, pdf_extractor: ProvenancePDFExtractor) -> AgentResult:
        """Extract population data using Files API with hybrid bounding box lookup."""
        start_time = datetime.now()

        prompt = f"""Extract the following population data from this medical research paper.

REQUIRED FIELDS:
- total_sample_size: Total number of patients in study
- surgical_group_size: Number in surgical intervention group
- control_group_size: Number in control/conservative group (if applicable)
- inclusion_criteria: Patient eligibility criteria for study enrollment
- exclusion_criteria: Reasons for patient exclusion from study

CRITICAL INSTRUCTIONS:
1. Quote the EXACT text from the PDF for each value
2. Do NOT paraphrase or summarize
3. Extract ONLY what is present in the document
4. If a field is not found, set value to null

Return ONLY a valid JSON object with these fields. For each field, include your confidence (0-1).

Format:
{{
  "total_sample_size": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "surgical_group_size": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "control_group_size": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "inclusion_criteria": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "exclusion_criteria": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}}
}}

IMPORTANT: Quote exact text from the PDF. This enables citation tracking."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=3000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "file",
                                    "file_id": file_id
                                },
                                "citations": {"enabled": True}
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            # Parse JSON response using robust extraction
            result_text = response.content[0].text
            result_data = self._extract_json_from_response(result_text)

            # Extract citations from response metadata
            citations_by_text = self._parse_citations(response)

            # Correlate citations to specific fields
            field_citations_map = self._correlate_citations_to_fields(result_data, citations_by_text)

            # Locate cited text in PDF using local Marker to get bounding boxes
            self._locate_citations_in_pdf(field_citations_map, pdf_extractor)

            # Create extraction results with citation data
            extractions = []
            for field, data in result_data.items():
                value = data.get('value')
                confidence = data.get('confidence', 0.8)

                # Get citation data for this field
                citation_info = field_citations_map.get(field, {})
                claude_citations = citation_info.get('raw_citations', [])
                cited_sections = citation_info.get('sections', [])
                cited_snippets = citation_info.get('snippets', [])
                citation_confidence = citation_info.get('confidence')

                # Try to find text location (fallback if citations don't have bounding boxes)
                search_results_fallback = pdf_extractor.search_text(str(value)[:50])
                page_num = search_results_fallback[0][0] if search_results_fallback else 1
                bbox = search_results_fallback[0][2] if search_results_fallback else None
                source_text = search_results_fallback[0][1] if search_results_fallback else str(value)

                extractions.append(ExtractionResult(
                    field=field,
                    value=value,
                    confidence=confidence,
                    page_number=page_num,
                    bounding_box=bbox,
                    source_text=source_text,
                    citations=[],
                    agent=self.name,
                    timestamp=datetime.now().isoformat(),
                    claude_citations=claude_citations,
                    cited_sections=cited_sections,
                    cited_text_snippets=cited_snippets,
                    citation_confidence=citation_confidence
                ))

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                fields_extracted=extractions,
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                fields_extracted=[],
                processing_time=processing_time,
                tokens_used=0,
                success=False,
                error=str(e)
            )

    def _extract_legacy(self, pdf_text: str, pdf_extractor: ProvenancePDFExtractor) -> AgentResult:
        """Legacy extraction using plain text (no citations)."""
        start_time = datetime.now()

        prompt = f"""Extract study population data from this cerebellar stroke paper:

REQUIRED FIELDS:
- total_sample_size: Total number of patients (integer)
- surgical_group_size: Number in surgical group (integer)
- control_group_size: Number in control group (integer)
- inclusion_criteria: Patient inclusion criteria (text)
- exclusion_criteria: Patient exclusion criteria (text)

SEARCH FOR:
- "patients", "subjects", "n =", "N ="
- "Methods" or "Patients and Methods" section
- Tables showing patient demographics

PDF TEXT:
{pdf_text[:5000]}

Extract ONLY from the PDF text above. Do NOT use example or placeholder values.

Return ONLY valid JSON with confidence scores for each field.

Format:
{{
  "total_sample_size": {{"value": <integer_from_pdf>, "confidence": 0.0-1.0}},
  "surgical_group_size": {{"value": <integer_from_pdf>, "confidence": 0.0-1.0}},
  ...
}}

IMPORTANT: Extract actual numbers from the PDF text, not examples."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text
            result_text = re.sub(r'```json\s*|\s*```', '', result_text).strip()
            result_data = json.loads(result_text)

            extractions = []
            for field, data in result_data.items():
                value = data.get('value')
                confidence = data.get('confidence', 0.8)

                # Find source location
                search_results = pdf_extractor.search_text(str(value)[:50])
                page_num = search_results[0][0] if search_results else 1
                bbox = search_results[0][2] if search_results else None
                source_text = search_results[0][1] if search_results else str(value)

                extractions.append(ExtractionResult(
                    field=field,
                    value=value,
                    confidence=confidence,
                    page_number=page_num,
                    bounding_box=bbox,
                    source_text=source_text,
                    citations=[],
                    agent=self.name,
                    timestamp=datetime.now().isoformat()
                ))

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                fields_extracted=extractions,
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                fields_extracted=[],
                processing_time=processing_time,
                tokens_used=0,
                success=False,
                error=str(e)
            )

class InterventionAgent(ExtractionAgent):
    """Extract surgical intervention details"""

    def extract(self, pdf_text: str, pdf_extractor: ProvenancePDFExtractor, use_search_results: bool = True, file_id: str = None) -> AgentResult:
        """
        Extract intervention data with optional citation support.

        Args:
            pdf_text: Full PDF text (used in legacy mode)
            pdf_extractor: PDF extractor for search_result blocks and location finding
            use_search_results: If True, use search_result blocks with citations (default)
                               If False, use legacy plain text mode
            file_id: If provided, use Files API hybrid mode (fastest)
        """
        if file_id:
            return self._extract_with_files_api(file_id, pdf_extractor)
        elif use_search_results:
            return self._extract_with_search_results(pdf_extractor)
        else:
            return self._extract_legacy(pdf_text, pdf_extractor)

    def _extract_with_search_results(self, pdf_extractor: ProvenancePDFExtractor) -> AgentResult:
        """Extract intervention data using search_result blocks with citation support."""
        start_time = datetime.now()

        # Get search_result blocks from PDF
        search_results = pdf_extractor.get_search_results(enable_citations=True)

        prompt = f"""Extract surgical intervention data from this cerebellar stroke paper.

REQUIRED FIELDS:
- surgical_type: One of: SDC_ALONE, SDC_EVD, SDC_HEMATOMA_EVACUATION, SDC_NECROSECTOMY
- timing_category: One of: <24h, 24-48h, >48h, UNKNOWN
- timing_hours: Precise timing in hours (float, or null)
- surgical_technique: Description of surgical technique

LOOK FOR:
- "suboccipital decompressive craniectomy", "SDC"
- "timing", "time from onset"
- Surgical procedure descriptions

CRITICAL INSTRUCTIONS:
1. Quote the EXACT text from the PDF for each value
2. Do NOT paraphrase or summarize
3. Extract ONLY what is present in the document
4. If a field is not found, set value to null

Return ONLY valid JSON with confidence scores.

Format:
{{
  "surgical_type": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "timing_category": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "timing_hours": {{"value": <exact_number>, "confidence": 0.0-1.0}},
  "surgical_technique": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}}
}}

IMPORTANT: Quote exact text from the PDF. This enables citation tracking."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2500,
                messages=[
                    {
                        "role": "user",
                        "content": [*search_results, {"type": "text", "text": prompt}]
                    }
                ]
            )

            # Parse JSON response using robust extraction
            result_text = response.content[0].text
            result_data = self._extract_json_from_response(result_text)

            # Extract citations from response metadata
            citations_by_text = self._parse_citations(response)

            # Correlate citations to specific fields
            field_citations_map = self._correlate_citations_to_fields(result_data, citations_by_text)

            # Locate cited text in PDF to get bounding boxes
            self._locate_citations_in_pdf(field_citations_map, pdf_extractor)

            # Create extraction results with citation data
            extractions = []
            for field, data in result_data.items():
                value = data.get('value')
                confidence = data.get('confidence', 0.8)

                # Get citation data for this field
                citation_info = field_citations_map.get(field, {})
                claude_citations = citation_info.get('raw_citations', [])
                cited_sections = citation_info.get('sections', [])
                cited_snippets = citation_info.get('snippets', [])
                citation_confidence = citation_info.get('confidence')

                # Try to find text location (fallback if citations don't have bounding boxes)
                search_results_fallback = pdf_extractor.search_text(str(value)[:50])
                page_num = search_results_fallback[0][0] if search_results_fallback else 1
                bbox = search_results_fallback[0][2] if search_results_fallback else None
                source_text = search_results_fallback[0][1] if search_results_fallback else str(value)

                extractions.append(ExtractionResult(
                    field=field,
                    value=value,
                    confidence=confidence,
                    page_number=page_num,
                    bounding_box=bbox,
                    source_text=source_text,
                    citations=[],
                    agent=self.name,
                    timestamp=datetime.now().isoformat(),
                    claude_citations=claude_citations,
                    cited_sections=cited_sections,
                    cited_text_snippets=cited_snippets,
                    citation_confidence=citation_confidence
                ))

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                fields_extracted=extractions,
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                fields_extracted=[],
                processing_time=processing_time,
                tokens_used=0,
                success=False,
                error=str(e)
            )

    def _extract_with_files_api(self, file_id: str, pdf_extractor: ProvenancePDFExtractor) -> AgentResult:
        """Extract intervention data using Files API with hybrid bounding box lookup."""
        start_time = datetime.now()

        prompt = f"""Extract the following surgical intervention data from this medical research paper.

REQUIRED FIELDS:
- surgical_type: Type of surgical decompression performed
- surgical_timing: Timing of surgery (e.g., <24h, 24-48h, >48h from onset)
- surgical_technique: Specific technical details of the surgical procedure
- anesthesia_type: Type of anesthesia used (e.g., general, local)

CRITICAL INSTRUCTIONS:
1. Quote the EXACT text from the PDF for each value
2. Do NOT paraphrase or summarize
3. Extract ONLY what is present in the document
4. If a field is not found, set value to null

Return ONLY a valid JSON object with these fields. For each field, include your confidence (0-1).

Format:
{{
  "surgical_type": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "surgical_timing": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "surgical_technique": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "anesthesia_type": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}}
}}

IMPORTANT: Quote exact text from the PDF. This enables citation tracking."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=3000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "file",
                                    "file_id": file_id
                                },
                                "citations": {"enabled": True}
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            # Parse JSON response using robust extraction
            result_text = response.content[0].text
            result_data = self._extract_json_from_response(result_text)

            # Extract citations from response metadata
            citations_by_text = self._parse_citations(response)

            # Correlate citations to specific fields
            field_citations_map = self._correlate_citations_to_fields(result_data, citations_by_text)

            # Locate cited text in PDF using local Marker to get bounding boxes
            self._locate_citations_in_pdf(field_citations_map, pdf_extractor)

            # Create extraction results with citation data
            extractions = []
            for field, data in result_data.items():
                value = data.get('value')
                confidence = data.get('confidence', 0.8)

                # Get citation data for this field
                citation_info = field_citations_map.get(field, {})
                claude_citations = citation_info.get('raw_citations', [])
                cited_sections = citation_info.get('sections', [])
                cited_snippets = citation_info.get('snippets', [])
                citation_confidence = citation_info.get('confidence')

                # Try to find text location (fallback if citations don't have bounding boxes)
                search_results_fallback = pdf_extractor.search_text(str(value)[:50])
                page_num = search_results_fallback[0][0] if search_results_fallback else 1
                bbox = search_results_fallback[0][2] if search_results_fallback else None
                source_text = search_results_fallback[0][1] if search_results_fallback else str(value)

                extractions.append(ExtractionResult(
                    field=field,
                    value=value,
                    confidence=confidence,
                    page_number=page_num,
                    bounding_box=bbox,
                    source_text=source_text,
                    citations=[],
                    agent=self.name,
                    timestamp=datetime.now().isoformat(),
                    claude_citations=claude_citations,
                    cited_sections=cited_sections,
                    cited_text_snippets=cited_snippets,
                    citation_confidence=citation_confidence
                ))

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                fields_extracted=extractions,
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                fields_extracted=[],
                processing_time=processing_time,
                tokens_used=0,
                success=False,
                error=str(e)
            )

    def _extract_legacy(self, pdf_text: str, pdf_extractor: ProvenancePDFExtractor) -> AgentResult:
        """Legacy extraction using plain text (no citations)."""
        start_time = datetime.now()

        prompt = f"""Extract surgical intervention data from this cerebellar stroke paper:

REQUIRED FIELDS:
- surgical_type: One of: SDC_ALONE, SDC_EVD, SDC_HEMATOMA_EVACUATION, SDC_NECROSECTOMY
- timing_category: One of: <24h, 24-48h, >48h, UNKNOWN
- timing_hours: Precise timing in hours (float, or null)
- surgical_technique: Description of surgical technique

LOOK FOR:
- "suboccipital decompressive craniectomy", "SDC"
- "timing", "time from onset"
- Surgical procedure descriptions

PDF TEXT:
{pdf_text}

Extract ONLY from the PDF text above. Do NOT use placeholder values.

Return ONLY valid JSON with confidence scores.

Format:
{{
  "surgical_type": {{"value": "<value_from_pdf>", "confidence": 0.0-1.0}},
  "timing_category": {{"value": "<value_from_pdf>", "confidence": 0.0-1.0}},
  "timing_hours": {{"value": <number_from_pdf>, "confidence": 0.0-1.0}},
  "surgical_technique": {{"value": "<description_from_pdf>", "confidence": 0.0-1.0}}
}}

IMPORTANT: Extract actual surgical details from the PDF, not examples."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text
            result_text = re.sub(r'```json\s*|\s*```', '', result_text).strip()
            result_data = json.loads(result_text)

            extractions = []
            for field, data in result_data.items():
                value = data.get('value')
                confidence = data.get('confidence', 0.8)

                search_results = pdf_extractor.search_text(str(value)[:50])
                page_num = search_results[0][0] if search_results else 1
                bbox = search_results[0][2] if search_results else None
                source_text = search_results[0][1] if search_results else str(value)

                extractions.append(ExtractionResult(
                    field=field,
                    value=value,
                    confidence=confidence,
                    page_number=page_num,
                    bounding_box=bbox,
                    source_text=source_text,
                    citations=[],
                    agent=self.name,
                    timestamp=datetime.now().isoformat()
                ))

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                fields_extracted=extractions,
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                fields_extracted=[],
                processing_time=processing_time,
                tokens_used=0,
                success=False,
                error=str(e)
            )

class OutcomesAgent(ExtractionAgent):
    """Extract outcome measures with hybrid search_result support"""

    def extract(self, pdf_text: str, pdf_extractor: ProvenancePDFExtractor, use_search_results: bool = True, file_id: str = None) -> AgentResult:
        """
        Extract outcomes with optional search_result blocks for enhanced citations.

        Args:
            pdf_text: Raw PDF text (used in legacy mode)
            pdf_extractor: PDF extractor instance (must have get_search_results() for new mode)
            use_search_results: If True, use search_result blocks for natural citations (DEFAULT)
            file_id: If provided, use Files API hybrid mode (fastest)
        """
        start_time = datetime.now()

        if file_id:
            # FASTEST: Use Files API hybrid mode
            return self._extract_with_files_api(file_id, pdf_extractor)
        elif use_search_results and hasattr(pdf_extractor, 'get_search_results'):
            # NEW APPROACH: Use search_result blocks for automatic citations
            return self._extract_with_search_results(pdf_extractor, start_time)
        else:
            # OLD APPROACH: Legacy text-based extraction
            return self._extract_legacy(pdf_text, pdf_extractor, start_time)

    def _extract_with_files_api(self, file_id: str, pdf_extractor: ProvenancePDFExtractor) -> AgentResult:
        """Extract outcome data using Files API with hybrid bounding box lookup."""
        start_time = datetime.now()

        prompt = f"""Extract the following outcome data from this medical research paper.

REQUIRED FIELDS:
- mortality_rate: In-hospital or 30-day mortality rate
- modified_rankin_score: mRS distribution at follow-up (functional outcome)
- complications: Surgical and medical complications
- predictors_of_outcome: Factors associated with favorable/poor outcomes

CRITICAL INSTRUCTIONS:
1. Quote the EXACT text from the PDF for each value
2. Do NOT paraphrase or summarize
3. Extract ONLY what is present in the document
4. If a field is not found, set value to null

Return ONLY a valid JSON object with these fields. For each field, include your confidence (0-1).

Format:
{{
  "mortality_rate": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "modified_rankin_score": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "complications": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "predictors_of_outcome": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}}
}}

IMPORTANT: Quote exact text from the PDF. This enables citation tracking."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=3000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "file",
                                    "file_id": file_id
                                },
                                "citations": {"enabled": True}
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            # Parse JSON response using robust extraction
            result_text = response.content[0].text
            result_data = self._extract_json_from_response(result_text)

            # Extract citations from response metadata
            citations_by_text = self._parse_citations(response)

            # Correlate citations to specific fields
            field_citations_map = self._correlate_citations_to_fields(result_data, citations_by_text)

            # Locate cited text in PDF using local Marker to get bounding boxes
            self._locate_citations_in_pdf(field_citations_map, pdf_extractor)

            # Create extraction results with citation data
            extractions = []
            for field, data in result_data.items():
                value = data.get('value')
                confidence = data.get('confidence', 0.8)

                # Get citation data for this field
                citation_info = field_citations_map.get(field, {})
                claude_citations = citation_info.get('raw_citations', [])
                cited_sections = citation_info.get('sections', [])
                cited_snippets = citation_info.get('snippets', [])
                citation_confidence = citation_info.get('confidence')

                # Try to find text location (fallback if citations don't have bounding boxes)
                search_results_fallback = pdf_extractor.search_text(str(value)[:50])
                page_num = search_results_fallback[0][0] if search_results_fallback else 1
                bbox = search_results_fallback[0][2] if search_results_fallback else None
                source_text = search_results_fallback[0][1] if search_results_fallback else str(value)

                extractions.append(ExtractionResult(
                    field=field,
                    value=value,
                    confidence=confidence,
                    page_number=page_num,
                    bounding_box=bbox,
                    source_text=source_text,
                    citations=[],
                    agent=self.name,
                    timestamp=datetime.now().isoformat(),
                    claude_citations=claude_citations,
                    cited_sections=cited_sections,
                    cited_text_snippets=cited_snippets,
                    citation_confidence=citation_confidence
                ))

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                fields_extracted=extractions,
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                fields_extracted=[],
                processing_time=processing_time,
                tokens_used=0,
                success=False,
                error=str(e)
            )

    def _extract_with_search_results(self, pdf_extractor, start_time) -> AgentResult:
        """New approach using search_result blocks for natural citations"""
        try:
            # Get search_result blocks from Marker extractor
            search_results = pdf_extractor.get_search_results(enable_citations=True)

            # Build prompt with instruction to use search results
            instruction = {
                "type": "text",
                "text": """I've provided search results from a cerebellar stroke surgery paper above. Extract the following outcome data from those search results:

REQUIRED FIELDS:
- mortality_30day_surgical: 30-day mortality rate in surgical group (%, float)
- mortality_30day_control: 30-day mortality rate in control group (%, float)
- mrs_favorable_surgical: Rate of favorable mRS (0-3) in surgical group (%, float)
- mrs_favorable_control: Rate of favorable mRS (0-3) in control group (%, float)

The data should be in the "Results" search result section.

CRITICAL: First, quote the exact text from the search results that contains each mortality and mRS value. This will provide citations. Then provide the JSON.

Response format:

CITATIONS:
[Quote the exact text containing the mortality rates]
[Quote the exact text containing the mRS scores]

JSON:
{
  "mortality_30day_surgical": {"value": 23.8, "confidence": 0.95},
  "mortality_30day_control": {"value": 71.4, "confidence": 0.95},
  "mrs_favorable_surgical": {"value": 57.1, "confidence": 0.95},
  "mrs_favorable_control": {"value": 14.3, "confidence": 0.95}
}

Use null for value if data not found. Set confidence between 0.0-1.0 based on clarity of the data."""
            }

            # Combine search results and instruction
            content = search_results + [instruction]

            # Call Claude with search_result blocks
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": content}]
            )

            # Parse JSON response using robust extraction
            full_response_text = ""
            for block in response.content:
                if block.type == "text":
                    full_response_text += block.text + "\n"

            result_data = self._extract_json_from_response(full_response_text)

            # Extract citations from response metadata
            citations_by_text = self._parse_citations(response)

            # Correlate citations to specific fields
            field_citations_map = self._correlate_citations_to_fields(result_data, citations_by_text)

            # Locate cited text in PDF to get bounding boxes
            self._locate_citations_in_pdf(field_citations_map, pdf_extractor)

            # Build extractions with enhanced citation data
            extractions = []
            for field, data in result_data.items():
                value = data.get('value')
                confidence = data.get('confidence', 0.8)

                # Find relevant search result for this field
                page_num = 1
                bbox = None
                source_text = str(value) if value else "Data not available"

                # Get citation info for this field
                field_citations = field_citations_map.get(field, {})

                extractions.append(ExtractionResult(
                    field=field,
                    value=value,
                    confidence=confidence,
                    page_number=page_num,
                    bounding_box=bbox,
                    source_text=source_text,
                    citations=[],  # Legacy field
                    agent=self.name,
                    timestamp=datetime.now().isoformat(),
                    # Enhanced citation fields
                    claude_citations=field_citations.get('raw_citations'),
                    cited_sections=field_citations.get('sections'),
                    cited_text_snippets=field_citations.get('snippets'),
                    citation_confidence=field_citations.get('confidence')
                ))

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                agent_name=f"{self.name} (search_result mode)",
                fields_extracted=extractions,
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                fields_extracted=[],
                processing_time=processing_time,
                tokens_used=0,
                success=False,
                error=f"search_result extraction failed: {str(e)}"
            )

    def _extract_legacy(self, pdf_text: str, pdf_extractor, start_time) -> AgentResult:
        """Legacy approach using plain text"""
        prompt = f"""Extract outcome data from this cerebellar stroke surgery paper:

REQUIRED FIELDS:
- mortality_30day_surgical: 30-day mortality rate in surgical group (%, float)
- mortality_30day_control: 30-day mortality rate in control group (%, float)
- mrs_favorable_surgical: Rate of favorable mRS (0-3) in surgical group (%, float)
- mrs_favorable_control: Rate of favorable mRS (0-3) in control group (%, float)

LOOK FOR:
- "mortality", "death", "died"
- "30-day", "in-hospital", "perioperative"
- "mRS", "modified Rankin Scale"
- "favorable outcome", "good outcome"
- Results tables

PDF TEXT:
{pdf_text}

Extract ONLY from the PDF text above. Do NOT use placeholder or example values.

Return ONLY valid JSON with confidence scores. Use null if data not available.

Format:
{{
  "mortality_30day_surgical": {{"value": <percentage_from_pdf>, "confidence": 0.0-1.0}},
  "mortality_30day_control": {{"value": <percentage_from_pdf>, "confidence": 0.0-1.0}},
  "mrs_favorable_surgical": {{"value": <percentage_from_pdf>, "confidence": 0.0-1.0}},
  "mrs_favorable_control": {{"value": <percentage_from_pdf>, "confidence": 0.0-1.0}}
}}

IMPORTANT: Extract actual percentages/numbers from the PDF Results section, not examples."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text
            result_text = re.sub(r'```json\s*|\s*```', '', result_text).strip()
            result_data = json.loads(result_text)

            extractions = []
            for field, data in result_data.items():
                value = data.get('value')
                confidence = data.get('confidence', 0.8)

                if value is not None:
                    search_results = pdf_extractor.search_text(str(value)[:20])
                    page_num = search_results[0][0] if search_results else 1
                    bbox = search_results[0][2] if search_results else None
                    source_text = search_results[0][1] if search_results else str(value)
                else:
                    page_num = 1
                    bbox = None
                    source_text = "Data not available"

                extractions.append(ExtractionResult(
                    field=field,
                    value=value,
                    confidence=confidence,
                    page_number=page_num,
                    bounding_box=bbox,
                    source_text=source_text,
                    citations=[],
                    agent=self.name,
                    timestamp=datetime.now().isoformat()
                ))

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                agent_name=f"{self.name} (legacy mode)",
                fields_extracted=extractions,
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                fields_extracted=[],
                processing_time=processing_time,
                tokens_used=0,
                success=False,
                error=str(e)
            )

    def _parse_citations(self, response) -> Dict:
        """
        Parse citation data from Claude's response.

        Returns dict mapping field names to citation info:
        {
            "field_name": {
                "raw_citations": [...],
                "sections": [...],
                "snippets": [...],
                "confidence": 0.0-1.0
            }
        }
        """
        citations_by_text = {}

        # Extract all text blocks with citations from response
        for content_block in response.content:
            if content_block.type == "text":
                text = content_block.text

                # Check if block has citations
                if hasattr(content_block, 'citations') and content_block.citations:
                    citations = content_block.citations
                    citations_by_text[text] = citations

        # If no citations found, return empty dict
        if not citations_by_text:
            return {}

        # Parse citations and extract metadata
        parsed_citations = {}

        for text, citations in citations_by_text.items():
            raw_citations = []
            sections = set()
            snippets = []

            for citation in citations:
                # Extract citation metadata
                citation_dict = {
                    "type": citation.type if hasattr(citation, 'type') else "unknown",
                    "cited_text": citation.cited_text if hasattr(citation, 'cited_text') else text,
                    "document_index": getattr(citation, 'document_index', None),
                    "document_title": getattr(citation, 'document_title', None) or getattr(citation, 'title', None),
                    "source": getattr(citation, 'source', None),
                }

                # Add type-specific location fields
                citation_dict.update(self._get_location_fields(citation))

                raw_citations.append(citation_dict)

                # Extract section titles
                if citation_dict['document_title']:
                    sections.add(citation_dict['document_title'])

                # Extract cited text snippets
                if citation_dict['cited_text']:
                    snippets.append(citation_dict['cited_text'])

            # Calculate citation confidence score
            confidence = self._calculate_citation_confidence(raw_citations)

            parsed_citations[text] = {
                "raw_citations": raw_citations,
                "sections": list(sections),
                "snippets": snippets,
                "confidence": confidence
            }

        return parsed_citations

    def _get_location_fields(self, citation) -> Dict:
        """Extract location fields based on citation type."""
        location_fields = {}
        citation_type = getattr(citation, 'type', None)

        if citation_type == "char_location":
            location_fields["start_char_index"] = getattr(citation, 'start_char_index', None)
            location_fields["end_char_index"] = getattr(citation, 'end_char_index', None)
        elif citation_type == "page_location":
            location_fields["start_page_number"] = getattr(citation, 'start_page_number', None)
            location_fields["end_page_number"] = getattr(citation, 'end_page_number', None)
        elif citation_type == "content_block_location" or citation_type == "search_result_location":
            location_fields["start_block_index"] = getattr(citation, 'start_block_index', None)
            location_fields["end_block_index"] = getattr(citation, 'end_block_index', None)
            location_fields["search_result_index"] = getattr(citation, 'search_result_index', None)

        return location_fields

    def _calculate_citation_confidence(self, raw_citations: List[Dict]) -> float:
        """
        Calculate confidence score based on citation quality.

        Scoring factors:
        - Number of citations (more = higher confidence)
        - Specificity of locations (page > block > char)
        - Length of cited text (longer = more specific)
        """
        if not raw_citations:
            return 0.0

        # Base score from number of citations (cap at 3)
        base_score = min(1.0, len(raw_citations) / 3.0)

        # Bonus for specific citation types
        specificity_bonus = 0.0
        for cit in raw_citations:
            if cit['type'] == 'page_location':
                specificity_bonus += 0.05
            elif cit['type'] in ['char_location', 'search_result_location']:
                specificity_bonus += 0.10

        # Bonus for longer cited text (more context)
        text_length_bonus = 0.0
        for cit in raw_citations:
            cited_text = cit.get('cited_text', '')
            if len(cited_text) > 50:
                text_length_bonus += 0.05
            if len(cited_text) > 100:
                text_length_bonus += 0.05

        final_score = min(1.0, base_score + specificity_bonus + text_length_bonus)
        return round(final_score, 2)

    def _correlate_citations_to_fields(self, result_data: Dict, citations_data: Dict) -> Dict:
        """
        Map citations to specific fields based on text content matching.

        Strategy: Match field values to citation text to determine which
        citations support which extracted fields.
        """
        field_citation_map = {}

        for field, data in result_data.items():
            value = str(data.get('value', ''))

            if not value or value == 'None':
                continue

            # Find citations containing this value
            matching_citations = []
            for text, cit_info in citations_data.items():
                # Check if the value appears in the cited text or snippets
                if value in text or any(value in snippet for snippet in cit_info.get('snippets', [])):
                    matching_citations.append(cit_info)

            if matching_citations:
                # Merge all matching citations (keep all per user preference)
                all_raw_citations = []
                all_sections = set()
                all_snippets = []
                max_confidence = 0.0

                for cit_info in matching_citations:
                    all_raw_citations.extend(cit_info['raw_citations'])
                    all_sections.update(cit_info['sections'])
                    all_snippets.extend(cit_info['snippets'])
                    max_confidence = max(max_confidence, cit_info['confidence'])

                field_citation_map[field] = {
                    "raw_citations": all_raw_citations,
                    "sections": list(all_sections),
                    "snippets": all_snippets,
                    "confidence": max_confidence
                }

        return field_citation_map

    def _locate_citations_in_pdf(self, field_citations_map: Dict, pdf_extractor) -> None:
        """
        Locate cited text in the PDF to get exact bounding boxes for highlighting.

        Uses pdf_extractor.search_text() to find the exact location of each
        cited text snippet. Modifies field_citations_map in place to add
        bounding box information.

        Args:
            field_citations_map: Dict mapping fields to their citation data
            pdf_extractor: PDF extractor instance with search_text() method
        """
        for field, citation_data in field_citations_map.items():
            raw_citations = citation_data.get('raw_citations', [])

            # Add bounding boxes to each raw citation
            for citation in raw_citations:
                cited_text = citation.get('cited_text', '')

                # Skip if no cited text or too long to search efficiently
                if not cited_text or len(cited_text) > 500:
                    continue

                try:
                    # Search for the cited text in the PDF
                    # Take first 100 chars for more reliable matching
                    search_query = cited_text[:100].strip()

                    if len(search_query) < 10:
                        # Too short to search reliably
                        continue

                    # Search in PDF
                    search_results = pdf_extractor.search_text(search_query)

                    if search_results:
                        # Take the first match
                        page_num, context, bbox = search_results[0]

                        # Add bounding box to citation
                        citation['pdf_bounding_box'] = bbox.to_dict() if bbox else None
                        citation['pdf_page'] = page_num
                        citation['pdf_context'] = context

                except Exception as e:
                    # Silently continue if search fails
                    continue

class ValidatorAgent(ExtractionAgent):
    """Validate and consolidate extractions"""
    
    def validate(self, all_extractions: List[ExtractionResult]) -> AgentResult:
        start_time = datetime.now()
        
        # Build validation summary
        extractions_by_field = {}
        for ext in all_extractions:
            if ext.field not in extractions_by_field:
                extractions_by_field[ext.field] = []
            extractions_by_field[ext.field].append(ext)
        
        # Check for conflicts and low confidence
        validations = []
        for field, exts in extractions_by_field.items():
            if len(exts) > 1:
                # Multiple extractions for same field - check consistency
                values = [e.value for e in exts]
                if len(set(map(str, values))) > 1:
                    # Conflict detected
                    best = max(exts, key=lambda e: e.confidence)
                    best.validation_status = "FLAGGED"
                    validations.append(best)
                else:
                    # Consistent - take highest confidence
                    best = max(exts, key=lambda e: e.confidence)
                    best.validation_status = "VALIDATED"
                    validations.append(best)
            else:
                # Single extraction
                ext = exts[0]
                if ext.confidence > 0.8:
                    ext.validation_status = "VALIDATED"
                else:
                    ext.validation_status = "REVIEW_NEEDED"
                validations.append(ext)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return AgentResult(
            agent_name=self.name,
            fields_extracted=validations,
            processing_time=processing_time,
            tokens_used=0,
            success=True
        )

# ============================================================================
# Main Extraction Orchestrator
# ============================================================================

class CerebellarExtractionSystem:
    """Orchestrate multi-agent extraction pipeline"""

    def __init__(self, api_key: str = ANTHROPIC_API_KEY):
        self.client = Anthropic(api_key=api_key)
        self.agents = [
            MetadataAgent("Metadata Agent", self.client),
            PopulationAgent("Population Agent", self.client),
            InterventionAgent("Intervention Agent", self.client),
            OutcomesAgent("Outcomes Agent", self.client),
        ]
        self.validator = ValidatorAgent("Validator Agent", self.client)
        self.uploaded_files = {}  # Track uploaded file IDs for cleanup

    def _upload_pdf_to_files_api(self, pdf_path: str) -> str:
        """
        Upload PDF to Anthropic Files API.

        Args:
            pdf_path: Path to PDF file

        Returns:
            file_id: Files API file ID
        """
        print(f"📤 Uploading PDF to Files API...")

        with open(pdf_path, 'rb') as f:
            file_response = self.client.files.create(
                file=f,
                purpose="extractive_qa"
            )

        file_id = file_response.id
        self.uploaded_files[pdf_path] = file_id

        print(f"   ✅ Upload complete: {file_id}")
        return file_id

    def _cleanup_files_api(self):
        """Clean up uploaded files from Files API."""
        for pdf_path, file_id in self.uploaded_files.items():
            try:
                self.client.files.delete(file_id)
                print(f"   🗑️  Deleted file: {file_id}")
            except Exception as e:
                print(f"   ⚠️  Could not delete {file_id}: {e}")

        self.uploaded_files.clear()

    def extract_from_pdf(self, pdf_path: str, use_search_results: bool = True, use_files_api: bool = False) -> Dict:
        """
        Run full extraction pipeline.

        Args:
            pdf_path: Path to PDF file
            use_search_results: If True, use search_result blocks with citations (default)
                               If False, use legacy plain text mode
            use_files_api: If True, use Files API for extraction (faster, more reliable)
                          If False, use local Marker processing (default)

        Hybrid Mode (use_files_api=True):
        - Uploads PDF to Files API for fast extraction with native citations
        - Uses local Marker to find exact bounding boxes for cited text
        - Cleans up uploaded file after extraction
        - 3-5x faster than search_result mode
        """
        if use_files_api:
            mode = "FILES_API (hybrid)"
        elif use_search_results:
            mode = "SEARCH_RESULT (with citations)"
        else:
            mode = "LEGACY (plain text)"

        print(f"\n🧠 Starting Cerebellar SDC Extraction")
        print(f"📄 PDF: {pdf_path}")
        print(f"🔧 Mode: {mode}")

        # Initialize PDF extractor (always needed for bounding boxes)
        pdf_extractor = ProvenancePDFExtractor(pdf_path)
        pdf_text = pdf_extractor.extract_all_text()

        print(f"📖 Extracted {len(pdf_text)} characters from PDF")

        # Upload to Files API if using hybrid mode
        file_id = None
        if use_files_api:
            try:
                file_id = self._upload_pdf_to_files_api(pdf_path)
            except Exception as e:
                print(f"   ⚠️  Files API upload failed: {e}")
                print(f"   ⚠️  Falling back to search_result mode")
                use_files_api = False

        # Run all agents
        all_results = []
        all_extractions = []

        for agent in self.agents:
            print(f"\n🤖 Running {agent.name}...")
            result = agent.extract(
                pdf_text,
                pdf_extractor,
                use_search_results=use_search_results,
                file_id=file_id if use_files_api else None
            )
            all_results.append(result)
            all_extractions.extend(result.fields_extracted)

            if result.success:
                print(f"   ✅ Extracted {len(result.fields_extracted)} fields in {result.processing_time:.2f}s")
                # Show citation stats if using search_results mode
                if use_search_results:
                    fields_with_citations = sum(1 for f in result.fields_extracted if f.claude_citations)
                    if fields_with_citations > 0:
                        total_citations = sum(len(f.claude_citations) for f in result.fields_extracted if f.claude_citations)
                        print(f"   📚 Citations: {fields_with_citations}/{len(result.fields_extracted)} fields, {total_citations} total")
            else:
                print(f"   ❌ Error: {result.error}")
        
        # Run validator
        print(f"\n✅ Running Validator Agent...")
        validation_result = self.validator.validate(all_extractions)
        all_results.append(validation_result)
        
        validated_extractions = validation_result.fields_extracted
        print(f"   ✅ Validated {len(validated_extractions)} fields")
        
        # Close PDF
        pdf_extractor.close()

        # Clean up Files API uploads
        if use_files_api:
            print(f"\n🗑️  Cleaning up Files API...")
            self._cleanup_files_api()

        # Build final output
        output = {
            "metadata": {
                "pdf_path": pdf_path,
                "extraction_date": datetime.now().isoformat(),
                "model": MODEL,
                "total_fields": len(validated_extractions),
                "total_tokens": sum(r.tokens_used for r in all_results),
                "total_time": sum(r.processing_time for r in all_results)
            },
            "agent_results": [
                {
                    "agent": r.agent_name,
                    "success": r.success,
                    "fields": len(r.fields_extracted),
                    "processing_time": r.processing_time,
                    "tokens": r.tokens_used,
                    "error": r.error
                }
                for r in all_results
            ],
            "extractions": [e.to_dict() for e in validated_extractions],
            "data": {e.field: e.value for e in validated_extractions}
        }
        
        print(f"\n✅ Extraction Complete!")
        print(f"   📊 Total fields: {len(validated_extractions)}")
        print(f"   ⏱️  Total time: {output['metadata']['total_time']:.2f}s")
        print(f"   🎯 Tokens used: {output['metadata']['total_tokens']}")
        
        return output

# ============================================================================
# CLI Interface
# ============================================================================

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python enhanced_clinical_extractor.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    if not os.path.exists(pdf_path):
        print(f"❌ Error: File not found: {pdf_path}")
        sys.exit(1)
    
    # Run extraction
    system = CerebellarExtractionSystem()
    results = system.extract_from_pdf(pdf_path)
    
    # Save results
    output_path = pdf_path.replace('.pdf', '_extraction.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_path}")
    
    # Print summary
    print(f"\n📋 EXTRACTION SUMMARY")
    print("=" * 60)
    for field, value in results['data'].items():
        print(f"{field}: {value}")

if __name__ == "__main__":
    main()
