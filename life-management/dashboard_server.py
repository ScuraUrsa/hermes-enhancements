#!/usr/bin/env python3
"""
Life Management Dashboard — HTTP Server
========================================
Prosty serwer HTTP z dashboardem i API.
Uruchom: python3 dashboard_server.py [port]
Domyślnie: http://localhost:8080
"""

from __future__ import annotations

import sys
import os
import json
from pathlib import Path
from datetime import datetime, date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent))

from life_cli import (
    LifeDB, TimeTracker, PeopleManager, EventManager, HabitTracker, ReportGenerator,
)
from gamification import Gamification

LIFE_DIR = Path(__file__).parent

# ── HTML Template ────────────────────────────────────────────────────────────

PAGE = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Life Management</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a1a;color:#d0d0d0;padding:16px}
h1{color:#00ff88;font-size:1.4em;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
.card{background:#12122a;border-radius:10px;padding:16px;border:1px solid #1e1e3a}
.card h2{color:#00ff88;font-size:1em;margin-bottom:10px}
.row{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e1e3a;font-size:0.9em}
.row:last-child{border-bottom:none}
.label{color:#777}
.val{font-weight:bold}
.bar{height:16px;background:#1e1e3a;border-radius:8px;margin:3px 0;overflow:hidden}
.fill{height:100%;border-radius:8px;transition:width .3s}
.alert{padding:7px 10px;border-radius:7px;margin:3px 0;font-size:0.85em}
.a-crit{background:#ff444418;border-left:3px solid #ff4444}
.a-high{background:#ffaa0018;border-left:3px solid #ffaa00}
.a-med{background:#00aaff18;border-left:3px solid #00aaff}
.a-low{background:#00ff8818;border-left:3px solid #00ff88}
.overdue{color:#ff4444}
.ok{color:#00ff88}
.tabs{display:flex;gap:8px;margin-bottom:14px}
.tab{padding:6px 14px;border-radius:6px;cursor:pointer;background:#12122a;border:1px solid #1e1e3a;color:#888;font-size:0.85em}
.tab.active{background:#00ff8820;border-color:#00ff88;color:#00ff88}
.hidden{display:none}
.refresh{color:#555;font-size:0.75em;text-align:right;margin-top:14px}
.quick-btn{display:inline-block;padding:5px 10px;margin:2px;border-radius:5px;background:#1e1e3a;color:#aaa;cursor:pointer;font-size:0.8em;border:none}
.quick-btn:hover{background:#2a2a4a;color:#fff}
.quick-btn.active-btn{background:#00ff8820;color:#00ff88;border:1px solid #00ff88}
input,select{background:#1e1e3a;border:1px solid #2a2a4a;color:#d0d0d0;padding:5px 8px;border-radius:5px;font-size:0.85em;margin:2px}
</style>
</head>
<body>
<h1>🧬 Life Management</h1>

<div class="tabs">
  <div class="tab active" onclick="showTab('today')">📅 Dziś</div>
  <div class="tab" onclick="showTab('people')">👥 Osoby</div>
  <div class="tab" onclick="showTab('habits')">💊 Nawykowe</div>
  <div class="tab" onclick="showTab('week')">📊 Tydzień</div>
  <div class="tab" onclick="showTab('quick')">⚡ Szybkie</div>
</div>

<div id="tab-today">
  <div class="grid">
    <div class="card"><h2>⏱️ Czas dziś</h2><div id="today-time"></div></div>
    <div class="card"><h2>🔔 Alerty</h2><div id="alerts"></div></div>
    <div class="card"><h2>📅 Nadchodzące</h2><div id="upcoming"></div></div>
    <div class="card"><h2>💊 Streaki</h2><div id="streaks"></div></div>
  </div>
</div>

<div id="tab-people" class="hidden">
  <div class="grid">
    <div class="card"><h2>👥 Balans (30 dni)</h2><div id="people-balance"></div></div>
    <div class="card"><h2>🔴 Overdue</h2><div id="people-overdue"></div></div>
    <div class="card"><h2>🎂 Urodziny</h2><div id="birthdays"></div></div>
  </div>
</div>

<div id="tab-habits" class="hidden">
  <div class="grid">
    <div class="card"><h2>💊 Dziś</h2><div id="habits-today"></div></div>
    <div class="card"><h2>📈 Tydzień</h2><div id="habits-week"></div></div>
  </div>
</div>

<div id="tab-week" class="hidden">
  <div class="grid">
    <div class="card"><h2>📊 Kategorie</h2><div id="week-cats"></div></div>
    <div class="card"><h2>👥 Osoby</h2><div id="week-people"></div></div>
  </div>
</div>

<div id="tab-quick" class="hidden">
  <div class="grid">
    <div class="card">
      <h2>⏱️ Start blok</h2>
      <select id="q-cat" onchange="updateQuickDesc()">
        <option value="praca">💼 Praca</option><option value="rodzina">👨‍👩‍👧 Rodzina</option>
        <option value="znajomi">👥 Znajomi</option><option value="zdrowie">💪 Zdrowie</option>
        <option value="jedzenie">🍽️ Jedzenie</option><option value="hobby">🎸 Hobby</option>
        <option value="odpoczynek">😴 Odpoczynek</option><option value="nauka">📚 Nauka</option>
        <option value="administracja">📋 Admin</option>
        <option value="transport">🚗 Transport</option>
      </select>
      <input id="q-desc" placeholder="opis (opcjonalnie)" style="width:140px">
      <button class="quick-btn active-btn" onclick="quickStart()">▶ Start</button>
      <button class="quick-btn" onclick="quickStop()" style="background:#ff444430;color:#ff6666">⏹ Stop</button>
      <div id="quick-status" style="margin-top:6px;font-size:0.8em;color:#888"></div>
    </div>
    <div class="card">
      <h2>💊 Szybkie logi</h2>
      <button class="quick-btn" onclick="quickLog('pill','taken')">💊 Pigułki ✓</button>
      <button class="quick-btn" onclick="quickLog('pill','skipped')">💊 Pigułki ✗</button>
      <button class="quick-btn" onclick="quickLog('water','250ml')">💧 Woda</button>
      <button class="quick-btn" onclick="quickLog('exercise','30min')">💪 Ćwiczenia</button>
      <br>
      <span style="font-size:0.8em;color:#888">Myśl:</span>
      <input id="thought-val" type="range" min="1" max="10" value="5" style="width:80px">
      <span id="thought-label" style="font-size:0.8em">5</span>
      <button class="quick-btn" onclick="quickLog('intrusive_thought','occurred',document.getElementById('thought-val').value)">🧠</button>
      <br>
      <span style="font-size:0.8em;color:#888">Podjadanie:</span>
      <input id="snack-val" type="range" min="1" max="10" value="5" style="width:80px">
      <span id="snack-label" style="font-size:0.8em">5</span>
      <button class="quick-btn" onclick="quickLog('snacking','occurred',document.getElementById('snack-val').value)">🍪</button>
    </div>
  </div>
</div>

<div class="refresh" id="refresh-time"></div>

<script>
const COLORS={praca:'#4a9eff',rodzina:'#ff6b6b',znajomi:'#ffd93d',zdrowie:'#6bcb77',jedzenie:'#ff8c42',hobby:'#a855f7',odpoczynek:'#4ecdc4',nauka:'#ff6b9d',administracja:'#95a5a6',transport:'#e67e22',higiena:'#1abc9c',inne:'#7f8c8d'};

function showTab(name){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('[id^="tab-"]').forEach(t=>t.classList.add('hidden'));
  document.getElementById('tab-'+name).classList.remove('hidden');
  event.target.classList.add('active');
}

async function api(path){
  const r=await fetch('/api/'+path);
  return r.json();
}

async function load(){
  const d=await api('dashboard');
  renderToday(d.today);
  renderAlerts(d.alerts);
  renderUpcoming(d.upcoming);
  renderStreaks(d.streaks);
  renderPeople(d.people);
  renderOverdue(d.people);
  renderBirthdays(d.upcoming?.birthdays||[]);
  renderHabitsToday(d.habits_today);
  renderHabitsWeek(d.habits_week);
  renderWeekCats(d.weekly);
  renderWeekPeople(d.people);
  document.getElementById('refresh-time').textContent='Odświeżono: '+new Date().toLocaleTimeString('pl-PL');
}

function renderToday(t){
  if(!t){document.getElementById('today-time').innerHTML='Brak danych';return}
  let h=`<div class="row"><span class="label">Śledzone</span><span class="val">${t.total_hours}h (${t.coverage_pct}%)</span></div>`;
  for(const[cat,mins]of Object.entries(t.by_category||{})){
    const hrs=(mins/60).toFixed(1);
    const pct=t.total_minutes>0?(mins/t.total_minutes*100).toFixed(0):0;
    h+=`<div class="row"><span class="label">${cat}</span><span class="val">${hrs}h</span></div>
    <div class="bar"><div class="fill" style="width:${pct}%;background:${COLORS[cat]||'#888'}"></div></div>`;
  }
  document.getElementById('today-time').innerHTML=h;
}

function renderAlerts(a){
  if(!a||!a.length){document.getElementById('alerts').innerHTML='✅ Brak alertów';return}
  document.getElementById('alerts').innerHTML=a.map(x=>
    `<div class="alert a-${x.priority}">${x.message}<br><small>→ ${x.action}</small></div>`
  ).join('');
}

function renderUpcoming(u){
  const el=document.getElementById('upcoming');
  if(!u){el.innerHTML='Brak';return}
  let h='';
  if(u.birthdays&&u.birthdays.length){
    h+='<strong>🎂 Urodziny:</strong><br>';
    u.birthdays.slice(0,5).forEach(b=>{h+=`<div style="font-size:0.85em">${b.name} — za ${b.days_until}d (${b.age} lat)</div>`});
  }
  if(u.events&&u.events.length){
    h+='<br><strong>📌 Wydarzenia:</strong><br>';
    u.events.slice(0,5).forEach(e=>{h+=`<div style="font-size:0.85em">${e.event_date} — ${e.title}</div>`});
  }
  el.innerHTML=h||'Brak nadchodzących';
}

function renderStreaks(s){
  if(!s){document.getElementById('streaks').innerHTML='Brak';return}
  let h='';
  for(const[n,d]of Object.entries(s)){
    const fire=d>=7?'🔥'.repeat(Math.min(d,10)):'';
    h+=`<div class="row"><span class="label">${n}</span><span class="val">${d} dni ${fire}</span></div>`;
  }
  document.getElementById('streaks').innerHTML=h||'Brak streaków';
}

function renderPeople(pp){
  if(!pp||!pp.length){document.getElementById('people-balance').innerHTML='Brak osób';return}
  document.getElementById('people-balance').innerHTML=pp.slice(0,15).map(p=>{
    const cls=p.overdue?'overdue':'ok';
    const icon=p.overdue?'🔴':'🟢';
    return `<div class="row"><span class="${cls}">${icon} ${p.name} <small>(${p.category})</small></span><span>${p.hours_last_30d}h | ${p.days_since_contact||'?'}d</span></div>`;
  }).join('');
}

function renderOverdue(pp){
  if(!pp){return}
  const overdue=pp.filter(p=>p.overdue);
  document.getElementById('people-overdue').innerHTML=overdue.length
    ? overdue.map(p=>`<div class="alert a-crit">🔴 ${p.name} (${p.category}) — ${p.days_since_contact}d bez kontaktu</div>`).join('')
    : '✅ Wszyscy w normie';
}

function renderBirthdays(bb){
  if(!bb||!bb.length){document.getElementById('birthdays').innerHTML='Brak w ciągu 30 dni';return}
  document.getElementById('birthdays').innerHTML=bb.map(b=>
    `<div class="row"><span>${b.days_until===0?'🎈':'📅'} ${b.name}</span><span>za ${b.days_until}d (${b.age} lat)</span></div>`
  ).join('');
}

function renderHabitsToday(h){
  if(!h){document.getElementById('habits-today').innerHTML='Brak logów';return}
  let out='';
  for(const[type,logs]of Object.entries(h)){
    out+=`<div class="row"><span class="label">${type}</span><span class="val">${logs.length}x</span></div>`;
  }
  document.getElementById('habits-today').innerHTML=out||'Brak logów na dziś';
}

function renderHabitsWeek(h){
  if(!h||!h.habits){document.getElementById('habits-week').innerHTML='Brak danych';return}
  let out='';
  for(const[type,data]of Object.entries(h.habits)){
    out+=`<div class="row"><span class="label">${type}</span><span class="val">${data.count}x (śr.int:${data.avg_intensity})</span></div>`;
  }
  document.getElementById('habits-week').innerHTML=out||'Brak';
}

function renderWeekCats(w){
  if(!w){document.getElementById('week-cats').innerHTML='Brak';return}
  let h=`<div class="row"><span class="label">Śr.dziennie</span><span class="val">${w.daily_average_hours}h</span></div>`;
  for(const[cat,hrs]of Object.entries(w.by_category||{})){
    h+=`<div class="row"><span class="label">${cat}</span><span class="val">${hrs}h</span></div>`;
  }
  document.getElementById('week-cats').innerHTML=h;
}

function renderWeekPeople(pp){
  if(!pp){return}
  const top=pp.filter(p=>p.hours_last_30d>0).sort((a,b)=>b.hours_last_30d-a.hours_last_30d).slice(0,10);
  document.getElementById('week-people').innerHTML=top.length
    ? top.map(p=>`<div class="row"><span>${p.name}</span><span>${p.hours_last_30d}h</span></div>`).join('')
    : 'Brak danych';
}

async function quickStart(){
  const cat=document.getElementById('q-cat').value;
  const desc=document.getElementById('q-desc').value;
  const r=await api('start?category='+cat+(desc?'&desc='+encodeURIComponent(desc):''));
  document.getElementById('quick-status').innerHTML=r.ok?`▶ ${r.category} — ${r.time}`:r.error;
  load();
}

async function quickStop(){
  const r=await api('stop');
  document.getElementById('quick-status').innerHTML=r.ok?`⏹ ${r.category} — ${r.duration}`:r.error;
  load();
}

async function quickLog(type,value,intensity){
  let url='api/habit?type='+type+'&value='+value;
  if(intensity)url+='&intensity='+intensity;
  await fetch(url);
  load();
}

document.getElementById('thought-val').oninput=function(){
  document.getElementById('thought-label').textContent=this.value;
};
document.getElementById('snack-val').oninput=function(){
  document.getElementById('snack-label').textContent=this.value;
};

load();
setInterval(load,30000);
</script>
</body>
</html>"""

# ── API Handler ──────────────────────────────────────────────────────────────

class LifeAPI:
    """Backend API dla dashboardu."""

    def __init__(self, db_path: str = ""):
        if not db_path:
            db_path = str(LIFE_DIR / "data" / "hermes_integration.db")
        self.db = LifeDB(db_path)
        self.tracker = TimeTracker(self.db)
        self.people = PeopleManager(self.db)
        self.events = EventManager(self.db)
        self.habits = HabitTracker(self.db)
        self.reports = ReportGenerator(self.db)
        self.gamification = Gamification(self.db)

    def dashboard(self) -> dict:
        """Pełne dane dashboardu."""
        today = self.tracker.get_today_summary()
        balance = self.people.get_balance_report()
        birthdays = self.people.get_upcoming_birthdays(30)
        upcoming_events = self.events.get_upcoming_events(30)
        weekly = self.tracker.get_weekly_report()
        habits_today = self.habits.get_today_habits()
        habits_week = self.habits.get_weekly_habit_report()

        # Alerty
        alerts = []
        needing = self.people.get_who_needs_attention(5)
        for p in needing:
            if p["overdue"]:
                alerts.append({
                    "type": "overdue_contact",
                    "priority": "high",
                    "message": f"🔴 {p['name']} ({p['category']}) — {p['days_since_contact']}d bez kontaktu",
                    "action": f"Zadzwoń lub napisz do {p['name']}",
                })

        for b in birthdays:
            if b["days_until"] <= 1:
                alerts.append({
                    "type": "birthday",
                    "priority": "critical" if b["days_until"] == 0 else "high",
                    "message": f"{'🎂 DZIŚ' if b['days_until']==0 else '🎂 JUTRO'} urodziny: {b['name']} ({b['age']} lat)",
                    "action": "Wyślij życzenia!" if b["days_until"] == 0 else "Przygotuj życzenia",
                })

        pills_today = habits_today.get("pills", [])
        if not pills_today:
            now = datetime.now()
            if now.hour >= 10:
                alerts.append({
                    "type": "pills_missed",
                    "priority": "critical",
                    "message": "💊 Nie wziąłeś dziś pigułek!",
                    "action": "Weź natychmiast",
                })

        return {
            "today": today,
            "people": balance["people"],
            "alerts": alerts,
            "streaks": {
                "pigułki": self.habits.get_streak("pills"),
                "ćwiczenia": self.habits.get_streak("exercise"),
            },
            "upcoming": {
                "birthdays": birthdays,
                "events": [dict(e) for e in upcoming_events],
            },
            "weekly": weekly,
            "habits_today": habits_today,
            "habits_week": habits_week,
        }

    def start_block(self, category: str, desc: str = "") -> dict:
        """Rozpocznij blok czasu."""
        try:
            block = self.tracker.start_block(category=category, description=desc)  # type: ignore[arg-type]
            return {"ok": True, "category": block.category, "time": block.start_time[:19]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def stop_block(self) -> dict:
        """Zakończ blok czasu."""
        block = self.tracker.stop_block()
        if not block:
            return {"ok": False, "error": "Brak aktywnego bloku"}
        try:
            s = datetime.fromisoformat(block.start_time)
            e = datetime.fromisoformat(block.end_time)
            minutes = int((e - s).total_seconds() / 60)
            duration = f"{minutes // 60}h {minutes % 60}m" if minutes >= 60 else f"{minutes}m"
        except Exception:
            duration = "?"
        return {"ok": True, "category": block.category, "duration": duration}

    def log_habit(self, habit_type: str, value: str, intensity: int = 5) -> dict:
        """Zaloguj nawyk."""
        try:
            self.habits.log(habit_type, value, intensity=intensity)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── HTTP Server ──────────────────────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    api: LifeAPI | None = None

    def log_message(self, format, *args):
        pass  # Wycisz logi HTTP

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_html(PAGE)
        elif path == "/api/dashboard":
            self._serve_json(self.api.dashboard())
        elif path == "/api/start":
            cat = params.get("category", ["inne"])[0]
            desc = params.get("desc", [""])[0]
            self._serve_json(self.api.start_block(cat, desc))
        elif path == "/api/stop":
            self._serve_json(self.api.stop_block())
        elif path == "/api/habit":
            ht = params.get("type", ["pills"])[0]
            val = params.get("value", [""])[0]
            intensity = int(params.get("intensity", ["5"])[0])
            self._serve_json(self.api.log_habit(ht, val, intensity))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def _serve_html(self, content: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def _serve_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    db_path = str(LIFE_DIR / "data" / "hermes_integration.db")

    if not os.path.exists(db_path):
        print("⚠️  Baza nie istnieje. Uruchom najpierw: python3 hermes_integration.py seed")
        db_path = str(LIFE_DIR / "data" / "bot_life.db")

    api = LifeAPI(db_path)
    DashboardHandler.api = api

    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"🧬 Life Management Dashboard")
    print(f"   http://localhost:{port}")
    print(f"   API: http://localhost:{port}/api/dashboard")
    print(f"   Ctrl+C to stop")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  Zatrzymano")
        server.shutdown()


if __name__ == "__main__":
    main()
