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
  find "pages/$k" -type f ! -name "*.part" ! -name "*.ytdl" ! -name "*.tmp" ! -name "*.frag*" ! -name "*.vtt.v1" >> .pc_files.txt
done < .keys.txt
$SSH "mkdir -p $DEST/pages && cd $DEST && find pages -type f" > .vm_files.txt
sort -u .pc_files.txt -o .pc_files.txt
# videos of digested lessons are pruned on the VM (prune_media.py leaves prefetch/.pruned): don't copy them back
# (only the video files: transcripts next to them still go over)
grep '/prefetch/.pruned$' .vm_files.txt | sed 's#/prefetch/.pruned$#/prefetch/#' > .pruned_prefixes.txt || true
if [ -s .pruned_prefixes.txt ]; then
  awk 'NR == FNR { p[$0] = 1; next }
       { d = $0; sub(/[^\/]*$/, "", d) }
       !(d in p && $0 ~ /\/video\.(mp4|mkv|webm|ts|m4a)$/)' .pruned_prefixes.txt .pc_files.txt > .pc_files.tmp
  mv .pc_files.tmp .pc_files.txt
fi
sort -u .vm_files.txt -o .vm_files.txt
comm -23 .pc_files.txt .vm_files.txt > .new_files.txt
# a re-transcribed VTT keeps its name; its new marker (video.pl.vtt.asr2) brings it along
grep '\.vtt\.asr[0-9]*$' .new_files.txt | sed 's/\.asr[0-9]*$//' >> .new_files.txt || true
# files left empty on the VM (tar on a full disk, 2026-10-20: 44 transcripts) but not on the PC: send again
$SSH "cd $DEST && find pages -type f -size 0" | sort > .vm_empty.txt
comm -12 .pc_files.txt .vm_empty.txt | while read -r f; do [ -s "$f" ] && echo "$f"; done >> .new_files.txt
# disk guard (2026-10-20, dev filled up to 100%): below MIN_FREE_GB on the VM send no videos, only text and
# transcripts; the pool digests and prunes what is there and the videos follow once space is back
MIN_FREE_GB="${MIN_FREE_GB:-15}"
free_gb=$($SSH "df -BG --output=avail / | tail -1 | tr -dc 0-9")
if [ "${free_gb:-0}" -lt "$MIN_FREE_GB" ]; then
  grep -vE '/video\.(mp4|mkv|webm|ts|m4a)$' .new_files.txt > .new_files.tmp || true
  mv .new_files.tmp .new_files.txt
  echo "VM free ${free_gb} GB < ${MIN_FREE_GB} GB: videos held back"
fi
echo "lessons on PC: $(wc -l < .keys.txt), files to copy: $(wc -l < .new_files.txt)"
if [ -s .new_files.txt ]; then
  tar cf - -T .new_files.txt | $SSH "cd $DEST && tar xf -"
fi
cat .map.snapshot.json | $SSH "cat > $DEST/map.pc.json"
scp -q -i "$KEY_FILE" /d/hermes/course-harvest/merge_map.py "ubuntu@$VM:$DEST/merge_map.py"
$SSH "cd $DEST && python3 merge_map.py"
