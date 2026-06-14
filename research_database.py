#!/usr/bin/env python3
"""
Research Hunter v7 - Intelligent Research Database System
Handles massive research with limited context using:
1. Chunking - Split large texts
2. Summarization - Compress information
3. Database Tracking - Know what was read
4. Vector Embeddings - Semantic search
"""

import json
import sqlite3
import hashlib
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
import os

@dataclass
class Paper:
    """Research Paper Record"""
    paper_id: str
    title: str
    authors: str
    abstract: str
    year: int
    source: str
    url: str
    status: str = "pending"  # pending, processed, analyzed, key_paper
    summary: str = ""
    key_findings: str = ""
    relevance_score: float = 0.0
    full_text_path: str = ""
    chunks_processed: int = 0
    created_at: str = ""
    processed_at: str = ""

@dataclass
class Chunk:
    """Document Chunk for Processing"""
    chunk_id: str
    paper_id: str
    chunk_index: int
    content: str
    tokens: int
    summary: str = ""
    embedding: str = ""  # Base64 encoded embedding
    processed: bool = False

class ResearchDatabase:
    """
    Database System for Tracking Research Progress
    
    Features:
    - Track 10,000+ papers efficiently
    - Know exactly what was read vs not
    - Process with limited context (4k)
    - Semantic search on summaries
    """
    
    def __init__(self, db_path: str = "research_db.sqlite"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with all tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Papers table - Main research papers
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                authors TEXT,
                abstract TEXT,
                year INTEGER,
                source TEXT,
                url TEXT,
                status TEXT DEFAULT 'pending',
                summary TEXT,
                key_findings TEXT,
                relevance_score REAL DEFAULT 0,
                full_text_path TEXT,
                chunks_processed INTEGER DEFAULT 0,
                created_at TEXT,
                processed_at TEXT
            )
        ''')
        
        # Chunks table - Processed chunks for each paper
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                paper_id TEXT,
                chunk_index INTEGER,
                content TEXT,
                tokens INTEGER,
                summary TEXT,
                embedding TEXT,
                processed INTEGER DEFAULT 0,
                FOREIGN KEY (paper_id) REFERENCES papers(paper_id)
            )
        ''')
        
        # Summaries table - Hierarchical summaries
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS summaries (
                summary_id TEXT PRIMARY KEY,
                paper_id TEXT,
                level INTEGER,  -- 1=chunk, 2=section, 3=paper, 4=topic
                content TEXT,
                source_chunks TEXT,  -- JSON array of chunk IDs
                created_at TEXT,
                FOREIGN KEY (paper_id) REFERENCES papers(paper_id)
            )
        ''')
        
        # Topics table - Research topics/themes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topics (
                topic_id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                papers_count INTEGER DEFAULT 0,
                last_updated TEXT
            )
        ''')
        
        # Processing queue - What needs processing
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processing_queue (
                queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT,
                task_type TEXT,  -- 'chunk', 'summarize', 'embed', 'analyze'
                priority INTEGER DEFAULT 5,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                FOREIGN KEY (paper_id) REFERENCES papers(paper_id)
            )
        ''')
        
        # Search index - For semantic search
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_index (
                index_id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT,
                content_text TEXT,
                content_type TEXT,  -- 'title', 'abstract', 'summary', 'chunk'
                embedding_vector TEXT,
                FOREIGN KEY (paper_id) REFERENCES papers(paper_id)
            )
        ''')
        
        # Create indexes for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_paper ON chunks(paper_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_queue_status ON processing_queue(status)')
        
        conn.commit()
        conn.close()
        print(f"✅ Database initialized: {self.db_path}")
    
    def add_paper(self, title: str, abstract: str = "", authors: str = "", 
                  year: int = 0, source: str = "", url: str = "") -> str:
        """Add a new paper to the database"""
        paper_id = hashlib.md5(f"{title}{authors}".encode()).hexdigest()[:12]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO papers (paper_id, title, authors, abstract, year, source, url, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (paper_id, title, authors, abstract, year, source, url, datetime.now().isoformat()))
            conn.commit()
            print(f"✅ Added paper: {title[:50]}...")
        except sqlite3.IntegrityError:
            print(f"⚠️  Paper already exists: {title[:50]}...")
        
        conn.close()
        return paper_id
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Split text into overlapping chunks for processing
        
        Strategy:
        - Chunk size: 500 tokens (fits in 4k context with prompt)
        - Overlap: 50 tokens (maintains context between chunks)
        - Smart splitting at sentence boundaries
        """
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk_text = ' '.join(chunk_words)
            chunks.append(chunk_text)
            
            if i + chunk_size >= len(words):
                break
        
        return chunks
    
    def process_paper(self, paper_id: str, full_text: str = "", 
                     context_limit: int = 4000) -> Dict[str, Any]:
        """
        Process a paper with limited context
        
        Strategy:
        1. If text < context_limit: Process directly
        2. If text > context_limit: Chunk, summarize, then synthesize
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get paper info
        cursor.execute('SELECT * FROM papers WHERE paper_id = ?', (paper_id,))
        paper = cursor.fetchone()
        
        if not paper:
            print(f"❌ Paper not found: {paper_id}")
            return {"error": "Paper not found"}
        
        results = {
            "paper_id": paper_id,
            "chunks_processed": 0,
            "summaries": [],
            "full_summary": "",
            "key_findings": []
        }
        
        # Process abstract (usually short, process directly)
        abstract = paper[3]  # abstract column
        if abstract:
            abstract_summary = self.summarize_text(abstract, context_limit)
            results["summaries"].append(("abstract", abstract_summary))
        
        # If full text exists and is large, chunk it
        if full_text:
            chunks = self.chunk_text(full_text, chunk_size=500)
            results["chunks_processed"] = len(chunks)
            
            print(f"📄 Processing {len(chunks)} chunks...")
            
            # Process each chunk
            for i, chunk in enumerate(chunks):
                chunk_id = f"{paper_id}_chunk_{i}"
                
                # Summarize chunk
                chunk_summary = self.summarize_text(chunk, context_limit)
                
                # Store chunk
                cursor.execute('''
                    INSERT OR REPLACE INTO chunks 
                    (chunk_id, paper_id, chunk_index, content, tokens, summary, processed)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                ''', (chunk_id, paper_id, i, chunk, len(chunk.split()), chunk_summary))
                
                results["summaries"].append((f"chunk_{i}", chunk_summary))
            
            # Synthesize final summary from chunk summaries
            if len(chunks) > 1:
                synthesis = self.synthesize_summaries(results["summaries"])
                results["full_summary"] = synthesis
            else:
                results["full_summary"] = results["summaries"][0][1] if results["summaries"] else ""
            
            # Update paper status
            cursor.execute('''
                UPDATE papers 
                SET status = 'processed', 
                    summary = ?, 
                    chunks_processed = ?,
                    processed_at = ?
                WHERE paper_id = ?
            ''', (results["full_summary"], len(chunks), datetime.now().isoformat(), paper_id))
        
        conn.commit()
        conn.close()
        
        return results
    
    def summarize_text(self, text: str, max_tokens: int = 500) -> str:
        """
        Summarize text using Ollama
        
        For actual implementation, this would call Ollama API
        """
        # This is a placeholder - in real use, call Ollama
        # For now, return first 200 chars as "summary"
        return text[:200] + "..." if len(text) > 200 else text
    
    def synthesize_summaries(self, summaries: List[tuple]) -> str:
        """
        Synthesize multiple summaries into one coherent summary
        
        This uses the LLM to combine information from multiple chunks
        """
        # Combine all summaries
        combined = "\n".join([s[1] for s in summaries])
        
        # This would call Ollama to synthesize
        # For now, return combined
        return f"Synthesized from {len(summaries)} sections:\n{combined[:1000]}"
    
    def get_processing_status(self) -> Dict[str, int]:
        """Get overall processing status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Count by status
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM papers 
            GROUP BY status
        ''')
        status_counts = dict(cursor.fetchall())
        
        # Total papers
        cursor.execute('SELECT COUNT(*) FROM papers')
        total = cursor.fetchone()[0]
        
        # Queue size
        cursor.execute('SELECT COUNT(*) FROM processing_queue WHERE status = "pending"')
        queue_size = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_papers": total,
            "pending": status_counts.get('pending', 0),
            "processed": status_counts.get('processed', 0),
            "analyzed": status_counts.get('analyzed', 0),
            "key_papers": status_counts.get('key_paper', 0),
            "queue_size": queue_size
        }
    
    def get_unprocessed_papers(self, limit: int = 100) -> List[Dict]:
        """Get papers that haven't been processed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT paper_id, title, abstract, source 
            FROM papers 
            WHERE status = 'pending'
            LIMIT ?
        ''', (limit,))
        
        papers = []
        for row in cursor.fetchall():
            papers.append({
                "paper_id": row[0],
                "title": row[1],
                "abstract": row[2],
                "source": row[3]
            })
        
        conn.close()
        return papers
    
    def mark_as_key_paper(self, paper_id: str, findings: str):
        """Mark a paper as key and store findings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE papers 
            SET status = 'key_paper', 
                key_findings = ?,
                processed_at = ?
            WHERE paper_id = ?
        ''', (findings, datetime.now().isoformat(), paper_id))
        
        conn.commit()
        conn.close()
        print(f"⭐ Marked as key paper: {paper_id}")
    
    def search_papers(self, query: str, search_type: str = "all") -> List[Dict]:
        """
        Search papers by title, abstract, or full content
        
        In production, this would use vector embeddings for semantic search
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if search_type == "all":
            cursor.execute('''
                SELECT paper_id, title, abstract, status, relevance_score
                FROM papers
                WHERE title LIKE ? OR abstract LIKE ?
                ORDER BY relevance_score DESC
            ''', (f'%{query}%', f'%{query}%'))
        elif search_type == "unprocessed":
            cursor.execute('''
                SELECT paper_id, title, abstract, status, relevance_score
                FROM papers
                WHERE (title LIKE ? OR abstract LIKE ?) AND status = 'pending'
                ORDER BY relevance_score DESC
            ''', (f'%{query}%', f'%{query}%'))
        elif search_type == "key":
            cursor.execute('''
                SELECT paper_id, title, abstract, status, key_findings
                FROM papers
                WHERE status = 'key_paper' AND (title LIKE ? OR abstract LIKE ?)
            ''', (f'%{query}%', f'%{query}%'))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "paper_id": row[0],
                "title": row[1],
                "abstract": row[2][:200] + "..." if row[2] and len(row[2]) > 200 else row[2],
                "status": row[3],
                "score": row[4]
            })
        
        conn.close()
        return results
    
    def generate_report(self) -> str:
        """Generate a comprehensive research report"""
        status = self.get_processing_status()
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║           RESEARCH DATABASE STATUS REPORT                    ║
╚══════════════════════════════════════════════════════════════╝

📊 OVERALL STATISTICS:
   Total Papers:     {status['total_papers']:>6}
   ⏳ Pending:       {status['pending']:>6}
   ✅ Processed:     {status['processed']:>6}
   🔍 Analyzed:      {status['analyzed']:>6}
   ⭐ Key Papers:    {status['key_papers']:>6}
   📋 Queue Size:    {status['queue_size']:>6}

📈 PROCESSING COVERAGE:
   Processed:        {status['processed']/max(status['total_papers'],1)*100:>5.1f}%
   Key Papers:      {status['key_papers']/max(status['total_papers'],1)*100:>5.1f}%
   Remaining:       {status['pending']/max(status['total_papers'],1)*100:>5.1f}%

"""
        return report


def demo():
    """Demonstrate the database system"""
    print("=" * 60)
    print("Research Hunter - Database System Demo")
    print("=" * 60)
    
    # Initialize database
    db = ResearchDatabase("demo_research.db")
    
    # Add sample papers
    print("\n📚 Adding sample papers...")
    db.add_paper(
        title="Deep Learning for Natural Language Processing",
        abstract="A comprehensive survey of deep learning methods for NLP tasks including text classification, sentiment analysis, and machine translation.",
        authors="John Smith, Jane Doe",
        year=2024,
        source="arXiv"
    )
    
    db.add_paper(
        title="Transformer Models in Computer Vision",
        abstract="We present a new approach to using transformer architectures for image recognition tasks.",
        authors="Alice Johnson",
        year=2023,
        source="IEEE"
    )
    
    db.add_paper(
        title="Arabic NLP: Challenges and Solutions",
        abstract="This paper addresses the unique challenges of processing Arabic text using modern NLP techniques.",
        authors="Ahmed Hassan, Fatima Ali",
        year=2024,
        source="ACL"
    )
    
    # Process a paper
    print("\n📄 Processing paper...")
    sample_text = "This is a sample research paper with multiple sections. " * 100
    results = db.process_paper("demo_paper", sample_text)
    print(f"   Chunks processed: {results['chunks_processed']}")
    
    # Check status
    print("\n📊 Database Status:")
    status = db.get_processing_status()
    for key, value in status.items():
        print(f"   {key}: {value}")
    
    # Generate report
    print(db.generate_report())
    
    # Search
    print("\n🔍 Searching for 'Arabic'...")
    results = db.search_papers("Arabic", "all")
    for r in results:
        print(f"   - {r['title']} ({r['status']})")
    
    print("\n✅ Demo complete!")
    return db


if __name__ == "__main__":
    demo()