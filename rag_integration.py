#!/usr/bin/env python3
"""
RAG MEMORY INTEGRATION for Research Hunter v2.4
==============================================
Integrates the bulletproof RAG Memory System into Research Hunter

Usage:
    from rag_integration import ResearchHunterRAG
    system = ResearchHunterRAG()
    result = system.generate_report("digital learning Libya", num_papers=100)
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import RAG system
try:
    from rag_memory_system import (
        ResearchHunterRAG,
        PaperDocument,
        RAGConfig,
        LLMClient,
        MemorySystem,
        RAGPipeline,
        KnowledgeGraph,
        HierarchicalSummarizer
    )
    RAG_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ RAG module not available: {e}")
    RAG_AVAILABLE = False


def integrate_rag_to_research_hunter():
    """Add RAG capabilities to Research Hunter main script"""
    if not RAG_AVAILABLE:
        print("❌ Cannot integrate - RAG module not available")
        return False
    
    try:
        with open("research_hunter_v2-4.py", "r") as f:
            content = f.read()
        
        if "from rag_integration import" in content:
            print("✅ RAG already integrated")
            return True
        
        # Add RAG import and initialization
        rag_code = '''
# ═══════════════════════════════════════════════════════════════════════════════
# RAG MEMORY SYSTEM - Bulletproof 6000+ Papers Analysis
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from rag_integration import ResearchHunterRAG, PaperDocument
    rag_system = ResearchHunterRAG()
    HAS_RAG = rag_system is not None
    if HAS_RAG:
        print(f"✅ RAG System: {rag_system.get_all_stats()['rag']['total_papers']} papers indexed")
    else:
        print("⚠️ RAG initialization returned None")
        HAS_RAG = False
except ImportError as e:
    rag_system = None
    HAS_RAG = False
    print(f"⚠️ RAG module not available: {e}")

# RAG Functions
def rag_index_papers(papers: list) -> dict:
    """Index papers into RAG system for semantic search"""
    if not HAS_RAG or not rag_system:
        return {"error": "RAG not available"}
    return rag_system.index_papers(papers)

def rag_search(query: str, use_memory: bool = True) -> dict:
    """Semantic search with memory context"""
    if not HAS_RAG or not rag_system:
        return {"error": "RAG not available"}
    return rag_system.search(query, use_memory)

def rag_generate_report(topic: str, num_papers: int = 100) -> dict:
    """Generate comprehensive research report with RAG"""
    if not HAS_RAG or not rag_system:
        return {"error": "RAG not available"}
    return rag_system.generate_report(topic, num_papers)

def rag_get_stats() -> dict:
    """Get RAG system statistics"""
    if not HAS_RAG or not rag_system:
        return {"error": "RAG not available"}
    return rag_system.get_all_stats()

def rag_test() -> dict:
    """Run RAG system tests"""
    if not HAS_RAG or not rag_system:
        return {"error": "RAG not available"}
    return rag_system.test_all()

'''
        
        # Find insertion point
        marker = "# ═══════════════════════════════════════════════════════════════════════════════\n# LLM 1.3 INTEGRATION"
        if marker in content:
            content = content.replace(marker, marker + "\n" + rag_code)
        else:
            # Try alternative
            import_marker = "# ── Imports ───────────────────────────────────────────────────────────────────"
            content = content.replace(import_marker, import_marker + "\n" + rag_code)
        
        with open("research_hunter_v2-4.py", "w") as f:
            f.write(content)
        
        print("✅ RAG integration code added to research_hunter_v2-4.py")
        return True
        
    except Exception as e:
        print(f"❌ Integration failed: {e}")
        return False


if __name__ == "__main__":
    print("="*70)
    print("🔬 RAG MEMORY SYSTEM INTEGRATION FOR RESEARCH HUNTER v2.4")
    print("="*70)
    print()
    
    if not RAG_AVAILABLE:
        print("❌ RAG module not available. Run: python rag_memory_system.py first")
        sys.exit(1)
    
    # Initialize system
    print("🚀 Initializing RAG Memory System...")
    system = ResearchHunterRAG()
    
    print("\n📊 System Statistics:")
    stats = system.get_all_stats()
    for component, data in stats.items():
        print(f"   {component}: {data}")
    
    print("\n🔄 To integrate with Research Hunter:")
    print("   Run: python rag_integration.py --integrate")
    
    print("\n🧪 To test RAG system:")
    print("   results = system.test_all()")
    
    print("\n📋 Available Functions:")
    print("   system.index_papers(papers)     # Index 6000+ papers")
    print("   system.search(query)          # Semantic search with memory")
    print("   system.generate_report(topic) # Generate research report")
    print("   system.get_all_stats()        # Get system statistics")