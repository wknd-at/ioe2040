import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

SOURCE_URL = "https://www.initiativeoesterreich2040.at/unsere-unterstuetzer-build"
BASE = "https://www.initiativeoesterreich2040.at"

OUT_DIR = "dist"
OUT_FILE = "dist/index.html"


# -----------------------------
# Helpers
# -----------------------------

def normalize_sort_key(name: str) -> str:
    s = name.strip().lower()
    s = (
        s.replace("ä", "ae")
         .replace("ö", "oe")
         .replace("ü", "ue")
         .replace("ß", "ss")
    )
    return re.sub(r"\s+", " ", s)


def fetch_html(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (supporter-scraper; +github-actions)"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def esc_attr(s: str) -> str:
    """Escape for safe insertion into HTML attributes and text."""
    s = s or ""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


# -----------------------------
# Extraction
# -----------------------------

def extract_entries(html: str):
    soup = BeautifulSoup(html, "lxml")
    headings = soup.find_all("h3")
    entries = []

    SKIP_TITLES = {
        "KONTAKTIEREN SIE UNS WENN SIE UNTERSTÜTZER WERDEN WOLLEN",
        "ÜBER INITIATIVE ÖSTERREICH 2040",
    }

    def find_logo_before_h3(h3):
        """
        Logo steht IMMER oberhalb des h3.
        Wir suchen rückwärts, stoppen aber beim vorherigen h3.
        """
        for el in h3.previous_elements:
            if getattr(el, "name", None) == "h3":
                break
            if getattr(el, "name", None) == "img":
                src = el.get("src")
                if src:
                    return urljoin(BASE, src)
        return None

    for h in headings:
        name = h.get_text(" ", strip=True).replace("\xa0", " ").strip()
        if not name:
            continue
        if name.upper() in SKIP_TITLES:
            continue

        logo_url = find_logo_before_h3(h)

        texts = []
        link = None

        # Vorwärts lesen bis zum nächsten h3
        for el in h.next_elements:
            if getattr(el, "name", None) == "h3":
                break

            if link is None and getattr(el, "name", None) == "a":
                href = el.get("href", "").strip()
                if href.startswith("http://") or href.startswith("https://"):
                    link = href

            if isinstance(el, str):
                t = el.strip().replace("\xa0", " ")
                if t:
                    texts.append(t)

        block_text = re.sub(r"\s+", " ", " ".join(texts)).strip()

        branche = None
        m = re.search(
            r"\bBranche\s*:\s*(.+?)(?=(?:\shttps?://)|$)",
            block_text,
            flags=re.IGNORECASE,
        )
        if m:
            branche = m.group(1).strip() or None

        # Nur echte Partner übernehmen
        if not (logo_url or branche or link):
            continue

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
        if key not in seen:
            seen.add(key)
            uniq.append(e)

    return sorted(uniq, key=lambda x: x["sort"])


# -----------------------------
# HTML Output
# -----------------------------

def build_html(entries):
    cards = []
    for e in entries:
        name = e["name"]
        branche_val = e.get("branche") or ""
        url_val = e.get("url") or ""
        logo = e.get("logo") or ""

        branche_text = f"Branche: {branche_val}" if branche_val else ""

        cards.append(f"""
        <a class="card"
           href="{esc_attr(url_val) or '#'}"
           target="_blank"
           rel="noopener"
           data-name="{esc_attr(name)}"
           data-branche="{esc_attr(branche_val)}"
           data-url="{esc_attr(url_val)}">
          <div class="logoWrap">
            <img src="{esc_attr(logo)}" alt="{esc_attr(name)}" loading="lazy" decoding="async">
          </div>
          <div class="name">{esc_attr(name)}</div>
          <div class="meta">{esc_attr(branche_text)}</div>
          <div class="url">{esc_attr(url_val)}</div>
        </a>
        """)

    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Unterstützer – alphabetisch</title>
<meta name="robots" content="noindex,nofollow">
<style>
html, body {{
  margin: 0;
  padding: 0;
  overflow: hidden; /* verhindert Scrollbars im iFrame */
}}

body {{
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
}}

#ioe2040Root {{
  padding: 24px;
}}

.topbar {{
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}}

.count {{
  color: #666;
  font-size: 14px;
}}

.searchWrap {{
  width: 360px; /* Desktop rechts oben */
  max-width: 100%;
}}

.searchWrap input {{
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e6e6e6;
  border-radius: 12px;
  font-size: 14px;
  outline: none;
}}

.searchWrap input:focus {{
  border-color: #bdbdbd;
}}

@media (max-width: 640px) {{
  .topbar {{
    flex-direction: column;
    align-items: stretch;
  }}
  .searchWrap {{
    width: 100%; /* Mobil volle Breite */
  }}
}}

.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}}

.card {{
  display: block;
  border: 1px solid #e6e6e6;
  border-radius: 14px;
  padding: 12px;
  text-decoration: none;
  color: inherit;
  background: #fff;
}}

.card:hover {{
  box-shadow: 0 6px 20px rgba(0,0,0,.06);
}}

.logoWrap {{
  height: 120px;
  display: flex;
  align-items: start;
  justify-content: start;
  margin-bottom: 10px;
}}

img {{
  max-width: 100%;
  max-height: 120px;
  object-fit: contain;
}}

.name {{
  font-weight: 700;
  margin-bottom: 4px;
}}

.meta {{
  color: #666;
  font-size: 14px;
  margin-bottom: 6px;
}}

.url {{
  color: #999;
  font-size: 12px;
  word-break: break-word;
}}

footer {{
  margin-top: 18px;
  font-size: 13px;
  color: #666;
}}
</style>
</head>
<body>

<div id="ioe2040Root">
  <div class="topbar">
    <!--<div class="count" id="count"></div>-->
    <div class="searchWrap">
      <input id="q" type="search" placeholder="Suchen (Name, Branche, URL)…" autocomplete="off">
    </div>
  </div>

  <div class="grid" id="grid">
    {''.join(cards)}
  </div>

  <footer>
    <!--Stand: <span id="ts"></span> · Partner: <strong id="total">{len(entries)}</strong>-->
  </footer>
</div>

<script>
(function() {{
  const ts = document.getElementById('ts');
  if (ts) ts.textContent = new Date().toLocaleString('de-AT');
}})();
</script>

<script>
(function() {{
  const input = document.getElementById('q');
  const cards = Array.from(document.querySelectorAll('.card'));
  const countEl = document.getElementById('count');

  function norm(s) {{
    return (s || "")
      .toLowerCase()
      .trim()
      .replace(/ä/g,'ae').replace(/ö/g,'oe').replace(/ü/g,'ue').replace(/ß/g,'ss');
  }}

  function updateCount(visible) {{
    if (!countEl) return;
    countEl.textContent = visible + " / " + cards.length + " angezeigt";
  }}

  function filter() {{
    const q = norm(input.value);
    let visible = 0;

    for (const c of cards) {{
      const hay = norm(
        (c.dataset.name || "") + " " +
        (c.dataset.branche || "") + " " +
        (c.dataset.url || "")
      );
      const show = !q || hay.includes(q);
      c.style.display = show ? "" : "none";
      if (show) visible++;
    }}

    updateCount(visible);

    // Nach Filter: Höhe neu melden (damit Webador iFrame passt)
    if (window.__ioe2040_requestHeight) window.__ioe2040_requestHeight();
  }}

  input.addEventListener('input', filter);
  updateCount(cards.length);
}})();
</script>

<script>
(function () {{
  const root = document.getElementById("ioe2040Root");
  if (!root) return;

  let last = 0;
  let stableCount = 0;
  let ticks = 0;

  const MAX_TICKS = 40;       // ~8s at 200ms
  const THRESHOLD = 2;        // px: treat as stable
  const SEND_THRESHOLD = 10;  // px: only send if change is meaningful

  function measureRootHeight() {{
    const rect = root.getBoundingClientRect();
    return Math.ceil(rect.height);
  }}

  function post(h) {{
    if (window.parent && window.parent !== window) {{
      window.parent.postMessage(
        {{ type: "ioe2040_iframe_height", height: h }},
        "*"
      );
    }}
  }}

  function step() {{
    ticks++;
    const h = measureRootHeight();

    if (Math.abs(h - last) <= THRESHOLD) {{
      stableCount++;
    }} else {{
      stableCount = 0;
    }}

    if (Math.abs(h - last) >= SEND_THRESHOLD) {{
      post(h);
    }}

    last = h;

    if (stableCount >= 3 || ticks >= MAX_TICKS) {{
      clearInterval(timer);
    }}
  }}

  // Expose for the filter script:
  window.__ioe2040_requestHeight = step;

  // Start now + then poll while layout settles (images/fonts)
  step();
  const timer = setInterval(step, 200);

  // Nudge on image load
  const imgs = document.images || [];
  for (let i = 0; i < imgs.length; i++) {{
    if (!imgs[i].complete) {{
      imgs[i].addEventListener("load", step, {{ once: true }});
      imgs[i].addEventListener("error", step, {{ once: true }});
    }}
  }}

  // Nudge when fonts are ready
  if (document.fonts && document.fonts.ready) {{
    document.fonts.ready.then(step);
  }}
}})();
</script>

</body>
</html>
"""


# -----------------------------
# Main
# -----------------------------

def ensure_dist():
    import os
    os.makedirs(OUT_DIR, exist_ok=True)


def main():
    html = fetch_html(SOURCE_URL)
    entries = extract_entries(html)

    missing = [e["name"] for e in entries if not e.get("branche")]
    print("Missing branche count:", len(missing))
    print("First missing:", missing[:10])

    if len(entries) < 10:
        raise SystemExit("Extraction looks wrong – aborting.")

    ensure_dist()
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(build_html(entries))

    print(f"OK: wrote {OUT_FILE} with {len(entries)} entries")


if __name__ == "__main__":
    main()
