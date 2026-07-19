# AI Agent Memory — Research (Lipiec 2026)

## Stan ekosystemu

### 5 głównych systemów memory (2026)

| System | GitHub Stars | Architektura | Best For |
|--------|-------------|-------------|----------|
| **Mem0** | ~55k | Memory layer (API) | Szybkie wdrożenie, ekosystem |
| **Zep** | ~5k | Enterprise memory | Compliance, multi-tenancy |
| **Graphiti** | ~3k | Graph-based (Neo4j) | Relacje, temporal knowledge |
| **Letta** | ~15k | Stateful agents | Persistent agent state |
| **LangMem** | ~2k | LangChain-native | LangChain ecosystem |

### Vector DBs (warstwa infrastruktury)

| DB | Latency | Recall | Open Source | Best For |
|----|---------|--------|-------------|----------|
| **Qdrant** | 3ms | 99.2% | ✅ (Rust) | Szybkość, filtering |
| **Pinecone** | 12ms | 95% | ❌ (SaaS) | Managed, scale |
| **ChromaDB** | ~10ms | ~97% | ✅ (Python) | Prototyping, local |
| **Weaviate** | ~8ms | ~98% | ✅ (Go) | Hybrid search |
| **Milvus** | ~5ms | ~99% | ✅ (C++) | Scale, GPU acceleration |

### 3 osie taksonomii memory (2026)

1. **Forms** (gdzie żyje): token, latent, parametric
2. **Functions** (do czego): factual, experiential, working
3. **Dynamics** (jak się zachowuje): formation, consolidation, forgetting, retrieval

## Hermes Memory obecnie

- **Built-in memory**: SQLite + FTS5 (session store)
- **Memory tool**: `memory` tool do zapisywania faktów
- **User profile**: osobny store na preferencje
- **Session search**: `session_search` — FTS5, bez aux-LLM
- **Pluggable backends**: Honcho, Mem0, i więcej
- **Konfiguracja**: `hermes memory setup`

## Rekomendacje

### POV #5: Mem0 + Hermes
- Mem0 jako zewnętrzny memory backend
- Automatyczna ekstrakcja faktów z konwersacji
- Cross-session memory z lepszą deduplikacją
- **Impact: 7/10, Effort: 5/10**

### POV #6: Qdrant + Hermes (RAG)
- Qdrant jako vector store dla dokumentów
- RAG pipeline: dokumenty → embedding → Qdrant → Hermes
- Daje: long-term document memory, semantic search
- **Impact: 8/10, Effort: 6/10**

### Ulepszenia istniejącego memory
- Hermes już ma solidny memory system
- `session_search` jest efektywny (FTS5, zero tokenów)
- Mem0 może dodać automatyczną ekstrakcję i deduplikację
- Qdrant może dodać semantic search nad dokumentami
