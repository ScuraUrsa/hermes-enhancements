#!/bin/bash
# PC side of the course pipeline: every 3 minutes copy finished lessons (video + GPU
# transcript) to the VM and make sure the VM's digest pool (`sitedigest pool`, N Sonnet
# workers) is running. Stops after ~90 min with nothing new to copy and no pool.
#   bash pipeline_loop.sh [site] [vm-ip] [workers] [model]
SITE="${1:-akademiasaas-pl}"
VM="${2:-192.168.56.108}"
WORKERS="${3:-3}"
MODEL="${4:-claude-code:sonnet}"
KEY_FILE=/d/hermes/terraforge-stacks/local/generated/id_rsa
SSH="ssh -i $KEY_FILE ubuntu@$VM"
DEST=".hermes/sitedigest/$SITE"
idle=0
while true; do
  out=$(bash /d/hermes/course-harvest/sync_to_vm.sh "$SITE" "$VM" 2>&1)
  echo "$(date +%H:%M:%S) $(echo "$out" | tr '\n' ' ')"
  # sitedigest's own pool (leased SQLite queue, map.lock, pause on the Claude limit); pid file, not
  # pgrep: a pattern would also match this ssh command's own line
  pool=$($SSH "cd ~/$DEST && if [ -f pool.pid ] && kill -0 \$(cat pool.pid) 2>/dev/null; then echo running; else     cd ~/ytbench && set -a && . ~/.hermes/.env && set +a && export PATH=~/ytbench/bin:\$PATH OMP_THREAD_LIMIT=1 &&     (nohup setsid ~/.hermes/ytdigest/venv/bin/sitedigest pool $SITE --workers $WORKERS --model $MODEL --follow --require-vtt --no-notion        >> ~/$DEST/pool.log 2>&1 < /dev/null & echo \$! > ~/$DEST/pool.pid) && echo started; fi")
  echo "$(date +%H:%M:%S) pool: $pool; $($SSH "tail -1 $DEST/pool.log 2>/dev/null")"
  # free disk: VM drops videos of digested lessons, the PC drops copies the VM already has (when D: is low)
  echo "$(date +%H:%M:%S) $($SSH "cd ~/$DEST && python3 prune_media.py" 2>&1 | tail -1); $(/d/hermes/course-harvest/venv/Scripts/python.exe /d/hermes/course-harvest/pc_prune.py --site "$SITE" 2>&1 | tail -1)"
  if echo "$out" | grep -q "files to copy: 0"; then idle=$((idle+1)); else idle=0; fi
  [ $idle -ge 30 ] && { echo "nothing new for ~90 min, sync loop stops"; break; }
  sleep 180
done
