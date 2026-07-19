# POV #3: Mem0 Memory + Hermes

## Cel
Zintegrować Mem0 jako zewnętrzny memory backend dla Hermesa.

## Status
✅ mem0ai zainstalowane
⚠️  Demo offline (brak OPENAI_API_KEY na tej VM)
✅ Koncepcja udokumentowana

## Szybki start

```bash
# 1. Zainstaluj
pip install mem0ai

# 2. Ustaw API key
export OPENAI_API_KEY="sk-..."

# 3. Uruchom demo
cd ~/workspace/hermes-enhancements/POV/03-mem0-memory
python3 demo.py
```

## Architektura

```
Hermes Agent ←→ Mem0 API ←→ Vector DB (Qdrant)
                    ↓
            Automatyczna ekstrakcja faktów
            Deduplikacja
            Temporal awareness
```

## Kluczowe funkcje Mem0

1. **Automatyczna ekstrakcja** — wyciąga fakty z konwersacji bez manualnego zapisywania
2. **Deduplikacja** — nie zapisuje dwa razy tego samego faktu
3. **Temporal awareness** — wie CO i KIEDY zostało zapisane
4. **Cross-session** — pamięć między sesjami
5. **Multi-user** — izolacja per user_id

## Porównanie z wbudowanym memory Hermesa

| Cecha | Hermes (built-in) | Mem0 |
|-------|-------------------|------|
| Autom. ekstrakcja | ❌ (manualne) | ✅ |
| Deduplikacja | ❌ | ✅ |
| Vector search | ❌ (FTS5) | ✅ |
| Cross-session | ✅ | ✅ |
| Instalacja | Wbudowany | pip install |
| Koszt | Darmowy | Wymaga API (OpenAI) |

## Integracja z Hermesem

```bash
# Hermes ma wbudowaną integrację z Mem0
hermes memory setup
# → Wybierz "Mem0" jako provider
# → Podaj OPENAI_API_KEY
```

## Wnioski

- Wbudowany memory Hermesa jest solidny (SQLite + FTS5, zero kosztów)
- Mem0 dodaje automatyczną ekstrakcję i deduplikację
- Wymaga API key (OpenAI lub kompatybilny)
- Rekomendacja: zostań przy wbudowanym, dodaj Mem0 gdy potrzebujesz automatyzacji
