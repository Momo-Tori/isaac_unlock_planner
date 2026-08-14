#!/usr/bin/env python3
"""Build static Chinese reward effects from External Item Descriptions (EID).

This is deliberately a build-time fetcher. The browser app itself stays offline.
It downloads Simplified-Chinese and English EID language packs for AB+, Repentance
and Repentance+, merges collectible/trinket/card/pill descriptions, and maps them
back to achievement IDs in data/unlocks.js. English reward names are used as a
secondary entity-ID lookup when Chinese-name matching is insufficient.
"""
from __future__ import annotations
from pathlib import Path
from urllib.request import Request, urlopen
import argparse, json, re

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'tools' / 'cache' / 'eid'
OUT = ROOT / 'data' / 'effects.js'
REPORT = ROOT / 'data' / 'effects-report.json'
UNLOCKS = ROOT / 'data' / 'unlocks.js'
RECS = ROOT / 'data' / 'recommendations.js'

SOURCES = [
    ('ab+', 'https://raw.githubusercontent.com/wofsauge/External-Item-Descriptions/master/descriptions/ab%2B/zh_cn.lua'),
    ('rep', 'https://raw.githubusercontent.com/wofsauge/External-Item-Descriptions/master/descriptions/rep/zh_cn.lua'),
    ('rep+', 'https://raw.githubusercontent.com/wofsauge/External-Item-Descriptions/master/descriptions/rep%2B/zh_cn.lua'),
]
EN_SOURCES = [
    ('ab+', 'https://raw.githubusercontent.com/wofsauge/External-Item-Descriptions/master/descriptions/ab%2B/en_us.lua'),
    ('rep', 'https://raw.githubusercontent.com/wofsauge/External-Item-Descriptions/master/descriptions/rep/en_us.lua'),
    ('rep+', 'https://raw.githubusercontent.com/wofsauge/External-Item-Descriptions/master/descriptions/rep%2B/en_us.lua'),
]

TUPLE_RE = re.compile(
    r'(?:\[(\d+)\]\s*=\s*)?\{\s*"(\d*)"\s*,\s*"((?:\\.|[^"\\])*)"\s*,\s*"((?:\\.|[^"\\])*)"\s*\}\s*,?\s*(?:--\s*([^\r\n]+))?'
)

# Markers intentionally include only the simple base description tables.
TABLE_MARKERS = {
    'ab+': {
        'collectible': ('EID.descriptions[languageCode].collectibles={', '---------- Trinkets ----------'),
        'trinket': ('EID.descriptions[languageCode].trinkets={', '---------- Cards ----------'),
        'card': ('EID.descriptions[languageCode].cards={', '---------- Pills ----------'),
        'pill': ('EID.descriptions[languageCode].pills={', 'EID.descriptions[languageCode].CharacterInfo = {'),
    },
    'rep': {
        'collectible': ('local repCollectibles={', 'EID:updateDescriptionsViaTable(repCollectibles'),
        'trinket': ('local repTrinkets={', 'EID:updateDescriptionsViaTable(repTrinkets'),
        'card': ('local repCards={', 'EID:updateDescriptionsViaTable(repCards'),
        'pill': ('local repPills={', 'EID:updateDescriptionsViaTable(repPills'),
    },
    'rep+': {
        'collectible': ('local collectibles = {', 'EID:updateDescriptionsViaTable(collectibles'),
        'trinket': ('local trinkets = {', 'EID:updateDescriptionsViaTable(trinkets'),
        'card': ('local cards = {', 'EID:updateDescriptionsViaTable(cards'),
    },
}

def load_js(path: Path, var: str):
    s=path.read_text('utf-8')
    m=re.search(rf'window\.{re.escape(var)}\s*=\s*(\{{.*\}});\s*$',s,re.S)
    if not m: raise RuntimeError(f'cannot parse {path}')
    return json.loads(m.group(1))

def fetch(url: str, path: Path, refresh: bool=False) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not refresh:
        return path.read_text('utf-8')
    req=Request(url, headers={'User-Agent':'isaac-unlock-planner-data-builder/2'})
    with urlopen(req, timeout=45) as r:
        b=r.read()
    path.write_bytes(b)
    return b.decode('utf-8')

def decode_lua_string(s: str) -> str:
    # Language pack strings mostly use ordinary UTF-8 text; handle common escaped quotes/backslashes.
    return s.replace('\\"','"').replace('\\\\','\\')

def clean_effect(s: str) -> str:
    s=decode_lua_string(s)
    s=re.sub(r'\{\{CR\}\}', '', s)
    s=re.sub(r'\{\{[^{}]+\}\}', '', s)
    # EID uses # as a display separator between effect clauses. Keep that
    # structure as line breaks so the generated UI does not collapse it into
    # one long semicolon-delimited paragraph.
    parts=[]
    for part in s.split('#'):
        part=re.sub(r'\s+',' ',part).strip(' ；')
        if part:
            parts.append(part)
    return '\n'.join(parts)

def norm_name(s: str) -> str:
    s=s.lower()
    s=re.sub(r'\[[^\]]*\]','',s)
    s=re.sub(r'\([^)]*[a-z][^)]*\)','',s)
    s=s.replace('卡牌','')
    s=s.replace('？','?').replace('＆','&')
    s=re.sub(r'^(?:[ivxlcdm]+|0)[-—–\s]*', '', s)
    s=re.sub(r'[^0-9a-z\u4e00-\u9fff?]+','',s)
    return s

def extract_section(text: str, start: str, end: str):
    a=text.find(start)
    if a<0: return ''
    b=text.find(end,a+len(start))
    if b<0: return ''
    return text[a:b]

def parse_pack(kind: str, text: str, language: str='zh'):
    out=[]
    for category,(start,end) in TABLE_MARKERS[kind].items():
        section=extract_section(text,start,end)
        if not section: continue
        for bracket_id, id_field, name, desc, comment in TUPLE_RE.findall(section):
            raw_id = id_field or bracket_id
            if not raw_id:
                continue
            entity_id=int(raw_id)
            row={
                'category':category,
                'id':entity_id,
                'name':decode_lua_string(name),
                'effect':clean_effect(desc),
                'commentName':(comment or '').strip(),
                'pack':kind,
                'language':language,
            }
            if language == 'zh':
                row['zhName']=row['name']
                row['enName']=row['commentName']
            else:
                row['enName']=row['name']
            out.append(row)
    return out

def is_baby_reward(name: str) -> bool:
    name = (name or "").strip()
    low = name.lower()
    return "baby" in low or "宝宝" in name

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--refresh', action='store_true', help='redownload EID language packs')
    args=ap.parse_args()
    merged={}
    english_entities={}
    source_stats={}
    for kind,url in SOURCES:
        path=CACHE/f'{kind.replace("+","plus")}_zh_cn.lua'
        text=fetch(url,path,args.refresh)
        rows=parse_pack(kind,text,'zh')
        source_stats[kind]=len(rows)
        for row in rows:
            merged[(row['category'],row['id'])]=row

    english_source_stats={}
    for kind,url in EN_SOURCES:
        path=CACHE/f'{kind.replace("+","plus")}_en_us.lua'
        text=fetch(url,path,args.refresh)
        rows=parse_pack(kind,text,'en')
        english_source_stats[kind]=len(rows)
        for row in rows:
            english_entities[(row['category'],row['id'])]=row

    by_zh={}
    by_en={}
    for row in merged.values():
        z=norm_name(row['zhName'])
        if z: by_zh.setdefault(z,[]).append(row)
        # Chinese packs often keep the canonical English name in a trailing comment.
        e=norm_name(row.get('enName',''))
        if e: by_en.setdefault(e,[]).append(row)
    # More reliable English-name index: resolve the entity ID from en_us first,
    # then use that exact category+ID to retrieve the Simplified-Chinese description.
    for key,enrow in english_entities.items():
        e=norm_name(enrow.get('enName',''))
        zhrow=merged.get(key)
        if e and zhrow:
            by_en.setdefault(e,[]).append(zhrow)

    english_aliases = {
        norm_name('Locust of Wrath'): norm_name('Locust of War'),
        norm_name('Sacraficial Dagger'): norm_name('Sacrificial Dagger'),
        norm_name("Samson's Chain"): norm_name("Samson's Chains"),
        norm_name('Gold Pill'): norm_name('Golden Pill'),
        norm_name('The High Priesstess'): norm_name('The High Priestess'),
    }

    unlocks=load_js(UNLOCKS,'ISAAC_UNLOCK_DATA')
    recs=load_js(RECS,'ISAAC_RECOMMENDATIONS').get('entries',{})
    entries={}
    unmatched=[]
    # Completion-mark rewards whose English names omit the crucial '?' or use a typo.
    # Values are EID card/rune IDs.
    explicit_card_ids = {
        '309': 41,  # Black Rune
        '524': 56, '525': 57, '526': 58, '527': 59, '528': 60, '529': 61,
        '530': 62, '534': 66, '535': 67, '536': 68, '537': 69, '539': 71,
        '540': 72, '541': 73, '543': 76, '544': 77,
    }
    for aid,base in unlocks['achievementCatalog'].items():
        match=merged.get(('card', explicit_card_ids[aid])) if aid in explicit_card_ids else None
        # Strongest signal: current item image embeds collectible ID.
        img=base.get('image') or ''
        m=re.search(r'collectibles_(\d+)_',img)
        if m:
            match=merged.get(('collectible',int(m.group(1))))
        names=[]
        if aid in recs: names.append(recs[aid].get('name',''))
        names.append(base.get('name',''))
        if not match:
            for name in names:
                key=norm_name(name)
                en_key=english_aliases.get(key,key)
                candidates=(by_zh.get(key,[])+by_en.get(en_key,[])) if key else []
                # Deduplicate identity tuples and prefer collectibles, then trinkets, then cards.
                uniq={(x['category'],x['id']):x for x in candidates}
                vals=list(uniq.values())
                if vals:
                    vals.sort(key=lambda x:({'collectible':0,'trinket':1,'card':2,'pill':3}.get(x['category'],9),x['id']))
                    match=vals[0]
                    break
        if not match and aid == '542':
            moon = merged.get(('card', 74))
            sun = merged.get(('card', 75))
            if moon and sun:
                entries[aid] = {
                    'name': 'XVIII-月亮？ / XIX-太阳？',
                    'effect': f"月亮？：{moon['effect']}\n太阳？：{sun['effect']}",
                    'entityType': 'card-bundle',
                    'entityId': [74,75],
                    'source': 'eid-zh_cn',
                }
                continue
        if match:
            entries[aid]={
                'name':match['zhName'],
                'effect':match['effect'],
                'entityType':match['category'],
                'entityId':match['id'],
                'source':'eid-zh_cn',
            }
        elif aid == '191':
            entries[aid]={'name':'一枚硬币','effect':'店主在每局开始时初始携带 1 枚硬币。','source':'local-special'}
        elif aid == '236':
            entries[aid]={'name':'木制硬币','effect':'店主在每局开始时初始携带主动道具「木制硬币」。','source':'local-special'}
        elif aid in recs and '[非道具]' in recs[aid].get('name',''):
            name=recs[aid]['name'].replace(' [非道具]','').replace('[非道具]','').strip()
            entries[aid]={'name':name,'effect':f'解锁「{name}」这一非收藏道具 / 机制内容。','source':'local-non-item'}
        elif base.get('effect'):
            entries[aid]={'effect':base['effect'],'source':'local-base'}
        else:
            display_name = (recs.get(aid) or {}).get('name') or base.get('name') or f'成就 #{aid}'
            if not is_baby_reward(display_name):
                entries[aid]={
                    'effect':f'解锁「{display_name}」这一非收藏道具 / 机制内容。',
                    'source':'local-non-item-fallback',
                }
            else:
                unmatched.append({'achievementId':int(aid),'name':display_name})

    payload={
        'version':1,
        'source':'https://github.com/wofsauge/External-Item-Descriptions',
        'entries':entries,
        'stats':{
            'eidRows':len(merged),
            'matchedAchievements':len(entries),
            'unmatchedAchievements':len(unmatched),
            'sourceRows':source_stats,
            'englishSourceRows':english_source_stats,
        }
    }
    OUT.write_text('// Generated by tools/crawl_effects.py\nwindow.ISAAC_EFFECTS = '+json.dumps(payload,ensure_ascii=False,indent=2)+';\n','utf-8')
    REPORT.write_text(json.dumps({'stats':payload['stats'],'unmatched':unmatched},ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(payload['stats'],ensure_ascii=False))

if __name__=='__main__':
    main()
