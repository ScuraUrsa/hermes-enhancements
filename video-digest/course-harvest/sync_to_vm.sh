#!/bin/bash
# Copy downloaded lessons from the PC harvest folder to a VM's sitedigest site folder.
# Copies every file the VM does not have yet (new lesson folders and transcripts that
# appear later); the VM's map keeps its digest results (merge_map.py).
#   bash sync_to_vm.sh [site] [vm-ip]
set -euo pipefail
SITE="${1:-akademiasaas-pl}"
VM="${2:-192.168.56.108}"
KEY_FILE=/d/hermes/terraforge-stacks/local/generated/id_rsa
SRC="/d/courses/$SITE"
DEST=".hermes/sitedigest/$SITE"
SSH="ssh -i $KEY_FILE ubuntu@$VM"

cd "$SRC"
cp map.json .map.snapshot.json   # the harvester rewrites map.json after every lesson
python -c "
import json
m = json.load(open('.map.snapshot.json', encoding='utf-8'))
open('.keys.txt', 'w', newline='\n').write(''.join(p['key'] + '\n' for p in m['pages'] if p.get('downloaded')))"
# files on the PC for downloaded lessons (text, video, transcript; skip partial downloads)
: > .pc_files.txt
while read -r k; do
  [ -d "pages/$k" ] || continue
  find "pages/$k" -type f ! -name "*.part" ! -name "*.ytdl" ! -name "*.tmp" ! -name "*.frag*" >> .pc_files.txt
done < .keys.txt
$SSH "mkdir -p $DEST/pages && cd $DEST && find pages -type f" > .vm_files.txt
sort -u .pc_files.txt -o .pc_files.txt
sort -u .vm_files.txt -o .vm_files.txt
comm -23 .pc_files.txt .vm_files.txt > .new_files.txt
echo "lessons on PC: $(wc -l < .keys.txt), files to copy: $(wc -l < .new_files.txt)"
if [ -s .new_files.txt ]; then
  tar cf - -T .new_files.txt | $SSH "cd $DEST && tar xf -"
fi
cat .map.snapshot.json | $SSH "cat > $DEST/map.pc.json"
scp -q -i "$KEY_FILE" /d/hermes/course-harvest/merge_map.py "ubuntu@$VM:$DEST/merge_map.py"
$SSH "cd $DEST && python3 merge_map.py"
