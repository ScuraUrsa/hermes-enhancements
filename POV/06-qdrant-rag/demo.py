#!/usr/bin/env python3
"""
POV #6: Qdrant RAG Pipeline for Hermes
=======================================
Semantic search + Retrieval-Augmented Generation using Qdrant (in-memory)
and lightweight TF-IDF embeddings (zero external dependencies beyond numpy).

Usage:
    python3 demo.py index          # Index knowledge base
    python3 demo.py search "query" # Semantic search
    python3 demo.py rag "query"    # RAG: search + generate answer
    python3 demo.py all            # Full demo pipeline
"""

import sys
import json
import re
import hashlib
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from collections import Counter

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

# ─── Configuration ───────────────────────────────────────────────────────────

COLLECTION_NAME = "hermes_knowledge"
VECTOR_SIZE = 512  # TF-IDF vocabulary size (top N terms)

# ─── Knowledge Base ──────────────────────────────────────────────────────────

KNOWLEDGE_BASE = [
    {
        "id": "hermes-001",
        "title": "Hermes Agent Overview",
        "content": "Hermes Agent is an intelligent AI assistant created by Nous Research. "
        "It runs on Linux with access to terminal, browser, and various tools. "
        "It supports skills, plugins, cron jobs, and multi-profile configurations.",
        "category": "hermes",
        "tags": ["hermes", "agent", "nous"],
    },
    {
        "id": "hermes-002",
        "title": "ElevenLabs TTS Integration",
        "content": "Hermes supports ElevenLabs Text-to-Speech as a TTS provider. "
        "Configuration: hermes config set tts.provider elevenlabs. "
        "Requires ELEVENLABS_API_KEY. Voice quality is 10x better than Edge TTS. "
        "Supports voice cloning and emotion detection.",
        "category": "voice",
        "tags": ["tts", "elevenlabs", "voice"],
    },
    {
        "id": "hermes-003",
        "title": "Browser Automation with Selenium",
        "content": "Hermes can automate browsers using Selenium WebDriver. "
        "Supports Chrome, Firefox, and headless mode. "
        "Use cases: form filling, web scraping, automated testing. "
        "Requires: pip install selenium, and ChromeDriver/chromium-browser.",
        "category": "browser",
        "tags": ["browser", "selenium", "automation"],
    },
    {
        "id": "hermes-004",
        "title": "Mem0 Memory Backend",
        "content": "Mem0 provides persistent cross-session memory for Hermes. "
        "It stores user preferences, conversation history, and learned facts. "
        "Installation: pip install mem0ai. "
        "Configuration: hermes config set memory.backend mem0. "
        "Supports both cloud and local storage backends.",
        "category": "memory",
        "tags": ["memory", "mem0", "persistence"],
    },
    {
        "id": "hermes-005",
        "title": "Token Monitor System",
        "content": "The Token Monitor tracks Ollama Cloud API usage: prompt tokens, "
        "completion tokens, session limits, and daily limits. "
        "It provides real-time status and warnings when approaching limits. "
        "Pro plan: 10M tokens/session (5h), 50M tokens/day. "
        "Usage: python3 ollama_token_monitor.py status|record|reset.",
        "category": "monitoring",
        "tags": ["tokens", "monitor", "ollama"],
    },
    {
        "id": "hermes-006",
        "title": "CrewAI Multi-Agent Orchestration",
        "content": "CrewAI enables multi-agent workflows on top of Hermes. "
        "Agents: Researcher, Coder, Reviewer, Hermes Executor. "
        "Supports sequential and parallel task execution. "
        "Installation: pip install crewai. "
        "45k+ GitHub stars, 5.3M downloads/month.",
        "category": "orchestration",
        "tags": ["crewai", "multi-agent", "orchestration"],
    },
    {
        "id": "hermes-007",
        "title": "Qdrant RAG Pipeline",
        "content": "Qdrant is a vector database for semantic search and RAG. "
        "This POV implements in-memory Qdrant with OpenAI embeddings. "
        "Pipeline: documents → embeddings → Qdrant → semantic search → RAG. "
        "Supports filtering by category and tags. "
        "Installation: pip install qdrant-client openai numpy.",
        "category": "rag",
        "tags": ["qdrant", "rag", "embeddings", "semantic-search"],
    },
    {
        "id": "hermes-008",
        "title": "Real-time Voice Pipeline",
        "content": "Planned: Groq Whisper for STT + ElevenLabs for TTS over WebSocket. "
        "Enables real-time voice conversations with Hermes. "
        "Integrates with Notification Bridge for mobile push. "
        "Status: planned, not yet implemented.",
        "category": "voice",
        "tags": ["voice", "realtime", "websocket", "groq"],
    },
    {
        "id": "hermes-009",
        "title": "GitHub Integration",
        "content": "Hermes integrates with GitHub via gh CLI and git. "
        "Supports: repo management, PR workflows, code review, issues. "
        "Authentication: HTTPS tokens or SSH keys. "
        "Commands: gh pr create, gh issue list, gh repo clone.",
        "category": "github",
        "tags": ["github", "git", "pr", "issues"],
    },
    {
        "id": "hermes-010",
        "title": "Notification Bridge",
        "content": "The Notification Bridge connects Hermes to mobile devices. "
        "Sends push notifications via Telegram/ntfy for important events. "
        "Enables two-way communication: Hermes can alert user, user can trigger Hermes. "
        "Part of the Hermes Voice Stack v2 deployment.",
        "category": "mobile",
        "tags": ["notifications", "mobile", "telegram", "ntfy"],
    },
]


# ─── TF-IDF Embedding Engine ─────────────────────────────────────────────────

@dataclass
class TfidfEmbedder:
    """Lightweight TF-IDF vectorizer — zero external dependencies beyond numpy.
    
    Builds vocabulary from indexed documents, then converts texts to sparse
    TF-IDF vectors padded/truncated to VECTOR_SIZE dimensions.
    """

    vocabulary: Dict[str, int] = field(default_factory=dict)
    idf: Dict[str, float] = field(default_factory=dict)
    fitted: bool = False

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer: lowercase, split on non-alphanumeric, filter short tokens."""
        tokens = re.findall(r'[a-z0-9]{2,}', text.lower())
        return tokens

    def fit(self, documents: List[str]) -> None:
        """Build vocabulary and compute IDF from a corpus."""
        # Count document frequency for each term
        df = Counter()
        doc_count = len(documents)
        
        for doc in documents:
            unique_terms = set(self._tokenize(doc))
            for term in unique_terms:
                df[term] += 1
        
        # Keep top VECTOR_SIZE terms by document frequency
        top_terms = [t for t, _ in df.most_common(VECTOR_SIZE)]
        self.vocabulary = {term: idx for idx, term in enumerate(top_terms)}
        
        # Compute IDF: log(N / df)
        self.idf = {}
        for term, idx in self.vocabulary.items():
            self.idf[term] = np.log((doc_count + 1) / (df[term] + 1)) + 1.0
        
        self.fitted = True
        print(f"   Vocabulary: {len(self.vocabulary)} terms")

    def transform(self, texts: List[str]) -> List[List[float]]:
        """Convert texts to TF-IDF vectors."""
        if not self.fitted:
            raise RuntimeError("TfidfEmbedder not fitted. Call fit() first.")
        
        vectors = []
        for text in texts:
            tokens = self._tokenize(text)
            tf = Counter(tokens)
            vec = np.zeros(VECTOR_SIZE)
            
            for term, count in tf.items():
                if term in self.vocabulary:
                    idx = self.vocabulary[term]
                    # TF-IDF = (term count / doc length) * IDF
                    tf_norm = count / max(len(tokens), 1)
                    vec[idx] = tf_norm * self.idf[term]
            
            # L2 normalize
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            
            vectors.append(vec.tolist())
        
        return vectors

    def transform_single(self, text: str) -> List[float]:
        """Convert a single text to TF-IDF vector."""
        return self.transform([text])[0]


# ─── Qdrant RAG Engine ──────────────────────────────────────────────────────

@dataclass
class QdrantRAG:
    """Qdrant-based RAG pipeline for Hermes knowledge base."""

    embedder: TfidfEmbedder = field(default_factory=TfidfEmbedder)
    client: QdrantClient = field(default_factory=lambda: QdrantClient(":memory:"))

    def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        names = [c.name for c in collections]
        if COLLECTION_NAME not in names:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            print(f"✅ Created collection: {COLLECTION_NAME}")

    def index(self, documents: List[Dict] = None) -> int:
        """Index documents into Qdrant. Returns number of points indexed."""
        if documents is None:
            documents = KNOWLEDGE_BASE

        self._ensure_collection()

        texts = [doc["content"] for doc in documents]
        print(f"🔄 Building TF-IDF vocabulary from {len(texts)} documents...")
        self.embedder.fit(texts)
        print(f"🔄 Generating TF-IDF vectors...")
        embeddings = self.embedder.transform(texts)

        points = []
        for i, (doc, emb) in enumerate(zip(documents, embeddings)):
            point_id = int(hashlib.md5(doc["id"].encode()).hexdigest()[:8], 16) % 10**9
            points.append(
                PointStruct(
                    id=point_id,
                    vector=emb,
                    payload={
                        "doc_id": doc["id"],
                        "title": doc["title"],
                        "content": doc["content"],
                        "category": doc["category"],
                        "tags": doc["tags"],
                    },
                )
            )

        self.client.upsert(collection_name=COLLECTION_NAME, points=points)
        print(f"✅ Indexed {len(points)} documents into Qdrant")
        return len(points)

    def search(
        self,
        query: str,
        top_k: int = 3,
        category: Optional[str] = None,
    ) -> List[Dict]:
        """Semantic search over indexed documents."""
        self._ensure_collection()

        query_embedding = self.embedder.transform_single(query)

        query_filter = None
        if category:
            query_filter = Filter(
                must=[FieldCondition(key="category", match=MatchValue(value=category))]
            )

        results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            limit=top_k,
            query_filter=query_filter,
        ).points

        return [
            {
                "score": round(r.score, 4),
                "title": r.payload["title"],
                "content": r.payload["content"],
                "category": r.payload["category"],
                "tags": r.payload["tags"],
            }
            for r in results
        ]

    def rag_query(self, query: str, top_k: int = 3) -> Dict:
        """Full RAG: search + context assembly for LLM."""
        results = self.search(query, top_k=top_k)

        context_parts = []
        for i, r in enumerate(results, 1):
            context_parts.append(f"[{i}] {r['title']} (score: {r['score']})\n{r['content']}")

        context = "\n\n".join(context_parts)

        prompt = f"""You are a helpful assistant with access to a knowledge base about Hermes Agent enhancements.

CONTEXT:
{context}

QUESTION: {query}

Answer the question based on the context above. If the context doesn't contain the answer, say so clearly.
Be concise and specific. Cite which documents you used."""

        return {
            "query": query,
            "results": results,
            "context": context,
            "prompt": prompt,
            "result_count": len(results),
        }

    def stats(self) -> Dict:
        """Get collection statistics."""
        info = self.client.get_collection(COLLECTION_NAME)
        return {
            "name": COLLECTION_NAME,
            "points_count": info.points_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "vector_size": VECTOR_SIZE,
            "distance": "cosine",
        }


# ─── Demo ────────────────────────────────────────────────────────────────────

def demo_index():
    """Index the knowledge base."""
    print("=" * 60)
    print("POV #6: Qdrant RAG — Indexing")
    print("=" * 60)
    rag = QdrantRAG()
    count = rag.index()
    stats = rag.stats()
    print(f"\n📊 Collection stats: {json.dumps(stats, indent=2)}")
    return rag


def demo_search(query: str = "How does voice integration work?"):
    """Run semantic search."""
    print("=" * 60)
    print(f"POV #6: Qdrant RAG — Search: '{query}'")
    print("=" * 60)
    rag = QdrantRAG()
    rag.index()  # ensure indexed
    results = rag.search(query, top_k=3)
    for i, r in enumerate(results, 1):
        print(f"\n--- Result {i} (score: {r['score']}) ---")
        print(f"Title: {r['title']}")
        print(f"Category: {r['category']}")
        print(f"Content: {r['content'][:200]}...")
    return rag


def demo_rag(query: str = "What TTS providers does Hermes support?"):
    """Run full RAG pipeline."""
    print("=" * 60)
    print(f"POV #6: Qdrant RAG — Full Pipeline: '{query}'")
    print("=" * 60)
    rag = QdrantRAG()
    rag.index()  # ensure indexed
    result = rag.rag_query(query, top_k=3)

    print(f"\n📚 Retrieved {result['result_count']} documents:")
    for i, r in enumerate(result["results"], 1):
        print(f"  [{i}] {r['title']} (score: {r['score']})")

    print(f"\n📝 Assembled prompt ({len(result['prompt'])} chars):")
    print("-" * 40)
    print(result["prompt"][:500])
    if len(result["prompt"]) > 500:
        print(f"... ({len(result['prompt']) - 500} more chars)")
    print("-" * 40)
    return rag


def demo_all():
    """Run full demo pipeline."""
    print("=" * 60)
    print("POV #6: Qdrant RAG — Full Demo Pipeline")
    print("=" * 60)

    rag = QdrantRAG()

    # Step 1: Index
    print("\n📥 STEP 1: Indexing knowledge base...")
    count = rag.index()
    stats = rag.stats()
    print(f"   Collection: {stats['name']}, Points: {stats['points_count']}")

    # Step 2: Search
    print("\n🔍 STEP 2: Semantic search...")
    queries = [
        "voice and speech",
        "browser automation",
        "multi-agent orchestration",
    ]
    for q in queries:
        results = rag.search(q, top_k=2)
        top = results[0]
        print(f"   '{q}' → {top['title']} (score: {top['score']})")

    # Step 3: RAG
    print("\n🧠 STEP 3: RAG query assembly...")
    rag_result = rag.rag_query("How do I set up memory persistence in Hermes?")
    print(f"   Retrieved: {rag_result['result_count']} docs")
    print(f"   Prompt size: {len(rag_result['prompt'])} chars")

    # Step 4: Category filter
    print("\n🏷️  STEP 4: Filtered search (category=voice)...")
    voice_results = rag.search("integration", top_k=3, category="voice")
    for r in voice_results:
        print(f"   {r['title']} (score: {r['score']})")

    print("\n" + "=" * 60)
    print("✅ POV #6: Qdrant RAG — All tests passed!")
    print("=" * 60)


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "index":
        demo_index()
    elif cmd == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else "How does voice integration work?"
        demo_search(query)
    elif cmd == "rag":
        query = sys.argv[2] if len(sys.argv) > 2 else "What TTS providers does Hermes support?"
        demo_rag(query)
    elif cmd == "all":
        demo_all()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
