#!/usr/bin/env python3
"""Rebuild the character/Boss/achievement matrix from a saved Huiji Wiki HTML page.

This builder only owns the physical unlock matrix. Existing reward metadata in
``data/unlocks.js`` is preserved when possible, so recommendation/effect data
remain independent build layers.
"""
from __future__ import annotations
from pathlib import Path
import argparse, json, re
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'unlocks.js'

CHAR_EN = [
    'Isaac','Magdalene','Cain','Judas','???','Eve','Samson','Azazel','Lazarus','Eden',
    'The Lost','Lilith','Keeper','Apollyon','The Forgotten','Bethany','Jacob and Esau',
    'Tainted Isaac','Tainted Magdalene','Tainted Cain','Tainted Judas','Tainted ???',
    'Tainted Eve','Tainted Samson','Tainted Azazel','Tainted Lazarus','Tainted Eden',
    'Tainted Lost','Tainted Lilith','Tainted Keeper','Tainted Apollyon','Tainted Forgotten',
    'Tainted Bethany','Tainted Jacob'
]
BOSS_ROWS = [
    (3, 'boss-rush', 'Boss Rush', 'Boss Rush', 'rush'),
    (2, 'moms-heart', '妈妈的心', "Mom's Heart", 'heart'),
    (4, 'hush', '死寂', 'Hush', 'hush'),
    (5, 'isaac-boss', '以撒', 'Isaac', 'isaac'),
    (6, 'satan', '撒旦', 'Satan', 'satan'),
    (7, 'blue-baby', '？？？', '???', 'blue'),
    (8, 'lamb', '羔羊', 'The Lamb', 'lamb'),
    (9, 'mega-satan', '超级撒旦', 'Mega Satan', 'mega'),
    (10, 'delirium', '精神错乱', 'Delirium', 'delirium'),
    (11, 'mother', '母亲', 'Mother', 'mother'),
    (12, 'beast', '祸兽', 'The Beast', 'beast'),
    (13, 'greed', '贪婪模式', 'Greed Mode', 'greed'),
    (14, 'greedier', '贪婪模式（困难）', 'Greedier Mode', 'greedier'),
]

def slug(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def load_existing():
    if not OUT.exists(): return {}
    s=OUT.read_text('utf-8')
    m=re.search(r'window\.ISAAC_UNLOCK_DATA\s*=\s*(\{.*\});\s*$',s,re.S)
    return json.loads(m.group(1)) if m else {}

def expand_table(table, width=36):
    active={}; grid=[]
    for tr in table.find_all('tr'):
        out=[None]*width; nxt={}
        for col,(cell,remaining) in active.items():
            out[col]=cell
            if remaining>1: nxt[col]=(cell,remaining-1)
        col=0
        for cell in tr.find_all(['th','td'],recursive=False):
            while col<width and out[col] is not None: col+=1
            colspan=int(cell.get('colspan',1)); rowspan=int(cell.get('rowspan',1))
            for k in range(colspan):
                if col+k>=width: break
                out[col+k]=cell
                if rowspan>1: nxt[col+k]=(cell,rowspan-1)
            col+=colspan
        active=nxt; grid.append(out)
    return grid

def achievement_id(cell):
    if cell is None: return None
    node=cell.find(id=re.compile(r'^Achievement_\d+$'))
    return int(node['id'].split('_')[1]) if node else None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('html', type=Path, help='saved Huiji Project:存档/成就 HTML')
    args=ap.parse_args()
    existing=load_existing()
    soup=BeautifulSoup(args.html.read_text('utf-8',errors='ignore'),'html.parser')
    tables=soup.find_all('table')
    if not tables: raise RuntimeError('achievement table not found')
    grid=expand_table(tables[0])

    old_chars={x.get('nameEn'):x for x in existing.get('characters',[])}
    characters=[]
    for idx,col in enumerate(range(1,35)):
        cell=grid[0][col]
        a=cell.find('a') if cell else None
        name=(a.get('title') if a else '') or (cell.get_text(' ',strip=True) if cell else '')
        en=CHAR_EN[idx]; old=old_chars.get(en,{})
        characters.append({
            'id': old.get('id') or f'c{idx:02d}-{slug(en) or idx}',
            'name': name,
            'nameEn': en,
            'tainted': idx>=17,
            'order': idx,
            'image': old.get('image'),
        })
    bosses=[{'id':bid,'name':name,'nameEn':en,'order':i,'icon':icon}
            for i,(_,bid,name,en,icon) in enumerate(BOSS_ROWS)]

    matrix={c['id']:[] for c in characters}
    for order,(row,bid,*_) in enumerate(BOSS_ROWS):
        for ci,char in enumerate(characters):
            aid=achievement_id(grid[row][ci+1])
            if aid is not None: matrix[char['id']].append((bid,aid,order))

    rules=[]
    for char in characters:
        grouped={}; order=[]
        for bid,aid,boss_order in matrix[char['id']]:
            if aid not in grouped:
                grouped[aid]={'bossIds':[],'orders':[]}; order.append(aid)
            grouped[aid]['bossIds'].append(bid); grouped[aid]['orders'].append(boss_order)
        for aid in order:
            g=grouped[aid]
            rules.append({'id':f"{char['id']}-a{aid}",'characterId':char['id'],
                          'bossIds':g['bossIds'],'achievementId':aid,'defaultOrder':min(g['orders'])})

    old_catalog=existing.get('achievementCatalog',{})
    catalog={}
    for aid in sorted({r['achievementId'] for r in rules}):
        catalog[str(aid)] = old_catalog.get(str(aid), {
            'name': f'成就 #{aid}', 'condition':'', 'image':None, 'quality':None, 'effect':''
        })

    payload={'version':2,'characters':characters,'bosses':bosses,
             'unlockRules':rules,'achievementCatalog':catalog}
    OUT.write_text('// Generated by tools/build_unlocks.py\nwindow.ISAAC_UNLOCK_DATA = '+json.dumps(payload,ensure_ascii=False,indent=2)+';\n','utf-8')
    print(json.dumps({'characters':len(characters),'bosses':len(bosses),'rules':len(rules),
                      'bundledRules':sum(len(r['bossIds'])>1 for r in rules)},ensure_ascii=False))

if __name__=='__main__': main()
