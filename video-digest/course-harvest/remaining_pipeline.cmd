@echo off
rem Sync to the dev VM every 3 min, keep the sitedigest pool (4 Sonnet workers) running, prune VM/PC videos.
D:\Git\bin\bash.exe /d/hermes/course-harvest/pipeline_loop.sh akademiasaas-pl 192.168.56.108 4 >> D:\courses\pipeline-remaining.log 2>&1
