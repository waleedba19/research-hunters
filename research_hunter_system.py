"""
research_hunter_system.py
=========================
Main system integrator for Research Hunter v2-4

Connects all components:
- Ollama (qwen2.5vl:3b) - AI Brain
- Universal Document Processor - Handles all document types
- Academic Learning Database - Learns patterns
- Playwright - Web scraping and dynamic content
- GitHub Workflow Integration - Form-based configuration

This is the CENTRAL HUB that orchestrates everything.
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# Import our modules
try:
    from universal_document_processor import UniversalDocumentProcessor, OllamaClient
    from academic_learning_database import AcademicLearningDatabase, WorkflowConfig
    HAS_DOC_PROCESSOR = True
except ImportError as e:
    print(f"Warning: Document processor not available: {e}")
    HAS_DOC_PROCESSOR = False

# Try to import Playwright
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# Try to import research hunter modules
try:
    from research_hunter_v2_4 import *
    HAS_RESEARCH_HUNTER = True
except ImportError:
    HAS_RESEARCH_HUNTER = False


@dataclass
class SystemConfig:
    """Central configuration for the entire system"""
    # Ollama settings
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5vl:3b"
    
    # Document processing
    supported_formats: List[str] = None
    
    # Learning settings
    learn_from_papers: bool = True
    min_papers_for_learning: int = 5
    
    # Output settings
    output_dir: str = "./research_output"
    save_intermediate: bool = True
    
    def __post_init__(self):
        if self.supported_formats is None:
            self.supported_formats = [
                ".pdf", ".docx", ".doc", ".odt", ".rtf",
                ".epub", ".mobi", ".html", ".htm", ".txt",
                ".png", ".jpg", ".jpeg", ".tiff", ".bmp",
                ".xlsx", ".xls", ".pptx", ".ppt"
            ]


class ResearchHunterSystem:
    """
    Main system orchestrator for Research Hunter v2-4
    
    This class coordinates:
    1. Ollama AI (qwen2.5vl:3b) - The brain
    2. Document Processing - All file types
    3. Learning Database - Pattern storage
    4. Web Scraping - Playwright integration
    5. Paper Generation - AI-powered writing
    """
    
    def __init__(self, config: SystemConfig = None):
        self.config = config or SystemConfig()
        
        # Initialize components
        self.ollama = None
        self.document_processor = None
        self.learning_db = None
        self.web_scraper = None
        
        # Status tracking
        self.status = {
            "ollama": False,
            "document_processor": False,
            "learning_db": False,
            "playwright": False
        }
        
        # Initialize all components
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all system components"""
        print("\n" + "=" * 60)
        print("🚀 INITIALIZING RESEARCH HUNTER SYSTEM")
        print("=" * 60)
        
        # 1. Initialize Ollama
        print("\n📡 Initializing Ollama...")
        self.ollama = OllamaClient(base_url=self.config.ollama_url)
        if self.ollama.available:
            print(f"   ✅ Ollama connected: {self.config.ollama_model}")
            self.status["ollama"] = True
        else:
            print("   ⚠️ Ollama not available - AI features disabled")
        
        # 2. Initialize Document Processor
        if HAS_DOC_PROCESSOR:
            print("\n📄 Initializing Document Processor...")
            try:
                self.document_processor = UniversalDocumentProcessor()
                print(f"   ✅ Document processor ready")
                print(f"   ✅ Supported formats: {len(self.config.supported_formats)} types")
                self.status["document_processor"] = True
            except Exception as e:
                print(f"   ⚠️ Document processor error: {e}")
        
        # 3. Initialize Learning Database
        print("\n🧠 Initializing Learning Database...")
        try:
            self.learning_db = AcademicLearningDatabase()
            stats = self.learning_db.get_statistics()
            print(f"   ✅ Database ready: {stats.get('papers', 0)} papers stored")
            print(f"   ✅ Study types: {stats.get('study_types', 0)}")
            self.status["learning_db"] = True
        except Exception as e:
            print(f"   ⚠️ Database error: {e}")
        
        # 4. Initialize Playwright
        if HAS_PLAYWRIGHT:
            print("\n🌐 Initializing Playwright...")
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    browser.close()
                print("   ✅ Playwright ready")
                self.status["playwright"] = True
            except Exception as e:
                print(f"   ⚠️ Playwright error: {e}")
        else:
            print("\n🌐 Playwright not installed - web scraping limited")
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 SYSTEM STATUS")
        print("=" * 60)
        for component, status in self.status.items():
            symbol = "✅" if status else "❌"
            print(f"   {symbol} {component.capitalize()}")
        print("=" * 60)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DOCUMENT PROCESSING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def process_document(self, file_path: str) -> Optional[Dict]:
        """Process any document type"""
        if not self.document_processor:
            print("Document processor not available")
            return None
        
        print(f"\n📄 Processing: {Path(file_path).name}")
        result = self.document_processor.process(file_path)
        
        if result.full_text:
            print(f"   ✅ Extracted {len(result.full_text)} characters")
            print(f"   ✅ Sections: {list(result.sections.keys())}")
            
            # Learn from this document if learning is enabled
            if self.config.learn_from_papers and self.learning_db:
                field = self._detect_field_from_content(result.full_text)
                self.learning_db.learn_from_papers(
                    [{"text_content": result.full_text}],
                    field=field
                )
        
        return {
            "text": result.full_text,
            "sections": result.sections,
            "metadata": asdict(result.metadata),
            "tables": result.tables,
            "processing_time": result.processing_time
        }
    
    def process_directory(self, dir_path: str, recursive: bool = True) -> List[Dict]:
        """Process all documents in a directory"""
        results = []
        dir_path = Path(dir_path)
        
        pattern = "**/*" if recursive else "*"
        for file_path in dir_path.glob(pattern):
            if file_path.suffix.lower() in self.config.supported_formats:
                try:
                    result = self.process_document(str(file_path))
                    if result:
                        result["file_path"] = str(file_path)
                        results.append(result)
                except Exception as e:
                    print(f"   ⚠️ Error processing {file_path}: {e}")
        
        return results
    
    def _detect_field_from_content(self, text: str) -> str:
        """Detect academic field from content"""
        if not self.ollama or not self.ollama.available:
            return "general"
        
        prompt = f"""Based on this academic text, identify the main academic field.
Return ONLY the field name, one of: linguistics, education, psychology, sociology, 
computer_science, medicine, engineering, economics, business, history, philosophy,
anthropology, political_science, literature, or general.

Text preview:
{text[:1000]}"""
        
        result = self.ollama.generate(prompt, temperature=0.1)
        result = result.strip().lower()
        
        valid_fields = ["linguistics", "education", "psychology", "sociology", 
                       "computer_science", "medicine", "engineering", "economics",
                       "business", "history", "philosophy", "anthropology",
                       "political_science", "literature", "general"]
        
        for field in valid_fields:
            if field in result:
                return field
        
        return "general"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WEB SCRAPING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def scrape_website(self, url: str, wait_for: str = None) -> Dict:
        """Scrape a website using Playwright"""
        if not self.status["playwright"]:
            return {"error": "Playwright not available", "url": url}
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                print(f"\n🌐 Scraping: {url}")
                page.goto(url, wait_until="networkidle", timeout=30000)
                
                if wait_for:
                    page.wait_for_selector(wait_for, timeout=10000)
                
                text = page.inner_text("body")
                html = page.content()
                title = page.title()
                
                browser.close()
                
                return {
                    "url": url,
                    "title": title,
                    "text": text,
                    "html": html,
                    "success": True
                }
        except Exception as e:
            return {"error": str(e), "url": url, "success": False}
    
    def search_web_intelligent(self, query: str, num_results: int = 10) -> List[Dict]:
        """Intelligently search the web using Playwright"""
        results = []
        
        # Use DuckDuckGo for search
        search_url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}"
        
        if not self.status["playwright"]:
            return results
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                page.goto(search_url, wait_until="networkidle", timeout=30000)
                
                # Wait for results
                page.wait_for_selector(".result", timeout=10000)
                
                # Extract results
                for i, result in enumerate(page.query_selector_all(".result")[:num_results]):
                    try:
                        title_elem = result.query_selector(".result__title a")
                        snippet_elem = result.query_selector(".result__snippet")
                        
                        if title_elem:
                            results.append({
                                "title": title_elem.inner_text(),
                                "url": title_elem.get_attribute("href"),
                                "snippet": snippet_elem.inner_text() if snippet_elem else ""
                            })
                    except:
                        continue
                
                browser.close()
        except Exception as e:
            print(f"Search error: {e}")
        
        return results
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PAPER GENERATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def generate_paper(self, config: WorkflowConfig, reference_papers: List[Dict] = None) -> str:
        """Generate a research paper using Ollama"""
        if not self.ollama:
            return "Error: Ollama not available"
        
        print(f"\n📝 Generating paper: {config.research_topic}")
        print(f"   Field: {config.academic_field}")
        print(f"   Type: {config.publication_type}")
        print(f"   Language: {config.language}")
        
        # Generate using learning database
        if self.learning_db and self.ollama.available:
            paper = self.learning_db.generate_research_paper(config, reference_papers)
        else:
            paper = self._generate_basic_paper(config)
        
        print(f"   ✅ Generated {len(paper)} characters")
        return paper
    
    def _generate_basic_paper(self, config: WorkflowConfig) -> str:
        """Basic paper generation without learning database"""
        prompt = f"""Write a complete academic research paper with the following details:

TOPIC: {config.research_topic}
ACADEMIC FIELD: {config.academic_field}
PAPER TYPE: {config.publication_type}
STUDY LEVEL: {config.study_level}
METHODOLOGY: {config.methodology}
LANGUAGE: {config.language}

Include all standard academic sections: Abstract, Introduction, Literature Review, 
Methodology, Results, Discussion, Conclusion, and References.

Write in formal academic style appropriate for {config.academic_field}."""
        
        return self.ollama.generate(prompt, temperature=0.3)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RESEARCH WORKFLOW
    # ═══════════════════════════════════════════════════════════════════════════
    
    def run_research_workflow(self, workflow_config: Dict) -> Dict:
        """
        Run complete research workflow based on GitHub workflow form inputs
        
        Args:
            workflow_config: Dict from GitHub workflow form
            
        Returns:
            Dict with results and generated paper
        """
        print("\n" + "=" * 60)
        print("🔬 RUNNING RESEARCH WORKFLOW")
        print("=" * 60)
        
        # Convert to WorkflowConfig
        config = WorkflowConfig(
            research_topic=workflow_config.get("research_topic", ""),
            academic_field=workflow_config.get("academic_field", "general"),
            publication_type=workflow_config.get("publication_type", "research_article"),
            study_level=workflow_config.get("study_level", "any"),
            methodology=workflow_config.get("methodology", "any"),
            language=workflow_config.get("form_language", "en").split("-")[0].strip(),
            year_range=f"{workflow_config.get('year_from', 'all')}-{workflow_config.get('year_to', 'all')}",
            quartile_filter=workflow_config.get("quartile_filter", "all"),
            search_mode=workflow_config.get("search_mode", "standard"),
            output_format=workflow_config.get("output_format", "all")
        )
        
        results = {
            "config": asdict(config),
            "papers_processed": 0,
            "web_content_scrapped": 0,
            "paper_generated": False,
            "output_path": None
        }
        
        # 1. Search web for relevant content
        if self.status["playwright"]:
            print("\n🔍 Searching web for research materials...")
            web_results = self.search_web_intelligent(
                config.research_topic,
                num_results=5
            )
            results["web_content_scrapped"] = len(web_results)
            print(f"   Found {len(web_results)} web sources")
        
        # 2. Process any documents in input directory
        input_dir = workflow_config.get("input_directory", "./papers")
        if os.path.exists(input_dir):
            print(f"\n📂 Processing documents from {input_dir}...")
            docs = self.process_directory(input_dir)
            results["papers_processed"] = len(docs)
            
            # Learn from processed papers
            if self.learning_db and len(docs) >= self.config.min_papers_for_learning:
                self.learning_db.learn_from_papers(
                    docs,
                    field=config.academic_field,
                    language=config.language
                )
        
        # 3. Generate research paper
        print("\n📝 Generating research paper...")
        paper_content = self.generate_paper(config, reference_papers=None)
        results["paper_generated"] = True
        
        # 4. Save output
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"research_paper_{int(time.time())}.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# {config.research_topic}\n\n")
            f.write(f"**Field:** {config.academic_field}\n")
            f.write(f"**Type:** {config.publication_type}\n")
            f.write(f"**Language:** {config.language}\n")
            f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")
            f.write("---\n\n")
            f.write(paper_content)
        
        results["output_path"] = str(output_file)
        
        print("\n" + "=" * 60)
        print("✅ RESEARCH WORKFLOW COMPLETE")
        print("=" * 60)
        print(f"   Output: {output_file}")
        print(f"   Papers processed: {results['papers_processed']}")
        print(f"   Web sources: {results['web_content_scrapped']}")
        
        return results
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SYSTEM STATUS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_status(self) -> Dict:
        """Get comprehensive system status"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "components": self.status,
            "overall_healthy": all(self.status.values()),
            "config": {
                "ollama_model": self.config.ollama_model,
                "ollama_url": self.config.ollama_url,
                "supported_formats": len(self.config.supported_formats),
                "learn_from_papers": self.config.learn_from_papers
            }
        }
        
        if self.learning_db:
            try:
                db_stats = self.learning_db.get_statistics()
                status["database"] = db_stats
            except:
                pass
        
        return status
    
    def health_check(self) -> bool:
        """Check if system is healthy"""
        # Core components that must be available
        core_components = ["ollama"]
        
        for comp in core_components:
            if not self.status.get(comp, False):
                return False
        
        return True


# ═══════════════════════════════════════════════════════════════════════════
# GITHUB WORKFLOW INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

def run_from_github_workflow():
    """Run system from GitHub workflow inputs"""
    import sys
    
    # Get inputs from environment
    config = {
        "research_topic": os.environ.get("INPUT_RESEARCH_TOPIC", ""),
        "academic_field": os.environ.get("INPUT_ACADEMIC_FIELD", "general"),
        "publication_type": os.environ.get("INPUT_PUBLICATION_TYPE", "research_article"),
        "study_level": os.environ.get("INPUT_STUDY_LEVEL", "any"),
        "methodology": os.environ.get("INPUT_RESEARCH_METHODOLOGY", "any"),
        "form_language": os.environ.get("INPUT_FORM_LANGUAGE", "en"),
        "year_from": os.environ.get("INPUT_YEAR_FROM", "all"),
        "year_to": os.environ.get("INPUT_YEAR_TO", "all"),
        "quartile_filter": os.environ.get("INPUT_QUARTILE_FILTER", "all"),
        "search_mode": os.environ.get("INPUT_SEARCH_MODE", "standard"),
        "output_format": os.environ.get("INPUT_OUTPUT_FORMAT", "all"),
        "input_directory": os.environ.get("INPUT_DIRECTORY", "./papers")
    }
    
    # Initialize system
    system = ResearchHunterSystem()
    
    # Run workflow
    results = system.run_research_workflow(config)
    
    # Output results
    print("\n📊 Workflow Results:")
    print(json.dumps(results, indent=2))
    
    return results


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("🔬 RESEARCH HUNTER v2-4 - SYSTEM INTEGRATOR")
    print("=" * 60)
    
    # Check if running from GitHub workflow
    if os.environ.get("GITHUB_ACTIONS"):
        run_from_github_workflow()
    else:
        # Interactive mode
        system = ResearchHunterSystem()
        
        print("\n" + "=" * 60)
        print("🎯 AVAILABLE COMMANDS")
        print("=" * 60)
        print("   1. Process document")
        print("   2. Generate research paper")
        print("   3. Scrape website")
        print("   4. Run research workflow")
        print("   5. System status")
        print("   6. Exit")
        print("=" * 60)
        
        while True:
            try:
                choice = input("\nEnter choice (1-6): ").strip()
                
                if choice == "1":
                    path = input("Enter document path: ").strip()
                    if path:
                        system.process_document(path)
                
                elif choice == "2":
                    topic = input("Enter research topic: ").strip()
                    if topic:
                        config = WorkflowConfig(
                            research_topic=topic,
                            academic_field="general",
                            publication_type="research_article",
                            study_level="any",
                            methodology="any",
                            language="en",
                            year_range="2020-2026",
                            quartile_filter="all",
                            search_mode="standard",
                            output_format="all"
                        )
                        paper = system.generate_paper(config)
                        print(f"\n{paper[:500]}...")
                
                elif choice == "3":
                    url = input("Enter URL: ").strip()
                    if url:
                        result = system.scrape_website(url)
                        print(f"\n{result.get('text', '')[:500]}...")
                
                elif choice == "4":
                    topic = input("Enter research topic: ").strip()
                    if topic:
                        config = WorkflowConfig(
                            research_topic=topic,
                            academic_field="general",
                            publication_type="research_article",
                            study_level="any",
                            methodology="any",
                            language="en",
                            year_range="2020-2026",
                            quartile_filter="all",
                            search_mode="standard",
                            output_format="all"
                        )
                        system.run_research_workflow({"research_topic": topic})
                
                elif choice == "5":
                    status = system.get_status()
                    print(json.dumps(status, indent=2))
                
                elif choice == "6":
                    print("\n👋 Goodbye!")
                    break
            
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n⚠️ Error: {e}")