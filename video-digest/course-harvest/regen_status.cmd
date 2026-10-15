@echo off
rem Live status of the v2 course report rebuild on the dev VM (refreshes every 30 s, Ctrl+C to quit).
chcp 65001 >nul
ssh -t -i D:\hermes\terraforge-stacks\local\generated\id_rsa ubuntu@192.168.56.108 "python3 ~/.hermes/sitedigest/akademiasaas-pl/regen_status.py --watch"
pause
