#!/usr/bin/env python3
"""
Research Hunter - Learning Integration System v3.0
====================================================
Integrates all components into a unified learning system:
- Paper Analyzer (reads and learns)
- Paper Generator (writes with learned patterns)
- Scopus DOCX Generator (creates publication-ready documents)
- RAG System (retrieves relevant knowledge)
- JSON Memory (stores everything learned)

Features:
- Unified learning loop
- Cross-component knowledge sharing
- Smart paper generation based on memory
- Scopus-quality output
- Continuous learning from searches

Author: Research Hunter v3.0 - Academic Intelligence
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

# Try to import optional dependencies
try:
    from paper_analyzer import PaperAnalyzer, learn_from_search_results, get_style_profile
    ANALYZER_AVAILABLE = True
except ImportError:
    ANALYZER_AVAILABLE = False
    print("⚠️ Paper Analyzer not available")

try:
    from paper_generator import PaperGenerator, GeneratedPaper
    GENERATOR_AVAILABLE = True
except ImportError:
    GENERATOR_AVAILABLE = False
    print("⚠️ Paper Generator not available")

try:
    from scopus_docx import ScopusDOCXGenerator, create_scopus_docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    print("⚠️ Scopus DOCX Generator not available")

try:
    from rag_memory_system import ResearchHunterRAG
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("⚠️ RAG System not available")


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

MEMORY_FILE = "academic_memory.json"
SESSION_FILE = "session_memory.json"
LEARNING_LOG_FILE = "learning_log.json"
PATTERNS_FILE = "learned_patterns.json"

@dataclass
class LearningSession:
    """Tracks a learning session"""
    session_id: str
    started_at: str
    ended_at: Optional[str] = None
    queries_executed: int = 0
    papers_analyzed: int = 0
    outputs_generated: int = 0
    knowledge_gained: List[str] = field(default_factory=list)
    topics_covered: List[str] = field(default_factory=list)


@dataclass
class ResearchIntent:
    """Tracks what we intend to write"""
    intent_id: str
    topic: str
    paper_type: str
    status: str = "planned"  # planned, in_progress, completed
    progress: float = 0.0
    sections_completed: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""


class AcademicIntelligenceSystem:
    """
    Unified Academic Intelligence System that learns from every search
    and generates Scopus-quality papers using all learned patterns.
    """
    
    def __init__(self, workspace_dir: str = "."):
        self.workspace = Path(workspace_dir)
        self.memory_file = self.workspace / MEMORY_FILE
        self.session_file = self.workspace / SESSION_FILE
        self.learning_log = self.workspace / LEARNING_LOG_FILE
        self.patterns_file = self.workspace / PATTERNS_FILE
        
        # Initialize components
        self.analyzer = None
        self.generator = None
        self.docx_generator = None
        self.rag_system = None
        
        # Load memory
        self.memory = self._load_memory()
        
        # Initialize components if available
        self._initialize_components()
        
        # Session tracking
        self.current_session = self._start_session()
        
        print("\n" + "="*70)
        print("🧠 RESEARCH HUNTER - ACADEMIC INTELLIGENCE SYSTEM v3.0")
        print("   Learning from Every Search • Writing Scopus-Quality Papers")
        print("="*70)
        print()
        
        # Show status
        self._show_system_status()
    
    def _load_memory(self) -> Dict:
        """Load the main JSON memory file"""
        if self.memory_file.exists():
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self._create_default_memory()
    
    def _create_default_memory(self) -> Dict:
        """Create default memory structure"""
        memory = {
            "_schema_version": "3.0",
            "_last_updated": datetime.now().isoformat(),
            "system_identity": {
                "name": "Research Hunter Academic Intelligence",
                "version": "3.0",
                "purpose": "Learn from every research paper and generate Scopus-quality academic articles"
            },
            "what_i_read": {
                "total_papers_read": 0,
                "papers": [],
                "systematic_reviews": [],
                "meta_analyses": [],
                "qualitative_studies": [],
                "quantitative_studies": [],
                "by_field": {},
                "by_year": {}
            },
            "what_i_wrote": {
                "total_outputs_generated": 0,
                "literature_reviews": [],
                "full_articles": [],
                "abstracts": []
            },
            "what_i_know": {
                "theoretical_frameworks": [],
                "key_concepts": {},
                "research_methods": [],
                "measurement_instruments": [],
                "statistical_techniques": [],
                "topics_covered": []
            },
            "what_i_intend_to_write": {
                "active_projects": [],
                "pending_sections": [],
                "planned_articles": []
            },
            "learning_history": [],
            "session_history": []
        }
        
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
        
        return memory
    
    def _initialize_components(self):
        """Initialize all available components"""
        if ANALYZER_AVAILABLE:
            try:
                self.analyzer = PaperAnalyzer()
                print("✅ Paper Analyzer: Ready")
            except Exception as e:
                print(f"⚠️ Paper Analyzer: Error - {e}")
        
        if GENERATOR_AVAILABLE:
            try:
                self.generator = PaperGenerator()
                print("✅ Paper Generator: Ready")
            except Exception as e:
                print(f"⚠️ Paper Generator: Error - {e}")
        
        if DOCX_AVAILABLE:
            try:
                self.docx_generator = ScopusDOCXGenerator()
                print("✅ Scopus DOCX Generator: Ready")
            except Exception as e:
                print(f"⚠️ Scopus DOCX Generator: Error - {e}")
        
        if RAG_AVAILABLE:
            try:
                self.rag_system = ResearchHunterRAG()
                print("✅ RAG System: Ready")
            except Exception as e:
                print(f"⚠️ RAG System: Not available - {e}")
        
        print()
    
    def _show_system_status(self):
        """Show current system status"""
        what_read = self.memory.get("what_i_read", {})
        what_wrote = self.memory.get("what_i_wrote", {})
        what_know = self.memory.get("what_i_know", {})
        
        print("📊 System Status:")
        print(f"   Papers analyzed: {what_read.get('total_papers_read', 0)}")
        print(f"   Papers generated: {what_wrote.get('total_outputs_generated', 0)}")
        print(f"   Concepts learned: {len(what_know.get('key_concepts', {}))}")
        print(f"   Research methods: {len(what_know.get('research_methods', []))}")
        print(f"   Topics covered: {len(what_know.get('topics_covered', []))}")
        print()
    
    def _save_memory(self):
        """Save memory to JSON file"""
        self.memory["_last_updated"] = datetime.now().isoformat()
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f, indent=2, ensure_ascii=False)
    
    def _start_session(self) -> LearningSession:
        """Start a new learning session"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session = LearningSession(
            session_id=session_id,
            started_at=datetime.now().isoformat()
        )
        return session
    
    def _end_session(self):
        """End the current session and log it"""
        self.current_session.ended_at = datetime.now().isoformat()
        
        # Add to session history
        session_history = self.memory.get("session_history", [])
        session_history.append({
            "session_id": self.current_session.session_id,
            "started_at": self.current_session.started_at,
            "ended_at": self.current_session.ended_at,
            "queries_executed": self.current_session.queries_executed,
            "papers_analyzed": self.current_session.papers_analyzed,
            "outputs_generated": self.current_session.outputs_generated,
            "topics_covered": self.current_session.topics_covered
        })
        
        # Keep only last 50 sessions
        if len(session_history) > 50:
            session_history = session_history[-50:]
        
        self.memory["session_history"] = session_history
        self._save_memory()
    
    # ═══════════════════════════════════════════════════════════════════════
    # LEARNING FUNCTIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def learn_from_search(self, query: str, results: List[Dict]) -> Dict[str, Any]:
        """
        Main learning function - called after every search.
        Updates memory with new knowledge.
        """
        print(f"\n🧠 LEARNING FROM SEARCH: {query}")
        print(f"   Results found: {len(results)}")
        
        self.current_session.queries_executed += 1
        
        learning_results = {
            "query": query,
            "papers_learned_from": 0,
            "concepts_added": [],
            "patterns_learned": [],
            "memory_updated": False
        }
        
        # Learn from each result
        for result in results:
            paper_data = {
                "title": result.get("title", "Unknown"),
                "abstract": result.get("abstract", ""),
                "content": result.get("abstract", ""),  # Use abstract as content
                "year": result.get("year", 2024),
                "journal": result.get("journal", "Unknown"),
                "quartile": result.get("quartile", ""),
                "authors": result.get("authors", []),
                "field": self._extract_field_from_query(query),
                "citations": result.get("citations", 0),
                "methodology": result.get("methodology", "")
            }
            
            # Use analyzer if available
            if self.analyzer:
                try:
                    self.analyzer.analyze_paper(paper_data)
                    learning_results["papers_learned_from"] += 1
                except Exception as e:
                    print(f"   ⚠️ Error analyzing paper: {e}")
            
            # Update memory directly
            self._update_memory_from_result(result)
        
        # Update topics covered
        field = self._extract_field_from_query(query)
        topics = self.memory.get("what_i_know", {}).get("topics_covered", [])
        if field not in topics:
            topics.append(field)
            self.memory["what_i_know"]["topics_covered"] = topics
        
        # Log learning
        self._log_learning(learning_results)
        
        # Save memory
        self._save_memory()
        learning_results["memory_updated"] = True
        
        print(f"   ✅ Learned from {learning_results['papers_learned_from']} papers")
        
        return learning_results
    
    def _update_memory_from_result(self, result: Dict):
        """Update memory directly from a search result"""
        # Ensure what_i_read structure exists
        if "what_i_read" not in self.memory:
            self.memory["what_i_read"] = {"total_papers_read": 0, "papers": [], "by_field": {}, "by_year": {}}
        
        what_read = self.memory["what_i_read"]
        what_read["total_papers_read"] = what_read.get("total_papers_read", 0) + 1
        
        # Add paper to list
        paper_entry = {
            "title": result.get("title", "Unknown"),
            "year": result.get("year", 2024),
            "journal": result.get("journal", "Unknown"),
            "citations": result.get("citations", 0),
            "abstract": result.get("abstract", "")[:200],
            "learned_at": datetime.now().isoformat()
        }
        
        if "papers" not in what_read:
            what_read["papers"] = []
        what_read["papers"].append(paper_entry)
        
        # Update by field
        field = self._extract_field_from_result(result)
        if "by_field" not in what_read:
            what_read["by_field"] = {}
        if field not in what_read["by_field"]:
            what_read["by_field"][field] = []
        what_read["by_field"][field].append(result.get("title", "Unknown"))
        
        # Update by year
        year = result.get("year", 2024)
        if "by_year" not in what_read:
            what_read["by_year"] = {}
        if year not in what_read["by_year"]:
            what_read["by_year"][year] = []
        what_read["by_year"][year].append(result.get("title", "Unknown"))
        
        self.memory["what_i_read"] = what_read
    
    def _extract_field_from_query(self, query: str) -> str:
        """Extract research field from query"""
        # Common fields
        fields = {
            "education": ["education", "learning", "teaching", "student", "school", "university"],
            "psychology": ["psychology", "mental", "behavior", "cognitive", "therapy"],
            "health": ["health", "medical", "clinical", "patient", "treatment"],
            "technology": ["technology", "digital", "mobile", "computer", "software"],
            "business": ["business", "management", "marketing", "finance", "economy"],
            "social": ["social", "community", "society", "cultural", "policy"]
        }
        
        query_lower = query.lower()
        for field_name, keywords in fields.items():
            if any(kw in query_lower for kw in keywords):
                return field_name
        
        return "General"
    
    def _extract_field_from_result(self, result: Dict) -> str:
        """Extract field from result"""
        title = result.get("title", "")
        return self._extract_field_from_query(title)
    
    def _log_learning(self, results: Dict):
        """Log learning event"""
        log = self.memory.get("learning_history", [])
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": results.get("query", ""),
            "papers_learned": results.get("papers_learned_from", 0),
            "concepts_added": results.get("concepts_added", []),
            "patterns_learned": results.get("patterns_learned", [])
        }
        
        log.append(log_entry)
        
        # Keep only last 100 entries
        if len(log) > 100:
            log = log[-100:]
        
        self.memory["learning_history"] = log
    
    # ═══════════════════════════════════════════════════════════════════════
    # PAPER GENERATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def generate_paper(
        self,
        topic: str,
        paper_type: str = "empirical",
        research_questions: Optional[List[str]] = None,
        use_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a complete research paper based on learned knowledge.
        
        Args:
            topic: The main research topic
            paper_type: Type of paper (empirical, systematic_review, etc.)
            research_questions: List of research questions
            use_rag: Whether to use RAG for relevant knowledge
            
        Returns:
            Dictionary with paper data and file path
        """
        print(f"\n📝 GENERATING PAPER: {topic}")
        print(f"   Type: {paper_type}")
        
        self.current_session.outputs_generated += 1
        
        result = {
            "topic": topic,
            "paper_type": paper_type,
            "generated_at": datetime.now().isoformat(),
            "status": "success",
            "docx_path": None,
            "markdown_content": None
        }
        
        # Get relevant knowledge from RAG
        relevant_knowledge = {}
        if use_rag and self.rag_system:
            try:
                search_results = self.rag_system.search(topic, top_k=10)
                relevant_knowledge = {
                    "similar_papers": [r.get("title", "") for r in search_results],
                    "key_concepts": [r.get("abstract", "")[:100] for r in search_results[:5]]
                }
            except Exception as e:
                print(f"   ⚠️ RAG search failed: {e}")
        
        # Generate paper using generator
        if self.generator:
            try:
                # Generate complete paper
                paper = self.generator.generate_complete_paper(
                    topic=topic,
                    paper_type=paper_type,
                    research_questions=research_questions
                )
                
                # Store paper info
                result["paper"] = paper.to_dict()
                
                # Generate DOCX
                if self.docx_generator:
                    sections = {s.name: s.content for s in paper.sections}
                    docx_path = self.docx_generator.create_paper(
                        title=paper.title,
                        abstract=paper.abstract,
                        keywords=paper.keywords,
                        sections=sections,
                        references=[]
                    )
                    result["docx_path"] = docx_path
                
                # Store markdown content
                result["markdown_content"] = self._paper_to_markdown(paper)
                
            except Exception as e:
                print(f"   ⚠️ Paper generation failed: {e}")
                result["status"] = "error"
                result["error"] = str(e)
        
        # Update memory
        self._update_memory_written(result)
        
        # Log output
        self._log_output(result)
        
        print(f"   ✅ Paper generated successfully")
        if result.get("docx_path"):
            print(f"   📄 DOCX saved: {result['docx_path']}")
        
        return result
    
    def _paper_to_markdown(self, paper) -> str:
        """Convert paper object to markdown format"""
        md = []
        
        # Title
        md.append(f"# {paper.title}")
        md.append("")
        
        # Abstract
        md.append("## Abstract")
        md.append(paper.abstract)
        md.append("")
        md.append(f"**Keywords:** {', '.join(paper.keywords)}")
        md.append("")
        
        # Sections
        for section in paper.sections:
            if section.name == "references":
                md.append(f"\n## {section.title}")
            else:
                md.append(f"\n## {section.title}")
            md.append(section.content)
            md.append("")
        
        return "\n".join(md)
    
    def _update_memory_written(self, result: Dict):
        """Update memory with generated paper"""
        what_wrote = self.memory.get("what_i_wrote", {})
        what_wrote["total_outputs_generated"] += 1
        
        paper_entry = {
            "title": result.get("paper", {}).get("title", "Generated Paper"),
            "topic": result.get("topic", ""),
            "paper_type": result.get("paper_type", "empirical"),
            "generated_at": result.get("generated_at", ""),
            "docx_path": result.get("docx_path", ""),
            "status": result.get("status", "unknown")
        }
        
        what_wrote["full_articles"].append(paper_entry)
        
        # Update intentions
        what_intend = self.memory.get("what_i_intend_to_write", {})
        if result["topic"] not in what_intend.get("active_projects", []):
            what_intend["active_projects"].append(result["topic"])
        
        self.memory["what_i_wrote"] = what_wrote
        self.memory["what_i_intend_to_write"] = what_intend
        self._save_memory()
    
    def _log_output(self, result: Dict):
        """Log output generation"""
        # This could log to a separate file if needed
        pass
    
    # ═══════════════════════════════════════════════════════════════════════
    # SYSTEMATIC REVIEW GENERATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def generate_systematic_review(
        self,
        topic: str,
        num_studies: int = 30,
        use_rag: bool = True
    ) -> Dict[str, Any]:
        """Generate a systematic review paper"""
        print(f"\n📝 GENERATING SYSTEMATIC REVIEW: {topic}")
        
        result = {
            "topic": topic,
            "paper_type": "systematic_review",
            "num_studies": num_studies,
            "generated_at": datetime.now().isoformat(),
            "status": "success",
            "docx_path": None
        }
        
        # Generate systematic review
        if self.generator:
            try:
                paper = self.generator.generate_systematic_review(
                    topic=topic,
                    num_studies=num_studies
                )
                
                result["paper"] = paper.to_dict()
                
                # Generate DOCX
                if self.docx_generator:
                    sections = {s.name: s.content for s in paper.sections}
                    docx_path = self.docx_generator.create_systematic_review(
                        title=paper.title,
                        abstract=paper.abstract,
                        keywords=paper.keywords,
                        sections=sections,
                        references=[],
                        num_studies=num_studies
                    )
                    result["docx_path"] = docx_path
                
            except Exception as e:
                print(f"   ⚠️ Systematic review generation failed: {e}")
                result["status"] = "error"
                result["error"] = str(e)
        
        self._update_memory_written(result)
        
        print(f"   ✅ Systematic review generated")
        
        return result
    
    # ═══════════════════════════════════════════════════════════════════════
    # KNOWLEDGE RETRIEVAL
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_knowledge_summary(self) -> Dict[str, Any]:
        """Get comprehensive knowledge summary"""
        what_read = self.memory.get("what_i_read", {})
        what_wrote = self.memory.get("what_i_wrote", {})
        what_know = self.memory.get("what_i_know", {})
        what_intend = self.memory.get("what_i_intend_to_write", {})
        
        return {
            "papers_analyzed": what_read.get("total_papers_read", 0),
            "papers_generated": what_wrote.get("total_outputs_generated", 0),
            "concepts_learned": len(what_know.get("key_concepts", {})),
            "research_methods": what_know.get("research_methods", []),
            "topics_covered": what_know.get("topics_covered", []),
            "active_projects": what_intend.get("active_projects", []),
            "fields_learned": list(what_read.get("by_field", {}).keys()),
            "years_covered": list(what_read.get("by_year", {}).keys()),
            "session_stats": {
                "queries": self.current_session.queries_executed,
                "papers_analyzed": self.current_session.papers_analyzed,
                "outputs_generated": self.current_session.outputs_generated,
                "topics_covered": self.current_session.topics_covered
            }
        }
    
    def get_style_profile(self, paper_type: str = "empirical") -> Dict[str, Any]:
        """Get style profile for a paper type"""
        if self.analyzer:
            return self.analyzer.generate_style_profile(paper_type)
        
        return {
            "paper_type": paper_type,
            "sections": ["abstract", "introduction", "literature_review", "methodology", "results", "discussion", "conclusion", "references"],
            "formatting": {
                "citation_style": "APA 7th",
                "font": "Times New Roman 12pt",
                "spacing": "Double",
                "margins": "1 inch"
            }
        }
    
    def search_knowledge(self, query: str) -> Dict[str, Any]:
        """Search the learned knowledge base"""
        results = {
            "query": query,
            "matching_papers": [],
            "matching_concepts": [],
            "matching_methods": []
        }
        
        # Search in papers read
        what_read = self.memory.get("what_i_read", {})
        for paper in what_read.get("papers", []):
            title = paper.get("title", "").lower()
            if query.lower() in title or query.lower() in paper.get("abstract", "").lower():
                results["matching_papers"].append(paper)
        
        # Search in concepts
        what_know = self.memory.get("what_i_know", {})
        concepts = what_know.get("key_concepts", {})
        for concept_name, concept_data in concepts.items():
            if query.lower() in concept_name.lower():
                results["matching_concepts"].append({
                    "name": concept_name,
                    "data": concept_data
                })
        
        # Search in methods
        methods = what_know.get("research_methods", [])
        for method in methods:
            if query.lower() in method.lower():
                results["matching_methods"].append(method)
        
        return results
    
    # ═══════════════════════════════════════════════════════════════════════
    # CONVENIENCE METHODS
    # ═══════════════════════════════════════════════════════════════════════
    
    def learn_and_generate(
        self,
        topic: str,
        search_results: List[Dict],
        paper_type: str = "empirical",
        generate_docx: bool = True
    ) -> Dict[str, Any]:
        """
        Complete workflow: Learn from search results and generate paper.
        
        This is the main method that ties everything together.
        """
        print("\n" + "="*70)
        print("🔄 LEARN AND GENERATE WORKFLOW")
        print("="*70)
        
        # Step 1: Learn from search results
        learning_results = self.learn_from_search(topic, search_results)
        
        # Step 2: Generate paper
        generation_results = self.generate_paper(
            topic=topic,
            paper_type=paper_type,
            use_rag=True
        )
        
        # Combine results
        workflow_results = {
            "topic": topic,
            "learning": learning_results,
            "generation": generation_results,
            "status": "complete" if generation_results.get("status") == "success" else "partial"
        }
        
        print("\n" + "="*70)
        print("✅ WORKFLOW COMPLETE")
        print(f"   Papers learned from: {learning_results['papers_learned_from']}")
        print(f"   Paper generated: {generation_results.get('status') == 'success'}")
        print("="*70)
        
        return workflow_results
    
    def get_system_capabilities(self) -> Dict[str, Any]:
        """Get system capabilities summary"""
        return {
            "components": {
                "paper_analyzer": ANALYZER_AVAILABLE,
                "paper_generator": GENERATOR_AVAILABLE,
                "scopus_docx": DOCX_AVAILABLE,
                "rag_system": RAG_AVAILABLE
            },
            "memory_stats": {
                "papers_in_memory": self.memory.get("what_i_read", {}).get("total_papers_read", 0),
                "articles_generated": self.memory.get("what_i_wrote", {}).get("total_outputs_generated", 0),
                "concepts_learned": len(self.memory.get("what_i_know", {}).get("key_concepts", {})),
                "sessions_tracked": len(self.memory.get("session_history", []))
            },
            "supported_paper_types": [
                "empirical",
                "systematic_review",
                "meta_analysis",
                "qualitative",
                "quantitative_survey",
                "experimental",
                "case_study"
            ],
            "output_formats": ["DOCX", "Markdown"],
            "citation_styles": ["APA 7th"]
        }


# ═══════════════════════════════════════════════════════════════════════════
# STANDALONE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def initialize_system(workspace_dir: str = ".") -> AcademicIntelligenceSystem:
    """Initialize the complete academic intelligence system"""
    return AcademicIntelligenceSystem(workspace_dir)


def learn_from_search(query: str, results: List[Dict]) -> Dict[str, Any]:
    """Standalone function to learn from search results"""
    system = AcademicIntelligenceSystem()
    return system.learn_from_search(query, results)


def generate_paper(
    topic: str,
    paper_type: str = "empirical",
    research_questions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Standalone function to generate a paper"""
    system = AcademicIntelligenceSystem()
    return system.generate_paper(topic, paper_type, research_questions)


def learn_and_generate(
    topic: str,
    search_results: List[Dict],
    paper_type: str = "empirical"
) -> Dict[str, Any]:
    """Standalone function for complete learn and generate workflow"""
    system = AcademicIntelligenceSystem()
    return system.learn_and_generate(topic, search_results, paper_type)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🧠 RESEARCH HUNTER - ACADEMIC INTELLIGENCE SYSTEM")
    print("="*70)
    print()
    
    # Initialize system
    system = AcademicIntelligenceSystem()
    
    # Show capabilities
    print("\n🎯 System Capabilities:")
    caps = system.get_system_capabilities()
    
    print("\n   Components:")
    for component, available in caps["components"].items():
        status = "✅" if available else "❌"
        print(f"   {status} {component}")
    
    print(f"\n   Supported paper types: {len(caps['supported_paper_types'])}")
    print(f"   Output formats: {caps['output_formats']}")
    print(f"   Citation styles: {caps['citation_styles']}")
    
    print("\n" + "="*70)
    print("💡 USAGE EXAMPLES")
    print("="*70)
    print("""
# Initialize the system
from learning_integration import initialize_system
system = initialize_system()

# Learn from search results
results = system.learn_from_search("mobile learning in education", search_results)

# Generate a paper
paper = system.generate_paper(
    topic="Mobile learning effectiveness",
    paper_type="quantitative_survey"
)

# Complete workflow: Learn and Generate
workflow = system.learn_and_generate(
    topic="Digital learning in Libya",
    search_results=search_results,
    paper_type="empirical"
)

# Get knowledge summary
summary = system.get_knowledge_summary()

# Search learned knowledge
knowledge = system.search_knowledge("learning outcomes")
""")