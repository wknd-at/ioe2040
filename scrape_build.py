import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

SOURCE_URL = "https://www.initiativeoesterreich2040.at/unsere-unterstuetzer"
BASE = "https://www.initiativeoesterreich2040.at"

OUT_DIR = "dist"
OUT_FILE = "dist/index.html"


def normalize_sort_key(name: str) -> str:
    """Stable alphabetic sort key with German-ish handling for umlauts/ß."""
    s = name.strip().lower()
    s = (
        s.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    s = re.sub(r"\s+", " ", s)
    return s


def fetch_html(url: str) -> str:
    """Fetch source HTML with a basic UA to reduce blocking."""
    headers = {"User-Agent": "Mozilla/5.0 (supporter-scraper; +github-actions)"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def extract_entries(html: str):
    """
    Extract supporter entries using <h3> headings as anchors.
    Walk forward in document order (next_elements) until the next <h3>.
    """
    soup = BeautifulSoup(html, "lxml")
    headings = soup.find_all("h3")
    entries = []

    for h in headings:
        name = h.get_text(" ", strip=True).replace("\xa0", " ").strip()
        if not name:
            continue

        # Skip obvious non-partner headings (page sections / CTAs)
        # (You can extend this list anytime.)
        skip_titles = {
            "KONTAKTIEREN SIE UNS WENN SIE UNTERSTÜTZER WERDEN WOLLEN",
            "ÜBER INITIATIVE ÖSTERREICH 2040",
        }
        if name.upper() in skip_titles:
            continue

        texts = []
        logo_url = None
        link = None

        # Walk forward in document order until next h3
        for el in h.next_elements:
            if getattr(el, "name", None) == "h3":
                break

            # First image in the block
            if logo_url is None and getattr(el, "name", None) == "img":
                src = el.get("src")
                if src:
                    logo_url = urljoin(BASE, src)

            # First external link in the block
            if link is None and getattr(el, "name", None) == "a":
                href = el.get("href", "").strip()
                if href.startswith("http://") or href.startswith("https://"):
                    link = href

            # Collect text nodes
            if isinstance(el, str):
                t = el.strip().replace("\xa0", " ")
                if t:
                    texts.append(t)

        block_text = " ".join(texts)
        block_text = re.sub(r"\s+", " ", block_text).strip()

        # Extract "Branche: ..."
        branche = None
        m = re.search(
            r"\bBranche\s*:\s*(.+?)(?=(?:\shttps?://)|$)",
            block_text,
            flags=re.IGNORECASE,
        )
        if m:
            val = m.group(1).strip()
            if val:
                branche = val

        # Fallback for logo if none found after h3
        if logo_url is None:
            prev_img = h.find_previous("img")
            if prev_img and prev_img.get("src"):
                logo_url = urljoin(BASE, prev_img["src"])

        # Filter out headings that are not actual supporter cards:
        # In your layout, real supporters have at least a logo OR a branche OR an external link.
        if not (logo_url or branche or link):
            continue

        entries.append(
            {
                "name": name,
                "branche": branche,
                "url": link,
                "logo": logo_url,
                "sort": normalize_sort_key(name),
            }
        )

    # Dedup (Name + url + logo)
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
        href = e.get("url") or "#"
        logo = e.get("logo") or ""
        branche = f"Branche: {e['branche']}" if e.get("branche") else ""

        cards.append(
            f"""
        <a class="card" href="{href}" target="_blank" rel="noopener">
          <div class="logoWrap">
            <img src="{logo}" alt="{e['name']}" loading="lazy" decoding="async">
          </div>
          <div class="name">{e['name']}</div>
          <div class="meta">{branche}</div>
        </a>
        """
        )

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
  <!-- <h1>Partner & Unterstützer (alphabetisch)</h1>
  <p class="hint">Automatisch aus der Webador-Seite gebaut. Stand: <span id="ts"></span>. Anzahl: {len(entries)}</p> -->

  <div class="grid">
    {''.join(cards)}
  </div>

  <footer>
    Stand: <span id="ts"></span>. Partner: <code>{len(entries)}</code>
  </footer>

  <script>
    const el = document.getElementById('ts');
    if (el) el.textContent = new Date().toLocaleString('de-AT');
  </script>
  
  <script>
(function () {{
  function sendHeight() {{
    const doc = document.documentElement;
    const body = document.body;

    const height = Math.max(
      doc.scrollHeight,
      doc.offsetHeight,
      doc.clientHeight,
      body ? body.scrollHeight : 0,
      body ? body.offsetHeight : 0
    );

    if (window.parent && window.parent !== window) {{
      window.parent.postMessage(
        {{ type: "ioe2040_iframe_height", height: height }},
        "*"
      );
    }}
  }}

  window.addEventListener("load", sendHeight);
  window.addEventListener("resize", function () {{
    setTimeout(sendHeight, 50);
  }});

  const mo = new MutationObserver(function () {{
    setTimeout(sendHeight, 50);
  }});
  mo.observe(document.documentElement, {{
    childList: true,
    subtree: true,
    attributes: true
  }});

  if ("ResizeObserver" in window) {{
    const ro = new ResizeObserver(function () {{
      setTimeout(sendHeight, 50);
    }});
    ro.observe(document.documentElement);
  }}

  const imgs = document.images || [];
  for (let i = 0; i < imgs.length; i++) {{
    if (!imgs[i].complete) {{
      imgs[i].addEventListener("load", function () {{
        setTimeout(sendHeight, 50);
      }}, {{ once: true }});
    }}
  }}

  setTimeout(sendHeight, 300);
  setTimeout(sendHeight, 1200);
}})();
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

    missing = [e["name"] for e in entries if not e.get("branche")]
    print("Missing branche count:", len(missing))
    print("First missing:", missing[:20])

    if len(entries) < 10:
        raise SystemExit(
            f"Extraction looks wrong (only {len(entries)} entries). Aborting deploy."
        )

    ensure_dist()
    out_html = build_html(entries)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(out_html)

    print(f"OK: wrote {OUT_FILE} with {len(entries)} entries")


if __name__ == "__main__":
    main()
