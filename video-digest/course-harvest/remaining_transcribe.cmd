@echo off
rem GPU transcription with the course glossaries, follows the downloads (--watch).
set PYTHONIOENCODING=utf-8
cd /d D:\hermes\course-harvest
venv\Scripts\python.exe -u transcribe_pc.py --watch >> D:\courses\transcribe-remaining.log 2>&1
