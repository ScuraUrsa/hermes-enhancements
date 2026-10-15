#!/bin/bash
# Sync new transcripts to the VM every 15 min while the PC re-transcribes; one last sync after asr_redo.cmd is done.
#   bash sync_loop.sh [site] [vm-ip]
cd "$(dirname "$0")"
while true; do
  done_flag=0; [ -f /d/courses/asr-redo.done ] && done_flag=1
  bash sync_to_vm.sh "${1:-akademiasaas-pl}" "${2:-192.168.56.108}" 2>&1 | tail -2 | sed "s/^/$(date +%H:%M) /"
  [ $done_flag = 1 ] && break
  sleep 900
done
echo "$(date +%H:%M) final sync done"
