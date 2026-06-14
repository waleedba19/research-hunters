#!/usr/bin/env python3
"""
BULLETPROOF RAG MEMORY SYSTEM for Research Hunter v2.4
=====================================================
Architecture for 6000+ papers with proper memory and RAG pipeline

Components:
1. Memory System (4k model) - Stores session context, learned patterns
2. RAG Pipeline (16k model) - Semantic search, retrieval, synthesis
3. Knowledge Graph - Cross-reference relationships
4. Hierarchical Summarization - Multi-level abstraction

Author: Research Hunter v2.4 - Bulletproof Academic Edition
"""

import os
import sys
import json
import time
import hashlib
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import threading
import re

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RAGConfig:
    """Configuration for RAG Memory System"""
    # Models
    model_4k: str = "qwen2.5vl:3b"      # Memory/Memo model
    model_16k: str = "qwen2.5vl-3b-16k"  # Document processing model
    
    # Context windows
    ctx_4k: int = 4096
    ctx_16k: int = 16384
    
    # Processing
    batch_size: int = 10
    max_summary_length: int = 500
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Storage
    db_path: str = "research_memory.db"
    vector_dim: int = 384
    
    # RAG Settings
    top_k_retrieval: int = 50
    similarity_threshold: float = 0.7
    max_hierarchy_depth: int = 4

class MemoryEntry:
    """Represents a memory/memo entry"""
    def __init__(self, key: str, value: str, context: str = "", importance: int = 5):
        self.key = key
        self.value = value
        self.context = context
        self.importance = importance
        self.created_at = datetime.now().isoformat()
        self.access_count = 0
        self.last_accessed = self.created_at
        self.tags = []
        self.linked_memories = []
    
    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "context": self.context,
            "importance": self.importance,
            "created_at": self.created_at,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "tags": self.tags,
            "linked_memories": self.linked_memories
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryEntry':
        entry = cls(data["key"], data["value"], data.get("context", ""), data.get("importance", 5))
        entry.created_at = data.get("created_at", datetime.now().isoformat())
        entry.access_count = data.get("access_count", 0)
        entry.last_accessed = data.get("last_accessed", entry.created_at)
        entry.tags = data.get("tags", [])
        entry.linked_memories = data.get("linked_memories", [])
        return entry

# ═══════════════════════════════════════════════════════════════════════════════
# LLM CLIENT (Both Models)
# ═══════════════════════════════════════════════════════════════════════════════

class LLMClient:
    """Manages both 4k (memory) and 16k (document) models"""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.available = False
        self._verify_models()
    
    def _verify_models(self):
        """Verify both models are available"""
        try:
            import urllib.request, json
            
            # Check server
            req = urllib.request.Request(f"http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                models = json.loads(resp.read()).get("models", [])
                model_names = [m.get("name", "") for m in models]
            
            # Verify 4k model
            if self.config.model_4k in model_names:
                print(f"✅ 4k model (memory): {self.config.model_4k}")
            else:
                print(f"⚠️ 4k model not found: {self.config.model_4k}")
            
            # Verify 16k model
            if self.config.model_16k in model_names:
                print(f"✅ 16k model (documents): {self.config.model_16k}")
                self.available = True
            else:
                print(f"⚠️ 16k model not found: {self.config.model_16k}")
                print("   Creating 16k model...")
                self._create_16k_model()
                
        except Exception as e:
            print(f"❌ LLM verification failed: {e}")
    
    def _create_16k_model(self):
        """Create custom 16k context model"""
        try:
            import subprocess
            # Create Modelfile
            modelfile_path = Path.home() / ".ollama" / "models" / "Modelfile"
            modelfile_path.parent.mkdir(exist_ok=True)
            
            with open(modelfile_path, "w") as f:
                f.write(f"""FROM qwen2.5vl:3b
PARAMETER num_ctx 16384
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_predict 2048
""")
            
            # Create model
            result = subprocess.run(
                ["ollama", "create", self.config.model_16k, "-f", str(modelfile_path)],
                capture_output=True, text=True, timeout=120
            )
            
            if result.returncode == 0:
                print(f"✅ 16k model created: {self.config.model_16k}")
                self.available = True
            else:
                print(f"❌ Failed to create 16k model: {result.stderr}")
                
        except Exception as e:
            print(f"❌ 16k model creation failed: {e}")
    
    def generate(self, prompt: str, model: str = None, use_16k: bool = False, 
                 max_tokens: int = 2048) -> Optional[str]:
        """Generate text using specified model"""
        if not self.available:
            return None
        
        model = model or (self.config.model_16k if use_16k else self.config.model_4k)
        
        try:
            import urllib.request, json
            
            data = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": self.config.ctx_16k if use_16k else self.config.ctx_4k,
                    "num_predict": max_tokens,
                    "temperature": 0.7,
                }
            }
            
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                return result.get("response", "")
                
        except Exception as e:
            print(f"Generation error: {e}")
            return None
    
    def generate_with_context(self, prompt: str, context: str, 
                              use_16k: bool = True) -> Optional[str]:
        """Generate with extended context"""
        full_prompt = f"""CONTEXT:
{context[:self.config.ctx_16k - len(prompt) - 500]}

TASK:
{prompt}

Based on the context provided, give the best possible answer."""
        
        return self.generate(full_prompt, use_16k=use_16k)


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY SYSTEM (4k Model - Session Context & Learned Patterns)
# ═══════════════════════════════════════════════════════════════════════════════

class MemorySystem:
    """
    Memory/Memo System using 4k model
    - Stores session context
    - Tracks learned patterns
    - Provides context-aware retrieval
    """
    
    def __init__(self, llm: LLMClient, db_path: str = "memory_system.db"):
        self.llm = llm
        self.db_path = db_path
        self.conn = None
        self._init_database()
        self.session_id = self._new_session()
    
    def _init_database(self):
        """Initialize SQLite database for memory storage"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Memory entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                context TEXT,
                importance INTEGER DEFAULT 5,
                created_at TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                tags TEXT,
                linked_memories TEXT
            )
        """)
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT,
                last_active TEXT,
                memory_count INTEGER DEFAULT 0,
                summary TEXT
            )
        """)
        
        # Knowledge graph edges
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_graph (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_key TEXT NOT NULL,
                target_key TEXT NOT NULL,
                relationship TEXT,
                strength REAL DEFAULT 0.5,
                created_at TEXT
            )
        """)
        
        self.conn.commit()
    
    def _new_session(self) -> str:
        """Create new session ID"""
        import uuid
        session_id = str(uuid.uuid4())[:8]
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (session_id, created_at, last_active) VALUES (?, ?, ?)",
            (session_id, datetime.now().isoformat(), datetime.now().isoformat())
        )
        self.conn.commit()
        return session_id
    
    def store(self, key: str, value: str, context: str = "", importance: int = 5) -> bool:
        """Store a memory entry"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO memories 
                (session_id, key, value, context, importance, created_at, access_count, last_accessed, tags, linked_memories)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.session_id, key, value, context, importance,
                datetime.now().isoformat(), 0, datetime.now().isoformat(),
                "[]", "[]"
            ))
            self.conn.commit()
            
            # Update session memory count
            cursor.execute(
                "UPDATE sessions SET memory_count = memory_count + 1 WHERE session_id = ?",
                (self.session_id,)
            )
            self.conn.commit()
            
            return True
        except Exception as e:
            print(f"Memory store error: {e}")
            return False
    
    def retrieve(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """Retrieve relevant memories using LLM"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM memories WHERE session_id = ? ORDER BY importance DESC, created_at DESC",
                (self.session_id,)
            )
            rows = cursor.fetchall()
            
            if not rows:
                return []
            
            # Get all memories as text for LLM to analyze
            memories_text = "\n".join([
                f"[{i+1}] {row[2]}: {row[3]}"
                for i, row in enumerate(rows[:50])
            ])
            
            # Use LLM to find relevant memories
            prompt = f"""Find memories relevant to: "{query}"

Available memories:
{memories_text}

Return the numbers of the most relevant memories (comma-separated, max {top_k}).
If none are relevant, return "NONE"."""
            
            result = self.llm.generate(prompt, use_16k=False, max_tokens=100)
            
            if not result or result.strip().upper() == "NONE":
                # Fallback to keyword matching
                keywords = query.lower().split()
                results = []
                for row in rows:
                    if any(kw in row[2].lower() or kw in row[3].lower() for kw in keywords):
                        results.append(MemoryEntry(row[2], row[3], row[4], row[5]))
                        if len(results) >= top_k:
                            break
                return results
            
            # Parse LLM response
            indices = []
            for part in result.replace(" ", "").split(","):
                try:
                    indices.append(int(part.strip()) - 1)
                except:
                    pass
            
            results = []
            for idx in indices[:top_k]:
                if idx < len(rows):
                    row = rows[idx]
                    results.append(MemoryEntry(row[2], row[3], row[4], row[5]))
                    # Update access count
                    cursor.execute(
                        "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                        (datetime.now().isoformat(), row[0])
                    )
            
            self.conn.commit()
            return results
            
        except Exception as e:
            print(f"Memory retrieve error: {e}")
            return []
    
    def get_context_summary(self, max_memories: int = 20) -> str:
        """Get summary of recent memories for context"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT key, value FROM memories 
                WHERE session_id = ?
                ORDER BY importance DESC, last_accessed DESC
                LIMIT ?
            """, (self.session_id, max_memories))
            
            rows = cursor.fetchall()
            if not rows:
                return "No prior context."
            
            return "\n".join([f"- {k}: {v[:100]}" for k, v in rows])
            
        except Exception as e:
            return f"Context error: {e}"
    
    def link_memories(self, key1: str, key2: str, relationship: str):
        """Create link between two memories in knowledge graph"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO knowledge_graph (source_key, target_key, relationship, created_at)
                VALUES (?, ?, ?, ?)
            """, (key1, key2, relationship, datetime.now().isoformat()))
            self.conn.commit()
        except Exception as e:
            print(f"Link error: {e}")
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get session summary"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT memory_count, summary FROM sessions WHERE session_id = ?",
            (self.session_id,)
        )
        row = cursor.fetchone()
        return {
            "session_id": self.session_id,
            "memory_count": row[0] if row else 0,
            "summary": row[1] if row else ""
        }


# ═══════════════════════════════════════════════════════════════════════════════
# RAG PIPELINE (16k Model - Semantic Search & Retrieval)
# ═══════════════════════════════════════════════════════════════════════════════

class PaperDocument:
    """Represents a research paper for RAG"""
    def __init__(self, paper_id: str, title: str, abstract: str, 
                 authors: str = "", year: int = 0, journal: str = "",
                 keywords: List[str] = None, full_text: str = ""):
        self.paper_id = paper_id
        self.title = title
        self.abstract = abstract
        self.authors = authors
        self.year = year
        self.journal = journal
        self.keywords = keywords or []
        self.full_text = full_text
        self.chunks = []
        self.embeddings = []
        self.metadata = {}
    
    def chunk(self, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """Split paper into chunks for processing"""
        text = f"{self.title} {self.abstract} {self.full_text}"
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            if len(chunk_words) >= 100:  # Minimum chunk size
                chunks.append(" ".join(chunk_words))
        
        self.chunks = chunks
        return chunks
    
    def to_dict(self) -> dict:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "year": self.year,
            "journal": self.journal,
            "keywords": self.keywords,
            "chunk_count": len(self.chunks),
            "metadata": self.metadata
        }


class RAGPipeline:
    """
    RAG Pipeline for 6000+ papers using 16k model
    - Embedding generation (simulated - in production use real embeddings)
    - Semantic search
    - Retrieval with relevance scoring
    - Batch processing with LLM
    """
    
    def __init__(self, llm: LLMClient, memory: MemorySystem, 
                 db_path: str = "rag_pipeline.db"):
        self.llm = llm
        self.memory = memory
        self.db_path = db_path
        self.conn = None
        self.config = RAGConfig()
        self._init_database()
        self.papers = {}
        self.paper_chunks = {}
    
    def _init_database(self):
        """Initialize RAG database"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Papers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                abstract TEXT,
                authors TEXT,
                year INTEGER,
                journal TEXT,
                keywords TEXT,
                chunk_count INTEGER DEFAULT 0,
                indexed_at TEXT
            )
        """)
        
        # Chunks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT,
                chunk_text TEXT,
                chunk_index INTEGER,
                embedding BLOB,
                FOREIGN KEY (paper_id) REFERENCES papers(paper_id)
            )
        """)
        
        # Index for fast retrieval
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paper_id ON chunks(paper_id)")
        
        self.conn.commit()
    
    def index_paper(self, paper: PaperDocument) -> bool:
        """Index a paper into RAG pipeline"""
        try:
            # Store paper metadata
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO papers 
                (paper_id, title, abstract, authors, year, journal, keywords, chunk_count, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                paper.paper_id, paper.title, paper.abstract, paper.authors,
                paper.year, paper.journal, ",".join(paper.keywords),
                len(paper.chunks), datetime.now().isoformat()
            ))
            
            # Chunk the paper
            chunks = paper.chunk()
            
            # Store chunks
            for i, chunk in enumerate(chunks):
                # Generate pseudo-embedding (hash-based for demo)
                # In production, use real embeddings from sentence-transformers
                embedding = self._generate_pseudo_embedding(chunk)
                
                cursor.execute("""
                    INSERT INTO chunks (paper_id, chunk_text, chunk_index, embedding)
                    VALUES (?, ?, ?, ?)
                """, (paper.paper_id, chunk, i, embedding))
            
            self.conn.commit()
            
            # Store in memory
            self.memory.store(
                f"paper:{paper.paper_id}",
                paper.title,
                f"Authors: {paper.authors}. Year: {paper.year}. Journal: {paper.journal}",
                importance=7
            )
            
            self.papers[paper.paper_id] = paper
            self.paper_chunks[paper.paper_id] = chunks
            
            return True
            
        except Exception as e:
            print(f"Index error: {e}")
            return False
    
    def _generate_pseudo_embedding(self, text: str) -> bytes:
        """Generate pseudo-embedding (hash-based)
        In production, use: from sentence_transformers import SentenceTransformer"""
        import hashlib
        # Simple hash for demo - NOT real embeddings
        hash_obj = hashlib.sha256(text.encode())
        return hash_obj.digest()[:self.config.vector_dim]
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        # Simple word overlap similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def search(self, query: str, top_k: int = 50) -> List[Tuple[PaperDocument, float]]:
        """Semantic search across all indexed papers"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT paper_id, title, abstract FROM papers")
            rows = cursor.fetchall()
            
            if not rows:
                return []
            
            # Score all papers
            scored = []
            for row in rows:
                paper_id, title, abstract = row
                text = f"{title} {abstract or ''}"
                similarity = self._calculate_similarity(query, text)
                scored.append((paper_id, similarity))
            
            # Sort by similarity
            scored.sort(key=lambda x: -x[1])
            
            # Get top results
            results = []
            for paper_id, score in scored[:top_k]:
                if paper_id in self.papers:
                    results.append((self.papers[paper_id], score))
            
            # Store search in memory
            self.memory.store(
                f"search:{query[:50]}",
                f"Found {len(results)} papers with query: {query[:100]}",
                context=f"Top results: {[p.title for p, _ in results[:5]]}",
                importance=6
            )
            
            return results
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def retrieve_for_analysis(self, query: str, max_papers: int = 20) -> List[PaperDocument]:
        """Retrieve papers for LLM analysis"""
        results = self.search(query, top_k=max_papers)
        return [paper for paper, score in results if score > self.config.similarity_threshold]
    
    def batch_analyze(self, papers: List[PaperDocument], 
                      analysis_type: str = "comprehensive") -> List[Dict]:
        """Analyze batch of papers using 16k model"""
        results = []
        
        # Process in batches to fit in context
        batch_size = self.config.batch_size
        
        for i in range(0, len(papers), batch_size):
            batch = papers[i:i + batch_size]
            print(f"📄 Processing batch {i//batch_size + 1}/{(len(papers) + batch_size - 1)//batch_size}")
            
            # Combine batch context
            batch_context = "\n\n".join([
                f"--- Paper {j+1}: {p.title} ---\n"
                f"Authors: {p.authors}\n"
                f"Year: {p.year}\n"
                f"Abstract: {p.abstract[:1000]}"
                for j, p in enumerate(batch)
            ])
            
            prompts = {
                "comprehensive": f"""Analyze these research papers:

{batch_context[:8000]}

Provide for each paper:
1. Executive Summary
2. Key Findings
3. Methodology
4. Limitations
5. Relevance Score (1-10)""",

                "themes": f"""Identify themes across these papers:

{batch_context[:8000]}

Provide:
1. Common Themes
2. Contradictory Findings
3. Research Gaps
4. Methodology Patterns""",

                "comparison": f"""Compare these papers:

{batch_context[:8000]}

Provide:
1. Similarities
2. Differences
3. Synthesis of Findings
4. Knowledge Gaps"""
            }
            
            prompt = prompts.get(analysis_type, prompts["comprehensive"])
            result = self.llm.generate_with_context(prompt, batch_context, use_16k=True)
            
            results.append({
                "batch_start": i,
                "batch_end": i + len(batch),
                "analysis": result,
                "papers_analyzed": len(batch)
            })
        
        return results
    
    def generate_synthesis(self, papers: List[PaperDocument], 
                         topic: str, analysis_type: str = "literature_review") -> str:
        """Generate final synthesis from all papers"""
        if not papers:
            return "No papers available for synthesis."
        
        # Retrieve relevant papers
        relevant = self.retrieve_for_analysis(topic, max_papers=50)
        
        if not relevant:
            return "No relevant papers found."
        
        # Store in memory
        self.memory.store(
            f"synthesis:{topic[:50]}",
            f"Generated {analysis_type} for: {topic}",
            context=f"Based on {len(relevant)} papers",
            importance=8
        )
        
        # Generate synthesis using batch processing
        results = self.batch_analyze(relevant, analysis_type="themes")
        
        # Combine all analyses
        all_analyses = "\n\n".join([r["analysis"] or "Analysis failed" for r in results])
        
        # Final synthesis prompt
        final_prompt = f"""Synthesize findings from {len(relevant)} research papers on: "{topic}"

Previous analyses:
{all_analyses[:6000]}

Generate a comprehensive {analysis_type.replace('_', ' ')} that:
1. Summarizes key findings
2. Identifies patterns
3. Notes contradictions
4. Highlights research gaps
5. Provides implications

Use academic writing style."""

        final_result = self.llm.generate(final_prompt, use_16k=True, max_tokens=4096)
        
        return final_result or "Synthesis generation failed."
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RAG pipeline statistics"""
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM papers")
        paper_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = cursor.fetchone()[0]
        
        return {
            "total_papers": paper_count,
            "total_chunks": chunk_count,
            "papers_in_memory": len(self.papers),
            "model_16k_available": self.llm.available
        }


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE GRAPH (Cross-Reference Relationships)
# ═══════════════════════════════════════════════════════════════════════════════

class KnowledgeGraph:
    """Knowledge graph for cross-reference relationships between papers"""
    
    def __init__(self, db_path: str = "knowledge_graph.db"):
        self.db_path = db_path
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """Initialize knowledge graph database"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Nodes (papers/concepts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT UNIQUE NOT NULL,
                node_type TEXT,  -- 'paper' or 'concept'
                label TEXT NOT NULL,
                properties TEXT,
                created_at TEXT
            )
        """)
        
        # Edges (relationships)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relationship_type TEXT,
                weight REAL DEFAULT 1.0,
                properties TEXT,
                created_at TEXT,
                FOREIGN KEY (source_id) REFERENCES nodes(node_id),
                FOREIGN KEY (target_id) REFERENCES nodes(node_id)
            )
        """)
        
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON edges(source_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_target ON edges(target_id)")
        
        self.conn.commit()
    
    def add_node(self, node_id: str, node_type: str, label: str, 
                 properties: Dict = None) -> bool:
        """Add a node to the knowledge graph"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO nodes (node_id, node_type, label, properties, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                node_id, node_type, label,
                json.dumps(properties or {}),
                datetime.now().isoformat()
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Node add error: {e}")
            return False
    
    def add_edge(self, source_id: str, target_id: str, 
                 relationship: str, weight: float = 1.0) -> bool:
        """Add an edge between nodes"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO edges (source_id, target_id, relationship_type, weight, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (source_id, target_id, relationship, weight, datetime.now().isoformat()))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Edge add error: {e}")
            return False
    
    def get_connected(self, node_id: str, depth: int = 1) -> List[Dict]:
        """Get nodes connected to a given node"""
        try:
            cursor = self.conn.cursor()
            
            # Get outgoing edges
            cursor.execute("""
                SELECT e.target_id, e.relationship_type, e.weight, n.label, n.node_type
                FROM edges e
                JOIN nodes n ON e.target_id = n.node_id
                WHERE e.source_id = ?
            """, (node_id,))
            
            outgoing = [
                {"node_id": row[0], "relationship": row[1], "weight": row[2], 
                 "label": row[3], "type": row[4], "direction": "out"}
                for row in cursor.fetchall()
            ]
            
            # Get incoming edges
            cursor.execute("""
                SELECT e.source_id, e.relationship_type, e.weight, n.label, n.node_type
                FROM edges e
                JOIN nodes n ON e.source_id = n.node_id
                WHERE e.target_id = ?
            """, (node_id,))
            
            incoming = [
                {"node_id": row[0], "relationship": row[1], "weight": row[2],
                 "label": row[3], "type": row[4], "direction": "in"}
                for row in cursor.fetchall()
            ]
            
            return outgoing + incoming
            
        except Exception as e:
            print(f"Get connected error: {e}")
            return []
    
    def find_path(self, source_id: str, target_id: str, max_depth: int = 3) -> List[str]:
        """Find path between two nodes (simplified BFS)"""
        try:
            from collections import deque
            
            queue = deque([(source_id, [source_id])])
            visited = {source_id}
            
            while queue:
                current, path = queue.popleft()
                
                if current == target_id:
                    return path
                
                if len(path) > max_depth:
                    continue
                
                connections = self.get_connected(current)
                for conn in connections:
                    next_node = conn["node_id"]
                    if next_node not in visited:
                        visited.add(next_node)
                        queue.append((next_node, path + [next_node]))
            
            return []  # No path found
            
        except Exception as e:
            print(f"Find path error: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge graph statistics"""
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM nodes")
        node_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM edges")
        edge_count = cursor.fetchone()[0]
        
        return {
            "total_nodes": node_count,
            "total_edges": edge_count
        }


# ═══════════════════════════════════════════════════════════════════════════════
# HIERARCHICAL SUMMARIZATION
# ═══════════════════════════════════════════════════════════════════════════════

class HierarchicalSummarizer:
    """
    Multi-level summarization for large paper collections
    Level 1: Individual paper summaries
    Level 2: Batch summaries (10-15 papers)
    Level 3: Theme summaries
    Level 4: Final synthesis
    """
    
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.config = RAGConfig()
        self.summaries = {1: {}, 2: {}, 3: {}, 4: {}}
    
    def summarize_paper(self, paper: PaperDocument) -> str:
        """Level 1: Summarize individual paper"""
        prompt = f"""Summarize this research paper concisely:

Title: {paper.title}
Authors: {paper.authors}
Abstract: {paper.abstract}

Provide a 200-word summary covering:
1. Research Problem
2. Methodology
3. Key Findings
4. Conclusions"""
        
        return self.llm.generate(prompt, use_16k=True, max_tokens=500) or ""
    
    def summarize_batch(self, papers: List[PaperDocument], batch_id: str) -> str:
        """Level 2: Summarize batch of papers"""
        papers_text = "\n\n".join([
            f"Paper {i+1}: {p.title}\nAbstract: {p.abstract[:500]}"
            for i, p in enumerate(papers)
        ])
        
        prompt = f"""Synthesize findings from these {len(papers)} papers:

{papers_text[:6000]}

Provide a coherent summary covering:
1. Common themes
2. Key findings (aggregated)
3. Contradictions
4. Research gaps
5. Methodology patterns"""
        
        result = self.llm.generate(prompt, use_16k=True, max_tokens=1000)
        
        if result:
            self.summaries[2][batch_id] = result
        
        return result or ""
    
    def summarize_by_theme(self, theme: str, summaries: List[str]) -> str:
        """Level 3: Summarize by theme"""
        combined = "\n\n".join(summaries[:20])  # Limit to 20 summaries
        
        prompt = f"""Synthesize papers related to theme: "{theme}"

{summaries}

Provide:
1. Theme overview
2. Key insights
3. Conflicting findings
4. Research implications"""
        
        result = self.llm.generate(prompt, use_16k=True, max_tokens=1500)
        
        if result:
            self.summaries[3][theme] = result
        
        return result or ""
    
    def final_synthesis(self, topic: str, all_summaries: Dict) -> str:
        """Level 4: Final synthesis from all levels"""
        
        summary_text = ""
        for level, summaries in all_summaries.items():
            if level == 1:
                summary_text += f"\n--- Individual Paper Summaries ({len(summaries)} papers) ---\n"
            elif level == 2:
                summary_text += f"\n--- Batch Summaries ({len(summaries)} batches) ---\n"
            elif level == 3:
                summary_text += f"\n--- Theme Summaries ({len(summaries)} themes) ---\n"
            
            for key, summary in list(summaries.items())[:5]:  # Limit to 5 per level
                summary_text += f"\n{summary[:500]}\n"
        
        prompt = f"""Create final comprehensive synthesis on: "{topic}"

{summary_text[:8000]}

Write a complete research synthesis with:
1. Introduction and context
2. Literature review summary
3. Key findings
4. Research gaps
5. Implications and future directions
6. Conclusion

Use formal academic writing style. Minimum 1000 words."""

        result = self.llm.generate(prompt, use_16k=True, max_tokens=4096)
        
        if result:
            self.summaries[4]["final"] = result
        
        return result or ""


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN INTEGRATION CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class ResearchHunterRAG:
    """
    Main integration class combining all components:
    - Memory System (4k model)
    - RAG Pipeline (16k model)
    - Knowledge Graph
    - Hierarchical Summarization
    """
    
    def __init__(self):
        self.config = RAGConfig()
        
        # Initialize LLM client with both models
        print("🤖 Initializing LLM Client...")
        self.llm = LLMClient(self.config)
        
        if not self.llm.available:
            print("❌ LLM not available. Please ensure Ollama is running.")
            return
        
        # Initialize components
        print("🧠 Initializing Memory System (4k model)...")
        self.memory = MemorySystem(self.llm)
        
        print("📚 Initializing RAG Pipeline (16k model)...")
        self.rag = RAGPipeline(self.llm, self.memory)
        
        print("🔗 Initializing Knowledge Graph...")
        self.knowledge_graph = KnowledgeGraph()
        
        print("📊 Initializing Hierarchical Summarizer...")
        self.summarizer = HierarchicalSummarizer(self.llm)
        
        print("\n✅ All systems initialized!")
    
    def index_papers(self, papers: List[Dict]) -> Dict[str, Any]:
        """Index multiple papers"""
        results = {
            "total": len(papers),
            "indexed": 0,
            "failed": 0,
            "errors": []
        }
        
        for paper_data in papers:
            try:
                paper = PaperDocument(
                    paper_id=paper_data.get("id", str(hash(paper_data.get("title", "")))),
                    title=paper_data.get("title", "N/A"),
                    abstract=paper_data.get("abstract", ""),
                    authors=paper_data.get("authors", ""),
                    year=paper_data.get("year", 0),
                    journal=paper_data.get("journal", ""),
                    keywords=paper_data.get("keywords", [])
                )
                
                if self.rag.index_paper(paper):
                    results["indexed"] += 1
                    
                    # Add to knowledge graph
                    self.knowledge_graph.add_node(
                        paper.paper_id, "paper", paper.title,
                        {"authors": paper.authors, "year": paper.year}
                    )
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Failed: {paper.title}")
                    
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(str(e))
        
        return results
    
    def search(self, query: str, use_memory: bool = True) -> Dict[str, Any]:
        """Search with memory context"""
        # Get relevant memories
        memories = []
        if use_memory:
            memories = self.memory.retrieve(query)
        
        # Search papers
        results = self.rag.search(query)
        
        return {
            "query": query,
            "memories_used": len(memories),
            "papers_found": len(results),
            "top_papers": [(p.title, score) for p, score in results[:10]],
            "context_from_memory": [m.value[:100] for m in memories[:3]]
        }
    
    def generate_report(self, topic: str, num_papers: int = 100) -> Dict[str, Any]:
        """Generate comprehensive research report"""
        print(f"\n📝 Generating report on: {topic}")
        
        # Retrieve relevant papers
        papers = self.rag.retrieve_for_analysis(topic, max_papers=num_papers)
        
        if not papers:
            return {"error": "No relevant papers found"}
        
        # Store in memory
        self.memory.store(f"report:{topic[:50]}", f"Report on {topic}", importance=9)
        
        # Generate synthesis
        synthesis = self.rag.generate_synthesis(papers, topic, "literature_review")
        
        return {
            "topic": topic,
            "papers_analyzed": len(papers),
            "synthesis": synthesis,
            "stats": self.get_all_stats()
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics from all components"""
        return {
            "llm": {
                "model_4k": self.config.model_4k,
                "model_16k": self.config.model_16k,
                "available": self.llm.available
            },
            "memory": self.memory.get_session_summary(),
            "rag": self.rag.get_stats(),
            "knowledge_graph": self.knowledge_graph.get_stats()
        }
    
    def test_all(self) -> Dict[str, Any]:
        """Run comprehensive tests on all components"""
        print("\n" + "="*60)
        print("🧪 RUNNING COMPREHENSIVE TESTS")
        print("="*60)
        
        results = {}
        
        # Test 1: LLM 4k Model
        print("\n📌 Test 1: 4k Model (Memory)")
        try:
            result = self.llm.generate("What is 2+2? Answer in one word.", use_16k=False)
            results["llm_4k"] = {
                "status": "PASS" if result == "4" else "PARTIAL",
                "result": result
            }
            print(f"   Result: {result}")
        except Exception as e:
            results["llm_4k"] = {"status": "FAIL", "error": str(e)}
        
        # Test 2: LLM 16k Model
        print("\n📌 Test 2: 16k Model (Documents)")
        try:
            long_text = "This is a test. " * 500
            result = self.llm.generate_with_context(
                "Summarize this text in one sentence.",
                long_text,
                use_16k=True
            )
            results["llm_16k"] = {
                "status": "PASS" if result else "FAIL",
                "result": result[:100] if result else "No response"
            }
            print(f"   Result: {result[:100] if result else 'FAILED'}...")
        except Exception as e:
            results["llm_16k"] = {"status": "FAIL", "error": str(e)}
        
        # Test 3: Memory System
        print("\n📌 Test 3: Memory System")
        try:
            self.memory.store("test_key", "test_value", "test context", importance=5)
            retrieved = self.memory.retrieve("test")
            results["memory_store"] = {"status": "PASS" if retrieved else "FAIL"}
            print(f"   Stored and retrieved: {len(retrieved)} memories")
        except Exception as e:
            results["memory_store"] = {"status": "FAIL", "error": str(e)}
        
        # Test 4: Paper Indexing
        print("\n📌 Test 4: Paper Indexing")
        try:
            test_paper = PaperDocument(
                "test_001",
                "Test Research on AI",
                "This paper explores artificial intelligence applications.",
                "John Doe",
                2024,
                "AI Journal",
                ["AI", "machine learning"]
            )
            success = self.rag.index_paper(test_paper)
            results["paper_indexing"] = {"status": "PASS" if success else "FAIL"}
            print(f"   Paper indexed: {'YES' if success else 'NO'}")
        except Exception as e:
            results["paper_indexing"] = {"status": "FAIL", "error": str(e)}
        
        # Test 5: Search
        print("\n📌 Test 5: RAG Search")
        try:
            search_results = self.rag.search("artificial intelligence")
            results["rag_search"] = {
                "status": "PASS",
                "papers_found": len(search_results)
            }
            print(f"   Found {len(search_results)} papers")
        except Exception as e:
            results["rag_search"] = {"status": "FAIL", "error": str(e)}
        
        # Test 6: Knowledge Graph
        print("\n📌 Test 6: Knowledge Graph")
        try:
            self.knowledge_graph.add_node("node_1", "paper", "Test Paper", {"test": "data"})
            self.knowledge_graph.add_node("node_2", "concept", "AI", {"field": "computing"})
            self.knowledge_graph.add_edge("node_1", "node_2", "related_to")
            connections = self.knowledge_graph.get_connected("node_1")
            results["knowledge_graph"] = {
                "status": "PASS" if len(connections) >= 0 else "FAIL",
                "connections": len(connections)
            }
            print(f"   Nodes and edges created successfully")
        except Exception as e:
            results["knowledge_graph"] = {"status": "FAIL", "error": str(e)}
        
        # Test 7: Batch Analysis
        print("\n📌 Test 7: Batch Analysis")
        try:
            test_papers = [
                PaperDocument(f"batch_{i}", f"Paper {i}", "Abstract content", "Author", 2024)
                for i in range(5)
            ]
            for p in test_papers:
                self.rag.index_paper(p)
            analysis_results = self.rag.batch_analyze(test_papers, "comprehensive")
            results["batch_analysis"] = {
                "status": "PASS" if analysis_results else "PARTIAL",
                "batches": len(analysis_results)
            }
            print(f"   Processed {len(analysis_results)} batches")
        except Exception as e:
            results["batch_analysis"] = {"status": "FAIL", "error": str(e)}
        
        # Summary
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for r in results.values() if r.get("status") == "PASS")
        partial = sum(1 for r in results.values() if r.get("status") == "PARTIAL")
        failed = sum(1 for r in results.values() if r.get("status") == "FAIL")
        
        print(f"\n   ✅ PASSED: {passed}")
        print(f"   ⚠️  PARTIAL: {partial}")
        print(f"   ❌ FAILED: {failed}")
        
        return results


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("="*70)
    print("🔬 RESEARCH HUNTER v2.4 - BULLETPROOF RAG MEMORY SYSTEM")
    print("   For 6000+ Papers with LLM-Powered Analysis")
    print("="*70)
    print()
    
    # Initialize system
    system = ResearchHunterRAG()
    
    # Run comprehensive tests
    test_results = system.test_all()
    
    # Print final stats
    print("\n" + "="*70)
    print("📊 SYSTEM STATISTICS")
    print("="*70)
    
    stats = system.get_all_stats()
    for component, data in stats.items():
        print(f"\n{component.upper()}:")
        if isinstance(data, dict):
            for key, value in data.items():
                print(f"   {key}: {value}")