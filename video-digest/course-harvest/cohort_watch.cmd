@echo off
rem Windows task "Hermes cohort watch" (12:30 and 22:30): follow the ODDF: AI SaaS cohort, see cohort_watch.py.
set PYTHONIOENCODING=utf-8
cd /d D:\hermes\course-harvest
venv\Scripts\python.exe -u cohort_watch.py >> D:\courses\cohort-watch.log 2>&1
