#!/usr/bin/env python3
"""
Smart Input Processor v2.0
==========================
Uses the 4k LLM model as the "brain" to analyze user inputs from workflow
and generate optimized search instructions for research_hunter_v2-4.py

The 4k model acts as an intelligent coordinator that:
1. Receives ALL user inputs from workflow form
2. Analyzes and understands user intent
3. Generates optimized search queries and instructions
4. Coordinates with 16k model for deep analysis
5. Ensures outputs match user selections exactly

This ensures NO manipulation - what user selects = what system produces
"""

import json
import re
import os
import subprocess
import time
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# LLM CONFIGURATION - 4k Model as Brain
# ─────────────────────────────────────────────────────────────────────────────
LLM_4K_MODEL = "qwen2.5vl:3b"  # Fast model for quick analysis
LLM_16K_MODEL = "qwen2.5vl-3b-16k"  # Long context for deep research

@dataclass
class UserInputAnalysis:
    """Complete analysis of user inputs by 4k model"""
    
    # Original inputs from workflow
    original_inputs: Dict[str, Any] = field(default_factory=dict)
    
    # 4k Model Analysis
    analyzed_intent: str = ""
    research_topic: str = ""
    research_questions: List[str] = field(default_factory=list)
    academic_field: str = ""
    study_type: str = ""
    paper_type_to_generate: str = ""
    
    # Optimized search parameters
    optimized_queries: List[str] = field(default_factory=list)
    search_keywords: List[str] = field(default_factory=list)
    excluded_keywords: List[str] = field(default_factory=list)
    year_range: tuple = (2000, 2026)
    languages: List[str] = field(default_factory=list)
    geographic_focus: str = ""
    
    # Platform selection based on inputs
    recommended_platforms: List[str] = field(default_factory=list)
    search_depth: str = "field"
    max_papers: int = 500
    
    # Output requirements
    required_formats: List[str] = field(default_factory=list)
    citation_style: str = "APA 7th"
    paper_structure: str = "IMRAD"
    
    # Instructions for 16k model
    instructions_for_16k: str = ""
    
    # Learning data
    learning_data: Dict[str, Any] = field(default_factory=dict)
    
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    model_used: str = LLM_4K_MODEL

class SmartInputProcessor:
    """
    The Brain of Research Hunter
    Uses 4k LLM to analyze user inputs and coordinate the entire research process
    """
    
    def __init__(self):
        self.memory_file = "academic_memory.json"
        self.learning_log = "learning_log.jsonl"
        self.prompt_history = []
        
        # Paper type to structure mapping
        self.paper_structures = {
            "empirical": "IMRAD",
            "qualitative": "Qualitative Structure",
            "mixed_methods": "Mixed Methods Structure",
            "systematic_review": "PRISMA Structure",
            "meta_analysis": "PRISMA + Effect Sizes",
            "scoping_review": "Scoping Review Structure",
            "narrative_review": "Narrative Synthesis",
            "integrative_review": "Integrative Structure",
            "experimental": "IMRAD with Intervention",
            "quasi_experimental": "Quasi-Experimental",
            "longitudinal": "Longitudinal IMRAD",
            "cross_sectional": "Cross-sectional IMRAD",
            "cohort": "Cohort Study Structure",
            "case_study": "Case Study Format",
            "phenomenological": "Phenomenology Format",
            "ethnographic": "Ethnography Format",
            "grounded_theory": "GT Structure",
            "action_research": "Action Research",
            "Delphi": "Delphi Study Format",
            "correlational": "Correlational IMRAD",
            "descriptive": "Descriptive Structure",
            "exploratory": "Exploratory IMRAD",
            "historical": "Historical Analysis",
            "comparative": "Comparative Structure",
            "evaluation": "Evaluation Framework",
            "policy_analysis": "Policy Analysis",
            "feasibility": "Feasibility Framework",
            "pilot": "Pilot Study Format",
            "validation": "Validation Study",
            "thesis_phd": "PhD Dissertation",
            "thesis_master": "Master's Thesis",
            "thesis_bachelor": "Bachelor's Thesis",
            "conference_paper": "Conference Format",
            "book_chapter": "Book Chapter",
            "technical_report": "Technical Report",
            "white_paper": "White Paper",
            "protocol": "Research Protocol",
            "proposal": "Research Proposal"
        }
        
        # Output format to file extension mapping
        self.output_mappings = {
            "all": ["docx", "pdf", "xlsx", "md", "txt", "json", "csv", "html"],
            "docx_scopus": ["docx"],
            "docx_standard": ["docx"],
            "docx_both": ["docx"],
            "pdf": ["pdf"],
            "excel_master": ["xlsx"],
            "excel_filtered": ["xlsx"],
            "excel_bibliography": ["xlsx"],
            "excel_analysis": ["xlsx"],
            "markdown": ["md"],
            "txt": ["txt"],
            "json": ["json"],
            "csv": ["csv"],
            "html": ["html"],
            "latex": ["tex"],
            "xml": ["xml"]
        }
        
        print("🧠 Smart Input Processor initialized")
        print(f"   Brain Model: {LLM_4K_MODEL}")
        print(f"   Deep Model: {LLM_16K_MODEL}")
    
    def call_llm_4k(self, system_prompt: str, user_prompt: str) -> str:
        """Call the 4k model for quick analysis"""
        try:
            # Use ollama to call the model
            cmd = [
                "ollama", "run", LLM_4K_MODEL,
                "--verbose", "false"
            ]
            
            full_prompt = f"""System: {system_prompt}

User Input: {user_prompt}

Provide your analysis in JSON format."""

            result = subprocess.run(
                cmd,
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"{{\"error\": \"Model call failed: {result.stderr}\"}}"
                
        except subprocess.TimeoutExpired:
            return '{"error": "Model timeout"}'
        except FileNotFoundError:
            return '{"error": "Ollama not installed"}'
        except Exception as e:
            return f'{{"error": "{str(e)}"}}'
    
    def call_llm_16k(self, system_prompt: str, user_prompt: str) -> str:
        """Call the 16k model for deep analysis"""
        try:
            cmd = ["ollama", "run", LLM_16K_MODEL]
            
            full_prompt = f"""System: {system_prompt}

{user_prompt}"""

            result = subprocess.run(
                cmd,
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=180
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"{{\"error\": \"Model call failed\"}}"
                
        except Exception as e:
            return f'{{"error": "{str(e)}"}}'
    
    def analyze_workflow_inputs(self, inputs: Dict[str, Any]) -> UserInputAnalysis:
        """
        MAIN FUNCTION: 4k model analyzes ALL user inputs from workflow
        Returns optimized analysis that guides the entire research process
        """
        
        print("\n" + "="*70)
        print("🧠 4K MODEL ANALYZING USER INPUTS...")
        print("="*70)
        
        # Store original inputs
        analysis = UserInputAnalysis()
        analysis.original_inputs = inputs
        
        # Build comprehensive input summary for 4k model
        input_summary = self._build_input_summary(inputs)
        
        # System prompt for 4k model - acts as intelligent coordinator
        system_prompt = """You are the BRAIN of Research Hunter v7.

Your job is to analyze ALL user inputs from the workflow form and create 
an OPTIMIZED research plan that will guide the search and output process.

You MUST:
1. Understand the user's ACTUAL research intent
2. Generate SPECIFIC search queries based on inputs
3. Select appropriate platforms based on study type
4. Determine what OUTPUT formats are needed
5. Create clear instructions for the search system

IMPORTANT RULES:
- What user SELECTS = What system PRODUCES (NO manipulation)
- If user selects systematic review, produce systematic review
- If user selects mixed methods, produce mixed methods structure
- If user selects DOCX+PDF, produce BOTH formats
- NEVER change user intent - only OPTIMIZE execution

Return your analysis in clean JSON format with these keys:
{
  "research_topic": "clarified research topic",
  "intent_summary": "what user wants to achieve",
  "optimized_queries": ["query 1", "query 2", "query 3"],
  "keywords": ["relevant", "keywords"],
  "excluded_terms": ["terms to exclude"],
  "recommended_platforms": ["platform1", "platform2"],
  "search_depth": "sample/quick/field/deep",
  "year_range": {"from": YYYY, "to": YYYY},
  "languages": ["en", "ar"],
  "paper_structure": "IMRAD/systematic/etc",
  "required_formats": ["docx", "pdf", "xlsx"],
  "output_instructions": "specific instructions for output generation"
}
"""
        
        # Call 4k model for analysis
        print("📡 Analyzing inputs with 4k model...")
        llm_response = self.call_llm_4k(system_prompt, input_summary)
        
        try:
            # Parse LLM response
            if "error" in llm_response:
                # Fallback to rule-based analysis
                print("⚠️ Using rule-based fallback analysis")
                analysis = self._rule_based_analysis(inputs)
            else:
                # Parse successful response
                parsed = json.loads(llm_response)
                analysis = self._parse_llm_analysis(parsed, inputs)
        except:
            print("⚠️ Parsing failed, using rule-based analysis")
            analysis = self._rule_based_analysis(inputs)
        
        # Generate instructions for 16k model
        analysis.instructions_for_16k = self._generate_16k_instructions(analysis)
        
        # Log learning data
        self._log_learning(analysis)
        
        # Update memory
        self._update_memory(analysis)
        
        print("\n✅ Analysis Complete!")
        print(f"   Topic: {analysis.research_topic}")
        print(f"   Queries: {len(analysis.optimized_queries)}")
        print(f"   Formats: {analysis.required_formats}")
        print(f"   Structure: {analysis.paper_structure}")
        
        return analysis
    
    def _build_input_summary(self, inputs: Dict[str, Any]) -> str:
        """Build a comprehensive summary of all user inputs"""
        summary_parts = []
        
        # Research Topic
        if inputs.get("title"):
            summary_parts.append(f"RESEARCH TOPIC: {inputs['title']}")
        
        # Research Questions
        rqs = []
        for i in range(1, 6):
            rq_key = f"rq{i}"
            if inputs.get(rq_key):
                rqs.append(f"RQ{i}: {inputs[rq_key]}")
        if rqs:
            summary_parts.append("\nRESEARCH QUESTIONS:\n" + "\n".join(rqs))
        
        # Academic Field
        if inputs.get("field"):
            summary_parts.append(f"\nACADEMIC FIELD: {inputs['field']}")
        
        # Study Type
        if inputs.get("study_type"):
            summary_parts.append(f"\nSTUDY TYPE: {inputs['study_type']}")
        
        # Paper to Generate
        if inputs.get("paper_type"):
            summary_parts.append(f"\nPAPER TO GENERATE: {inputs['paper_type']}")
        
        # Output Formats
        if inputs.get("output_format"):
            summary_parts.append(f"\nOUTPUT FORMAT: {inputs['output_format']}")
        
        # Year Range
        year_from = inputs.get("year_from", "all")
        year_to = inputs.get("year_to", "2026")
        summary_parts.append(f"\nYEAR RANGE: {year_from} to {year_to}")
        
        # Language
        if inputs.get("language"):
            summary_parts.append(f"\nLANGUAGE: {inputs['language']}")
        
        # Search Mode
        if inputs.get("mode"):
            summary_parts.append(f"\nSEARCH DEPTH: {inputs['mode']}")
        
        # Learning System
        if inputs.get("learn"):
            summary_parts.append("\nLEARNING: ENABLED")
        
        return "\n".join(summary_parts)
    
    def _rule_based_analysis(self, inputs: Dict[str, Any]) -> UserInputAnalysis:
        """
        Fallback rule-based analysis when LLM is unavailable
        Ensures basic functionality even without LLM
        """
        analysis = UserInputAnalysis()
        analysis.original_inputs = inputs
        
        # Extract topic
        analysis.research_topic = inputs.get("title", "Unknown Topic")
        
        # Extract research questions
        for i in range(1, 6):
            rq = inputs.get(f"rq{i}", "")
            if rq:
                analysis.research_questions.append(rq)
        
        # Determine study type
        study_type = inputs.get("study_type", "auto")
        if "auto" not in study_type.lower():
            analysis.study_type = study_type
        
        # Paper type to generate
        paper_type = inputs.get("paper_type", "empirical")
        analysis.paper_type_to_generate = paper_type
        analysis.paper_structure = self.paper_structures.get(paper_type, "IMRAD")
        
        # Generate search queries from topic
        topic = analysis.research_topic
        queries = [
            topic,
            topic + " " + analysis.academic_field,
            topic + " methodology",
            topic + " findings"
        ]
        analysis.optimized_queries = [q for q in queries if q.strip()]
        
        # Extract keywords
        analysis.search_keywords = topic.split()
        
        # Year range
        year_from = inputs.get("year_from", "")
        year_to = inputs.get("year_to", "2026")
        
        # Parse year_from
        if year_from in ["", "all", "All Years (No Limit)"]:
            analysis.year_range = (2000, 2026)
        elif "2026" in str(year_from):
            analysis.year_range = (2026, 2026)
        elif "2025" in str(year_from):
            analysis.year_range = (2025, 2026)
        elif "2020" in str(year_from):
            analysis.year_range = (2020, 2026)
        elif "2015" in str(year_from):
            analysis.year_range = (2015, 2026)
        elif "2010" in str(year_from):
            analysis.year_range = (2010, 2026)
        elif "2000" in str(year_from):
            analysis.year_range = (2000, 2026)
        elif "1500" in str(year_from):
            analysis.year_range = (1500, 2026)
        else:
            analysis.year_range = (2000, 2026)
        
        # Parse year_to
        if year_to:
            year_to_clean = re.sub(r'[^\d]', '', str(year_to))
            if year_to_clean:
                analysis.year_range = (analysis.year_range[0], int(year_to_clean))
        
        # Search depth
        analysis.search_depth = inputs.get("mode", "field")
        
        # Output formats
        output_format = inputs.get("output_format", "all")
        analysis.required_formats = self.output_mappings.get(output_format, ["docx"])
        
        # Determine platforms based on study type
        analysis.recommended_platforms = self._select_platforms(study_type, inputs.get("field", ""))
        
        return analysis
    
    def _parse_llm_analysis(self, parsed: Dict, inputs: Dict) -> UserInputAnalysis:
        """Parse LLM response into structured analysis"""
        analysis = UserInputAnalysis()
        analysis.original_inputs = inputs
        
        # Basic info
        analysis.research_topic = parsed.get("research_topic", inputs.get("title", ""))
        analysis.academic_field = parsed.get("academic_field", inputs.get("field", ""))
        
        # Queries and keywords
        analysis.optimized_queries = parsed.get("optimized_queries", [])
        analysis.search_keywords = parsed.get("keywords", [])
        analysis.excluded_keywords = parsed.get("excluded_terms", [])
        
        # Year range
        year_range = parsed.get("year_range", {})
        if isinstance(year_range, dict):
            analysis.year_range = (
                year_range.get("from", 2000),
                year_range.get("to", 2026)
            )
        else:
            analysis.year_range = (2000, 2026)
        
        # Platforms
        analysis.recommended_platforms = parsed.get("recommended_platforms", [])
        analysis.search_depth = parsed.get("search_depth", "field")
        
        # Output
        analysis.required_formats = parsed.get("required_formats", ["docx"])
        analysis.paper_structure = parsed.get("paper_structure", "IMRAD")
        
        # Paper type
        analysis.paper_type_to_generate = inputs.get("paper_type", "empirical")
        
        # Ensure required formats match user selection EXACTLY
        output_format = inputs.get("output_format", "all")
        if output_format != "all":
            # Use exactly what user selected
            analysis.required_formats = self.output_mappings.get(output_format, ["docx"])
        
        return analysis
    
    def _select_platforms(self, study_type: str, field: str) -> List[str]:
        """Select optimal platforms based on study type and field"""
        
        # Base platforms for all types
        base_platforms = [
            "Google Scholar",
            "Semantic Scholar",
            "PubMed Central",
            "CORE.ac.uk"
        ]
        
        # Study-specific platforms
        if "systematic" in study_type.lower() or "meta" in study_type.lower():
            return base_platforms + [
                "Cochrane Library",
                "PROSPERO",
                "JBI",
                "Campbell Collaboration",
                "Epistemonikos"
            ]
        
        if "qualitative" in study_type.lower():
            return base_platforms + [
                "CINAHL",
                "PsycINFO",
                "ERIC",
                "Qualitative Research databases"
            ]
        
        if "historical" in study_type.lower():
            return base_platforms + [
                "Internet Archive",
                "HathiTrust",
                "WorldCat",
                "JSTOR",
                "Early English Books Online"
            ]
        
        # Field-specific additions
        if "education" in field.lower():
            return base_platforms + ["ERIC", "Educational Journals"]
        
        if "medical" in field.lower() or "health" in field.lower():
            return base_platforms + ["PubMed", "Cochrane", "EMBASE"]
        
        if "psychology" in field.lower():
            return base_platforms + ["PsycINFO", "PSYCH Articles"]
        
        return base_platforms
    
    def _generate_16k_instructions(self, analysis: UserInputAnalysis) -> str:
        """Generate instructions for the 16k deep analysis model"""
        
        instructions = f"""
16K MODEL INSTRUCTIONS
======================

TOPIC: {analysis.research_topic}

RESEARCH QUESTIONS:
{chr(10).join(f"- {rq}" for rq in analysis.research_questions)}

OPTIMIZED SEARCH QUERIES:
{chr(10).join(f"- {q}" for q in analysis.optimized_queries)}

YEAR RANGE: {analysis.year_range[0]} to {analysis.year_range[1]}

PAPER STRUCTURE TO GENERATE: {analysis.paper_structure}

REQUIRED OUTPUT FORMATS:
{chr(10).join(f"- {f}" for f in analysis.required_formats)}

SEARCH DEPTH: {analysis.search_depth}

RECOMMENDED PLATFORMS:
{chr(10).join(f"- {p}" for p in analysis.recommended_platforms)}

IMPORTANT:
- Generate paper in EXACT structure requested
- Output in ALL formats selected by user
- Use citations from retrieved papers
- Follow {analysis.citation_style} format
- Do NOT deviate from user requirements
"""
        
        return instructions
    
    def _log_learning(self, analysis: UserInputAnalysis):
        """Log analysis to learning file for future reference"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "topic": analysis.research_topic,
                "field": analysis.academic_field,
                "paper_type": analysis.paper_type_to_generate,
                "queries_used": analysis.optimized_queries,
                "formats_requested": analysis.required_formats,
                "model_used": analysis.model_used
            }
            
            with open(self.learning_log, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
                
        except Exception as e:
            print(f"⚠️ Learning log error: {e}")
    
    def _update_memory(self, analysis: UserInputAnalysis):
        """Update the JSON memory with new learning"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r") as f:
                    memory = json.load(f)
            else:
                memory = {"what_i_intend_to_write": {"active_projects": []}}
            
            # Add to intended writes
            if "what_i_intend_to_write" not in memory:
                memory["what_i_intend_to_write"] = {"active_projects": []}
            
            project = {
                "topic": analysis.research_topic,
                "paper_type": analysis.paper_type_to_generate,
                "structure": analysis.paper_structure,
                "formats": analysis.required_formats,
                "queries": analysis.optimized_queries,
                "timestamp": datetime.now().isoformat()
            }
            
            memory["what_i_intend_to_write"]["active_projects"].append(project)
            
            with open(self.memory_file, "w") as f:
                json.dump(memory, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"⚠️ Memory update error: {e}")
    
    def generate_search_command(self, analysis: UserInputAnalysis) -> str:
        """Generate the command to run research_hunter_v2-4.py with optimized parameters"""
        
        cmd_parts = ["python", "research_hunter_v2-4.py"]
        
        # Add topic
        if analysis.research_topic:
            cmd_parts.append(f'--title "{analysis.research_topic}"')
        
        # Add research questions
        for i, rq in enumerate(analysis.research_questions[:5], 1):
            cmd_parts.append(f'--rq{i} "{rq}"')
        
        # Add optimized queries
        if analysis.optimized_queries:
            queries_str = "; ".join(analysis.optimized_queries[:3])
            cmd_parts.append(f'--keywords "{queries_str}"')
        
        # Add year range
        cmd_parts.append(f'--year-from {analysis.year_range[0]}')
        cmd_parts.append(f'--year-to {analysis.year_range[1]}')
        
        # Add search depth
        cmd_parts.append(f'--mode {analysis.search_depth}')
        
        # Add paper type for generation
        if analysis.paper_type_to_generate:
            cmd_parts.append(f'--paper-type {analysis.paper_type_to_generate}')
        
        # Add output format
        output_map = {
            "all": "both",
            "docx_scopus": "scopus",
            "docx_standard": "standard",
            "docx_both": "both",
            "pdf": "standard",
            "excel_master": "standard",
            "markdown": "standard",
            "json": "standard",
            "txt": "standard"
        }
        output_format = analysis.original_inputs.get("output_format", "all")
        mapped_format = output_map.get(output_format, "both")
        cmd_parts.append(f'--output-format {mapped_format}')
        
        # Add learning flag
        if analysis.original_inputs.get("learn", True):
            cmd_parts.append("--learn")
        
        # Add paper generation flag
        if analysis.original_inputs.get("generate_paper", False):
            cmd_parts.append("--generate-paper")
        
        return " ".join(cmd_parts)
    
    def validate_outputs(self, expected_formats: List[str], actual_files: List[str]) -> Dict[str, bool]:
        """Validate that outputs match user expectations"""
        
        results = {}
        
        # Check each expected format
        format_extensions = {
            "docx": ".docx",
            "pdf": ".pdf",
            "xlsx": ".xlsx",
            "md": ".md",
            "txt": ".txt",
            "json": ".json",
            "csv": ".csv",
            "html": ".html",
            "tex": ".tex",
            "xml": ".xml"
        }
        
        for fmt in expected_formats:
            ext = format_extensions.get(fmt, f".{fmt}")
            found = any(ext in f.lower() for f in actual_files)
            results[fmt] = found
        
        # Overall validation
        results["all_valid"] = all(results.values())
        
        return results


# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Process inputs from workflow and generate search plan"""
    
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║     🧠 SMART INPUT PROCESSOR v2.0 - Research Hunter Brain           ║
║                                                                       ║
║  4k Model: Analyzes user inputs from workflow                        ║
║  16k Model: Deep analysis and synthesis                              ║
║                                                                       ║
║  WHAT USER SELECTS = WHAT SYSTEM PRODUCES                            ║
╚═══════════════════════════════════════════════════════════════════════╝
    """)
    
    # Example usage with workflow inputs
    sample_inputs = {
        "title": "Digital Learning in MENA Region",
        "rq1": "What is the impact of digital learning on student outcomes?",
        "rq2": "How do teachers perceive e-learning tools?",
        "field": "Education",
        "study_type": "empirical",
        "paper_type": "systematic_review",
        "output_format": "all",
        "year_from": "2020",
        "year_to": "2026",
        "language": "en",
        "mode": "field",
        "learn": True,
        "generate_paper": True
    }
    
    # Initialize processor
    processor = SmartInputProcessor()
    
    # Process inputs with 4k model
    analysis = processor.analyze_workflow_inputs(sample_inputs)
    
    # Generate search command
    cmd = processor.generate_search_command(analysis)
    print(f"\n🔧 Generated Search Command:\n   {cmd}")
    
    # Show output validation
    print("\n📋 Expected Outputs:")
    for fmt in analysis.required_formats:
        print(f"   ✅ {fmt.upper()}")


if __name__ == "__main__":
    main()
