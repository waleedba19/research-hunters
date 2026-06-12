#!/usr/bin/env python3
"""
Research Hunter - Paper Analyzer & Learning System v3.0
========================================================
Analyzes research papers, learns their structures and styles,
and updates the JSON memory system with findings.

Features:
- Analyze paper structure and sections
- Extract methodology patterns
- Learn citation formats
- Identify academic vocabulary
- Update memory with learned patterns
- Generate style fingerprints

Author: Research Hunter v3.0 - Academic Intelligence
"""

import json
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import Counter, defaultdict
import hashlib

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

MEMORY_FILE = "academic_memory.json"
STYLES_FILE = "academic_styles.md"

@dataclass
class PaperAnalysis:
    """Complete analysis of a research paper"""
    paper_id: str
    title: str
    
    # Structural Analysis
    sections_found: List[str] = field(default_factory=list)
    section_order: List[str] = field(default_factory=list)
    missing_sections: List[str] = field(default_factory=list)
    extra_sections: List[str] = field(default_factory=list)
    
    # Content Analysis
    word_counts: Dict[str, int] = field(default_factory=dict)
    citation_count: int = 0
    references: List[str] = field(default_factory=list)
    
    # Style Analysis
    writing_style: str = "academic"
    formality_level: str = "formal"
    voice: str = "passive"
    
    # Methodology Detection
    methodology_type: str = ""
    research_design: str = ""
    data_collection: List[str] = field(default_factory=list)
    analysis_methods: List[str] = field(default_factory=list)
    
    # Quality Indicators
    abstract_present: bool = False
    keywords_present: bool = False
    introduction_complete: bool = False
    conclusion_present: bool = False
    references_formatted: bool = False
    
    # Learned Elements
    transition_phrases: List[str] = field(default_factory=list)
    hedging_phrases: List[str] = field(default_factory=list)
    field_specific_terms: List[str] = field(default_factory=list)
    
    # Metadata
    journal_type: str = ""
    quartile: str = ""
    year: int = 0
    authors_count: int = 0
    
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())

class PaperAnalyzer:
    """
    Intelligent Paper Analyzer that learns from every paper analyzed.
    Updates the JSON memory system with new patterns and styles.
    """
    
    def __init__(self, memory_file: str = MEMORY_FILE):
        self.memory_file = Path(memory_file)
        self.memory = self._load_memory()
        self.styles_file = Path(STYLES_FILE)
        
        # Standard section names for detection
        self.standard_sections = {
            "abstract": ["abstract", "summary"],
            "introduction": ["introduction", "1. introduction", "background"],
            "literature_review": ["literature review", "theoretical framework", "prior research", "related work", "background and literature"],
            "methodology": ["methodology", "method", "methods", "research design", "materials and methods", "procedure"],
            "results": ["results", "findings", "results and discussion", "data analysis"],
            "discussion": ["discussion", "discussion and conclusions"],
            "conclusion": ["conclusion", "conclusions", "conclusion and recommendations", "summary and conclusion"],
            "references": ["references", "bibliography", "works cited"],
            "acknowledgments": ["acknowledgments", "acknowledgements"],
            "appendices": ["appendix", "appendices", "supplementary"]
        }
        
        # Transition phrases to detect
        self.transition_patterns = [
            r'\b(furthermore|moreover|additionally|also)\b',
            r'\b(however|nevertheless|in contrast|conversely)\b',
            r'\b(therefore|consequently|thus|hence|accordingly)\b',
            r'\b(for example|for instance|specifically|to illustrate)\b',
            r'\b(importantly|notably|significantly|indeed)\b',
            r'\b(in summary|to conclude|in conclusion|overall)\b',
            r'\b(first|second|finally|subsequently|ultimately)\b'
        ]
        
        # Hedging phrases to detect
        self.hedging_patterns = [
            r'\b(may|might|could|would)\s+(indicate|suggest|explain)',
            r'\b(it\s+appears|it\s+seems)\b',
            r'\b(the\s+findings\s+suggest)\b',
            r'\b(approximately|roughly|about)\b',
            r'\b(potentially|possibly|likely|unlikely)\b',
            r'\b(to\s+some\s+extent|in\s+part)\b'
        ]
        
        # Methodology keywords
        self.methodology_keywords = {
            "quantitative": ["survey", "questionnaire", "statistical", "regression", "correlation", 
                            "ANOVA", "t-test", "SPSS", "quantitative", "numerical", "experimental"],
            "qualitative": ["interview", "focus group", "thematic analysis", "phenomenology",
                           "grounded theory", "ethnography", "qualitative", "narrative", "case study"],
            "mixed_methods": ["mixed methods", "mixed-method", "triangulation", "convergent"],
            "experimental": ["randomized", "control group", "intervention", "pre-test", "post-test"],
            "longitudinal": ["longitudinal", "cohort", "panel", "follow-up", "prospective"],
            "cross-sectional": ["cross-sectional", "prevalence", "survey-based"]
        }
        
        # Citation pattern
        self.citation_pattern = r'\(([A-Z][a-z]+(?:\s+(?:et\s+al\.?|&\\s+[A-Z][a-z]+))?(?:,\s*\d{4}[a-z]?)?(?:,\s*p?\.?\s*\d+(?:\u2013\d+)?)?)\)'
        
        print("📚 Paper Analyzer initialized")
        print(f"   Memory file: {self.memory_file}")
        print(f"   Total papers in memory: {self.memory['what_i_read']['total_papers_read']}")
    
    def _load_memory(self) -> Dict:
        """Load the JSON memory file"""
        if self.memory_file.exists():
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self._create_default_memory()
    
    def _create_default_memory(self) -> Dict:
        """Create default memory structure"""
        default = {
            "_schema_version": "3.0",
            "_last_updated": datetime.now().isoformat(),
            "what_i_read": {"total_papers_read": 0, "papers": []},
            "what_i_wrote": {"total_outputs_generated": 0, "literature_reviews": []},
            "what_i_know": {"theoretical_frameworks": [], "key_concepts": {}},
            "what_i_intend_to_write": {"active_projects": [], "pending_sections": []},
            "paper_styles": {},
            "learned_patterns": {
                "title_patterns": [],
                "section_order_patterns": [],
                "transition_phrases": [],
                "hedging_phrases": [],
                "citation_density": {}
            },
            "vocabulary_learned": {
                "transition_words": [],
                "hedging_phrases": [],
                "methodology_terms": [],
                "statistical_terms": [],
                "field_specific_terms": {}
            }
        }
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(default, f, indent=2, ensure_ascii=False)
        return default
    
    def _save_memory(self):
        """Save updated memory to JSON file"""
        self.memory["_last_updated"] = datetime.now().isoformat()
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f, indent=2, ensure_ascii=False)
    
    def _generate_paper_id(self, title: str) -> str:
        """Generate unique ID for paper"""
        hash_input = f"{title}_{datetime.now().isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for analysis"""
        text = text.lower()
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _detect_sections(self, content: str) -> Tuple[List[str], List[str], List[str]]:
        """Detect sections in paper content"""
        found_sections = []
        normalized = self._normalize_text(content)
        
        for section_type, keywords in self.standard_sections.items():
            for keyword in keywords:
                if keyword in normalized:
                    found_sections.append(section_type)
                    break
        
        # Determine missing standard sections
        required = ["abstract", "introduction", "methodology", "results", "discussion", "references"]
        missing = [s for s in required if s not in found_sections]
        
        return found_sections, missing, []
    
    def _extract_citations(self, content: str) -> Tuple[int, List[str]]:
        """Extract all citations from content"""
        citations = re.findall(self.citation_pattern, content)
        return len(citations), list(set(citations))
    
    def _detect_transitions(self, content: str) -> List[str]:
        """Detect transition phrases used in paper"""
        found = []
        for pattern in self.transition_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            found.extend([m.lower() if isinstance(m, str) else m[0].lower() for m in matches])
        return list(set(found))
    
    def _detect_hedging(self, content: str) -> List[str]:
        """Detect hedging phrases used in paper"""
        found = []
        for pattern in self.hedging_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            found.extend([m if isinstance(m, str) else ' '.join(m) for m in matches])
        return list(set(found))
    
    def _detect_methodology(self, content: str) -> Dict[str, Any]:
        """Detect research methodology used"""
        normalized = self._normalize_text(content)
        result = {
            "type": "unknown",
            "design": "unknown",
            "data_collection": [],
            "analysis_methods": []
        }
        
        # Detect methodology type
        for method_type, keywords in self.methodology_keywords.items():
            if sum(1 for kw in keywords if kw in normalized) >= 2:
                result["type"] = method_type
                break
        
        # Detect specific designs
        if "systematic review" in normalized or "meta-analysis" in normalized:
            result["design"] = "systematic_review" if "meta-analysis" not in normalized else "meta_analysis"
        elif any(kw in normalized for kw in ["randomized controlled", "RCT"]):
            result["design"] = "RCT"
        elif any(kw in normalized for kw in ["quasi-experimental", "quasi experimental"]):
            result["design"] = "quasi_experimental"
        elif any(kw in normalized for kw in ["correlational", "correlation study"]):
            result["design"] = "correlational"
        elif any(kw in normalized for kw in ["phenomenological", "lived experience"]):
            result["design"] = "phenomenology"
        elif any(kw in normalized for kw in ["case study", "case-study"]):
            result["design"] = "case_study"
        
        # Detect data collection methods
        data_methods = {
            "surveys": ["survey", "questionnaire"],
            "interviews": ["interview", "semi-structured", "in-depth interview"],
            "focus_groups": ["focus group", "focus-group"],
            "observations": ["observation", "observational"],
            "experiments": ["experiment", "laboratory"],
            "document_analysis": ["document analysis", "content analysis"],
            "secondary_data": ["secondary data", "existing data", "dataset"]
        }
        
        for method, keywords in data_methods.items():
            if any(kw in normalized for kw in keywords):
                result["data_collection"].append(method)
        
        # Detect analysis methods
        analysis_methods = {
            "descriptive_stats": ["mean", "standard deviation", "frequency", "percentage"],
            "inferential_stats": ["t-test", "anova", "regression", "chi-square", "MANOVA"],
            "thematic_analysis": ["thematic analysis", "themes", "coding", "categorization"],
            "content_analysis": ["content analysis", "qualitative content"],
            "SEM": ["structural equation", "SEM", "path analysis"],
            "multilevel": ["multilevel", "hierarchical linear", "HLM"],
            "qualitative_software": ["NVivo", "ATLAS.ti", "MAXQDA"]
        }
        
        for method, keywords in analysis_methods.items():
            if any(kw in normalized for kw in keywords):
                result["analysis_methods"].append(method)
        
        return result
    
    def _extract_field_terms(self, content: str) -> List[str]:
        """Extract field-specific terminology"""
        terms = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', content)
        
        # Filter to meaningful multi-word terms
        field_terms = []
        skip_words = {"The", "This", "That", "These", "Those", "However", "Therefore", 
                     "Figure", "Table", "Appendix", "Note", "Example"}
        
        for term in terms:
            if term not in skip_words and len(term) > 5:
                field_terms.append(term)
        
        return list(set(field_terms))[:20]
    
    def _analyze_title(self, title: str) -> Dict[str, Any]:
        """Analyze paper title structure"""
        analysis = {
            "length": len(title.split()),
            "has_colon": ":" in title,
            "has_subtitle": bool(re.search(r':\s*.+\s*[-\u2013]\s*.+', title)),
            "contains_question": "?" in title,
            "contains_method": bool(re.search(r'(study|review|analysis|investigation|examination)', title, re.I)),
            "contains_population": bool(re.search(r'(students?|teachers?|learners?|participants?|children?|adults?)', title, re.I)),
            "contains_location": bool(re.search(r'(Libya|MENA|Arab|Africa|Europe|Asia|USA|UK)', title)),
            "format": "standard"
        }
        
        if analysis["has_subtitle"]:
            analysis["format"] = "with_subtitle"
        elif analysis["has_colon"]:
            analysis["format"] = "with_colon"
        elif analysis["contains_question"]:
            analysis["format"] = "question"
        
        return analysis
    
    def _count_words(self, content: str) -> Dict[str, int]:
        """Count words in different sections"""
        sections = {}
        current_section = "other"
        current_text = ""
        
        lines = content.split('\n')
        for line in lines:
            line_lower = self._normalize_text(line)
            
            # Detect section headers
            section_found = False
            for section_type, keywords in self.standard_sections.items():
                if any(kw in line_lower and len(line) < 100 for kw in keywords):
                    if current_text and current_section != "other":
                        sections[current_section] = len(current_text.split())
                    current_section = section_type
                    current_text = ""
                    section_found = True
                    break
            
            if not section_found:
                current_text += " " + line
        
        # Count remaining
        if current_text and current_section != "other":
            sections[current_section] = len(current_text.split())
        
        return sections
    
    def analyze_paper(self, paper_data: Dict[str, Any]) -> PaperAnalysis:
        """
        Complete analysis of a research paper.
        Takes paper data and returns comprehensive analysis.
        """
        paper_id = self._generate_paper_id(paper_data.get("title", "unknown"))
        title = paper_data.get("title", "")
        content = paper_data.get("content", "")
        abstract = paper_data.get("abstract", "")
        
        print(f"\n📄 Analyzing: {title[:60]}...")
        
        # Full content for analysis
        full_content = f"{abstract}\n\n{content}"
        
        # Structural analysis
        sections_found, missing_sections, extra_sections = self._detect_sections(full_content)
        
        # Content analysis
        citation_count, citations = self._extract_citations(full_content)
        word_counts = self._count_words(full_content)
        
        # Style analysis
        transitions = self._detect_transitions(full_content)
        hedging = self._detect_hedging(full_content)
        title_analysis = self._analyze_title(title)
        
        # Methodology detection
        methodology = self._detect_methodology(full_content)
        
        # Field terms
        field_terms = self._extract_field_terms(full_content)
        
        # Create analysis object
        analysis = PaperAnalysis(
            paper_id=paper_id,
            title=title,
            sections_found=sections_found,
            section_order=sections_found,
            missing_sections=missing_sections,
            extra_sections=extra_sections,
            word_counts=word_counts,
            citation_count=citation_count,
            references=citations[:50],
            writing_style="academic",
            methodology_type=methodology["type"],
            research_design=methodology["design"],
            data_collection=methodology["data_collection"],
            analysis_methods=methodology["analysis_methods"],
            abstract_present="abstract" in sections_found,
            keywords_present="keywords" in full_content.lower(),
            introduction_complete="introduction" in sections_found,
            conclusion_present="conclusion" in sections_found,
            references_formatted="references" in sections_found,
            transition_phrases=transitions,
            hedging_phrases=hedging,
            field_specific_terms=field_terms,
            journal_type=paper_data.get("journal", ""),
            quartile=paper_data.get("quartile", ""),
            year=paper_data.get("year", 0),
            authors_count=len(paper_data.get("authors", []))
        )
        
        # Update memory with learned patterns
        self._update_memory(analysis, paper_data)
        
        return analysis
    
    def _update_memory(self, analysis: PaperAnalysis, paper_data: Dict):
        """Update the JSON memory with learned patterns"""
        memory = self.memory
        
        # Ensure what_i_read structure exists
        if "what_i_read" not in memory:
            memory["what_i_read"] = {
                "total_papers_read": 0, "papers": [], "by_field": {}, "by_year": {},
                "systematic_reviews": [], "meta_analyses": [], "qualitative_studies": [],
                "quantitative_studies": [], "mixed_methods": []
            }
        
        # Ensure learned_patterns structure exists
        if "learned_patterns" not in memory:
            memory["learned_patterns"] = {
                "title_patterns": [], "section_order_patterns": [], "transition_phrases": [],
                "hedging_phrases": [], "citation_density": {}
            }
        
        # Ensure vocabulary_learned structure exists
        if "vocabulary_learned" not in memory:
            memory["vocabulary_learned"] = {
                "transition_words": [], "hedging_phrases": [], "methodology_terms": [],
                "statistical_terms": [], "field_specific_terms": {}
            }
        
        # Update what_i_read
        what_read = memory["what_i_read"]
        what_read["total_papers_read"] = what_read.get("total_papers_read", 0) + 1
        
        # Ensure nested structures exist
        for key in ["papers", "by_field", "by_year", "systematic_reviews", "meta_analyses", 
                    "qualitative_studies", "quantitative_studies", "mixed_methods"]:
            if key not in what_read:
                what_read[key] = []
        
        paper_entry = {
            "paper_id": analysis.paper_id,
            "title": analysis.title,
            "year": analysis.year,
            "journal": analysis.journal_type,
            "quartile": analysis.quartile,
            "methodology": analysis.methodology_type,
            "design": analysis.research_design,
            "sections": analysis.sections_found,
            "citation_count": analysis.citation_count,
            "word_counts": analysis.word_counts,
            "analyzed_at": analysis.analyzed_at
        }
        what_read["papers"].append(paper_entry)
        
        # Categorize by type
        if "systematic review" in analysis.research_design.lower():
            what_read["systematic_reviews"].append(paper_entry)
        elif "meta-analysis" in analysis.research_design.lower():
            what_read["meta_analyses"].append(paper_entry)
        elif analysis.methodology_type == "qualitative":
            what_read["qualitative_studies"].append(paper_entry)
        elif analysis.methodology_type == "quantitative":
            what_read["quantitative_studies"].append(paper_entry)
        elif analysis.methodology_type == "mixed_methods":
            what_read["mixed_methods"].append(paper_entry)
        
        # Update by field
        field = paper_data.get("field", "General")
        if field not in what_read["by_field"]:
            what_read["by_field"][field] = []
        what_read["by_field"][field].append(analysis.paper_id)
        
        # Update by year
        if analysis.year:
            if analysis.year not in what_read["by_year"]:
                what_read["by_year"][analysis.year] = []
            what_read["by_year"][analysis.year].append(analysis.paper_id)
        
        # Update learned patterns
        patterns = memory["learned_patterns"]
        
        # Title patterns
        title_pattern = {
            "has_colon": ":" in analysis.title,
            "has_subtitle": bool(re.search(r':\s*.+\s*[-\u2013]\s*.+', analysis.title)),
            "length": len(analysis.title.split()),
            "year": analysis.year
        }
        patterns["title_patterns"].append(title_pattern)
        
        # Section order patterns
        patterns["section_order_patterns"].append(analysis.section_order)
        
        # Transition phrases
        for phrase in analysis.transition_phrases:
            if phrase not in patterns["transition_phrases"]:
                patterns["transition_phrases"].append(phrase)
        
        # Hedging phrases
        for phrase in analysis.hedging_phrases:
            if phrase not in patterns["hedging_phrases"]:
                patterns["hedging_phrases"].append(phrase)
        
        # Citation density by journal
        if analysis.journal_type:
            if analysis.journal_type not in patterns["citation_density"]:
                patterns["citation_density"][analysis.journal_type] = []
            patterns["citation_density"][analysis.journal_type].append(analysis.citation_count)
        
        # Update vocabulary
        vocab = memory["vocabulary_learned"]
        vocab["transition_words"] = list(set(vocab["transition_words"] + analysis.transition_phrases))
        vocab["hedging_phrases"] = list(set(vocab["hedging_phrases"] + analysis.hedging_phrases))
        
        # Methodology terms
        for method in analysis.data_collection + analysis.analysis_methods:
            if method not in vocab["methodology_terms"]:
                vocab["methodology_terms"].append(method)
        
        # Field specific terms
        for term in analysis.field_specific_terms:
            field = paper_data.get("field", "General")
            if field not in vocab["field_specific_terms"]:
                vocab["field_specific_terms"][field] = []
            if term not in vocab["field_specific_terms"][field]:
                vocab["field_specific_terms"][field].append(term)
        
        # Update what_i_know
        what_know = memory["what_i_know"]
        
        # Track key concepts
        if analysis.title not in what_know["key_concepts"]:
            what_know["key_concepts"][analysis.title] = {
                "paper_id": analysis.paper_id,
                "methodology": analysis.methodology_type,
                "findings_summary": paper_data.get("abstract", "")[:200]
            }
        
        # Track research methods
        if analysis.methodology_type and analysis.methodology_type not in what_know["research_methods"]:
            what_know["research_methods"].append(analysis.methodology_type)
        
        if analysis.research_design and analysis.research_design not in what_know["research_methods"]:
            what_know["research_methods"].append(analysis.research_design)
        
        # Save updated memory
        self._save_memory()
        
        print(f"   ✅ Memory updated - Total papers: {what_read['total_papers_read']}")
    
    def get_knowledge_summary(self) -> Dict[str, Any]:
        """Get summary of learned knowledge"""
        memory = self.memory
        
        return {
            "papers_analyzed": memory["what_i_read"]["total_papers_read"],
            "methodologies_learned": len(memory["what_i_know"]["research_methods"]),
            "concepts_learned": len(memory["what_i_know"]["key_concepts"]),
            "transition_phrases_learned": len(memory["vocabulary_learned"]["transition_words"]),
            "hedging_phrases_learned": len(memory["vocabulary_learned"]["hedging_phrases"]),
            "fields_covered": list(memory["what_i_read"]["by_field"].keys()),
            "years_covered": list(memory["what_i_read"]["by_year"].keys()),
            "avg_citation_density": self._calculate_avg_citations()
        }
    
    def _calculate_avg_citations(self) -> Dict[str, float]:
        """Calculate average citation density by journal type"""
        patterns = self.memory["learned_patterns"]["citation_density"]
        result = {}
        
        for journal, counts in patterns.items():
            if counts:
                result[journal] = round(sum(counts) / len(counts), 2)
        
        return result
    
    def generate_style_profile(self, paper_type: str = "empirical") -> Dict[str, Any]:
        """
        Generate a style profile based on learned patterns.
        Used for generating new papers in similar style.
        """
        memory = self.memory
        patterns = memory["learned_patterns"]
        vocab = memory["vocabulary_learned"]
        
        # Analyze common section orders
        section_orders = patterns["section_order_patterns"]
        most_common_order = {}
        for order in section_orders:
            order_tuple = tuple(order)
            most_common_order[order_tuple] = most_common_order.get(order_tuple, 0) + 1
        
        common_order = max(most_common_order.keys(), key=lambda x: most_common_order[x]) if most_common_order else []
        
        # Calculate typical word counts
        all_word_counts = [w for p in memory["what_i_read"]["papers"] for w in p.get("word_counts", {}).values()]
        avg_words = sum(all_word_counts) / len(all_word_counts) if all_word_counts else 0
        
        profile = {
            "paper_type": paper_type,
            "suggested_sections": list(common_order) if common_order else [
                "abstract", "introduction", "literature_review", 
                "methodology", "results", "discussion", "conclusion", "references"
            ],
            "typical_word_counts": {
                "abstract": 250,
                "introduction": 1000,
                "literature_review": 2000,
                "methodology": 1500,
                "results": 2500,
                "discussion": 2000,
                "conclusion": 500
            },
            "recommended_transitions": vocab["transition_words"][:10],
            "recommended_hedging": vocab["hedging_phrases"][:10],
            "citation_density": self._calculate_avg_citations(),
            "formatting": {
                "citation_style": "APA 7th",
                "font": "Times New Roman 12pt",
                "spacing": "Double",
                "margins": "1 inch"
            }
        }
        
        return profile
    
    def learn_from_excel(self, excel_data: List[Dict]) -> Dict[str, Any]:
        """
        Learn patterns from Excel data (paper metadata).
        Updates memory with information from bulk paper analysis.
        """
        results = {
            "papers_processed": 0,
            "fields_learned": set(),
            "journals_learned": set(),
            "methodologies_found": Counter()
        }
        
        for paper in excel_data:
            results["papers_processed"] += 1
            
            # Extract metadata
            title = paper.get("title", "")
            field = paper.get("field", "Unknown")
            journal = paper.get("journal", "")
            methodology = paper.get("methodology", "")
            
            results["fields_learned"].add(field)
            results["journals_learned"].add(journal)
            if methodology:
                results["methodologies_found"][methodology] += 1
            
            # Create minimal analysis for memory update
            paper_id = self._generate_paper_id(title)
            
            # Update what_i_read
            what_read = self.memory["what_i_read"]
            what_read["total_papers_read"] += 1
            
            paper_entry = {
                "paper_id": paper_id,
                "title": title,
                "year": paper.get("year", 0),
                "journal": journal,
                "quartile": paper.get("quartile", ""),
                "methodology": methodology,
                "field": field,
                "citations": paper.get("citations", 0)
            }
            what_read["papers"].append(paper_entry)
            
            # Update by field
            if field not in what_read["by_field"]:
                what_read["by_field"][field] = []
            what_read["by_field"][field].append(paper_id)
            
            # Save memory
            self._save_memory()
            
            # Convert sets to lists for return
            results["fields_learned"] = list(results["fields_learned"])
            results["journals_learned"] = list(results["journals_learned"])
        
        print(f"\n📚 Learned from {results['papers_processed']} papers")
        print(f"   Fields: {len(results['fields_learned'])}")
        print(f"   Journals: {len(results['journals_learned'])}")
        print(f"   Top methodologies: {results['methodologies_found'].most_common(5)}")
        
        return results


# ═══════════════════════════════════════════════════════════════════════════
# STANDALONE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def analyze_paper_file(filepath: str) -> PaperAnalysis:
    """Analyze a paper from file"""
    analyzer = PaperAnalyzer()
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple parsing - assumes first line is title
    lines = content.split('\n')
    title = lines[0].strip()
    
    paper_data = {
        "title": title,
        "content": content,
        "abstract": "",
        "year": 2024
    }
    
    return analyzer.analyze_paper(paper_data)

def learn_from_search_results(results: List[Dict]) -> Dict[str, Any]:
    """Learn from search results (papers found during research)"""
    analyzer = PaperAnalyzer()
    
    for result in results:
        paper_data = {
            "title": result.get("title", ""),
            "content": result.get("abstract", ""),
            "abstract": result.get("abstract", ""),
            "year": result.get("year", 0),
            "journal": result.get("journal", ""),
            "quartile": result.get("quartile", ""),
            "authors": result.get("authors", []),
            "field": result.get("field", "General")
        }
        analyzer.analyze_paper(paper_data)
    
    return analyzer.get_knowledge_summary()

def get_style_profile(paper_type: str = "empirical") -> Dict[str, Any]:
    """Get a style profile for generating similar papers"""
    analyzer = PaperAnalyzer()
    return analyzer.generate_style_profile(paper_type)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("="*70)
    print("📚 RESEARCH HUNTER - PAPER ANALYZER v3.0")
    print("   Learning from Every Research Paper")
    print("="*70)
    print()
    
    # Initialize analyzer
    analyzer = PaperAnalyzer()
    
    # Show current knowledge state
    print("\n📊 Current Knowledge State:")
    summary = analyzer.get_knowledge_summary()
    for key, value in summary.items():
        if not isinstance(value, list):
            print(f"   {key}: {value}")
    
    print("\n📁 Fields covered:", summary.get("fields_covered", []))
    print("📅 Years covered:", summary.get("years_covered", []))
    
    print("\n" + "="*70)
    print("💡 USAGE EXAMPLES")
    print("="*70)
    print("""
# Analyze a single paper
from paper_analyzer import PaperAnalyzer
analyzer = PaperAnalyzer()
analysis = analyzer.analyze_paper({
    "title": "Impact of Technology on Learning",
    "content": "...full paper content...",
    "abstract": "...abstract...",
    "year": 2024,
    "journal": "Education Journal",
    "quartile": "Q1",
    "authors": ["Smith, J.", "Doe, A."],
    "field": "Education"
})

# Learn from search results
from paper_analyzer import learn_from_search_results
summary = learn_from_search_results(search_results_list)

# Get style profile for paper generation
from paper_analyzer import get_style_profile
profile = get_style_profile("systematic_review")
""")