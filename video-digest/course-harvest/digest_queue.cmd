@echo off
rem Windows task "Hermes digest queue" (every 10 min): run Hermes' queued video digests, check dev's Claude login.
set PYTHONIOENCODING=utf-8
cd /d D:\hermes\course-harvest
venv\Scripts\python.exe -u digest_queue.py >> D:\courses\digest-queue.log 2>&1
