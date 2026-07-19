#!/usr/bin/env python3
"""
POV #10: Hermes Custom Plugin — Selenium Browser Tool
Plugin Hermesa opakowujący Selenium WebDriver jako narzędzia agenta.

Instalacja:
    cp -r POV/10-hermes-selenium-plugin ~/.hermes/plugins/selenium_browser/
    pip install selenium webdriver-manager

Rejestruje narzędzia:
    - browser_navigate(url) → snapshot
    - browser_click(selector) → snapshot
    - browser_type(selector, text) → snapshot
    - browser_snapshot() → dict
    - browser_screenshot() → base64 PNG
"""

import time
import base64
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

# Globalna instancja przeglądarki
_driver = None
_options = None


def _get_driver() -> webdriver.Chrome:
    """Lazy init przeglądarki."""
    global _driver, _options
    if _driver is None:
        _options = Options()
        _options.add_argument("--headless=new")
        _options.add_argument("--no-sandbox")
        _options.add_argument("--disable-dev-shm-usage")
        _options.add_argument("--disable-gpu")
        _options.add_argument("--window-size=1920,1080")
        _options.page_load_strategy = 'eager'

        service = Service(ChromeDriverManager().install())
        _driver = webdriver.Chrome(service=service, options=_options)
        _driver.set_page_load_timeout(10)
    return _driver


def _get_snapshot() -> dict:
    """Pobierz accessibility snapshot strony."""
    driver = _get_driver()
    try:
        title = driver.title
        url = driver.current_url

        body_text = driver.find_element(By.TAG_NAME, "body").text[:2000]

        interactive = []
        for elem in driver.find_elements(By.CSS_SELECTOR,
            "a, button, input, select, textarea, [role='button'], [onclick]"):
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
    except Exception as e:
        return {"error": str(e), "title": "", "url": ""}


# === NARZĘDZIA HERMESA ===

def browser_navigate(url: str) -> dict:
    """Nawiguj do URL i zwróć snapshot strony."""
    try:
        driver = _get_driver()
        driver.get(url)
        time.sleep(0.5)
        return _get_snapshot()
    except Exception as e:
        return {"error": str(e)}


def browser_click(selector: str) -> dict:
    """Kliknij element po CSS selectorze i zwróć snapshot."""
    try:
        driver = _get_driver()
        elem = driver.find_element(By.CSS_SELECTOR, selector)
        elem.click()
        time.sleep(0.5)
        return _get_snapshot()
    except Exception as e:
        return {"error": str(e)}


def browser_type(selector: str, text: str) -> dict:
    """Wpisz tekst w pole po CSS selectorze i zwróć snapshot."""
    try:
        driver = _get_driver()
        elem = driver.find_element(By.CSS_SELECTOR, selector)
        elem.clear()
        elem.send_keys(text)
        time.sleep(0.3)
        return _get_snapshot()
    except Exception as e:
        return {"error": str(e)}


def browser_snapshot() -> dict:
    """Zwróć accessibility snapshot bieżącej strony."""
    return _get_snapshot()


def browser_screenshot() -> dict:
    """Zrób screenshot i zwróć jako base64 PNG."""
    try:
        driver = _get_driver()
        screenshot = driver.get_screenshot_as_base64()
        return {"screenshot_base64": screenshot, "format": "png"}
    except Exception as e:
        return {"error": str(e)}


def browser_close() -> dict:
    """Zamknij przeglądarkę."""
    global _driver
    if _driver:
        try:
            _driver.quit()
        except:
            pass
        _driver = None
    return {"status": "closed"}


# === REJESTRACJA PLUGINU ===

def register_plugin():
    """Zarejestruj narzędzia w Hermes registry (jeśli dostępne)."""
    try:
        from tools.registry import registry

        tools = [
            ("browser_navigate", browser_navigate, {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to navigate to"}
                },
                "required": ["url"]
            }),
            ("browser_click", browser_click, {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of element to click"}
                },
                "required": ["selector"]
            }),
            ("browser_type", browser_type, {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of input field"},
                    "text": {"type": "string", "description": "Text to type"}
                },
                "required": ["selector", "text"]
            }),
            ("browser_snapshot", browser_snapshot, {
                "type": "object",
                "properties": {},
                "required": []
            }),
            ("browser_screenshot", browser_screenshot, {
                "type": "object",
                "properties": {},
                "required": []
            }),
            ("browser_close", browser_close, {
                "type": "object",
                "properties": {},
                "required": []
            }),
        ]

        for name, handler, schema in tools:
            registry.register(
                name=name,
                toolset="selenium_browser",
                schema=schema,
                handler=lambda args, h=handler, **kw: h(**args),
            )

        print(f"[selenium_browser] Zarejestrowano {len(tools)} narzędzi")
        return True
    except ImportError:
        print("[selenium_browser] Hermes registry niedostępne — plugin działa standalone")
        return False


# Auto-rejestracja przy imporcie
register_plugin()
