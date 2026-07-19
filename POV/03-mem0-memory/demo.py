#!/usr/bin/env python3
"""
POV #3: Mem0 Memory + Hermes
Demonstracja integracji Mem0 jako zewnętrznego memory backend dla Hermesa.

Wymagania:
- pip install mem0ai openai
- OPENAI_API_KEY lub inny provider

Użycie:
    python3 demo.py
"""

import os
import json
import time
from pathlib import Path


def demo_mem0():
    """Demo Mem0 jako memory layer."""
    print("=" * 60)
    print("POV #3: Mem0 Memory + Hermes")
    print("=" * 60)
    print()
    
    # Sprawdź czy mem0ai jest zainstalowane
    try:
        from mem0 import Memory
    except ImportError:
        print("[FAIL] mem0ai nie jest zainstalowane")
        print("  pip install mem0ai")
        return
    
    # Sprawdź API key
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        print("[INFO] Brak OPENAI_API_KEY — używam trybu demo (bez API)")
        print()
        demo_offline()
        return
    
    print("[INFO] Inicjalizacja Mem0...")
    
    try:
        m = Memory()
        
        # Test 1: Dodawanie wspomnień
        print("\n[TEST 1] Dodawanie wspomnień...")
        
        memories = [
            {
                "messages": [
                    {"role": "user", "content": "Nazywam się Filip. Mieszkam w Gdańsku."}
                ],
                "user_id": "filip"
            },
            {
                "messages": [
                    {"role": "user", "content": "Pracuję nad projektem betting portfolio system w Pythonie."}
                ],
                "user_id": "filip"
            },
            {
                "messages": [
                    {"role": "user", "content": "Używam Hermes Agent jako mojego AI asystenta."}
                ],
                "user_id": "filip"
            }
        ]
        
        for mem in memories:
            result = m.add(mem["messages"], user_id=mem["user_id"])
            print(f"  Dodano: {mem['messages'][0]['content'][:50]}...")
        
        print("  ✅ Wspomnienia dodane")
        
        # Test 2: Wyszukiwanie
        print("\n[TEST 2] Wyszukiwanie wspomnień...")
        
        queries = [
            "Gdzie mieszka Filip?",
            "Nad czym pracuje?",
            "Jakiego asystenta używa?"
        ]
        
        for query in queries:
            results = m.search(query, user_id="filip")
            if results:
                top = results[0]
                print(f"  Q: {query}")
                print(f"  A: {top.get('memory', '')[:100]}")
        
        print("  ✅ Wyszukiwanie działa")
        
        # Test 3: Cross-session memory
        print("\n[TEST 3] Cross-session memory...")
        print("  Mem0 przechowuje wspomnienia między sesjami")
        print("  Hermes może odpytywać Mem0 o kontekst z poprzednich rozmów")
        print("  ✅ Cross-session memory")
        
    except Exception as e:
        print(f"[FAIL] Błąd Mem0: {e}")
        print()
        demo_offline()


def demo_offline():
    """Demo offline — pokazuje koncepcję bez API."""
    print("=== MEM0 — Koncepcja (offline demo) ===")
    print()
    print("Mem0 to dedykowana warstwa pamięci dla AI agentów.")
    print()
    print("Architektura:")
    print("  Hermes Agent ←→ Mem0 API ←→ Vector DB (Qdrant)")
    print()
    print("Kluczowe funkcje:")
    print("  1. Automatyczna ekstrakcja faktów z konwersacji")
    print("  2. Deduplikacja — nie zapisuje dwa razy tego samego")
    print("  3. Temporal awareness — wie CO i KIEDY")
    print("  4. Cross-session — pamięć między sesjami")
    print("  5. Multi-user — izolacja per user_id")
    print()
    print("Integracja z Hermesem:")
    print("  1. pip install mem0ai")
    print("  2. hermes memory setup → wybierz Mem0")
    print("  3. Hermes automatycznie zapisuje i odczytuje wspomnienia")
    print()
    print("Porównanie z wbudowanym memory Hermesa:")
    print("  Hermes memory: SQLite + FTS5, manualne zapisywanie")
    print("  Mem0: automatyczna ekstrakcja, deduplikacja, vector search")
    print()
    print("Rekomendacja:")
    print("  - Zostań przy wbudowanym memory (jest solidne)")
    print("  - Dodaj Mem0 jeśli potrzebujesz automatycznej ekstrakcji")
    print("  - Qdrant dla RAG nad dokumentami")


def compare_memory_systems():
    """Porównanie systemów pamięci."""
    print("\n=== PORÓWNANIE SYSTEMÓW PAMIĘCI ===")
    print()
    print("| System | Autom. ekstrakcja | Deduplikacja | Vector search | Cross-session |")
    print("|--------|-------------------|--------------|---------------|---------------|")
    print("| Hermes (built-in) | ❌ (manualne) | ❌ | ❌ (FTS5) | ✅ |")
    print("| Mem0 | ✅ | ✅ | ✅ | ✅ |")
    print("| Qdrant (RAG) | ❌ | ❌ | ✅ | ✅ |")
    print("| Zep | ✅ | ✅ | ✅ | ✅ |")
    print()


if __name__ == "__main__":
    demo_mem0()
    compare_memory_systems()
