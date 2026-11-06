"""On the VM: fill digest.notion_url in the sitedigest map from the Notion database itself (matched by the
"Klucz" property = lesson key). Used after map entries were rebuilt (2026-11-06: ODDF 1.0/2.0 left the
library and their map entries were restored without Notion links), so push_notion.py --only-new does not
create duplicate rows. Needs NOTION_API_KEY.

  python fill_notion_urls.py SITE [--database e44ec7c6c4fc4f92af0a8626144963d4]
"""

from __future__ import annotations

import argparse
import os
import sys

import requests

from sitedigest import config, crawl


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--database", default="e44ec7c6c4fc4f92af0a8626144963d4", help='"Kursy: lekcje"')
    a = ap.parse_args()
    h = {"Authorization": f"Bearer {os.environ['NOTION_API_KEY']}", "Notion-Version": "2022-06-28",
         "Content-Type": "application/json"}
    urls: dict[str, str] = {}
    body: dict = {"page_size": 100}
    while True:
        r = requests.post(f"https://api.notion.com/v1/databases/{a.database}/query", headers=h, json=body, timeout=60)
        r.raise_for_status()
        d = r.json()
        for pg in d["results"]:
            key = "".join(t["plain_text"] for t in pg["properties"].get("Klucz", {}).get("rich_text", []))
            if key and not key.endswith("-v1"):
                urls.setdefault(key, pg["url"])
        if not d.get("has_more"):
            break
        body["start_cursor"] = d["next_cursor"]
    print(f"Notion rows with a key: {len(urls)}", flush=True)
    cfg = config.load()
    n = 0
    with crawl.map_lock(cfg, a.site):
        m = crawl.load_map(cfg, a.site)
        for p in m["pages"]:
            dg = p.get("digest") or {}
            if dg and not dg.get("notion_url") and p["key"] in urls:
                dg["notion_url"] = urls[p["key"]]
                n += 1
        crawl.save_map(cfg, a.site, m)
    print(f"filled {n} Notion links", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
