@echo off
rem Live status of the course report rebuild on the dev VM (refreshes every 60 s, Ctrl+C to quit).
rem The script is sent over ssh, so nothing needs to be installed on the VM.
ssh -i D:\hermes\terraforge-stacks\local\generated\id_rsa ubuntu@192.168.56.108 python3 - --watch 60 < "%~dp0status.py"
