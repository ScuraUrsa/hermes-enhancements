# course-harvest (PC side of sitedigest for login-gated course platforms)

Some course platforms can't be crawled from the VM: Zanfia (akademiasaas.pl) logs in
with an emailed code kept by Firebase in the browser, lists lessons only in React
state, and serves videos from Bunny Stream with signed, expiring links. course-harvest
runs on Filip's Windows PC, where he logs in once, and hands the VM a ready
sitedigest site folder (`~/.hermes/sitedigest/<site>/`).

```
PC (Windows, Chrome profile D:\courses\.profile-zanfia, GTX 1650 Ti)       dev VM
harvest_zanfia.py map        all products -> map.json (sitedigest format)
harvest_zanfia.py download   per lesson: text.md + signed link -> yt-dlp
                             (3 parallel) -> pages/<key>/prefetch/video.mp4
transcribe_pc.py --watch     faster-whisper large-v3-turbo on the GPU
                             -> prefetch/video.pl.vtt (~8-11x real time)
whimsical.py                 linked Whimsical mind maps: branches expanded,
                             screenshot -> pages/<key>/shot.jpg
sync_to_vm.sh                new files only (tar over ssh) ----------->  merge_map.py (map.lock)
pipeline_loop.sh             sync every 3 min + keeps the pool up ----->  sitedigest pool --workers 3
                                                                          --follow --require-vtt
requeue.py (on the VM)       send lessons back to the pool, e.g. after a mind map was added
```

The login never leaves the PC: only lesson text and media go to the VM. Videos are
referenced in the map as `local:prefetch/video.mp4`; sitedigest uses a `.vtt` next to
the file as the transcript. Licence: Akademia SaaS regulamin § 6 allows saving the
content on the buyer's own devices for personal use. DRM-protected players are not
circumvented (none on Zanfia/Bunny so far).

## Setup (PC)

```powershell
python -m venv D:\hermes\course-harvest\venv
D:\hermes\course-harvest\venv\Scripts\python -m pip install -r requirements-pc.txt
# Whisper model: the Hugging Face cache download stalls on this PC, so fetch the files directly
#   https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo -> models\faster-whisper-large-v3-turbo\
```

## Run (one course)

```powershell
venv\Scripts\python harvest_zanfia.py map                    # Chrome opens; log in once
venv\Scripts\python harvest_zanfia.py download --course akademia-globalnego-startupu --parallel 3
venv\Scripts\python transcribe_pc.py --course akademia-globalnego-startupu --watch
venv\Scripts\python whimsical.py --course akademia-globalnego-startupu
bash pipeline_loop.sh akademiasaas-pl 192.168.56.108 3      # sync + VM pool
```

Notes from the first run (Od Developera Do Foundera 3.0, 199 lessons / 34 h; Akademia
Globalnego Startupu, 178 lessons / 33 h):
- Bunny players can take >15 s to appear; the harvester waits up to 45 s.
- Lesson tabs: "Opis lekcji" is captured; "Notatki" (personal notes) and "Zapytaj kurs"
  (AI chat) are not course content. Extra material is linked: Whimsical maps (97 lessons)
  and shared Google Sheets (exported by sitedigest).
- Sonnet: ~80-100 s per lesson; 3 workers -> one lesson every ~30 s; the 5-hour Claude
  session limit is the real cap (the pool pauses until the reset).
- PyAV 19 (Python 3.14) dropped `metadata_errors`, which faster-whisper 1.2 passes;
  transcribe_pc.py strips it.
