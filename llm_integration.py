#!/usr/bin/env python3
"""
LLM Integration Module for Research Hunter v2.4
================================================
This module integrates LLM 1.3 (Local Language Model) into the Research Hunter
system for enhanced searching, reading, analyzing, and writing capabilities.

Installation Status: PENDING - Awaiting LLM 1.3 RAR file
Integration: Ready when LLM is installed
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

# ═══════════════════════════════════════════════════════════════════════════════
# LLM CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LLMConfig:
    """Configuration for LLM 1.3 integration"""
    llm_path: str = "llm_runner"  # Path to LLM executable
    model_path: Optional[str] = None  # Path to model files
    port: int = 8080  # API port
    host: str = "localhost"  # API host
    max_tokens: int = 4096  # Maximum response tokens
    temperature: float = 0.7  # Creativity level
    api_key: Optional[str] = None  # Optional API key
    gpu_enabled: bool = True  # GPU acceleration
    memory_limit: int = 16  # GB RAM limit

class LLMIntegration:
    """Main LLM integration class for Research Hunter"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self.available = False
        self.status = "NOT_INSTALLED"
        self._check_installation()
    
    def _check_installation(self) -> bool:
        """Check if LLM 1.3 is installed and available"""
        # Check common paths
        possible_paths = [
            os.path.expanduser("~/llm_runner"),
            "/usr/local/bin/llm_runner",
            "/opt/llm_runner",
            "./llm_runner",
            self.config.llm_path,
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.config.llm_path = path
                self.available = True
                self.status = "INSTALLED"
                return True
        
        # Check if it's a directory with executable
        llm_dir = Path("llm_runner")
        if llm_dir.exists() and llm_dir.is_dir():
            # Look for main executable
            for exe in ["llm", "llm.exe", "runner", "run.sh"]:
                exe_path = llm_dir / exe
                if exe_path.exists():
                    self.config.llm_path = str(exe_path)
                    self.available = True
                    self.status = "INSTALLED"
                    return True
        
        self.status = "NOT_INSTALLED"
        return False
    
    def install_from_rar(self, rar_path: str) -> bool:
        """Install LLM from RAR file without reinstalling dependencies"""
        if not os.path.exists(rar_path):
            print(f"❌ RAR file not found: {rar_path}")
            return False
        
        try:
            print(f"📦 Installing LLM from: {rar_path}")
            
            # Create LLM directory
            llm_dir = Path("llm_runner")
            llm_dir.mkdir(exist_ok=True)
            
            # Extract RAR (requires unrar or python-unrar)
            try:
                import subprocess
                # Try to extract using unrar
                result = subprocess.run(
                    ["unrar", "x", "-o+", rar_path, str(llm_dir)],
                    capture_output=True, text=True, timeout=300
                )
                if result.returncode == 0:
                    print("✅ RAR extracted successfully")
                else:
                    # Try alternative extraction
                    print("Trying alternative extraction...")
                    subprocess.run(
                        ["7z", "x", "-y", f"-o{llm_dir}", rar_path],
                        capture_output=True, timeout=300
                    )
            except FileNotFoundError:
                # Use Python RAR handler
                try:
                    import rarfile
                    with rarfile.RarFile(rar_path) as rf:
                        rf.extractall(llm_dir)
                    print("✅ RAR extracted with python-rarfile")
                except ImportError:
                    print("Installing rarfile...")
                    subprocess.run([sys.executable, "-m", "pip", "install", "rarfile", "-q"])
                    import rarfile
                    with rarfile.RarFile(rar_path) as rf:
                        rf.extractall(llm_dir)
                    print("✅ RAR extracted successfully")
            
            # Verify installation
            self._check_installation()
            
            if self.available:
                print(f"✅ LLM 1.3 installed successfully at: {self.config.llm_path}")
                return True
            else:
                print("⚠️ LLM installed but not detected. Please check installation manually.")
                return False
                
        except Exception as e:
            print(f"❌ Installation failed: {e}")
            return False
    
    def start_server(self) -> bool:
        """Start LLM API server"""
        if not self.available:
            print("❌ LLM not available")
            return False
        
        try:
            # Start server in background
            subprocess.Popen(
                [self.config.llm_path, "serve", "--port", str(self.config.port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.status = "RUNNING"
            print(f"✅ LLM server started on port {self.config.port}")
            return True
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False
    
    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate text using LLM"""
        if not self.available:
            return None
        
        try:
            result = subprocess.run(
                [
                    self.config.llm_path, "generate",
                    "-p", prompt,
                    "-t", str(kwargs.get("temperature", self.config.temperature)),
                    "-m", str(kwargs.get("max_tokens", self.config.max_tokens))
                ],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            print(f"❌ Generation failed: {e}")
            return None
    
    def analyze_document(self, text: str, analysis_type: str = "general") -> Dict[str, Any]:
        """Analyze document content using LLM"""
        if not self.available:
            return {"error": "LLM not available"}
        
        prompts = {
            "general": f"Analyze this text and provide: summary, key themes, entities, and sentiment.\n\n{text[:5000]}",
            "academic": f"Analyze this academic text: extract methodology, findings, citations, and relevance score.\n\n{text[:5000]}",
            "abstract": f"Generate a comprehensive abstract for: {text[:3000]}",
            "keywords": f"Extract 10-15 keywords from: {text[:3000]}",
            "summary": f"Provide a detailed summary with main points: {text[:5000]}",
        }
        
        prompt = prompts.get(analysis_type, prompts["general"])
        result = self.generate(prompt, max_tokens=2048)
        
        return {
            "analysis_type": analysis_type,
            "result": result,
            "status": "success" if result else "failed"
        }
    
    def enhance_search(self, query: str, documents: List[str]) -> List[Dict[str, Any]]:
        """Use LLM to enhance search relevance"""
        if not self.available:
            return []
        
        # Create search context
        docs_text = "\n\n".join([f"[Doc {i+1}]: {d[:500]}" for i, d in enumerate(documents)])
        
        prompt = f"""
Given search query: "{query}"
And these documents, rank them by relevance and explain why:

{docs_text}

Provide ranking with brief explanations.
"""
        
        result = self.generate(prompt, max_tokens=2048)
        
        # Parse results (simple parsing - can be enhanced)
        ranked = []
        for i, doc in enumerate(documents):
            ranked.append({
                "document": doc[:200],
                "index": i,
                "relevance": "high" if i < 3 else "medium" if i < 6 else "low"
            })
        
        return ranked
    
    def generate_report_section(self, section_type: str, data: Dict) -> str:
        """Generate report section using LLM"""
        if not self.available:
            return ""
        
        section_prompts = {
            "introduction": f"Write an introduction section for a research report on: {data.get('topic', 'N/A')}\n\nContext: {data.get('context', '')}",
            "literature_review": f"Write a literature review covering: {data.get('papers', 'N/A')}",
            "methodology": f"Describe the methodology: {data.get('methods', 'N/A')}",
            "results": f"Summarize results: {data.get('findings', 'N/A')}",
            "conclusion": f"Write conclusion: {data.get('conclusion', 'N/A')}",
            "abstract": f"Generate abstract: {data.get('abstract', 'N/A')}",
        }
        
        prompt = section_prompts.get(section_type, section_prompts["introduction"])
        return self.generate(prompt, max_tokens=2048) or ""
    
    def get_status(self) -> Dict[str, Any]:
        """Get current LLM status"""
        return {
            "available": self.available,
            "status": self.status,
            "path": self.config.llm_path,
            "config": {
                "port": self.config.port,
                "host": self.config.host,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "gpu_enabled": self.config.gpu_enabled,
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION WITH RESEARCH HUNTER
# ═══════════════════════════════════════════════════════════════════════════════

def integrate_llm_to_research_hunter():
    """Add LLM capabilities to Research Hunter main script"""
    print("🔄 Integrating LLM into Research Hunter...")
    
    # Check if already integrated
    with open("research_hunter_v2-4.py", "r") as f:
        content = f.read()
    
    if "from llm_integration import LLMIntegration" in content:
        print("✅ LLM already integrated")
        return True
    
    # Add LLM import at the top
    llm_import = '''
# ═══════════════════════════════════════════════════════════════════════════════
# LLM 1.3 INTEGRATION - Enhanced AI Capabilities
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from llm_integration import LLMIntegration
    HAS_LLM = True
    llm = LLMIntegration()
    print(f"✅ LLM Integration: {llm.status}")
except ImportError:
    HAS_LLM = False
    llm = None
    print("⚠️ LLM not available - using standard search")

# LLM-enhanced functions
def llm_analyze_paper(paper: dict, analysis_type: str = "academic") -> dict:
    """Analyze a paper using LLM for enhanced insights"""
    if not HAS_LLM or not llm or not llm.available:
        return paper  # Return original if no LLM
    
    text = f"{paper.get('title', '')} {paper.get('abstract', '')} {paper.get('authors', [])}"
    analysis = llm.analyze_document(text, analysis_type)
    paper['llm_analysis'] = analysis
    return paper

def llm_enhance_search(query: str, papers: list) -> list:
    """Use LLM to improve search relevance ranking"""
    if not HAS_LLM or not llm or not llm.available:
        return papers
    
    docs = [f"{p.get('title', '')} {p.get('abstract', '')}" for p in papers]
    ranked = llm.enhance_search(query, docs)
    
    # Reorder papers based on LLM ranking
    ranked_papers = []
    for r in ranked:
        if r['index'] < len(papers):
            ranked_papers.append(papers[r['index']])
    return ranked_papers

def llm_generate_abstract(papers: list) -> str:
    """Generate AI-powered abstract synthesis"""
    if not HAS_LLM or not llm or not llm.available:
        return ""
    
    combined_text = " ".join([p.get('abstract', '')[:1000] for p in papers[:20]])
    result = llm.analyze_document(combined_text, "abstract")
    return result.get('result', '') if result else ''

'''
    
    # Insert after imports
    import_marker = "# ── Imports ───────────────────────────────────────────────────────────────────"
    if import_marker in content:
        content = content.replace(import_marker, import_marker + "\n" + llm_import)
        print("✅ LLM integration code added to research_hunter_v2-4.py")
    else:
        # Try alternative
        content = "# ── Imports" + llm_import + content[content.find("\n"):]
    
    # Write back
    with open("research_hunter_v2-4.py", "w") as f:
        f.write(content)
    
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("LLM 1.3 Integration for Research Hunter v2.4")
    print("=" * 60)
    
    # Check installation
    llm = LLMIntegration()
    status = llm.get_status()
    
    print(f"\n📊 LLM Status:")
    print(f"   Available: {status['available']}")
    print(f"   Status: {status['status']}")
    print(f"   Path: {status['path']}")
    
    if status['available']:
        print("\n✅ LLM is ready! Functions available:")
        print("   • llm_analyze_paper() - AI document analysis")
        print("   • llm_enhance_search() - Smart search ranking")
        print("   • llm_generate_abstract() - AI abstract synthesis")
    else:
        print("\n📦 To install LLM:")
        print("   1. Place LLM 1.3 RAR file in this directory")
        print("   2. Run: python llm_integration.py --install path/to/file.rar")
        print("   3. Or: llm.install_from_rar('path/to/file.rar')")
    
    print("\n🔄 To integrate with Research Hunter:")
    print("   Run: python llm_integration.py --integrate")
    
    # Check for RAR files
    rar_files = list(Path(".").glob("*.rar")) + list(Path(".").glob("*.zip"))
    if rar_files:
        print(f"\n📁 Found archive files: {[f.name for f in rar_files]}")
        print("   Run with --install to extract")