import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

SOURCE_URL = "https://www.initiativeoesterreich2040.at/unsere-unterstuetzer"
BASE = "https://www.initiativeoesterreich2040.at"

OUT_DIR = "dist"
OUT_FILE = "dist/index.html"

def normalize_sort_key(name: str) -> str:
    s = name.strip().lower()
    s = (s.replace("ä", "ae")
           .replace("ö", "oe")
           .replace("ü", "ue")
           .replace("ß", "ss"))
    s = re.sub(r"\s+", " ", s)
    return s

def fetch_html(url: str) -> str:
    # Set a UA to reduce chances of being blocked
    headers = {"User-Agent": "Mozilla/5.0 (supporter-scraper; +github-actions)"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text

def extract_entries(html: str):
    soup = BeautifulSoup(html, "lxml")

    entries = []
    headings = soup.find_all("h3")

    for i, h in enumerate(headings):
        name = h.get_text(" ", strip=True)
        if not name:
            continue

        # Alles zwischen diesem h3 und dem nächsten h3 als "Block"
        block_nodes = []
        node = h.next_sibling
        while node is not None and not (getattr(node, "name", None) == "h3"):
            block_nodes.append(node)
            node = node.next_sibling

        block_soup = BeautifulSoup("", "lxml")
        wrapper = block_soup.new_tag("div")
        for n in block_nodes:
            # NavigableString oder Tag – beides anhängen
            try:
                wrapper.append(n)
            except Exception:
                pass
        block_soup.append(wrapper)

        # Text aus Block (normalisiert, inkl. NBSP)
        block_text = wrapper.get_text(" ", strip=True).replace("\xa0", " ")
        # Branche via Regex aus dem Block-Text
        branche = None
        m = re.search(r"\bBranche\s*:\s*(.+?)(?=$)", block_text, flags=re.IGNORECASE)
        if m:
            # manchmal hängt noch URL/sonstiges im Text; wir schneiden bei "http" ab
            val = m.group(1).strip()
            val = re.split(r"\shttps?://", val, maxsplit=1)[0].strip()
            branche = val or None

        # Link: erster externer http(s)-Link im Block
        link = None
        for a in wrapper.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("http://") or href.startswith("https://"):
                link = href
                break

        # Logo: erstes Bild im Block (falls keines, fallback: img kurz vor h3)
        logo_url = None
        img = wrapper.find("img")
        if img and img.get("src"):
            logo_url = urljoin(BASE, img["src"])
        else:
            prev_img = h.find_previous("img")
            if prev_img and prev_img.get("src"):
                logo_url = urljoin(BASE, prev_img["src"])

        entries.append({
            "name": name,
            "branche": branche,
            "url": link,
            "logo": logo_url,
            "sort": normalize_sort_key(name),
        })

    # Dedup
    seen = set()
    uniq = []
    for e in entries:
        key = (e["name"], e["url"], e["logo"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)

    return sorted(uniq, key=lambda x: x["sort"])


def build_html(entries):
    cards = []
    for e in entries:
        href = e["url"] or "#"
        logo = e["logo"] or ""
        branche = f"Branche: {e['branche']}" if e.get("branche") else ""
        cards.append(f"""
        <a class="card" href="{href}" target="_blank" rel="noopener">
          <div class="logoWrap">
            <img src="{logo}" alt="{e['name']}" loading="lazy" decoding="async">
          </div>
          <div class="name">{e['name']}</div>
          <div class="meta">{branche}</div>
        </a>
        """)

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Unsere Unterstützer (alphabetisch)</title>
  <meta name="robots" content="noindex,nofollow">
  <style>
    :root {{ --border:#e6e6e6; --bg:#fff; --text:#111; --muted:#666; }}
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; color: var(--text); background: var(--bg); }}
    h1 {{ font-size: 24px; margin: 0 0 12px; }}
    .hint {{ color: var(--muted); margin: 0 0 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }}
    .card {{ display: block; border: 1px solid var(--border); border-radius: 14px; padding: 12px; text-decoration: none; color: inherit; background:#fff; }}
    .card:hover {{ box-shadow: 0 6px 20px rgba(0,0,0,.06); }}
    .logoWrap {{ height: 120px; display:flex; align-items:center; justify-content:center; margin-bottom: 10px; }}
    img {{ max-width: 100%; max-height: 120px; object-fit: contain; display: block; }}
    .name {{ font-weight: 750; line-height: 1.2; margin-bottom: 4px; }}
    .meta {{ color: var(--muted); font-size: 14px; min-height: 18px; }}
    footer {{ margin-top: 24px; color: var(--muted); font-size: 13px; }}
    code {{ background:#f6f6f6; padding:2px 6px; border-radius:6px; }}
  </style>
</head>
<body>
  <h1>Partner & Unterstützer (alphabetisch)</h1>
  <!-- <p class="hint">Automatisch aus der Webador-Seite gebaut. Stand: <span id="ts"></span>. Anzahl: {len(entries)}</p> -->

  <div class="grid">
    {''.join(cards)}
  </div>

  <footer>
    Quelle: <code>{SOURCE_URL}</code>
  </footer>

  <script>
    // Timestamp injected by build via meta tag below if needed; fallback to client time
    document.getElementById('ts').textContent = new Date().toLocaleString('de-AT');
  </script>
</body>
</html>
"""

def ensure_dist():
    import os
    os.makedirs(OUT_DIR, exist_ok=True)

def main():
    html = fetch_html(SOURCE_URL)
    entries = extract_entries(html)

    if len(entries) < 10:
        # Safety check so you don't accidentally deploy an empty/broken page
        raise SystemExit(f"Extraction looks wrong (only {len(entries)} entries). Aborting deploy.")

    ensure_dist()
    out_html = build_html(entries)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(out_html)

    print(f"OK: wrote {OUT_FILE} with {len(entries)} entries")

if __name__ == "__main__":
    main()
