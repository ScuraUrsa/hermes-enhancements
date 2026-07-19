#!/usr/bin/env python3
"""
POV #2: Selenium Browser Automation + Hermes
Demonstracja automatyzacji przeglądarki przez Selenium WebDriver.

Wymagania:
- pip install selenium webdriver-manager
- Google Chrome (już zainstalowany)

Użycie:
    python3 demo.py
"""

import time
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


class HermesBrowser:
    """Wrapper do automatyzacji przeglądarki dla Hermesa."""
    
    def __init__(self, headless: bool = True):
        self.options = Options()
        if headless:
            self.options.add_argument("--headless=new")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--window-size=1920,1080")
        self.options.page_load_strategy = 'eager'  # nie czekaj na wszystkie zasoby
        self.driver = None
    
    def start(self):
        """Uruchom przeglądarkę."""
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=self.options)
        self.driver.set_page_load_timeout(10)
        return self
    
    def navigate(self, url: str):
        """Nawiguj do URL."""
        try:
            self.driver.get(url)
        except Exception as e:
            print(f"  [WARN] Page load timeout: {e}")
        return self
    
    def get_snapshot(self) -> dict:
        """Pobierz accessibility snapshot strony."""
        title = self.driver.title
        url = self.driver.current_url
        
        body_text = self.driver.find_element(By.TAG_NAME, "body").text[:2000]
        
        interactive = []
        for elem in self.driver.find_elements(By.CSS_SELECTOR, 
            "a, button, input, select, textarea, [role='button']"):
            try:
                tag = elem.tag_name
                text = elem.text or elem.get_attribute("placeholder") or elem.get_attribute("aria-label") or ""
                elem_id = elem.get_attribute("id") or ""
                href = elem.get_attribute("href") or ""
                interactive.append({
                    "tag": tag,
                    "text": text[:100],
                    "id": elem_id,
                    "href": href[:200]
                })
            except:
                pass
        
        return {
            "title": title,
            "url": url,
            "body_preview": body_text[:500],
            "interactive_elements": interactive[:20],
            "total_interactive": len(interactive)
        }
    
    def type_text(self, css: str, text: str):
        """Wpisz tekst w pole."""
        elem = self.driver.find_element(By.CSS_SELECTOR, css)
        elem.clear()
        elem.send_keys(text)
        return self
    
    def close(self):
        """Zamknij przeglądarkę."""
        if self.driver:
            self.driver.quit()


def demo():
    """Demo automatyzacji przeglądarki."""
    print("=" * 60)
    print("POV #2: Selenium Browser Automation + Hermes")
    print("=" * 60)
    print()
    
    browser = HermesBrowser(headless=True)
    
    try:
        # Test 1: Lokalny plik HTML
        print("[TEST 1] Ładowanie lokalnej strony...")
        browser.start()
        browser.navigate(f"file:///tmp/hermes_test_page.html")
        time.sleep(1)
        snapshot = browser.get_snapshot()
        print(f"  Title: {snapshot['title']}")
        print(f"  Body: {snapshot['body_preview'][:100]}")
        print(f"  Interactive elements: {snapshot['total_interactive']}")
        print("  ✅ Lokalna strona działa")
        
        # Test 2: Wypełnianie formularza
        print("\n[TEST 2] Wypełnianie formularza...")
        browser.type_text("input[name='name']", "Filip Kaźmierczak")
        browser.type_text("input[name='email']", "test@example.com")
        print("  ✅ Formularz wypełniony")
        
        # Test 3: Snapshot po wypełnieniu
        print("\n[TEST 3] Snapshot po interakcji...")
        snapshot = browser.get_snapshot()
        print(f"  Elementy: {len(snapshot['interactive_elements'])}")
        for el in snapshot['interactive_elements']:
            print(f"    <{el['tag']}> {el['text'][:50]}")
        print("  ✅ Snapshot działa")
        
        print("\n=== INTEGRACJA Z HERMESEM ===")
        print()
        print("Selenium może być użyte jako custom tool dla Hermesa:")
        print()
        print("1. Stwórz plugin: ~/.hermes/plugins/browser_selenium/")
        print("2. Zarejestruj narzędzia: navigate, click, type, snapshot")
        print("3. Hermes zyskuje pełną kontrolę nad przeglądarką")
        print()
        print("Alternatywnie: Playwright MCP (wymaga Node.js + sudo)")
        print("  hermes mcp add playwright --command 'npx @playwright/mcp'")
        
    finally:
        browser.close()
        print("\n[OK] Przeglądarka zamknięta")


if __name__ == "__main__":
    demo()
