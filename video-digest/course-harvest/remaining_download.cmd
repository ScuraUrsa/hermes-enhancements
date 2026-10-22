@echo off
rem Download the remaining Akademia SaaS courses, smallest/most useful first (Filip 2026-10-19: use the weekly limit).
set PYTHONIOENCODING=utf-8
cd /d D:\hermes\course-harvest
for %%C in (machina-sprzedazy marketing-saas nagrania-live-i-mentoringow-mKzH od-developera-do-foundera-2.0 od-developera-do-foundera-1.0) do (
  venv\Scripts\python.exe -u harvest_zanfia.py download --course %%C --parallel 3 >> D:\courses\download-remaining.log 2>&1
)
echo done > D:\courses\download-remaining.done
