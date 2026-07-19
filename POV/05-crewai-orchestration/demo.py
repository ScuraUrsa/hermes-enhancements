#!/usr/bin/env python3
"""
POV #5: CrewAI + Hermes — Multi-Agent Orchestration
Demonstracja integracji CrewAI jako warstwy orchestracji nad Hermesem.

Wymagania:
- pip install crewai
- OLLAMA_API_KEY (lub OPENAI_API_KEY)

Użycie:
    python3 demo.py
"""

import os
import sys
from pathlib import Path

# Sprawdź API key
def get_api_key():
    for var in ["OLLAMA_API_KEY", "OPENAI_API_KEY"]:
        key = os.environ.get(var)
        if key:
            return key, var
    
    env_path = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("OLLAMA_API_KEY="):
                return line.split("=", 1)[1].strip(), "OLLAMA_API_KEY"
    
    return None, None


def demo_crewai():
    """Demo CrewAI multi-agent system."""
    print("=" * 60)
    print("POV #5: CrewAI + Hermes — Multi-Agent Orchestration")
    print("=" * 60)
    print()
    
    api_key, key_name = get_api_key()
    if not api_key:
        print("[INFO] Brak API key — demo koncepcyjne")
        demo_concept()
        return
    
    print(f"[INFO] API key: {key_name}")
    
    try:
        from crewai import Agent, Task, Crew, Process
        
        # Używamy Ollama Cloud jako provider
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_API_BASE"] = "https://ollama.com/v1"
        
        # Agent 1: Researcher
        researcher = Agent(
            role="Senior Researcher",
            goal="Research the latest AI agent frameworks and find the best tools for Hermes Agent enhancement",
            backstory="You are an expert AI researcher with deep knowledge of agent frameworks, MCP servers, and AI tools.",
            allow_delegation=False,
            verbose=False,
            llm="openai/deepseek-v4-pro",  # przez Ollama Cloud
        )
        
        # Agent 2: Coder
        coder = Agent(
            role="Senior Python Developer",
            goal="Write production-quality Python code for Hermes Agent plugins and tools",
            backstory="You are a senior Python developer specialized in AI agent tools and plugins.",
            allow_delegation=False,
            verbose=False,
            llm="openai/deepseek-v4-pro",
        )
        
        # Agent 3: Reviewer
        reviewer = Agent(
            role="Code Reviewer",
            goal="Review code for quality, security, and best practices",
            backstory="You are a meticulous code reviewer who catches bugs and ensures production quality.",
            allow_delegation=False,
            verbose=False,
            llm="openai/deepseek-v4-pro",
        )
        
        # Task 1: Research
        research_task = Task(
            description="Research the top 3 MCP servers that would most benefit Hermes Agent. For each, explain why and how to integrate.",
            expected_output="A markdown report with 3 MCP servers, their benefits, and integration steps.",
            agent=researcher,
        )
        
        # Task 2: Code
        code_task = Task(
            description="Write a Python plugin for Hermes Agent that integrates with one of the researched MCP servers. Include error handling and tests.",
            expected_output="Complete Python plugin code with docstrings, error handling, and test cases.",
            agent=coder,
        )
        
        # Task 3: Review
        review_task = Task(
            description="Review the Python plugin code. Check for: security issues, error handling completeness, code style, and test coverage.",
            expected_output="A review report with findings, severity levels, and recommendations.",
            agent=reviewer,
        )
        
        # Crew
        crew = Crew(
            agents=[researcher, coder, reviewer],
            tasks=[research_task, code_task, review_task],
            process=Process.sequential,
            verbose=False,
        )
        
        print("[INFO] Uruchamiam crew (Researcher → Coder → Reviewer)...")
        print("       Model: deepseek-v4-pro przez Ollama Cloud")
        print()
        
        result = crew.kickoff()
        
        print("=" * 60)
        print("CREW RESULT:")
        print("=" * 60)
        print(result)
        
    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        print("Instalacja: pip install crewai")
        demo_concept()
    except Exception as e:
        print(f"[FAIL] CrewAI error: {e}")
        demo_concept()


def demo_concept():
    """Demo koncepcyjne — pokazuje architekturę bez API."""
    print("=== CREWAI + HERMES — Koncepcja ===")
    print()
    print("Architektura:")
    print("  CrewAI (orchestrator)")
    print("    ├── Researcher Agent → szuka informacji")
    print("    ├── Coder Agent → pisze kod")
    print("    ├── Reviewer Agent → sprawdza jakość")
    print("    └── Hermes Agent → wykonuje zadania systemowe")
    print()
    print("Integracja z Hermesem:")
    print("  1. CrewAI jako warstwa planowania")
    print("  2. Hermes jako 'worker agent' wykonujący tool calls")
    print("  3. CrewAI deleguje zadania do Hermesa przez API/webhook")
    print()
    print("Przykładowy flow:")
    print("  User → CrewAI (plan) → Researcher (research)")
    print("                        → Coder (implement)")
    print("                        → Reviewer (review)")
    print("                        → Hermes (execute: git, tests, deploy)")
    print()
    print("Kluczowe zalety:")
    print("  - Role-based: intuicyjny model ( Researcher, Coder, Reviewer)")
    print("  - Sequential/parallel: elastyczne procesy")
    print("  - Tool integration: każdy agent może używać narzędzi")
    print("  - Memory: CrewAI ma wbudowaną pamięć konwersacji")
    print()
    print("Ograniczenia:")
    print("  - Wymaga API key (OpenAI lub Ollama Cloud)")
    print("  - Każdy agent = osobny API call (koszt tokenów)")
    print("  - CrewAI 1.15.4 zainstalowane, gotowe do użycia")


if __name__ == "__main__":
    demo_crewai()
