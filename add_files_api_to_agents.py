#!/usr/bin/env python3
"""
Script to add Files API support to remaining agents in cerebellar_extractor_pro.py
Adds _extract_with_files_api() method to PopulationAgent, InterventionAgent, and OutcomesAgent
"""

import re

# Read the file
with open('cerebellar_extractor_pro.py', 'r') as f:
    content = f.read()

# Agent configurations with their specific prompts
agents = {
    'PopulationAgent': {
        'fields_desc': '''- total_sample_size: Total number of patients in study
- surgical_group_size: Number in surgical intervention group
- control_group_size: Number in control/conservative group (if applicable)
- inclusion_criteria: Patient eligibility criteria for study enrollment
- exclusion_criteria: Reasons for patient exclusion from study''',
        'fields_format': '''"total_sample_size": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "surgical_group_size": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "control_group_size": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "inclusion_criteria": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "exclusion_criteria": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}}'''
    },
    'InterventionAgent': {
        'fields_desc': '''- surgical_type: Type of surgical decompression performed
- surgical_timing: Timing of surgery (e.g., <24h, 24-48h, >48h from onset)
- surgical_technique: Specific technical details of the surgical procedure
- anesthesia_type: Type of anesthesia used (e.g., general, local)''',
        'fields_format': '''"surgical_type": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "surgical_timing": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "surgical_technique": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "anesthesia_type": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}}'''
    },
    'OutcomesAgent': {
        'fields_desc': '''- mortality_rate: In-hospital or 30-day mortality rate
- modified_rankin_score: mRS distribution at follow-up (functional outcome)
- complications: Surgical and medical complications
- predictors_of_outcome: Factors associated with favorable/poor outcomes''',
        'fields_format': '''"mortality_rate": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "modified_rankin_score": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "complications": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}},
  "predictors_of_outcome": {{"value": "<exact_quoted_text>", "confidence": 0.0-1.0}}'''
    }
}

for agent_name, agent_config in agents.items():
    print(f"Processing {agent_name}...")

    # 1. Update extract() method signature to include file_id
    pattern = rf'(class {agent_name}\(ExtractionAgent\):.*?def extract\(self, pdf_text: str, pdf_extractor: ProvenancePDFExtractor, use_search_results: bool = True)\) -> AgentResult:'
    replacement = rf'\1, file_id: str = None) -> AgentResult:'
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    # 2. Update routing logic in extract() method to handle file_id
    pattern = rf'(class {agent_name}\(ExtractionAgent\):.*?def extract\(self.*?\n.*?""".*?""")\s+if use_search_results:'
    replacement = rf'\1\n        if file_id:\n            return self._extract_with_files_api(file_id, pdf_extractor)\n        elif use_search_results:'
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    # 3. Update docstring to mention file_id parameter
    pattern = rf'(class {agent_name}\(ExtractionAgent\):.*?def extract\(.*?\n.*?""".*?use_search_results:.*?If False, use legacy plain text mode)\n'
    replacement = rf'\1\n            file_id: If provided, use Files API hybrid mode (fastest)\n'
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    # 4. Add _extract_with_files_api() method before _extract_legacy()
    # Find the _extract_legacy method for this agent
    pattern = rf'(class {agent_name}\(ExtractionAgent\):.*?)(    def _extract_legacy\(self, pdf_text: str, pdf_extractor: ProvenancePDFExtractor\) -> AgentResult:)'

    files_api_method = f'''    def _extract_with_files_api(self, file_id: str, pdf_extractor: ProvenancePDFExtractor) -> AgentResult:
        """Extract data using Files API with hybrid bounding box lookup."""
        start_time = datetime.now()

        prompt = f"""Extract the following data from this medical research paper.

REQUIRED FIELDS:
{agent_config['fields_desc']}

CRITICAL INSTRUCTIONS:
1. Quote the EXACT text from the PDF for each value
2. Do NOT paraphrase or summarize
3. Extract ONLY what is present in the document
4. If a field is not found, set value to null

Return ONLY a valid JSON object with these fields. For each field, include your confidence (0-1).

Format:
{{{{
  {agent_config['fields_format']}
}}}}

IMPORTANT: Quote exact text from the PDF. This enables citation tracking."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=3000,
                messages=[
                    {{
                        "role": "user",
                        "content": [
                            {{
                                "type": "document",
                                "source": {{
                                    "type": "file",
                                    "file_id": file_id
                                }},
                                "citations": {{"enabled": True}}
                            }},
                            {{
                                "type": "text",
                                "text": prompt
                            }}
                        ]
                    }}
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
                citation_info = field_citations_map.get(field, {{}})
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

    '''

    replacement = rf'\1{files_api_method}\2'
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    print(f"  ✅ Added Files API support to {agent_name}")

# Write back the updated file
with open('cerebellar_extractor_pro.py', 'w') as f:
    f.write(content)

print("\n✅ All agents updated with Files API support!")
print("   - PopulationAgent")
print("   - InterventionAgent")
print("   - OutcomesAgent")
