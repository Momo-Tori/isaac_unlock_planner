#!/usr/bin/env python3
"""Download character and unlock/reward artwork into local assets/.

Run at build time. Images are normalized to PNG so browser paths stay stable.
Boss artwork is deliberately not fetched here: v4 bundles the 13 manually curated
Boss images supplied by the project user and should not overwrite them.

Sources:
- Character portraits: saarsc/IsaacCasinoOBS (GitHub)
- Achievement artwork is supplied as a local sprite and is not downloaded by this builder.
"""
from __future__ import annotations
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from io import BytesIO
import argparse, html, json, re, time

ROOT = Path(__file__).resolve().parents[1]
UNLOCKS = ROOT / 'data' / 'unlocks.js'
ASSETS = ROOT / 'assets'
UA = 'isaac-unlock-planner-asset-builder/3 (+static local cache)'

CHAR_FILES = {
    'c00-isaac':'Isaac.png','c01-magdalene':'Magdalene.png','c02-cain':'Cain.png','c03-judas':'Judas.png',
    'c04-4':'Blue Baby.png','c05-eve':'Eve.png','c06-samson':'Samson.png','c07-azazel':'Azazel.png',
    'c08-lazarus':'Lazarus.png','c09-eden':'Eden.png','c10-the-lost':'Lost.png','c11-lilith':'Lilith.png',
    'c12-keeper':'Keeper.png','c13-apollyon':'Apollyon.png','c14-the-forgotten':'Forgotten.png','c15-bethany':'Bethany.png',
    'c16-jacob-and-esau':'Jacob & Esau.png','c17-tainted-isaac':'T Isaac.png','c18-tainted-magdalene':'T Magdalene.png',
    'c19-tainted-cain':'T Cain.png','c20-tainted-judas':'T Judas.png','c21-tainted':'T Blue Baby.png','c22-tainted-eve':'T Eve.png',
    'c23-tainted-samson':'T Samson.png','c24-tainted-azazel':'T Azazel.png','c25-tainted-lazarus':'T Lazarus.png',
    'c26-tainted-eden':'T Eden.png','c27-tainted-lost':'T Lost.png','c28-tainted-lilith':'T Lilith.png',
    'c29-tainted-keeper':'T Keeper.png','c30-tainted-apollyon':'T Apollyon.png','c31-tainted-forgotten':'T Forgotten.png',
    'c32-tainted-bethany':'T Bethany.png','c33-tainted-jacob':'T Jacob.png',
}

OG_RE = re.compile(r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I)
OG_RE_REV = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']', re.I)

def load_js(path: Path, var: str):
    s = path.read_text('utf-8')
    m = re.search(rf'window\.{re.escape(var)}\s*=\s*(\{{.*\}});\s*$', s, re.S)
    if not m: raise RuntimeError(f'Cannot parse {path}')
    return json.loads(m.group(1))

def get(url: str, binary: bool=True):
    req = Request(url, headers={'User-Agent': UA, 'Accept':'image/avif,image/webp,image/png,image/*,*/*;q=0.8' if binary else 'text/html,*/*;q=0.8'})
    with urlopen(req, timeout=30) as r:
        return r.read()

def page_og_image(title: str):
    slug = quote(title.replace(' ','_'), safe='()?_')
    pages = [
        'https://bindingofisaacrebirth.wiki.gg/wiki/' + slug,
        'https://bindingofisaacrebirth.fandom.com/wiki/' + slug,
    ]
    for url in pages:
        try:
            text = get(url, binary=False).decode('utf-8', 'replace')
        except Exception:
            continue
        m = OG_RE.search(text) or OG_RE_REV.search(text)
        if m:
            return html.unescape(m.group(1))
    return None

def save_png(blob: bytes, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
        im = Image.open(BytesIO(blob)).convert('RGBA')
        im.save(dest, format='PNG', optimize=True)
    except Exception:
        # If Pillow is unavailable but source is already PNG, preserve it.
        if blob.startswith(b'\x89PNG\r\n\x1a\n'):
            dest.write_bytes(blob)
        else:
            raise RuntimeError('Pillow is required to normalize non-PNG assets')

def download_first(urls, dest: Path, refresh=False):
    if dest.exists() and not refresh: return True
    for url in [u for u in urls if u]:
        try:
            save_png(get(url), dest)
            return True
        except Exception as exc:
            last = exc
    print(f'[miss] {dest.name}: {last if "last" in locals() else "no source"}')
    return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--refresh', action='store_true')
    ap.add_argument('--delay', type=float, default=.08, help='polite delay between wiki page fallbacks')
    args=ap.parse_args()
    data=load_js(UNLOCKS,'ISAAC_UNLOCK_DATA')
    stats={'characters':0,'bosses':0,'achievements':0,'achievementTotal':len(data['achievementCatalog'])}

    for c in data['characters']:
        fn=CHAR_FILES.get(c['id'])
        gh=('https://raw.githubusercontent.com/saarsc/IsaacCasinoOBS/main/Imges/Characters/'+quote(fn, safe='')) if fn else None
        if download_first([gh, c.get('image')], ASSETS/'character'/f"{c['id']}.png", args.refresh): stats['characters']+=1

    # Boss images are user-curated assets bundled with the project. Never overwrite them.
    stats['bosses'] = sum(1 for b in data['bosses'] if (ASSETS/'boss'/f"{b['id']}.png").exists())

    # Achievement artwork is bundled as one 20×33 sprite, one 64×64 cell per ID.
    sprite = ASSETS/'achievement'/'Achievement_sprite.jpg'
    stats['achievements'] = len(data['achievementCatalog']) if sprite.exists() else 0

    (ASSETS/'asset-report.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(stats,ensure_ascii=False))

if __name__=='__main__': main()
