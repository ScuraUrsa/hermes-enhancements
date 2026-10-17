#!/bin/bash
# Slow v2 report rebuild (Filip 2026-10-15). Started by cron every 20 min; flock keeps one copy;
# stops for good once regen.finished exists (written when no lesson is left).
cd ~/.hermes/sitedigest/akademiasaas-pl || exit 1
[ -f regen.finished ] && exit 0
exec 9>regen.lock; flock -n 9 || exit 0
set -a; . ~/.hermes/.env; set +a
export PATH=~/ytbench/bin:$PATH
~/.hermes/ytdigest/venv/bin/python -u regen_reports.py akademiasaas-pl --workers 2 --pause-sec 15 --daily-cap 300 >> regen.log 2>&1
tail -1 regen.log | grep -q "without a v2 report: 0$" && date -u > regen.finished
