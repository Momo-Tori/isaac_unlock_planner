#!/usr/bin/env python3
"""Rebuild data/unlocks.js from source inputs only.

Inputs:
- a saved Huiji Wiki ``Project:存档/成就`` HTML page for the physical
  character/Boss -> achievement-ID matrix;
- ``tools/achievement_rewards_en.json`` for canonical *English* reward names.

The previous generated ``data/unlocks.js`` is deliberately never read.  This
keeps the generated catalog reproducible and prevents translated display names
from leaking back into the EID matching key.
"""
from __future__ import annotations
from pathlib import Path
import argparse, json, re
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'unlocks.js'
EN_CATALOG = ROOT / 'tools' / 'achievement_rewards_en.json'

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


def load_english_catalog(path: Path):
    data=json.loads(path.read_text('utf-8'))
    entries=data.get('entries',{})
    bad=[(aid,name) for aid,name in entries.items() if re.search(r'[\u3400-\u9fff]',name or '')]
    if bad:
        raise RuntimeError(f'English catalog contains CJK names: {bad[:5]}')
    return entries


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


def condition_for(rule, characters_by_id, bosses_by_id):
    char=characters_by_id[rule['characterId']]['nameEn']
    targets=' / '.join(bosses_by_id[x]['nameEn'] for x in rule['bossIds'])
    return f'Defeat {targets} as {char}'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('html', type=Path, help='saved Huiji Project:存档/成就 HTML')
    ap.add_argument('--catalog', type=Path, default=EN_CATALOG,
                    help='canonical English reward-name seed')
    args=ap.parse_args()

    english_catalog=load_english_catalog(args.catalog)
    soup=BeautifulSoup(args.html.read_text('utf-8',errors='ignore'),'html.parser')
    tables=soup.find_all('table')
    if not tables: raise RuntimeError('achievement table not found')
    grid=expand_table(tables[0])

    characters=[]
    for idx,col in enumerate(range(1,35)):
        cell=grid[0][col]
        a=cell.find('a') if cell else None
        name=(a.get('title') if a else '') or (cell.get_text(' ',strip=True) if cell else '')
        en=CHAR_EN[idx]
        characters.append({
            'id': f'c{idx:02d}-{slug(en) or idx}',
            'name': name,
            'nameEn': en,
            'tainted': idx>=17,
            'order': idx,
            'image': None,
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

    required=sorted({r['achievementId'] for r in rules})
    missing=[aid for aid in required if str(aid) not in english_catalog]
    if missing:
        raise RuntimeError(f'English reward catalog is missing {len(missing)} achievement IDs: {missing[:20]}')

    chars_by_id={x['id']:x for x in characters}
    bosses_by_id={x['id']:x for x in bosses}
    rule_by_aid={r['achievementId']:r for r in rules}
    catalog={}
    for aid in required:
        rule=rule_by_aid[aid]
        catalog[str(aid)]={
            'name':english_catalog[str(aid)],
            'condition':condition_for(rule,chars_by_id,bosses_by_id),
            'image':None,
            'quality':None,
            'effect':'',
        }

    payload={'version':3,'catalogLanguage':'en','characters':characters,'bosses':bosses,
             'unlockRules':rules,'achievementCatalog':catalog}
    OUT.write_text('// Generated from source inputs by tools/build_unlocks.py\nwindow.ISAAC_UNLOCK_DATA = '+json.dumps(payload,ensure_ascii=False,indent=2)+';\n','utf-8')
    print(json.dumps({'characters':len(characters),'bosses':len(bosses),'rules':len(rules),
                      'catalog':len(catalog),'catalogCjkNames':sum(bool(re.search(r'[\u3400-\u9fff]',x['name'])) for x in catalog.values()),
                      'bundledRules':sum(len(r['bossIds'])>1 for r in rules)},ensure_ascii=False))

if __name__=='__main__': main()
