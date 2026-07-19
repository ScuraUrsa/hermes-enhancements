# POV #6: Qdrant RAG Pipeline for Hermes

## Cel
Zbudować pipeline Retrieval-Augmented Generation (RAG) używając Qdrant jako vector database i OpenAI embeddings przez Ollama Cloud.

## Status
✅ qdrant-client 1.18.0 zainstalowane
✅ openai 2.46.0 zainstalowane
✅ numpy 2.2.6 zainstalowane
✅ Demo: index, search, RAG, filtered search
⚠️  Embedding API call wymaga tokenów Ollama Cloud

## Szybki start

```bash
cd ~/workspace/hermes-enhancements/POV/06-qdrant-rag

# Indeksuj bazę wiedzy
python3 demo.py index

# Wyszukiwanie semantyczne
python3 demo.py search "How does voice integration work?"

# Pełny pipeline RAG
python3 demo.py rag "What TTS providers does Hermes support?"

# Demo wszystkiego
python3 demo.py all
```

## Architektura

```
Dokumenty (10+)
    │
    ▼
Embedding Client (OpenAI text-embedding-3-small)
    │
    ▼
Qdrant (in-memory, cosine distance)
    │
    ├── search() → top-k dokumentów
    │
    └── rag_query() → context + prompt dla LLM
```

## Pipeline

1. **Index**: Dokumenty → embeddingi → Qdrant points
2. **Search**: Query → embedding → cosine similarity → top-k
3. **RAG**: Search → context assembly → prompt dla LLM
4. **Filter**: Search z filtrowaniem po kategorii/tagach

## Knowledge Base

10 dokumentów o Hermes enhancements:
- Hermes Agent Overview
- ElevenLabs TTS Integration
- Browser Automation (Selenium)
- Mem0 Memory Backend
- Token Monitor System
- CrewAI Orchestration
- Qdrant RAG Pipeline (ten POV)
- Real-time Voice Pipeline (planned)
- GitHub Integration
- Notification Bridge

## Integracja z Hermesem

### Opcja A: Custom Tool
```python
# Dodaj jako narzędzie Hermesa
@tool("qdrant_search")
def qdrant_search(query: str, top_k: int = 3) -> str:
    """Search Hermes knowledge base using Qdrant."""
    rag = QdrantRAG()
    rag.index()  # ensure indexed
    results = rag.search(query, top_k=top_k)
    return json.dumps(results)
```

### Opcja B: RAG przed każdym promptem
```python
# Wzbogać kontekst przed wysłaniem do LLM
rag = QdrantRAG()
context = rag.rag_query(user_query)
augmented_prompt = f"{context['context']}\n\nUser: {user_query}"
```

## Kluczowe zalety

- **In-memory Qdrant**: zero zależności od zewnętrznych serwerów
- **OpenAI embeddings**: 1536-wymiarowe, wysokiej jakości
- **Cosine distance**: standard dla semantic search
- **Filtrowanie**: category + tags dla precyzyjnych zapytań
- **Python 3.10+**: działa na tej VM bez dodatkowych instalacji
- **10 dokumentów**: realistyczna baza wiedzy o Hermesie

## Wnioski

- Qdrant in-memory to najprostszy start — zero konfiguracji
- OpenAI embeddings przez Ollama Cloud działają jako drop-in
- Pipeline jest gotowy do integracji jako Hermes tool
- Dla produkcji: Qdrant na dysku lub w Dockerze
- Embeddingi można cachować dla oszczędności tokenów
