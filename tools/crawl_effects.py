#!/usr/bin/env python3
"""Build Chinese reward effects from EID using an English-first pipeline.

Matching order:
1. Canonical English reward name from data/unlocks.js -> EID en_us.
2. Exact (category, entity ID) -> EID zh_cn for display name/effect.
3. Only if English matching fails, try the old Chinese-name route using the
   dedicated build-time ``tools/non_eid_fallback_zh.json`` labels. This is
   deliberately last-resort and is completely independent of recommendation
   priority configuration.
4. Explicit local mechanics/character/baby fallbacks.

The generated unlock catalog itself is never used as a Chinese matching source.
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
ZH_FALLBACK = ROOT / 'tools' / 'non_eid_fallback_zh.json'

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

CATEGORY_PRIORITY = {'collectible':0, 'trinket':1, 'card':2, 'pill':3}

# English-only aliases for source typos / achievement-title wording differences.
ENGLISH_ALIASES_RAW = {
    'A Cross': 'The Relic',
    'The D20': 'D20',
    'Celctic Cross': 'Celtic Cross',
    'Blood Penny': 'Bloody Penny',
    'Abbadon': 'Abaddon',
    'The D100': 'D100',
    'Euthanesia': 'Euthanasia',
    'Temporary Tatoo': 'Temporary Tattoo',
    'Soul of Lillith': 'Soul of Lilith',
    'Locust of Wrath': 'Locust of War',
    'Sacraficial Dagger': 'Sacrificial Dagger',
    "Samson's Chain": "Samson's Chains",
    'Gold Pill': 'Golden Pill',
    'The High Priesstess': 'The High Priestess',
}

# Completion-mark rewards whose achievement title is not a safe single-name key.
EXPLICIT_ENTITY_IDS = {
    '309': ('card', 41),  # Black Rune
    '432': ('collectible', 577),  # Damocles; 656 is its hidden passive duplicate
    '524': ('card', 56), '525': ('card', 57), '526': ('card', 58),
    '527': ('card', 59), '528': ('card', 60), '529': ('card', 61),
    '530': ('card', 62), '534': ('card', 66), '535': ('card', 67),
    '536': ('card', 68), '537': ('card', 69), '539': ('card', 71),
    '540': ('card', 72), '541': ('card', 73), '543': ('card', 76),
    '544': ('card', 77),
}

MULTI_REWARD_BUNDLES = {
    '227': {
        'name':'止痛药！ / 上瘾！',
        'entityType':'pill-bundle',
        'parts':[('止痛药！','pill',28),('上瘾！','pill',29)],
    },
    '228': {
        'name':'放-松 / ？？？',
        'entityType':'pill-bundle',
        'parts':[('放-松','pill',30),('？？？','pill',31)],
    },
    '233': {
        'name':'空白符文 / 透明符文',
        'entityType':'card-collectible-bundle',
        'parts':[('空白符文','card',40),('透明符文','collectible',263)],
    },
    '542': {
        'name':'XVIII-月亮？ / XIX-太阳？',
        'entityType':'card-bundle',
        'parts':[('月亮？','card',74),('太阳？','card',75)],
    },
}

LOCAL_SPECIALS = {
    '191': {'name':'一枚硬币','effect':'店主在每局开始时初始携带 1 枚硬币。','source':'local-special'},
    '236': {'name':'木制硬币','effect':'店主在每局开始时初始携带主动道具「木制硬币」。','source':'local-special'},
    '237': {'name':'商店钥匙','effect':'店主在每局开始时初始携带「商店钥匙」。','source':'local-special'},
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
    req=Request(url, headers={'User-Agent':'isaac-unlock-planner-data-builder/3'})
    with urlopen(req, timeout=45) as r:
        b=r.read()
    path.write_bytes(b)
    return b.decode('utf-8')


def decode_lua_string(s: str) -> str:
    return s.replace('\\"','"').replace('\\\\','\\')


def clean_effect(s: str) -> str:
    s=decode_lua_string(s)
    s=re.sub(r'\{\{CR\}\}', '', s)
    s=re.sub(r'\{\{[^{}]+\}\}', '', s)
    parts=[]
    for part in s.split('#'):
        part=re.sub(r'\s+',' ',part).strip(' ；')
        if part: parts.append(part)
    return '\n'.join(parts)


def norm_name(s: str) -> str:
    """Minimal English-only key normalization.

    Do not strip Roman numerals: C/D/M etc. can be real first letters (Cry Baby,
    Dry Baby).  Chinese text is never passed to this function.
    """
    s=(s or '').lower().strip()
    s=re.sub(r'\[[^\]]*\]','',s)
    s=re.sub(r'\([^)]*\)','',s)
    s=re.sub(r'[^0-9a-z?]+','',s)
    return s


def norm_zh_name(s: str) -> str:
    """Legacy Chinese matching key, used only after English EID lookup fails."""
    s=(s or '').lower()
    s=re.sub(r'\[[^\]]*\]','',s)
    # Parenthetical English aliases are display metadata in recommendation data.
    s=re.sub(r'\([^)]*[a-z][^)]*\)','',s)
    s=s.replace('卡牌','').replace('？','?').replace('＆','&')
    s=re.sub(r'^(?:[ivxlcdm]+|0)[-—–\s]*', '', s)
    s=re.sub(r'[^0-9a-z\u4e00-\u9fff?]+','',s)
    return s


def extract_section(text: str, start: str, end: str):
    a=text.find(start)
    if a<0: return ''
    b=text.find(end,a+len(start))
    return '' if b<0 else text[a:b]


def parse_pack(kind: str, text: str, language: str='zh'):
    out=[]
    for category,(start,end) in TABLE_MARKERS[kind].items():
        section=extract_section(text,start,end)
        if not section: continue
        for bracket_id, id_field, name, desc, comment in TUPLE_RE.findall(section):
            raw_id=id_field or bracket_id
            if not raw_id: continue
            row={
                'category':category,
                'id':int(raw_id),
                'name':decode_lua_string(name),
                'effect':clean_effect(desc),
                'commentName':(comment or '').strip(),
                'pack':kind,
                'language':language,
            }
            if language=='zh':
                row['zhName']=row['name']
                row['enName']=row['commentName']
            else:
                row['enName']=row['name']
            out.append(row)
    return out


def choose(candidates):
    uniq={(x['category'],x['id']):x for x in candidates}
    vals=list(uniq.values())
    vals.sort(key=lambda x:(CATEGORY_PRIORITY.get(x['category'],9),x['id']))
    return vals[0] if vals else None


def is_baby_reward(en_name: str, zh_name: str='') -> bool:
    return 'baby' in (en_name or '').lower() or '宝宝' in (zh_name or '')


def strip_non_item_marker(name: str) -> str:
    return (name or '').replace(' [非道具]','').replace('[非道具]','').strip()


def build_bundle(spec, merged):
    lines=[]; ids=[]
    for label,category,entity_id in spec['parts']:
        row=merged.get((category,entity_id))
        if not row:
            raise RuntimeError(f'missing EID entity for bundle: {category} {entity_id}')
        lines.append(f"{label}：{row['effect']}")
        ids.append(entity_id)
    return {
        'name':spec['name'],
        'effect':'\n'.join(lines),
        'entityType':spec['entityType'],
        'entityId':ids,
        'source':'eid-zh_cn-bundle',
        'matchRoute':'explicit-bundle',
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--refresh', action='store_true', help='redownload EID language packs')
    args=ap.parse_args()

    merged={}; english_entities={}; source_stats={}; english_source_stats={}
    for kind,url in SOURCES:
        path=CACHE/f'{kind.replace("+","plus")}_zh_cn.lua'
        rows=parse_pack(kind,fetch(url,path,args.refresh),'zh')
        source_stats[kind]=len(rows)
        for row in rows: merged[(row['category'],row['id'])]=row
    for kind,url in EN_SOURCES:
        path=CACHE/f'{kind.replace("+","plus")}_en_us.lua'
        rows=parse_pack(kind,fetch(url,path,args.refresh),'en')
        english_source_stats[kind]=len(rows)
        for row in rows: english_entities[(row['category'],row['id'])]=row

    by_en={}
    for key,enrow in english_entities.items():
        zhrow=merged.get(key)
        k=norm_name(enrow.get('enName',''))
        if k and zhrow: by_en.setdefault(k,[]).append(zhrow)

    # Chinese index exists only for the last-resort branch below.
    by_zh={}
    for row in merged.values():
        k=norm_zh_name(row.get('zhName',''))
        if k: by_zh.setdefault(k,[]).append(row)

    english_aliases={norm_name(a):norm_name(b) for a,b in ENGLISH_ALIASES_RAW.items()}
    unlocks=load_js(UNLOCKS,'ISAAC_UNLOCK_DATA')
    zh_fallback=json.loads(ZH_FALLBACK.read_text('utf-8')).get('entries',{})

    entries={}; unmatched=[]; audit=[]
    counts={'english':0,'chineseFallback':0,'explicit':0,'localSpecial':0,'localFallback':0}

    for aid,base in unlocks['achievementCatalog'].items():
        en_name=base.get('name','')
        fallback_name=(zh_fallback.get(aid) or {}).get('name','')

        if aid in LOCAL_SPECIALS:
            entries[aid]=dict(LOCAL_SPECIALS[aid], matchRoute='local-special')
            counts['localSpecial']+=1
            audit.append({'achievementId':int(aid),'englishName':en_name,'route':'local-special'})
            continue

        if aid in MULTI_REWARD_BUNDLES:
            entries[aid]=build_bundle(MULTI_REWARD_BUNDLES[aid],merged)
            counts['explicit']+=1
            audit.append({'achievementId':int(aid),'englishName':en_name,'route':'explicit-bundle','entityId':entries[aid]['entityId']})
            continue

        match=None; route=None
        if aid in EXPLICIT_ENTITY_IDS:
            key=EXPLICIT_ENTITY_IDS[aid]
            match=merged.get(key)
            route='explicit-entity-id' if match else None

        # Main route: English name -> en_us entity -> same ID in zh_cn.
        if not match:
            en_key=norm_name(en_name)
            resolved_key=english_aliases.get(en_key,en_key)
            match=choose(by_en.get(resolved_key,[])) if resolved_key else None
            if match: route='english-eid'

        # Last-resort legacy route: only after English matching has failed.
        # This Chinese surface is a dedicated non-EID fallback seed, not recommendation data.
        if not match and fallback_name:
            zh_key=norm_zh_name(strip_non_item_marker(fallback_name))
            match=choose(by_zh.get(zh_key,[])) if zh_key else None
            if match: route='chinese-fallback-eid'

        if match:
            entries[aid]={
                'name':match['zhName'],
                'effect':match['effect'],
                'entityType':match['category'],
                'entityId':match['id'],
                'source':'eid-zh_cn',
                'matchRoute':route,
            }
            if route=='chinese-fallback-eid': counts['chineseFallback']+=1
            else: counts['english']+=1
            audit.append({'achievementId':int(aid),'englishName':en_name,'route':route,
                          'entityType':match['category'],'entityId':match['id'],'zhName':match['zhName']})
            continue

        # EID did not resolve an entity.  From here on this is genuinely a
        # character/starting-item/mechanic/baby-style unlock rather than an EID item.
        clean_zh=strip_non_item_marker(fallback_name)
        display_name=clean_zh or en_name or f'成就 #{aid}'
        if is_baby_reward(en_name,display_name):
            # Baby/cosmetic unlocks are deliberately not resolved through EID.
            # Keep the report aligned with the English-first catalog even when a
            # Chinese non-EID fallback label exists for UI/mechanic purposes.
            report_name = en_name or display_name
            unmatched.append({'achievementId':int(aid),'englishName':en_name,'name':report_name,'reason':'baby-or-cosmetic'})
            audit.append({'achievementId':int(aid),'englishName':en_name,'route':'unmatched-baby','name':report_name})
        else:
            entries[aid]={
                'name':display_name,
                'effect':f'解锁「{display_name}」这一非收藏道具 / 机制内容。',
                'source':'local-non-item-fallback',
                'matchRoute':'local-generic-fallback',
            }
            counts['localFallback']+=1
            audit.append({'achievementId':int(aid),'englishName':en_name,'route':'local-generic-fallback','name':display_name})

    # Challenge-only multi-reward achievement IDs are not in the completion-mark catalog.
    for aid in ('227','228','233'):
        entries[aid]=build_bundle(MULTI_REWARD_BUNDLES[aid],merged)
        counts['explicit']+=1
        audit.append({'achievementId':int(aid),'route':'explicit-bundle-challenge','entityId':entries[aid]['entityId']})

    catalog_ids=set(unlocks['achievementCatalog'])
    payload={
        'version':2,
        'source':'https://github.com/wofsauge/External-Item-Descriptions',
        'pipeline':'english-first-id-to-zh; dedicated-non-eid-zh-fallback-only-after-english-miss',
        'entries':entries,
        'stats':{
            'eidRows':len(merged),
            'matchedAchievements':sum(1 for aid in catalog_ids if aid in entries),
            'unmatchedAchievements':len(unmatched),
            'specialAchievementEntries':sum(1 for aid in entries if aid not in catalog_ids),
            'routes':counts,
            'sourceRows':source_stats,
            'englishSourceRows':english_source_stats,
        }
    }
    OUT.write_text('// Generated by tools/crawl_effects.py\nwindow.ISAAC_EFFECTS = '+json.dumps(payload,ensure_ascii=False,indent=2)+';\n','utf-8')
    REPORT.write_text(json.dumps({'stats':payload['stats'],'unmatched':unmatched,'audit':audit},ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(payload['stats'],ensure_ascii=False))

if __name__=='__main__':
    main()
