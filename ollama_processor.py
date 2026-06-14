#!/usr/bin/env python3
"""
Research Hunter v7 - Ollama Integration for Research Processing
Handles large texts with limited context using chunking and summarization
"""

import os
import json
import base64
import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

# Configuration
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5vl:3b")
CONTEXT_LIMIT = 4000  # tokens (4k context)

@dataclass
class ChunkResult:
    """Result of processing a chunk"""
    chunk_index: int
    summary: str
    key_points: List[str]
    tokens_used: int

@dataclass
class PaperAnalysis:
    """Complete analysis of a research paper"""
    paper_id: str
    title: str
    overall_summary: str
    key_findings: List[str]
    methodology: str
    limitations: str
    future_work: str
    relevance_to_query: float
    chunks_processed: int
    full_text_available: bool

class OllamaProcessor:
    """
    Process research papers using Ollama with limited context
    
    Strategies for 4k context:
    1. Chunking - Split into ~500 token chunks
    2. Summarize each chunk
    3. Synthesize summaries
    4. Track what's processed
    """
    
    def __init__(self, model: str = OLLAMA_MODEL, base_url: str = OLLAMA_URL):
        self.model = model
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
        
    def check_connection(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def generate(self, prompt: str, system: str = "", 
                 max_tokens: int = 500, temperature: float = 0.3) -> str:
        """
        Generate response from Ollama
        
        Args:
            prompt: User prompt
            system: System prompt (instructions)
            max_tokens: Max tokens to generate
            temperature: Creativity (0=exact, 1=creative)
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature
            }
        }
        
        if system:
            payload["system"] = system
        
        try:
            response = requests.post(self.api_url, json=payload, timeout=120)
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                return f"Error: {response.status_code}"
        except Exception as e:
            return f"Connection error: {e}"
    
    def count_tokens(self, text: str) -> int:
        """Rough token count (words * 1.3)"""
        return int(len(text.split()) * 1.3)
    
    def chunk_text(self, text: str, chunk_size: int = 500) -> List[Dict]:
        """
        Split text into manageable chunks
        
        For 4k context:
        - Reserve ~500 tokens for prompt/response
        - Use ~3000 tokens for input chunk
        - ~500 tokens = ~375 words
        """
        words = text.split()
        chunks = []
        
        current_pos = 0
        chunk_index = 0
        
        while current_pos < len(words):
            # Get chunk words
            chunk_words = words[current_pos:current_pos + chunk_size]
            chunk_text = ' '.join(chunk_words)
            
            chunks.append({
                "index": chunk_index,
                "text": chunk_text,
                "tokens": self.count_tokens(chunk_text),
                "start_word": current_pos,
                "end_word": current_pos + len(chunk_words)
            })
            
            current_pos += chunk_size
            chunk_index += 1
        
        return chunks
    
    def summarize_chunk(self, chunk: Dict, purpose: str = "general") -> ChunkResult:
        """
        Summarize a single chunk of text
        
        For 4k context, chunks should be ~500 tokens
        """
        system_prompt = f"""You are a research assistant analyzing academic papers.
Purpose: {purpose}

Instructions:
1. Provide a brief summary (2-3 sentences)
2. List key points (bullet format)
3. Note any important findings or methods

Be concise and focus on essential information."""
        
        prompt = f"""Summarize this section of a research paper:

---BEGIN SECTION---
{chunk['text']}
---END SECTION---

Provide:
1. Summary:
2. Key Points:
3. Important Details:"""
        
        response = self.generate(prompt, system=system_prompt, max_tokens=300)
        
        # Parse response (simple parsing)
        lines = response.split('\n')
        summary = ""
        key_points = []
        
        current_section = ""
        for line in lines:
            if "summary" in line.lower():
                current_section = "summary"
            elif "key point" in line.lower():
                current_section = "key_points"
            elif current_section == "summary" and line.strip():
                summary += line + " "
            elif current_section == "key_points" and line.strip():
                if line.strip().startswith(('-', '*', '•')):
                    key_points.append(line.strip())
        
        return ChunkResult(
            chunk_index=chunk['index'],
            summary=summary.strip() or response[:200],
            key_points=key_points[:5],
            tokens_used=chunk['tokens']
        )
    
    def synthesize_summaries(self, chunk_summaries: List[ChunkResult], 
                           paper_title: str = "") -> str:
        """
        Combine multiple chunk summaries into one coherent summary
        
        This is the key to handling large documents with limited context!
        """
        # Combine all summaries
        combined_text = "\n\n".join([
            f"Section {cs.chunk_index + 1}:\n{cs.summary}\nKey Points: " + 
            "\n".join(cs.key_points) if cs.key_points else "None"
            for cs in chunk_summaries
        ])
        
        prompt = f"""You are synthesizing a comprehensive summary from multiple section summaries.

Paper Title: {paper_title or "Unknown"}

Section Summaries:
{combined_text}

Instructions:
1. Create a coherent overall summary
2. Consolidate key findings (remove duplicates)
3. Identify main themes and contributions
4. Note any contradictions between sections

Provide:
- Overall Summary (2-3 paragraphs)
- Consolidated Key Findings (bullet list)
- Main Themes (3-5 items)"""
        
        return self.generate(prompt, max_tokens=800, temperature=0.3)
    
    def analyze_paper(self, paper_text: str, title: str = "", 
                     query: str = "") -> PaperAnalysis:
        """
        Complete analysis of a research paper
        
        Handles large texts by:
        1. Chunking into ~500 token pieces
        2. Summarizing each chunk
        3. Synthesizing into final analysis
        """
        print(f"📄 Analyzing paper: {title[:50]}...")
        print(f"   Text length: {len(paper_text.split())} words")
        
        # Check if text fits in context
        total_tokens = self.count_tokens(paper_text)
        print(f"   Estimated tokens: {total_tokens}")
        
        if total_tokens <= CONTEXT_LIMIT:
            # Small text - process directly
            print("   📝 Small text - direct analysis")
            return self._analyze_direct(paper_text, title, query)
        else:
            # Large text - use chunking
            print(f"   📑 Large text - chunking into smaller pieces")
            return self._analyze_chunked(paper_text, title, query)
    
    def _analyze_direct(self, text: str, title: str, query: str) -> PaperAnalysis:
        """Analyze a small paper directly (under 4k tokens)"""
        purpose = f"Research query: {query}" if query else "general research"
        
        prompt = f"""Analyze this research paper:

Title: {title or "Untitled"}

---BEGIN PAPER---
{text[:3000]}  # Limit to fit in context
---END PAPER---

{f"User is researching: {query}" if query else ""}

Provide:
1. Summary (2-3 paragraphs)
2. Key Findings (bullet list)
3. Methodology
4. Limitations
5. Future Work Suggestions
6. Relevance Score (0-10) for: {query or 'general research'}"""
        
        response = self.generate(prompt, max_tokens=1000)
        
        # Parse response
        return PaperAnalysis(
            paper_id="",
            title=title,
            overall_summary=response[:500],
            key_findings=self._extract_findings(response),
            methodology=self._extract_section(response, "methodology"),
            limitations=self._extract_section(response, "limitation"),
            future_work=self._extract_section(response, "future"),
            relevance_to_query=self._extract_score(response, query),
            chunks_processed=1,
            full_text_available=True
        )
    
    def _analyze_chunked(self, text: str, title: str, query: str) -> PaperAnalysis:
        """Analyze a large paper using chunking strategy"""
        # Calculate chunk size based on context limit
        # Leave room for prompt (~1000 tokens) and output (~500 tokens)
        chunk_size = min(500, (CONTEXT_LIMIT - 1500) // 2)
        
        # Split into chunks
        chunks = self.chunk_text(text, chunk_size=chunk_size)
        print(f"   📑 Split into {len(chunks)} chunks")
        
        # Process each chunk
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            print(f"   Processing chunk {i+1}/{len(chunks)}...")
            result = self.summarize_chunk(chunk, purpose=f"research query: {query}")
            chunk_summaries.append(result)
        
        # Synthesize all summaries
        print("   🔄 Synthesizing summaries...")
        overall_summary = self.synthesize_summaries(chunk_summaries, title)
        
        # Extract key findings from all chunks
        all_findings = []
        for cs in chunk_summaries:
            all_findings.extend(cs.key_points)
        
        return PaperAnalysis(
            paper_id="",
            title=title,
            overall_summary=overall_summary,
            key_findings=all_findings[:10],  # Top 10 findings
            methodology="See chunk summaries",
            limitations="See chunk summaries",
            future_work="See chunk summaries",
            relevance_to_query=7.0,  # Estimate
            chunks_processed=len(chunks),
            full_text_available=True
        )
    
    def _extract_findings(self, text: str) -> List[str]:
        """Extract key findings from response"""
        findings = []
        in_findings = False
        
        for line in text.split('\n'):
            if 'key finding' in line.lower():
                in_findings = True
            elif in_findings and line.strip().startswith(('-', '*', '•', '1.', '2.', '3.')):
                findings.append(line.strip())
            elif in_findings and line.strip() and not line.strip().startswith(('-', '*', '•')):
                if len(findings) > 0:
                    break
        
        return findings[:5]
    
    def _extract_section(self, text: str, section: str) -> str:
        """Extract a specific section from response"""
        lines = text.split('\n')
        section_text = []
        in_section = False
        
        for line in lines:
            if section.lower() in line.lower():
                in_section = True
                continue
            elif in_section:
                if line.strip() and not line.strip().startswith(('-', '*', '•')):
                    if any(s in line.lower() for s in ['summary', 'finding', 'methodology', 'limitation', 'future']):
                        break
                    section_text.append(line.strip())
        
        return ' '.join(section_text[:3])
    
    def _extract_score(self, text: str, query: str) -> float:
        """Extract relevance score from response"""
        import re
        match = re.search(r'[Rr]elevance.*?(\d+\.?\d*)', text)
        if match:
            return float(match.group(1))
        return 7.0  # Default score
    
    def process_batch(self, papers: List[Dict], 
                     database) -> Dict[str, Any]:
        """
        Process multiple papers and update database
        
        Args:
            papers: List of paper dicts with 'text' and 'title'
            database: ResearchDatabase instance
        
        Returns:
            Processing summary
        """
        results = {
            "processed": 0,
            "failed": 0,
            "total_chunks": 0,
            "key_papers": []
        }
        
        for paper in papers:
            try:
                text = paper.get('text', paper.get('abstract', ''))
                title = paper.get('title', 'Untitled')
                paper_id = paper.get('id', title[:20])
                
                # Analyze paper
                analysis = self.analyze_paper(text, title)
                
                # Update database
                if analysis.relevance_to_query >= 8.0:
                    database.mark_as_key_paper(paper_id, analysis.overall_summary)
                    results["key_papers"].append(title)
                
                results["processed"] += 1
                results["total_chunks"] += analysis.chunks_processed
                
            except Exception as e:
                print(f"❌ Failed to process {paper.get('title', 'unknown')}: {e}")
                results["failed"] += 1
        
        return results


def demo():
    """Demo the Ollama processor"""
    print("=" * 60)
    print("Ollama Research Processor Demo")
    print("=" * 60)
    
    # Initialize processor
    processor = OllamaProcessor()
    
    # Check connection
    print("\n🔌 Checking Ollama connection...")
    if processor.check_connection():
        print("✅ Ollama is running!")
    else:
        print("⚠️  Ollama not running. Starting in demo mode...")
    
    # Demo chunking
    print("\n📑 Demo: Chunking a large text")
    sample_text = "This is section one of a research paper. " * 100
    chunks = processor.chunk_text(sample_text, chunk_size=50)
    print(f"   Original: {len(sample_text.split())} words")
    print(f"   Chunks: {len(chunks)}")
    print(f"   Chunk 1: {chunks[0]['text'][:50]}...")
    
    # Demo small text analysis
    print("\n📄 Demo: Small text analysis")
    small_text = "This paper presents a novel approach to machine learning. We demonstrate improved accuracy on benchmark datasets. Our method achieves 95% accuracy compared to previous state-of-the-art of 90%."
    
    analysis = processor._analyze_direct(small_text, "Sample Paper", "machine learning")
    print(f"   Summary: {analysis.overall_summary[:100]}...")
    print(f"   Chunks: {analysis.chunks_processed}")
    
    print("\n✅ Demo complete!")
    return processor


if __name__ == "__main__":
    demo()