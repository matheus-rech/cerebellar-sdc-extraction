import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { FileText, CheckCircle, XCircle, AlertTriangle, Play, Pause, Download, Upload, Settings, Users, BarChart3, Loader2, Activity, Clock, TrendingUp, Filter, Save, FolderOpen } from 'lucide-react';

export default function DualLLMScreeningTool() {
  // API Configuration
  const [apiKeys, setApiKeys] = useState({
    openai: 'sk-1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t',
    anthropic: 'sk-1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t'
  });

  // Model Configuration
  const [modelConfig, setModelConfig] = useState({
    conservativeProvider: 'anthropic',
    conservativeModel: 'claude-sonnet-4-20250514',
    conservativeTemp: 0.1,
    liberalProvider: 'openai',
    liberalModel: 'gpt-4',
    liberalTemp: 0.3,
    maxRetries: 3,
    rateLimitDelay: 1000,
    batchSize: 3
  });

  // State Management
  const [citations, setCitations] = useState([]);
  const [criteria, setCriteria] = useState({
    researchQuestion: '',
    population: '',
    intervention: '',
    comparison: '',
    outcome: '',
    timeframe: '',
    studyTypes: '',
    inclusionLanguage: '',
    inclusionPublication: '',
    inclusionSampleSize: '',
    inclusionDataAvailability: '',
    otherInclusion: '',
    exclusionStudyTypes: '',
    exclusionPopulations: '',
    exclusionInterventions: '',
    exclusionLanguages: '',
    otherExclusion: ''
  });
  
  const [results, setResults] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedFilter, setSelectedFilter] = useState('all');
  const [stats, setStats] = useState({
    total: 0,
    included: 0,
    excluded: 0,
    uncertain: 0,
    conflicts: 0,
    humanReview: 0,
    avgConfidence: 0,
    avgTime: 0,
    errors: 0
  });
  const [logs, setLogs] = useState([]);
  const [sessionStartTime, setSessionStartTime] = useState(null);

  // Add log entry
  const addLog = useCallback((message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [{
      id: Date.now(),
      timestamp,
      message,
      type
    }, ...prev].slice(0, 100));
  }, []);

  // Parse citations from various formats
  const parseCitations = (text) => {
    const lines = text.trim().split('\n\n');
    const parsed = [];
    
    lines.forEach((block, idx) => {
      if (!block.trim()) return;
      
      const lines = block.split('\n');
      const citation = {
        id: `cite_${Date.now()}_${idx}`,
        title: '',
        authors: '',
        journal: '',
        year: '',
        abstract: '',
        doi: '',
        pmid: ''
      };
      
      lines.forEach(line => {
        const lower = line.toLowerCase();
        if (lower.includes('title:')) {
          citation.title = line.split(':', 2)[1]?.trim() || '';
        } else if (lower.includes('author')) {
          citation.authors = line.split(':', 2)[1]?.trim() || '';
        } else if (lower.includes('journal:')) {
          citation.journal = line.split(':', 2)[1]?.trim() || '';
        } else if (lower.includes('year:')) {
          citation.year = line.split(':', 2)[1]?.trim() || '';
        } else if (lower.includes('abstract:')) {
          citation.abstract = line.split(':', 2)[1]?.trim() || '';
        } else if (lower.includes('doi:')) {
          citation.doi = line.split(':', 2)[1]?.trim() || '';
        } else if (lower.includes('pmid:')) {
          citation.pmid = line.split(':', 2)[1]?.trim() || '';
        } else if (citation.abstract) {
          citation.abstract += ' ' + line.trim();
        }
      });
      
      if (citation.title || citation.abstract) {
        parsed.push(citation);
      }
    });
    
    return parsed;
  };

  // Handle file upload
  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const text = e.target.result;
          
          // Try JSON first
          if (file.name.endsWith('.json')) {
            const data = JSON.parse(text);
            if (Array.isArray(data)) {
              setCitations(data.map((c, idx) => ({
                ...c,
                id: c.id || `cite_${Date.now()}_${idx}`
              })));
            } else if (data.citations) {
              setCitations(data.citations);
            }
            addLog(`Loaded ${data.length || data.citations?.length} citations from JSON`, 'success');
          } else {
            // Parse as text
            const parsed = parseCitations(text);
            setCitations(parsed);
            addLog(`Loaded ${parsed.length} citations from file`, 'success');
          }
        } catch (error) {
          addLog(`Error loading file: ${error.message}`, 'error');
        }
      };
      reader.readAsText(file);
    }
  };

  // Create evaluation prompt
  const createPrompt = (citation, strategy) => {
    const persona = strategy === 'conservative' 
      ? `You are Dr. Sarah Chen, a meticulous systematic reviewer with 20 years of experience in evidence-based medicine. You follow Cochrane guidelines strictly and believe in minimizing false negatives. When uncertain, you prefer to include studies for human review rather than risk excluding potentially relevant research.`
      : `You are Dr. Michael Rodriguez, an efficient systematic reviewer who values both thoroughness and practicality. You have extensive experience in rapid reviews and understand the importance of focusing resources on the most relevant studies. You balance comprehensiveness with efficiency.`;
    
    const approach = strategy === 'conservative'
      ? "err on the side of inclusion to avoid missing potentially relevant studies. When in doubt, include for human review."
      : "balance comprehensiveness with efficiency, excluding studies that clearly don't meet the criteria while including borderline cases that show promise.";

    return `${persona}

You are screening citations for a systematic review with the following criteria:

**Research Question:** 
${criteria.researchQuestion || 'Not specified'}

**PICOTT Criteria:**
- Population: ${criteria.population || 'Not specified'}
- Intervention: ${criteria.intervention || 'Not specified'}
- Comparator: ${criteria.comparison || 'Not specified'}
- Outcome: ${criteria.outcome || 'Not specified'}
- Timeframe: ${criteria.timeframe || 'Not specified'}
- Study Types: ${criteria.studyTypes || 'Not specified'}

**Inclusion Criteria:**
- Language: ${criteria.inclusionLanguage || 'Not specified'}
- Publication: ${criteria.inclusionPublication || 'Not specified'}
- Sample Size: ${criteria.inclusionSampleSize || 'Not specified'}
- Data Availability: ${criteria.inclusionDataAvailability || 'Not specified'}
- Other: ${criteria.otherInclusion || 'Not specified'}

**Exclusion Criteria:**
- Study Types: ${criteria.exclusionStudyTypes || 'Not specified'}
- Populations: ${criteria.exclusionPopulations || 'Not specified'}
- Interventions: ${criteria.exclusionInterventions || 'Not specified'}
- Languages: ${criteria.exclusionLanguages || 'Not specified'}
- Other: ${criteria.otherExclusion || 'Not specified'}

**Citation to evaluate:**
Title: ${citation.title || 'Not provided'}
Authors: ${citation.authors || 'Not provided'}
Journal: ${citation.journal || 'Not provided'}
Year: ${citation.year || 'Not provided'}
${citation.doi ? `DOI: ${citation.doi}` : ''}
${citation.pmid ? `PMID: ${citation.pmid}` : ''}
Abstract: ${citation.abstract || 'Not provided'}

**Your approach:** ${approach}

**IMPORTANT INSTRUCTIONS:**
1. Carefully evaluate if the citation matches the PICOTT criteria
2. Consider both inclusion and exclusion criteria
3. Provide specific evidence from the abstract to support your decision
4. Be thorough in your reasoning

Respond with ONLY a valid JSON object (no markdown formatting, no code blocks, no additional text) in this EXACT format:

{
  "decision": "include",
  "confidence": 85,
  "reasoning": "Detailed explanation of your decision with specific references to the abstract",
  "pico_matches": {
    "population": true,
    "intervention": true,
    "comparator": false,
    "outcome": true,
    "timeframe": true,
    "study_type": true
  },
  "quality_score": 75,
  "evidence_quotes": ["Relevant quote 1 from abstract", "Relevant quote 2 from abstract"]
}

The decision must be exactly one of: "include", "exclude", or "uncertain"
The confidence must be a number between 0 and 100
The quality_score must be a number between 0 and 100`;
  };

  // Call OpenAI API
  const callOpenAI = async (prompt, model, temperature, retries = 0) => {
    try {
      const response = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${apiKeys.openai}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: model,
          messages: [{ role: "user", content: prompt }],
          temperature: temperature,
          max_tokens: 2000
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`OpenAI API error ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      const text = data.choices[0].message.content;
      
      // Clean up response
      const cleaned = text
        .replace(/```json\n?/g, '')
        .replace(/```\n?/g, '')
        .replace(/^[^{]*/, '')
        .replace(/[^}]*$/, '')
        .trim();
      
      return JSON.parse(cleaned);
    } catch (error) {
      if (retries < modelConfig.maxRetries) {
        addLog(`OpenAI API error, retrying (${retries + 1}/${modelConfig.maxRetries})...`, 'warning');
        await new Promise(resolve => setTimeout(resolve, modelConfig.rateLimitDelay * (retries + 1)));
        return callOpenAI(prompt, model, temperature, retries + 1);
      }
      throw error;
    }
  };

  // Call Anthropic API
  const callAnthropic = async (prompt, model, temperature, retries = 0) => {
    try {
      const response = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "x-api-key": apiKeys.anthropic,
          "Content-Type": "application/json",
          "anthropic-version": "2023-06-01"
        },
        body: JSON.stringify({
          model: model,
          max_tokens: 2000,
          temperature: temperature,
          messages: [{ role: "user", content: prompt }]
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Anthropic API error ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      const text = data.content[0].text;
      
      // Clean up response
      const cleaned = text
        .replace(/```json\n?/g, '')
        .replace(/```\n?/g, '')
        .replace(/^[^{]*/, '')
        .replace(/[^}]*$/, '')
        .trim();
      
      return JSON.parse(cleaned);
    } catch (error) {
      if (retries < modelConfig.maxRetries) {
        addLog(`Anthropic API error, retrying (${retries + 1}/${modelConfig.maxRetries})...`, 'warning');
        await new Promise(resolve => setTimeout(resolve, modelConfig.rateLimitDelay * (retries + 1)));
        return callAnthropic(prompt, model, temperature, retries + 1);
      }
      throw error;
    }
  };

  // Evaluate with single LLM
  const evaluateSingleLLM = async (citation, strategy) => {
    const startTime = Date.now();
    const prompt = createPrompt(citation, strategy);
    
    const isConservative = strategy === 'conservative';
    const provider = isConservative ? modelConfig.conservativeProvider : modelConfig.liberalProvider;
    const model = isConservative ? modelConfig.conservativeModel : modelConfig.liberalModel;
    const temperature = isConservative ? modelConfig.conservativeTemp : modelConfig.liberalTemp;
    
    try {
      let result;
      if (provider === 'openai') {
        result = await callOpenAI(prompt, model, temperature);
      } else {
        result = await callAnthropic(prompt, model, temperature);
      }
      
      const processingTime = (Date.now() - startTime) / 1000;
      
      return {
        ...result,
        model: model,
        provider: provider,
        strategy: strategy,
        processingTime: processingTime,
        error: null
      };
    } catch (error) {
      const processingTime = (Date.now() - startTime) / 1000;
      addLog(`Error in ${strategy} evaluation: ${error.message}`, 'error');
      
      return {
        decision: 'uncertain',
        confidence: 0,
        reasoning: `Error during evaluation: ${error.message}`,
        pico_matches: {},
        quality_score: 0,
        evidence_quotes: [],
        model: model,
        provider: provider,
        strategy: strategy,
        processingTime: processingTime,
        error: error.message
      };
    }
  };

  // Evaluate single citation with both models
  const evaluateCitation = async (citation) => {
    const startTime = Date.now();
    
    addLog(`Evaluating: ${citation.title.substring(0, 60)}...`, 'info');
    
    try {
      // Run both evaluations in parallel
      const [conservativeResult, liberalResult] = await Promise.all([
        evaluateSingleLLM(citation, 'conservative'),
        evaluateSingleLLM(citation, 'liberal')
      ]);
      
      // Analyze results and determine final decision
      const analysis = analyzeResults(conservativeResult, liberalResult);
      
      const totalTime = (Date.now() - startTime) / 1000;
      
      return {
        citationId: citation.id,
        citation: citation,
        conservative: conservativeResult,
        liberal: liberalResult,
        ...analysis,
        totalProcessingTime: totalTime,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      const totalTime = (Date.now() - startTime) / 1000;
      addLog(`Critical error evaluating citation: ${error.message}`, 'error');
      
      return {
        citationId: citation.id,
        citation: citation,
        conservative: { decision: 'uncertain', confidence: 0, reasoning: error.message, error: error.message },
        liberal: { decision: 'uncertain', confidence: 0, reasoning: error.message, error: error.message },
        finalDecision: 'uncertain',
        confidenceScore: 0,
        conflict: true,
        humanReview: true,
        totalProcessingTime: totalTime,
        timestamp: new Date().toISOString(),
        error: error.message
      };
    }
  };

  // Analyze results from both LLMs
  const analyzeResults = (conservative, liberal) => {
    // Handle errors
    if (conservative.error || liberal.error) {
      return {
        finalDecision: 'uncertain',
        confidenceScore: 0,
        conflict: true,
        humanReview: true,
        analysisNote: 'Error in one or both evaluations'
      };
    }
    
    // Check for agreement
    if (conservative.decision === liberal.decision) {
      const avgConfidence = (conservative.confidence + liberal.confidence) / 2;
      return {
        finalDecision: conservative.decision,
        confidenceScore: avgConfidence,
        conflict: false,
        humanReview: avgConfidence < 70, // Low confidence needs review
        analysisNote: 'Both models agree'
      };
    }
    
    // Disagreement detected
    const conflict = true;
    
    // If one is uncertain
    if (conservative.decision === 'uncertain' || liberal.decision === 'uncertain') {
      if (conservative.decision !== 'uncertain') {
        return {
          finalDecision: conservative.decision,
          confidenceScore: conservative.confidence * 0.8,
          conflict: conflict,
          humanReview: true,
          analysisNote: 'Liberal model uncertain, using conservative decision'
        };
      } else {
        return {
          finalDecision: liberal.decision,
          confidenceScore: liberal.confidence * 0.8,
          conflict: conflict,
          humanReview: true,
          analysisNote: 'Conservative model uncertain, using liberal decision'
        };
      }
    }
    
    // Direct conflict (include vs exclude)
    // Conservative approach: if conservative says include, include it
    if (conservative.decision === 'include') {
      return {
        finalDecision: 'include',
        confidenceScore: conservative.confidence * 0.7,
        conflict: conflict,
        humanReview: true,
        analysisNote: 'Conflict resolved: Conservative model prefers inclusion'
      };
    } else {
      // Both have strong opinions but disagree
      return {
        finalDecision: 'uncertain',
        confidenceScore: 50,
        conflict: conflict,
        humanReview: true,
        analysisNote: 'Strong disagreement between models'
      };
    }
  };

  // Process all citations
  const processAllCitations = async () => {
    if (citations.length === 0) {
      addLog('No citations to process', 'warning');
      return;
    }

    if (!criteria.researchQuestion || !criteria.population || !criteria.intervention || !criteria.outcome) {
      addLog('Please complete the minimum required criteria (Research Question, Population, Intervention, Outcome)', 'warning');
      return;
    }

    setIsProcessing(true);
    setResults([]);
    setCurrentIndex(0);
    setSessionStartTime(Date.now());
    addLog(`Starting dual LLM screening of ${citations.length} citations...`, 'success');
    addLog(`Conservative: ${modelConfig.conservativeProvider} (${modelConfig.conservativeModel})`, 'info');
    addLog(`Liberal: ${modelConfig.liberalProvider} (${modelConfig.liberalModel})`, 'info');

    const allResults = [];

    for (let i = 0; i < citations.length && isProcessing; i++) {
      setCurrentIndex(i);
      
      const result = await evaluateCitation(citations[i]);
      allResults.push(result);
      setResults([...allResults]);
      
      // Update stats
      updateStatistics(allResults);
      
      addLog(`Completed ${i + 1}/${citations.length}: ${result.finalDecision.toUpperCase()} (${result.confidenceScore.toFixed(0)}%)`, 
        result.finalDecision === 'include' ? 'success' : result.finalDecision === 'exclude' ? 'info' : 'warning');
      
      // Rate limiting delay between citations
      if (i < citations.length - 1) {
        await new Promise(resolve => setTimeout(resolve, modelConfig.rateLimitDelay));
      }
    }

    setIsProcessing(false);
    const duration = ((Date.now() - sessionStartTime) / 1000 / 60).toFixed(1);
    addLog(`Screening complete! Processed ${allResults.length} citations in ${duration} minutes.`, 'success');
  };

  // Update statistics
  const updateStatistics = (results) => {
    if (results.length === 0) return;
    
    const newStats = {
      total: results.length,
      included: results.filter(r => r.finalDecision === 'include').length,
      excluded: results.filter(r => r.finalDecision === 'exclude').length,
      uncertain: results.filter(r => r.finalDecision === 'uncertain').length,
      conflicts: results.filter(r => r.conflict).length,
      humanReview: results.filter(r => r.humanReview).length,
      avgConfidence: results.reduce((sum, r) => sum + r.confidenceScore, 0) / results.length,
      avgTime: results.reduce((sum, r) => sum + r.totalProcessingTime, 0) / results.length,
      errors: results.filter(r => r.error || r.conservative.error || r.liberal.error).length
    };
    
    setStats(newStats);
  };

  // Export results
  const exportResults = () => {
    const exportData = {
      metadata: {
        exportDate: new Date().toISOString(),
        totalCitations: citations.length,
        processedCitations: results.length,
        sessionDuration: sessionStartTime ? ((Date.now() - sessionStartTime) / 1000 / 60).toFixed(1) + ' minutes' : 'N/A',
        modelConfig: modelConfig
      },
      criteria: criteria,
      statistics: stats,
      citations: citations,
      results: results.map(r => ({
        ...r,
        citation: {
          id: r.citation.id,
          title: r.citation.title,
          authors: r.citation.authors,
          journal: r.citation.journal,
          year: r.citation.year,
          doi: r.citation.doi,
          pmid: r.citation.pmid
        }
      }))
    };
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dual_llm_screening_${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    
    addLog('Results exported successfully', 'success');
  };

  // Export to CSV for PRISMA
  const exportToCSV = () => {
    const headers = [
      'Citation ID', 'Title', 'Authors', 'Year', 'Journal', 
      'Final Decision', 'Confidence', 'Conflict', 'Human Review',
      'Conservative Decision', 'Conservative Confidence', 
      'Liberal Decision', 'Liberal Confidence',
      'Processing Time (s)'
    ];
    
    const rows = results.map(r => [
      r.citationId,
      r.citation.title,
      r.citation.authors,
      r.citation.year,
      r.citation.journal,
      r.finalDecision,
      r.confidenceScore.toFixed(1),
      r.conflict ? 'Yes' : 'No',
      r.humanReview ? 'Yes' : 'No',
      r.conservative.decision,
      r.conservative.confidence,
      r.liberal.decision,
      r.liberal.confidence,
      r.totalProcessingTime.toFixed(2)
    ]);
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `screening_results_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    
    addLog('CSV exported successfully', 'success');
  };

  // Get decision badge color
  const getDecisionColor = (decision) => {
    switch (decision) {
      case 'include': return 'bg-green-600 hover:bg-green-700';
      case 'exclude': return 'bg-red-600 hover:bg-red-700';
      case 'uncertain': return 'bg-yellow-600 hover:bg-yellow-700';
      default: return 'bg-gray-600 hover:bg-gray-700';
    }
  };

  // Filter results
  const filteredResults = results.filter(r => {
    if (selectedFilter === 'all') return true;
    if (selectedFilter === 'conflicts') return r.conflict;
    if (selectedFilter === 'review') return r.humanReview;
    return r.finalDecision === selectedFilter;
  });

  // Load sample data
  const loadSampleData = () => {
    const sampleCitations = [
      {
        id: 'sample_1',
        title: 'Surgical decompression for space-occupying cerebellar infarction: a systematic review and meta-analysis',
        authors: 'Smith J, Johnson K, Williams R, Brown A',
        journal: 'Neurosurgery',
        year: '2023',
        doi: '10.1093/neuros/xyz123',
        pmid: '12345678',
        abstract: 'Background: Space-occupying cerebellar infarction can lead to fatal brainstem compression. Suboccipital decompressive craniectomy (SDC) is performed to relieve pressure, but optimal timing and patient selection remain unclear. Methods: We conducted a systematic review of studies reporting outcomes after SDC for cerebellar infarction. We searched PubMed, Embase, and Cochrane databases from 1990-2023. Primary outcome was mortality at hospital discharge. Secondary outcomes included modified Rankin Scale (mRS) scores at 3 months. Results: We identified 45 studies including 823 patients. Overall mortality was 22% (95% CI: 18-26%). Favorable outcomes (mRS 0-3) were achieved in 60% of survivors. Early surgery (<24 hours) was associated with lower mortality (OR 0.45, 95% CI: 0.28-0.72, p<0.001). Complications included CSF leak (8%), wound infection (5%), and rebleeding (3%). Conclusion: SDC appears to improve outcomes in carefully selected patients with space-occupying cerebellar infarction, particularly when performed early. Further prospective studies are needed to refine patient selection criteria.'
      },
      {
        id: 'sample_2',
        title: 'Medical management and outcomes of acute ischemic stroke: a comprehensive review',
        authors: 'Brown A, Davis M, Wilson T',
        journal: 'Stroke',
        year: '2022',
        doi: '10.1161/STROKEAHA.122.123456',
        pmid: '87654321',
        abstract: 'This comprehensive review discusses current medical management strategies for acute ischemic stroke including thrombolysis, thrombectomy, and supportive care. We review the evidence for blood pressure management, antiplatelet therapy, and neuroprotective strategies. No surgical interventions were discussed. The focus is entirely on pharmacological and endovascular approaches to acute stroke care.'
      },
      {
        id: 'sample_3',
        title: 'Outcomes following cerebellar stroke in elderly patients: a single-center retrospective study',
        authors: 'Martinez L, Garcia P, Rodriguez M',
        journal: 'Journal of Stroke and Cerebrovascular Diseases',
        year: '2021',
        doi: '10.1016/j.jstrokecerebrovasdis.2021.123456',
        abstract: 'We retrospectively reviewed outcomes in 156 elderly patients (>65 years) with cerebellar stroke at our institution. Most patients (89%) were managed conservatively. Fifteen patients developed malignant edema requiring intervention. Eight underwent ventriculostomy placement only, while seven had suboccipital decompression. Mortality in the surgical group was 28% compared to 12% in the medically managed group. Mean age in surgical patients was 71±6 years. The study suggests that elderly patients with cerebellar infarction can often be managed conservatively, with surgery reserved for those developing significant mass effect.'
      }
    ];
    
    const sampleCriteria = {
      researchQuestion: 'What is the efficacy and safety of suboccipital decompressive craniectomy for space-occupying cerebellar infarction?',
      population: 'Adult patients (≥18 years) with space-occupying cerebellar infarction causing mass effect or brainstem compression',
      intervention: 'Suboccipital decompressive craniectomy (SDC) or posterior fossa decompression with or without duraplasty',
      comparison: 'Conservative medical management, ventriculostomy alone, or no treatment',
      outcome: 'Primary: Mortality at hospital discharge or 30 days. Secondary: Modified Rankin Scale (mRS) scores, Glasgow Outcome Scale (GOS), complications (infection, CSF leak, rebleeding), length of hospital stay',
      timeframe: '1990-2024',
      studyTypes: 'Randomized controlled trials, cohort studies, case-control studies, case series with ≥5 patients',
      inclusionLanguage: 'English, Portuguese, Spanish, French, German',
      inclusionPublication: 'Peer-reviewed journal articles, conference abstracts with sufficient data',
      inclusionSampleSize: 'Case series must include ≥5 patients',
      exclusionStudyTypes: 'Case reports (<5 patients), editorials, commentaries, reviews without original data',
      exclusionPopulations: 'Pediatric patients (<18 years), traumatic cerebellar injury, tumor-related cerebellar lesions',
      exclusionInterventions: 'Ventriculostomy alone without decompression',
      exclusionLanguages: 'Languages not listed in inclusion criteria without English abstract'
    };
    
    setCitations(sampleCitations);
    setCriteria(sampleCriteria);
    addLog(`Loaded ${sampleCitations.length} sample citations and criteria template`, 'success');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 p-4">
      <div className="max-w-7xl mx-auto space-y-4">
        {/* Header */}
        <Card className="border-t-4 border-t-blue-600 shadow-lg">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileText className="w-10 h-10 text-blue-600" />
                <div>
                  <CardTitle className="text-3xl">Dual LLM Screening Tool v3.0</CardTitle>
                  <CardDescription className="text-base">
                    AI-powered systematic review citation screening with dual evaluation strategies
                  </CardDescription>
                </div>
              </div>
              {sessionStartTime && (
                <div className="text-right">
                  <div className="text-sm text-slate-600">Session Time</div>
                  <div className="text-2xl font-bold text-blue-600">
                    {Math.floor((Date.now() - sessionStartTime) / 1000 / 60)}m
                  </div>
                </div>
              )}
            </div>
          </CardHeader>
        </Card>

        {/* Statistics Dashboard */}
        {results.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
            <Card className="hover:shadow-md transition-shadow">
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-3xl font-bold text-slate-800">{stats.total}</div>
                    <div className="text-xs text-slate-600 flex items-center gap-1">
                      <FileText className="w-3 h-3" />
                      Total
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="hover:shadow-md transition-shadow">
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-3xl font-bold text-green-600">{stats.included}</div>
                    <div className="text-xs text-slate-600 flex items-center gap-1">
                      <CheckCircle className="w-3 h-3" />
                      Included
                    </div>
                  </div>
                  <div className="text-xs text-slate-500">{((stats.included/stats.total)*100).toFixed(0)}%</div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="hover:shadow-md transition-shadow">
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-3xl font-bold text-red-600">{stats.excluded}</div>
                    <div className="text-xs text-slate-600 flex items-center gap-1">
                      <XCircle className="w-3 h-3" />
                      Excluded
                    </div>
                  </div>
                  <div className="text-xs text-slate-500">{((stats.excluded/stats.total)*100).toFixed(0)}%</div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="hover:shadow-md transition-shadow">
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-3xl font-bold text-yellow-600">{stats.uncertain}</div>
                    <div className="text-xs text-slate-600 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      Uncertain
                    </div>
                  </div>
                  <div className="text-xs text-slate-500">{((stats.uncertain/stats.total)*100).toFixed(0)}%</div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="hover:shadow-md transition-shadow">
              <CardContent className="pt-4">
                <div>
                  <div className="text-3xl font-bold text-orange-600">{stats.conflicts}</div>
                  <div className="text-xs text-slate-600 flex items-center gap-1">
                    <Activity className="w-3 h-3" />
                    Conflicts
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="hover:shadow-md transition-shadow">
              <CardContent className="pt-4">
                <div>
                  <div className="text-3xl font-bold text-purple-600">{stats.humanReview}</div>
                  <div className="text-xs text-slate-600 flex items-center gap-1">
                    <Users className="w-3 h-3" />
                    Review
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="hover:shadow-md transition-shadow">
              <CardContent className="pt-4">
                <div>
                  <div className="text-3xl font-bold text-blue-600">{stats.avgConfidence.toFixed(0)}%</div>
                  <div className="text-xs text-slate-600 flex items-center gap-1">
                    <TrendingUp className="w-3 h-3" />
                    Avg Conf.
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="hover:shadow-md transition-shadow">
              <CardContent className="pt-4">
                <div>
                  <div className="text-3xl font-bold text-indigo-600">{stats.avgTime.toFixed(1)}s</div>
                  <div className="text-xs text-slate-600 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    Avg Time
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Main Tabs */}
        <Tabs defaultValue="criteria" className="w-full">
          <TabsList className="grid w-full grid-cols-6 h-auto">
            <TabsTrigger value="config" className="flex flex-col items-center gap-1 py-2">
              <Settings className="w-4 h-4" />
              <span className="text-xs">Config</span>
            </TabsTrigger>
            <TabsTrigger value="criteria" className="flex flex-col items-center gap-1 py-2">
              <FileText className="w-4 h-4" />
              <span className="text-xs">Criteria</span>
            </TabsTrigger>
            <TabsTrigger value="citations" className="flex flex-col items-center gap-1 py-2">
              <Upload className="w-4 h-4" />
              <span className="text-xs">Citations ({citations.length})</span>
            </TabsTrigger>
            <TabsTrigger value="screening" className="flex flex-col items-center gap-1 py-2">
              <Play className="w-4 h-4" />
              <span className="text-xs">Screening</span>
            </TabsTrigger>
            <TabsTrigger value="results" className="flex flex-col items-center gap-1 py-2">
              <BarChart3 className="w-4 h-4" />
              <span className="text-xs">Results ({results.length})</span>
            </TabsTrigger>
            <TabsTrigger value="logs" className="flex flex-col items-center gap-1 py-2">
              <Activity className="w-4 h-4" />
              <span className="text-xs">Logs</span>
            </TabsTrigger>
          </TabsList>

          {/* Configuration Tab */}
          <TabsContent value="config">
            <Card>
              <CardHeader>
                <CardTitle>Model Configuration</CardTitle>
                <CardDescription>Configure API keys and model settings for dual evaluation</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <Alert>
                  <AlertDescription>
                    <strong>Dual Strategy Approach:</strong> This tool uses two AI models with different evaluation strategies:
                    <ul className="list-disc list-inside mt-2 space-y-1 text-sm">
                      <li><strong>Conservative Strategy:</strong> Prefers inclusion to minimize false negatives (missing relevant studies)</li>
                      <li><strong>Liberal Strategy:</strong> Balances efficiency with thoroughness for practical screening</li>
                    </ul>
                  </AlertDescription>
                </Alert>

                <div className="grid md:grid-cols-2 gap-6">
                  {/* Conservative Model Config */}
                  <div className="p-4 border-2 border-blue-200 rounded-lg bg-blue-50">
                    <h3 className="font-semibold text-lg mb-3 text-blue-900">Conservative Model (Dr. Chen)</h3>
                    
                    <div className="space-y-3">
                      <div>
                        <Label>Provider</Label>
                        <Select value={modelConfig.conservativeProvider} onValueChange={(v) => setModelConfig({...modelConfig, conservativeProvider: v})}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="anthropic">Anthropic</SelectItem>
                            <SelectItem value="openai">OpenAI</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      
                      <div>
                        <Label>Model</Label>
                        <Select value={modelConfig.conservativeModel} onValueChange={(v) => setModelConfig({...modelConfig, conservativeModel: v})}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {modelConfig.conservativeProvider === 'anthropic' ? (
                              <>
                                <SelectItem value="claude-sonnet-4-20250514">Claude Sonnet 4</SelectItem>
                                <SelectItem value="claude-opus-4-20250514">Claude Opus 4</SelectItem>
                              </>
                            ) : (
                              <>
                                <SelectItem value="gpt-4">GPT-4</SelectItem>
                                <SelectItem value="gpt-4-turbo">GPT-4 Turbo</SelectItem>
                                <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                              </>
                            )}
                          </SelectContent>
                        </Select>
                      </div>
                      
                      <div>
                        <Label>Temperature: {modelConfig.conservativeTemp}</Label>
                        <Input
                          type="range"
                          min="0"
                          max="1"
                          step="0.1"
                          value={modelConfig.conservativeTemp}
                          onChange={(e) => setModelConfig({...modelConfig, conservativeTemp: parseFloat(e.target.value)})}
                          className="mt-1"
                        />
                        <p className="text-xs text-slate-600 mt-1">Lower = more deterministic</p>
                      </div>
                    </div>
                  </div>

                  {/* Liberal Model Config */}
                  <div className="p-4 border-2 border-green-200 rounded-lg bg-green-50">
                    <h3 className="font-semibold text-lg mb-3 text-green-900">Liberal Model (Dr. Rodriguez)</h3>
                    
                    <div className="space-y-3">
                      <div>
                        <Label>Provider</Label>
                        <Select value={modelConfig.liberalProvider} onValueChange={(v) => setModelConfig({...modelConfig, liberalProvider: v})}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="openai">OpenAI</SelectItem>
                            <SelectItem value="anthropic">Anthropic</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      
                      <div>
                        <Label>Model</Label>
                        <Select value={modelConfig.liberalModel} onValueChange={(v) => setModelConfig({...modelConfig, liberalModel: v})}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {modelConfig.liberalProvider === 'openai' ? (
                              <>
                                <SelectItem value="gpt-4">GPT-4</SelectItem>
                                <SelectItem value="gpt-4-turbo">GPT-4 Turbo</SelectItem>
                                <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                              </>
                            ) : (
                              <>
                                <SelectItem value="claude-sonnet-4-20250514">Claude Sonnet 4</SelectItem>
                                <SelectItem value="claude-opus-4-20250514">Claude Opus 4</SelectItem>
                              </>
                            )}
                          </SelectContent>
                        </Select>
                      </div>
                      
                      <div>
                        <Label>Temperature: {modelConfig.liberalTemp}</Label>
                        <Input
                          type="range"
                          min="0"
                          max="1"
                          step="0.1"
                          value={modelConfig.liberalTemp}
                          onChange={(e) => setModelConfig({...modelConfig, liberalTemp: parseFloat(e.target.value)})}
                          className="mt-1"
                        />
                        <p className="text-xs text-slate-600 mt-1">Higher = more creative</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Processing Settings */}
                <div className="grid md:grid-cols-3 gap-4 p-4 bg-slate-50 rounded-lg">
                  <div>
                    <Label>Max Retries</Label>
                    <Input
                      type="number"
                      min="1"
                      max="5"
                      value={modelConfig.maxRetries}
                      onChange={(e) => setModelConfig({...modelConfig, maxRetries: parseInt(e.target.value)})}
                    />
                  </div>
                  <div>
                    <Label>Rate Limit Delay (ms)</Label>
                    <Input
                      type="number"
                      min="500"
                      max="5000"
                      step="500"
                      value={modelConfig.rateLimitDelay}
                      onChange={(e) => setModelConfig({...modelConfig, rateLimitDelay: parseInt(e.target.value)})}
                    />
                  </div>
                  <div>
                    <Label>Batch Size</Label>
                    <Input
                      type="number"
                      min="1"
                      max="10"
                      value={modelConfig.batchSize}
                      onChange={(e) => setModelConfig({...modelConfig, batchSize: parseInt(e.target.value)})}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Criteria Tab */}
          <TabsContent value="criteria">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Screening Criteria (PICOTT)</CardTitle>
                    <CardDescription>Define your systematic review inclusion/exclusion criteria</CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={loadSampleData}>
                      <FolderOpen className="w-4 h-4 mr-2" />
                      Load Sample
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <p className="text-sm text-amber-900">
                    <strong>Tip:</strong> The more detailed and specific your criteria, the more accurate the AI screening will be. 
                    Fields marked with * are required for optimal performance.
                  </p>
                </div>

                <div>
                  <Label htmlFor="researchQuestion" className="text-base font-semibold">Research Question *</Label>
                  <Textarea
                    id="researchQuestion"
                    placeholder="What is the primary research question your systematic review aims to answer?"
                    value={criteria.researchQuestion}
                    onChange={(e) => setCriteria({...criteria, researchQuestion: e.target.value})}
                    className="min-h-[80px] mt-2"
                  />
                </div>
                
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="population" className="font-semibold">Population *</Label>
                    <Textarea
                      id="population"
                      placeholder="e.g., Adults (≥18 years) with space-occupying cerebellar infarction causing mass effect"
                      value={criteria.population}
                      onChange={(e) => setCriteria({...criteria, population: e.target.value})}
                      className="mt-2"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="intervention" className="font-semibold">Intervention *</Label>
                    <Textarea
                      id="intervention"
                      placeholder="e.g., Suboccipital decompressive craniectomy (SDC) with or without duraplasty"
                      value={criteria.intervention}
                      onChange={(e) => setCriteria({...criteria, intervention: e.target.value})}
                      className="mt-2"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="comparison">Comparator</Label>
                    <Textarea
                      id="comparison"
                      placeholder="e.g., Conservative medical management, ventriculostomy alone"
                      value={criteria.comparison}
                      onChange={(e) => setCriteria({...criteria, comparison: e.target.value})}
                      className="mt-2"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="outcome" className="font-semibold">Outcomes *</Label>
                    <Textarea
                      id="outcome"
                      placeholder="e.g., Mortality, mRS scores, complications, length of stay"
                      value={criteria.outcome}
                      onChange={(e) => setCriteria({...criteria, outcome: e.target.value})}
                      className="mt-2"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="timeframe">Timeframe</Label>
                    <Input
                      id="timeframe"
                      placeholder="e.g., 1990-2024"
                      value={criteria.timeframe}
                      onChange={(e) => setCriteria({...criteria, timeframe: e.target.value})}
                      className="mt-2"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="studyTypes">Study Types</Label>
                    <Input
                      id="studyTypes"
                      placeholder="e.g., RCTs, cohort studies, case series (≥5 patients)"
                      value={criteria.studyTypes}
                      onChange={(e) => setCriteria({...criteria, studyTypes: e.target.value})}
                      className="mt-2"
                    />
                  </div>
                </div>

                <div className="border-t pt-4">
                  <h3 className="font-semibold text-lg mb-3">Inclusion Criteria</h3>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="inclusionLanguage">Languages</Label>
                      <Input
                        id="inclusionLanguage"
                        placeholder="e.g., English, Portuguese, Spanish"
                        value={criteria.inclusionLanguage}
                        onChange={(e) => setCriteria({...criteria, inclusionLanguage: e.target.value})}
                        className="mt-2"
                      />
                    </div>
                    
                    <div>
                      <Label htmlFor="inclusionPublication">Publication Types</Label>
                      <Input
                        id="inclusionPublication"
                        placeholder="e.g., Peer-reviewed articles, conference abstracts"
                        value={criteria.inclusionPublication}
                        onChange={(e) => setCriteria({...criteria, inclusionPublication: e.target.value})}
                        className="mt-2"
                      />
                    </div>
                    
                    <div>
                      <Label htmlFor="inclusionSampleSize">Sample Size</Label>
                      <Input
                        id="inclusionSampleSize"
                        placeholder="e.g., Case series ≥5 patients"
                        value={criteria.inclusionSampleSize}
                        onChange={(e) => setCriteria({...criteria, inclusionSampleSize: e.target.value})}
                        className="mt-2"
                      />
                    </div>
                    
                    <div>
                      <Label htmlFor="otherInclusion">Other Inclusion Criteria</Label>
                      <Input
                        id="otherInclusion"
                        placeholder="Any other inclusion criteria"
                        value={criteria.otherInclusion}
                        onChange={(e) => setCriteria({...criteria, otherInclusion: e.target.value})}
                        className="mt-2"
                      />
                    </div>
                  </div>
                </div>

                <div className="border-t pt-4">
                  <h3 className="font-semibold text-lg mb-3">Exclusion Criteria</h3>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="exclusionStudyTypes">Study Types</Label>
                      <Input
                        id="exclusionStudyTypes"
                        placeholder="e.g., Case reports (<5 patients), editorials, reviews"
                        value={criteria.exclusionStudyTypes}
                        onChange={(e) => setCriteria({...criteria, exclusionStudyTypes: e.target.value})}
                        className="mt-2"
                      />
                    </div>
                    
                    <div>
                      <Label htmlFor="exclusionPopulations">Populations</Label>
                      <Input
                        id="exclusionPopulations"
                        placeholder="e.g., Pediatric patients, traumatic injury"
                        value={criteria.exclusionPopulations}
                        onChange={(e) => setCriteria({...criteria, exclusionPopulations: e.target.value})}
                        className="mt-2"
                      />
                    </div>
                    
                    <div>
                      <Label htmlFor="exclusionInterventions">Interventions</Label>
                      <Input
                        id="exclusionInterventions"
                        placeholder="e.g., Ventriculostomy alone without decompression"
                        value={criteria.exclusionInterventions}
                        onChange={(e) => setCriteria({...criteria, exclusionInterventions: e.target.value})}
                        className="mt-2"
                      />
                    </div>
                    
                    <div>
                      <Label htmlFor="exclusionLanguages">Languages</Label>
                      <Input
                        id="exclusionLanguages"
                        placeholder="e.g., Languages without English abstract"
                        value={criteria.exclusionLanguages}
                        onChange={(e) => setCriteria({...criteria, exclusionLanguages: e.target.value})}
                        className="mt-2"
                      />
                    </div>
                    
                    <div className="md:col-span-2">
                      <Label htmlFor="otherExclusion">Other Exclusion Criteria</Label>
                      <Textarea
                        id="otherExclusion"
                        placeholder="Any other exclusion criteria"
                        value={criteria.otherExclusion}
                        onChange={(e) => setCriteria({...criteria, otherExclusion: e.target.value})}
                        className="mt-2"
                      />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Citations Tab */}
          <TabsContent value="citations">
            <Card>
              <CardHeader>
                <CardTitle>Upload Citations</CardTitle>
                <CardDescription>Upload or paste citations for screening (supports .txt, .json formats)</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2 flex-wrap">
                  <Button
                    onClick={() => document.getElementById('fileInput').click()}
                    className="flex items-center gap-2"
                  >
                    <Upload className="w-4 h-4" />
                    Upload File
                  </Button>
                  <input
                    id="fileInput"
                    type="file"
                    accept=".txt,.json"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                  <Button
                    variant="outline"
                    onClick={loadSampleData}
                  >
                    Load Sample Data
                  </Button>
                  {citations.length > 0 && (
                    <Button
                      variant="outline"
                      onClick={() => {
                        setCitations([]);
                        addLog('Citations cleared', 'info');
                      }}
                    >
                      Clear All
                    </Button>
                  )}
                </div>

                <Alert>
                  <AlertDescription>
                    <strong>Format:</strong> Upload a text file with citations in the following format:
                    <pre className="mt-2 text-xs bg-slate-100 p-2 rounded overflow-x-auto">
Title: Study title here{'\n'}
Authors: Author names{'\n'}
Journal: Journal name{'\n'}
Year: 2024{'\n'}
Abstract: Abstract text here{'\n'}
{'\n'}
Title: Next citation...
                    </pre>
                  </AlertDescription>
                </Alert>

                {citations.length > 0 && (
                  <div>
                    <div className="mb-3 flex items-center justify-between">
                      <span className="font-semibold text-lg">Loaded Citations: {citations.length}</span>
                      <Badge variant="outline" className="text-sm">
                        {citations.length} citations ready for screening
                      </Badge>
                    </div>
                    <ScrollArea className="h-[500px] rounded-md border p-4">
                      <div className="space-y-3">
                        {citations.map((citation, idx) => (
                          <Card key={citation.id} className="hover:shadow-md transition-shadow">
                            <CardHeader className="pb-2">
                              <div className="flex items-start justify-between">
                                <CardTitle className="text-sm leading-tight">
                                  {idx + 1}. {citation.title || 'Untitled'}
                                </CardTitle>
                                <Badge variant="outline" className="ml-2 shrink-0">
                                  {citation.year}
                                </Badge>
                              </div>
                              <CardDescription className="text-xs">
                                {citation.authors} • {citation.journal}
                                {citation.doi && ` • DOI: ${citation.doi}`}
                              </CardDescription>
                            </CardHeader>
                            <CardContent>
                              <p className="text-xs text-slate-600 line-clamp-4">
                                {citation.abstract || 'No abstract available'}
                              </p>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    </ScrollArea>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Screening Tab */}
          <TabsContent value="screening">
            <Card>
              <CardHeader>
                <CardTitle>Run Screening</CardTitle>
                <CardDescription>Execute dual LLM evaluation on your citations</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Alert className="border-blue-200 bg-blue-50">
                  <AlertDescription>
                    <div className="space-y-2">
                      <p className="font-semibold text-blue-900">How it works:</p>
                      <ol className="list-decimal list-inside space-y-1 text-sm text-blue-800">
                        <li>Each citation is evaluated independently by two AI models</li>
                        <li><strong>Conservative Model:</strong> Uses {modelConfig.conservativeProvider} ({modelConfig.conservativeModel}) - prefers inclusion when uncertain</li>
                        <li><strong>Liberal Model:</strong> Uses {modelConfig.liberalProvider} ({modelConfig.liberalModel}) - balances thoroughness with efficiency</li>
                        <li>Results are compared and conflicts are flagged for human review</li>
                        <li>Final decisions prioritize the conservative approach to minimize false negatives</li>
                      </ol>
                    </div>
                  </AlertDescription>
                </Alert>

                {isProcessing && (
                  <div className="space-y-3 p-4 bg-slate-50 rounded-lg">
                    <div className="flex justify-between items-center">
                      <span className="font-semibold">Processing citation {currentIndex + 1} of {citations.length}</span>
                      <span className="text-sm text-slate-600">{Math.round(((currentIndex + 1) / citations.length) * 100)}%</span>
                    </div>
                    <Progress value={((currentIndex + 1) / citations.length) * 100} className="h-3" />
                    {citations[currentIndex] && (
                      <p className="text-sm text-slate-600 truncate">
                        {citations[currentIndex].title}
                      </p>
                    )}
                    <div className="flex items-center gap-2 text-sm text-slate-600">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Evaluating with both models...
                    </div>
                  </div>
                )}

                <div className="flex gap-2 flex-wrap">
                  <Button
                    onClick={processAllCitations}
                    disabled={isProcessing || citations.length === 0 || !criteria.researchQuestion || !criteria.population || !criteria.intervention}
                    className="flex items-center gap-2"
                    size="lg"
                  >
                    {isProcessing ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <Play className="w-5 h-5" />
                        Start Screening
                      </>
                    )}
                  </Button>
                  
                  {isProcessing && (
                    <Button
                      variant="outline"
                      onClick={() => {
                        setIsProcessing(false);
                        addLog('Screening paused by user', 'warning');
                      }}
                      className="flex items-center gap-2"
                      size="lg"
                    >
                      <Pause className="w-5 h-5" />
                      Pause
                    </Button>
                  )}
                  
                  {results.length > 0 && !isProcessing && (
                    <>
                      <Button
                        variant="outline"
                        onClick={exportResults}
                        className="flex items-center gap-2"
                      >
                        <Download className="w-4 h-4" />
                        Export JSON
                      </Button>
                      <Button
                        variant="outline"
                        onClick={exportToCSV}
                        className="flex items-center gap-2"
                      >
                        <Download className="w-4 h-4" />
                        Export CSV
                      </Button>
                    </>
                  )}
                </div>

                {!criteria.researchQuestion || !criteria.population || !criteria.intervention ? (
                  <Alert variant="destructive">
                    <AlertDescription>
                      Please complete the minimum required criteria fields (Research Question, Population, Intervention, Outcome) before starting screening.
                    </AlertDescription>
                  </Alert>
                ) : citations.length === 0 ? (
                  <Alert variant="destructive">
                    <AlertDescription>
                      Please upload citations before starting screening.
                    </AlertDescription>
                  </Alert>
                ) : null}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Results Tab */}
          <TabsContent value="results">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Screening Results</CardTitle>
                    <CardDescription>Detailed results from dual LLM evaluation</CardDescription>
                  </div>
                  {results.length > 0 && (
                    <Select value={selectedFilter} onValueChange={setSelectedFilter}>
                      <SelectTrigger className="w-48">
                        <SelectValue placeholder="Filter results" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All ({results.length})</SelectItem>
                        <SelectItem value="include">Included ({results.filter(r => r.finalDecision === 'include').length})</SelectItem>
                        <SelectItem value="exclude">Excluded ({results.filter(r => r.finalDecision === 'exclude').length})</SelectItem>
                        <SelectItem value="uncertain">Uncertain ({results.filter(r => r.finalDecision === 'uncertain').length})</SelectItem>
                        <SelectItem value="conflicts">Conflicts ({results.filter(r => r.conflict).length})</SelectItem>
                        <SelectItem value="review">Needs Review ({results.filter(r => r.humanReview).length})</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                {results.length === 0 ? (
                  <Alert>
                    <AlertDescription>
                      No results yet. Run screening from the Screening tab to see results here.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <ScrollArea className="h-[700px]">
                    <div className="space-y-4">
                      {filteredResults.map((result, idx) => (
                        <Card key={result.citationId} className="hover:shadow-lg transition-shadow">
                          <CardHeader className="pb-3">
                            <div className="flex items-start justify-between gap-4">
                              <div className="flex-1 min-w-0">
                                <CardTitle className="text-base leading-tight">
                                  {results.indexOf(result) + 1}. {result.citation.title}
                                </CardTitle>
                                <CardDescription className="text-xs mt-1">
                                  {result.citation.authors} • {result.citation.journal} {result.citation.year}
                                  {result.citation.doi && ` • ${result.citation.doi}`}
                                </CardDescription>
                              </div>
                              <div className="flex flex-col items-end gap-1 shrink-0">
                                <Badge className={`${getDecisionColor(result.finalDecision)} text-white px-3 py-1`}>
                                  {result.finalDecision.toUpperCase()}
                                </Badge>
                                <span className="text-xs font-semibold text-slate-600">
                                  {result.confidenceScore.toFixed(0)}% confident
                                </span>
                                {result.conflict && (
                                  <Badge variant="outline" className="text-orange-600 border-orange-600 text-xs">
                                    <AlertTriangle className="w-3 h-3 mr-1" />
                                    Conflict
                                  </Badge>
                                )}
                                {result.humanReview && (
                                  <Badge variant="outline" className="text-purple-600 border-purple-600 text-xs">
                                    <Users className="w-3 h-3 mr-1" />
                                    Review Needed
                                  </Badge>
                                )}
                              </div>
                            </div>
                            {result.analysisNote && (
                              <p className="text-xs text-slate-600 italic mt-2">
                                {result.analysisNote}
                              </p>
                            )}
                          </CardHeader>
                          <CardContent>
                            <div className="grid md:grid-cols-2 gap-4">
                              {/* Conservative Result */}
                              <div className="border-2 border-blue-200 rounded-lg p-4 bg-gradient-to-br from-blue-50 to-white">
                                <div className="font-semibold text-sm mb-3 flex items-center gap-2 text-blue-900">
                                  <CheckCircle className="w-4 h-4" />
                                  Conservative (Dr. Chen)
                                  <Badge variant="outline" className="ml-auto text-xs">
                                    {result.conservative.provider}
                                  </Badge>
                                </div>
                                <div className="space-y-2">
                                  <div className="flex items-center justify-between text-sm">
                                    <span className="text-slate-600">Decision:</span>
                                    <Badge className={getDecisionColor(result.conservative.decision)}>
                                      {result.conservative.decision}
                                    </Badge>
                                  </div>
                                  <div className="flex items-center justify-between text-sm">
                                    <span className="text-slate-600">Confidence:</span>
                                    <span className="font-semibold">{result.conservative.confidence}%</span>
                                  </div>
                                  <div className="flex items-center justify-between text-sm">
                                    <span className="text-slate-600">Quality:</span>
                                    <span className="font-semibold">{result.conservative.quality_score}/100</span>
                                  </div>
                                  <div className="text-xs mt-3 p-3 bg-white rounded border">
                                    <strong className="text-slate-700">Reasoning:</strong>
                                    <p className="mt-2 text-slate-600 leading-relaxed">
                                      {result.conservative.reasoning}
                                    </p>
                                  </div>
                                  {result.conservative.evidence_quotes?.length > 0 && (
                                    <div className="text-xs mt-2">
                                      <strong className="text-slate-700">Evidence:</strong>
                                      <ul className="mt-1 space-y-1">
                                        {result.conservative.evidence_quotes.map((quote, i) => (
                                          <li key={i} className="text-slate-600 italic pl-2 border-l-2 border-blue-300">
                                            "{quote}"
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                  <div className="text-xs text-slate-500 mt-2 pt-2 border-t">
                                    Time: {result.conservative.processingTime?.toFixed(2)}s
                                  </div>
                                </div>
                              </div>

                              {/* Liberal Result */}
                              <div className="border-2 border-green-200 rounded-lg p-4 bg-gradient-to-br from-green-50 to-white">
                                <div className="font-semibold text-sm mb-3 flex items-center gap-2 text-green-900">
                                  <XCircle className="w-4 h-4" />
                                  Liberal (Dr. Rodriguez)
                                  <Badge variant="outline" className="ml-auto text-xs">
                                    {result.liberal.provider}
                                  </Badge>
                                </div>
                                <div className="space-y-2">
                                  <div className="flex items-center justify-between text-sm">
                                    <span className="text-slate-600">Decision:</span>
                                    <Badge className={getDecisionColor(result.liberal.decision)}>
                                      {result.liberal.decision}
                                    </Badge>
                                  </div>
                                  <div className="flex items-center justify-between text-sm">
                                    <span className="text-slate-600">Confidence:</span>
                                    <span className="font-semibold">{result.liberal.confidence}%</span>
                                  </div>
                                  <div className="flex items-center justify-between text-sm">
                                    <span className="text-slate-600">Quality:</span>
                                    <span className="font-semibold">{result.liberal.quality_score}/100</span>
                                  </div>
                                  <div className="text-xs mt-3 p-3 bg-white rounded border">
                                    <strong className="text-slate-700">Reasoning:</strong>
                                    <p className="mt-2 text-slate-600 leading-relaxed">
                                      {result.liberal.reasoning}
                                    </p>
                                  </div>
                                  {result.liberal.evidence_quotes?.length > 0 && (
                                    <div className="text-xs mt-2">
                                      <strong className="text-slate-700">Evidence:</strong>
                                      <ul className="mt-1 space-y-1">
                                        {result.liberal.evidence_quotes.map((quote, i) => (
                                          <li key={i} className="text-slate-600 italic pl-2 border-l-2 border-green-300">
                                            "{quote}"
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                  <div className="text-xs text-slate-500 mt-2 pt-2 border-t">
                                    Time: {result.liberal.processingTime?.toFixed(2)}s
                                  </div>
                                </div>
                              </div>
                            </div>

                            {/* Processing Info */}
                            <div className="mt-4 pt-4 border-t flex justify-between items-center text-xs text-slate-600">
                              <span>Total processing time: {result.totalProcessingTime.toFixed(2)}s</span>
                              <span>{new Date(result.timestamp).toLocaleString()}</span>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </ScrollArea>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Logs Tab */}
          <TabsContent value="logs">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Activity Log</CardTitle>
                    <CardDescription>Real-time screening process log ({logs.length} entries)</CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setLogs([]);
                      addLog('Log cleared', 'info');
                    }}
                  >
                    Clear Log
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[700px]">
                  {logs.length === 0 ? (
                    <Alert>
                      <AlertDescription>No activity yet. Start screening to see logs.</AlertDescription>
                    </Alert>
                  ) : (
                    <div className="space-y-2 font-mono">
                      {logs.map((log) => (
                        <div
                          key={log.id}
                          className={`p-3 rounded-lg text-sm ${
                            log.type === 'error' ? 'bg-red-50 text-red-700 border border-red-200' :
                            log.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' :
                            log.type === 'warning' ? 'bg-yellow-50 text-yellow-700 border border-yellow-200' :
                            'bg-slate-50 text-slate-700 border border-slate-200'
                          }`}
                        >
                          <span className="text-xs opacity-70">[{log.timestamp}]</span> {log.message}
                        </div>
                      ))}
                    </div>
                  )}
                </ScrollArea>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}