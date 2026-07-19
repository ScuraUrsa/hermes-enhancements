#!/usr/bin/env python3
"""
POV #9: GitHub MCP Integration
Klient GitHub API przez `gh` CLI — bez zewnętrznych bibliotek.
Wymaga: gh CLI zalogowane (gh auth login)
"""

import subprocess
import json
import sys
import os
from datetime import datetime


def _gh(args: list[str], stdin: str | None = None) -> dict:
    """Wywołaj `gh` CLI i zwróć sparsowany JSON."""
    cmd = ["gh"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=stdin,
            timeout=30,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip(), "exit_code": result.returncode}
        if not result.stdout.strip():
            return {}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "Timeout po 30s"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "raw": result.stdout[:500]}
    except FileNotFoundError:
        return {"error": "gh CLI nie znalezione. Zainstaluj: https://cli.github.com"}


def list_issues(repo: str = "ScuraUrsa/hermes-enhancements", state: str = "open", limit: int = 10) -> dict:
    """Lista issues w repozytorium."""
    return _gh([
        "issue", "list",
        "--repo", repo,
        "--state", state,
        "--limit", str(limit),
        "--json", "number,title,state,createdAt,url,labels",
    ])


def create_issue(repo: str, title: str, body: str = "", labels: list[str] | None = None) -> dict:
    """Utwórz nowe issue. Zwraca dict z 'url' lub 'error'."""
    args = [
        "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
    ]
    if labels:
        for label in labels:
            args.extend(["--label", label])
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip()}
        url = result.stdout.strip()
        if url.startswith("https://"):
            number = url.rstrip("/").split("/")[-1]
            return {"url": url, "number": int(number)}
        return {"url": url}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout po 30s"}
    except FileNotFoundError:
        return {"error": "gh CLI nie znalezione"}


def list_prs(repo: str = "ScuraUrsa/hermes-enhancements", state: str = "open", limit: int = 10) -> dict:
    """Lista Pull Requestów."""
    return _gh([
        "pr", "list",
        "--repo", repo,
        "--state", state,
        "--limit", str(limit),
        "--json", "number,title,state,createdAt,url,author",
    ])


def repo_info(repo: str = "ScuraUrsa/hermes-enhancements") -> dict:
    """Informacje o repozytorium."""
    return _gh([
        "repo", "view", repo,
        "--json", "name,description,url,stargazerCount,forkCount,defaultBranchRef,createdAt,updatedAt,isPrivate,diskUsage",
    ])


def search_issues(repo: str, query: str, limit: int = 10) -> dict:
    """Szukaj issues po słowach kluczowych."""
    return _gh([
        "search", "issues",
        "--repo", repo,
        query,
        "--limit", str(limit),
        "--json", "number,title,state,createdAt,url",
    ])


def list_labels(repo: str = "ScuraUrsa/hermes-enhancements") -> dict:
    """Lista etykiet w repo."""
    return _gh([
        "label", "list",
        "--repo", repo,
        "--json", "name,color,description",
    ])


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    repo = os.environ.get("GITHUB_REPO", "ScuraUrsa/hermes-enhancements")

    # 1. Repo info
    print_section("📦 REPO INFO")
    info = repo_info(repo)
    if "error" in info:
        print(f"  ❌ Błąd: {info['error']}")
    else:
        print(f"  Nazwa:        {info.get('name', '?')}")
        print(f"  Opis:         {info.get('description', '?')}")
        print(f"  URL:          {info.get('url', '?')}")
        print(f"  ⭐ Gwiazdki:  {info.get('stargazerCount', 0)}")
        print(f"  🍴 Forki:     {info.get('forkCount', 0)}")
        print(f"  🔒 Prywatne:  {info.get('isPrivate', '?')}")
        print(f"  📅 Utworzone: {info.get('createdAt', '?')}")
        print(f"  💾 Dysk:      {info.get('diskUsage', 0)} KB")

    # 2. List issues
    print_section("🐛 OPEN ISSUES")
    issues = list_issues(repo)
    if "error" in issues:
        print(f"  ❌ Błąd: {issues['error']}")
    elif not issues:
        print("  Brak otwartych issues.")
    else:
        for i in issues:
            labels = ", ".join(l["name"] for l in i.get("labels", []))
            print(f"  #{i['number']} [{i['state']}] {i['title']}")
            if labels:
                print(f"       Etykiety: {labels}")
            print(f"       {i['url']}")

    # 3. List PRs
    print_section("🔀 OPEN PULL REQUESTS")
    prs = list_prs(repo)
    if "error" in prs:
        print(f"  ❌ Błąd: {prs['error']}")
    elif not prs:
        print("  Brak otwartych PR-ów.")
    else:
        for pr in prs:
            author = pr.get("author", {}).get("login", "?") if isinstance(pr.get("author"), dict) else pr.get("author", "?")
            print(f"  #{pr['number']} [{pr['state']}] {pr['title']}")
            print(f"       Autor: {author}")
            print(f"       {pr['url']}")

    # 4. Create test issue (opcjonalnie — tylko gdy flaga --create-test)
    if "--create-test" in sys.argv:
        print_section("📝 TWORZENIE TESTOWEGO ISSUE")
        result = create_issue(
            repo=repo,
            title=f"[TEST] GitHub MCP Integration — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            body="To jest testowe issue utworzone przez POV #9: GitHub MCP Integration.\n\n"
                 "✅ gh CLI działa poprawnie\n"
                 "✅ Tworzenie issues przez CLI potwierdzone",
            labels=["enhancement"],
        )
        if "error" in result:
            print(f"  ❌ Błąd: {result['error']}")
        else:
            print(f"  ✅ Issue utworzone: {result.get('url', result)}")

    # 5. Labels
    print_section("🏷️  LABELS")
    labels = list_labels(repo)
    if "error" in labels:
        print(f"  ❌ Błąd: {labels['error']}")
    elif not labels:
        print("  Brak etykiet.")
    else:
        for l in labels[:15]:
            print(f"  [{l['color']}] {l['name']}")

    print(f"\n{'='*60}")
    print("  ✅ POV #9: GitHub MCP Integration — DEMO zakończone")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
