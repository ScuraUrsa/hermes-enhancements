# pantry-guard — strażnik zapisów spiżarni

Mały lokalny model (Qwen3.5-4B na llama.cpp) czasem odpisuje „Dodałem mleko ✅”, choć nie wywołał
`dom.py` (w benchmarku 3 na 69 przebiegów w rundzie 3). Bywa też, że po `dom batch` z liniami ❌
odpowiedź ich nie wspomina. Ten plugin Hermesa sprawdza odpowiedź, zanim trafi do Filipa:

| Sytuacja w turze | Co robi |
|---|---|
| Odpowiedź mówi „dodałem / zapisałem / przeniosłem / usunąłem / zmieniłem…”, a żadne wywołanie `dom.py` nic nie zapisało (brak wywołania albo exit ≠ 0 bez linii ✅) | Zastępuje odpowiedź: „⚠️ Nic nie zostało zapisane w spiżarni…” |
| `dom batch` miał linie ❌, a odpowiedź ich nie przyznaje | Dopisuje „⚠️ Tego NIE zapisano:” z liniami ❌ |
| Odpowiedź sama mówi, że czegoś nie zapisano, albo nic nie twierdzi o zapisie | Bez zmian |
| Brak `dom.py` i nic o spiżarni/szafach w pytaniu ani w odpowiedzi (np. „Dodałem spotkanie”) | Bez zmian |

Hooki: `pre_llm_call` (zeruje bufor sesji), `post_tool_call` (zapisuje wywołania terminala z `dom.py`,
exit code i wynik), `transform_llm_output` (sprawdza odpowiedź). Hook może tylko podmienić tekst, więc
plugin nie każe modelowi powtórzyć, tylko mówi uczciwie, że nic nie zapisano.
Działa na Hermesie 0.20 (prod, `a6ede70c2`). Przy streamingu użytkownik zobaczyłby oba teksty, ale prod
ma streaming wyłączony.

Domyślnie pilnuje tylko modelu `qwen3.5-4b` (dostawca `local-qwen`). Pozostałe modele ustawia się w config:

```yaml
plugins:
  enabled: [pantry-guard]
  entries:
    pantry-guard:
      settings: {enabled: true, models: ["qwen3.5-4b"]}   # ["*"] = każdy model
```

Instalacja ręczna: skopiować `plugin/` jako `~/.hermes/plugins/pantry-guard/`, dopisać powyższe do
`~/.hermes/config.yaml`, zrestartować gateway. Testy: `python3 -m pytest -q pantry-guard/tests` (21, bez Hermesa).
