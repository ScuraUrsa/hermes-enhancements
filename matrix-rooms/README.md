# matrix_rooms: osobne pokoje Matrix na projekty i długie zadania

Prośba Filipa z 24.10.2026: główna rozmowa z Hermesem w Matrix służy do powiadomień, powtarzalnych rzeczy,
szybkiej rozmowy i bieżących spraw. Projekty, research i długie zadania idą do osobnych pokoi, żeby każde
miało własną sesję i własny kontekst. Plan: `plany/research/2026-10-24-matrix-kontekst-i-pokoje.md` (K101).

## Co robi

- Narzędzie `matrix_room_create(name, brief, topic?)` zakłada szyfrowany, prywatny pokój przez żywy adapter
  Matrix bramy (to samo urządzenie E2EE, bez drugiego logowania), zaprasza Filipa z prawami admina i zapisuje
  streszczenie zadania w `~/.hermes/matrix_rooms/briefs.json`.
- Hermes używa go na prośbę („załóż pokój X”) albo sam, gdy w głównej rozmowie pojawia się projekt, research
  lub długie zadanie (reguła jest w opisie narzędzia, więc model widzi ją w każdej turze).
- Bot nie może sam zacząć tury w nowym pokoju (Hermes v0.20 nie wstrzykuje wiadomości do bramy), więc
  hook `pre_llm_call` dokleja streszczenie do pierwszej wiadomości Filipa w tym pokoju. Raz.
- Pokój z Filipem i botem (≤2 osoby) to dla adaptera DM: osobna sesja, bez wymogu wzmianki.

Kliknięcie działa bez wtyczki: pokój założony w Elemencie z zaproszeniem `@hermes` bot przyjmuje sam
(zaproszenia od `MATRIX_ALLOWED_USERS`).

## Wdrożenie

Rola WOBI `hermes` (`hermes_local_plugins`, pliki w `ansible/roles/hermes/files/plugins/matrix_rooms/`).
Ręcznie: skopiuj `plugin/` do `~/.hermes/plugins/matrix_rooms/`, dodaj `matrix_rooms` do `plugins.enabled`
w `~/.hermes/config.yaml`, zrestartuj `hermes-gateway`.

## Testy

`python -m pytest matrix-rooms/tests` (bez Hermesa: atrapa bramy i klienta mautrix).
