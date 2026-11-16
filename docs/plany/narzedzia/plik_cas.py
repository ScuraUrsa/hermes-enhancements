#!/usr/bin/env python3
"""Bezpieczny zapis wspólnych plików planów (compare-and-swap).

Każdy wątek/agent przed edycją robi `wersja`, pracuje na swojej kopii, a zapisuje przez `zapisz`
z wersją, od której zaczął. Jeśli ktoś w międzyczasie zmienił plik, zapis jest odrzucony (kod 3):
trzeba przeczytać plik od nowa, nanieść swoje zmiany na nową wersję i spróbować jeszcze raz.

    python3 plik_cas.py wersja KOLEJKA.md              # wypisuje sha256 bieżącej treści
    python3 plik_cas.py zapisz KOLEJKA.md <sha> nowy.md # zapisuje nowy.md, jeśli KOLEJKA.md ma nadal <sha>

Blokada: plik `<nazwa>.lock` tworzony atomowo (O_EXCL); stara blokada (> 120 s) jest zdejmowana.
"""
import hashlib
import os
import sys
import time

LOCK_STALE_S = 120


def sha(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        return "brak"


def lock(path):
    lp = path + ".lock"
    for _ in range(60):
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time()}\n".encode())
            os.close(fd)
            return lp
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lp) > LOCK_STALE_S:
                    os.remove(lp)
                    continue
            except FileNotFoundError:
                continue
            time.sleep(1)
    sys.exit("plik zablokowany ponad 60 s, spróbuj później")


def save(path, expected, new_path):
    lp = lock(path)
    try:
        current = sha(path)
        if current != expected:
            print(f"ODRZUCONE: plik zmienił się od Twojego odczytu (było {expected[:12]}, jest {current[:12]}). "
                  "Przeczytaj go ponownie, nanieś swoje zmiany na nową wersję i zapisz jeszcze raz.")
            return 3
        with open(new_path, "rb") as f:
            data = f.read()
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        print(f"ZAPISANE: nowa wersja {sha(path)[:12]}")
        return 0
    finally:
        os.remove(lp)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "wersja":
        print(sha(sys.argv[2]))
    elif len(sys.argv) == 5 and sys.argv[1] == "zapisz":
        sys.exit(save(sys.argv[2], sys.argv[3], sys.argv[4]))
    else:
        sys.exit(__doc__)
