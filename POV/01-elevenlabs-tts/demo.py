#!/usr/bin/env python3
"""
POV #1: ElevenLabs TTS + Hermes
Demonstracja integracji ElevenLabs Text-to-Speech z Hermes Agent.

Wymagania:
- pip install elevenlabs
- ELEVENLABS_API_KEY w zmiennych środowiskowych (lub w Bitwarden)

Użycie:
    python3 demo.py "Cześć, tu Hermes. Testuję ElevenLabs."
"""

import os
import sys
import subprocess
import json
from pathlib import Path

# Pobierz API key z Bitwarden lub env
def get_api_key():
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        return key
    
    try:
        result = subprocess.run(
            ["bws", "secret", "get", "893e302b-cd6b-4b40-aaea-b47b01615bb2",
             "--server-url", "https://vault.bitwarden.eu"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data["value"]
    except Exception as e:
        print(f"[ERROR] Nie można pobrać API key: {e}", file=sys.stderr)
    
    return None


def test_elevenlabs_tts(text: str, output_path: str = None):
    """Testuje ElevenLabs TTS i zapisuje audio do pliku."""
    from elevenlabs import ElevenLabs
    
    api_key = get_api_key()
    if not api_key:
        print("[FAIL] Brak ELEVENLABS_API_KEY")
        return False
    
    client = ElevenLabs(api_key=api_key)
    
    # List dostępnych głosów
    print("[INFO] Pobieram listę głosów...")
    voices = client.voices.get_all()
    print(f"[INFO] Dostępne głosy: {len(voices.voices)}")
    for v in voices.voices[:5]:
        print(f"  - {v.name} (id: {v.voice_id})")
    
    # Generuj audio
    print(f"\n[INFO] Generuję audio dla: '{text}'")
    audio = client.text_to_speech.convert(
        text=text,
        voice_id="JBFqnCBsd6RMkjVDRZzb",  # "George" - naturalny męski głos
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    
    # Zapisz
    if output_path is None:
        output_path = "/tmp/hermes_elevenlabs_demo.mp3"
    
    # audio to generator bajtów
    audio_bytes = b"".join(audio)
    Path(output_path).write_bytes(audio_bytes)
    
    file_size = len(audio_bytes)
    print(f"[OK] Audio zapisane: {output_path} ({file_size} bajtów)")
    
    return True


def compare_with_edge_tts(text: str):
    """Porównuje ElevenLabs z Edge TTS (obecny default Hermesa)."""
    print("\n=== PORÓWNANIE: ElevenLabs vs Edge TTS ===")
    print(f"Tekst: '{text}'")
    print()
    
    # ElevenLabs
    import time
    start = time.time()
    success = test_elevenlabs_tts(text, "/tmp/hermes_elevenlabs.mp3")
    eleven_time = time.time() - start
    
    if success:
        print(f"  ElevenLabs: {eleven_time:.2f}s → /tmp/hermes_elevenlabs.mp3")
    
    # Edge TTS (przez hermes)
    print(f"  Edge TTS: wbudowany w Hermesa (darmowy, offline)")
    print()
    print("Wnioski:")
    print("  - ElevenLabs: lepsza jakość, naturalne brzmienie, 32+ języków")
    print("  - Edge TTS: darmowy, nie wymaga API key, działa offline")
    print("  - Rekomendacja: ElevenLabs dla jakości, Edge dla fallbacku")


def configure_hermes():
    """Instrukcja konfiguracji Hermesa."""
    print("\n=== KONFIGURACJA HERMESA ===")
    print()
    print("1. Dodaj API key do .env:")
    print("   echo 'ELEVENLABS_API_KEY=sk_...' >> ~/.hermes/.env")
    print()
    print("2. Zmień provider TTS:")
    print("   hermes config set tts.provider elevenlabs")
    print()
    print("3. Restartuj Hermesa:")
    print("   /reset (w sesji) lub zrestartuj CLI")
    print()
    print("4. Test:")
    print("   /voice tts")
    print("   Cześć, tu Hermes na ElevenLabs!")


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "Cześć! Tu Hermes Agent. Testuję syntezę mowy ElevenLabs. Jakość jest znacznie lepsza niż domyślny Edge TTS."
    
    print("=" * 60)
    print("POV #1: ElevenLabs TTS + Hermes")
    print("=" * 60)
    print()
    
    compare_with_edge_tts(text)
    configure_hermes()
