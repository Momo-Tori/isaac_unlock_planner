#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
UNLOCKS = ROOT / 'data' / 'unlocks.js'
SOURCE = ROOT / 'tools' / 'recommendation_seed.json'
OUT_JS = ROOT / 'data' / 'recommendations.js'
OUT_REPORT = ROOT / 'data' / 'recommendations-report.json'


# Priority corrections supplied for the current recommendation source revision.
# Entries promoted from implicit normal are created automatically below.
PRIORITY_OVERRIDES_BY_ACHIEVEMENT = {
    '186': ('strong', '虚空之喉'),
    '133': ('strong', '一百面骰'),
    '185': ('normal', '盲目的怒火'),
    '56': ('recommended', '血之权利'),
    '130': ('strong', '思想'),
    '49': ('strong', '二十面骰'),
    '239': ('strong', '业报'),
    '217': ('normal', '上吊绳宝宝'),
    '291': ('strong', '复杂性骨折'),
    '462': ('normal', '嗜血小宠'),
    '441': ('strong', '选择？'),
    '453': ('recommended', '空虚之心'),
    '455': ('recommended', '亚巴顿宝宝'),
    '467': ('strong', '触手朋友'),
    '203': ('recommended', '朋友盒'),
    '316': ('normal', '棕色粪块'),
    '309': ('recommended', '黑符文'),
    '621': ('normal', '犹大的魂石'),
    '624': ('recommended', '参孙的魂石'),
    '626': ('recommended', '拉撒路的魂石'),
    '634': ('recommended', '雅各与以扫的魂石'),
    '558': ('recommended', '奇怪的钥匙'),
    '568': ('normal', '儿童涂鸦'),
    '586': ('strong', '合成宝袋'),
    '590': ('recommended', '狂怒！'),
    '595': ('strong', '格罗'),
    '563': ('recommended', '阿撒泻勒的残角'),
    '506': ('recommended', '复仇之魂'),
    '507': ('strong', '小以扫'),
    '541': ('strong', 'XVII-星星？'),
    '535': ('recommended', 'XI-力量？'),
    '543': ('strong', 'XX-审判？'),
    '544': ('strong', 'XXI-世界？'),
    '542': ('strong', 'XVIII-月亮？ / XIX-太阳？'),
}

CONDITION_TO_BOSSES = {
    '妈妈的心': ['moms-heart'],
    '困难妈心': ['moms-heart'],
    '头目车轮战': ['boss-rush'],
    '死寂': ['hush'],
    '以撒': ['isaac-boss'],
    '撒旦': ['satan'],
    '???': ['blue-baby'],
    '羔羊': ['lamb'],
    '超级撒旦': ['mega-satan'],
    '精神错乱': ['delirium'],
    '母亲': ['mother'],
    '祸兽': ['beast'],
    '普通贪婪': ['greed'],
    '困难贪婪': ['greedier'],
    '头目/死寂': ['boss-rush', 'hush'],
    '以撒/撒旦/???/羔羊': ['isaac-boss', 'satan', 'blue-baby', 'lamb'],
}

def load_js_object(path: Path, varname: str):
    s = path.read_text('utf-8')
    m = re.search(rf'window\.{re.escape(varname)}\s*=\s*(\{{.*\}});\s*$', s, re.S)
    if not m:
        raise RuntimeError(f'cannot parse {path}')
    return json.loads(m.group(1))

def main():
    data = load_js_object(UNLOCKS, 'ISAAC_UNLOCK_DATA')
    source = json.loads(SOURCE.read_text('utf-8'))
    by_char = {}
    for rule in data['unlockRules']:
        by_char.setdefault(rule['characterId'], []).append(rule)

    entries, unmatched = {}, []
    matched_source = 0
    for group in ('normal', 'tainted'):
        for char_group in source[group]:
            ci = char_group['characterIndex']
            char = data['characters'][ci]
            rules = by_char.get(char['id'], [])
            for item in char_group['items']:
                expected = CONDITION_TO_BOSSES.get(item['condition'])
                if not expected:
                    unmatched.append({**item, 'character': char['name'], 'reason': 'condition-not-in-current-boss-model'})
                    continue
                expected_set = set(expected)
                candidates = [r for r in rules if set(r['bossIds']) == expected_set]
                if not candidates and len(expected) == 1:
                    candidates = [r for r in rules if expected[0] in r['bossIds'] and len(r['bossIds']) == 1]
                if len(candidates) != 1:
                    unmatched.append({**item, 'character': char['name'], 'expectedBossIds': expected, 'reason': f'match-count-{len(candidates)}'})
                    continue
                r = candidates[0]
                aid = str(r['achievementId'])
                entries[aid] = {
                    'priority': item['priority'],
                    'name': item['rewardName'],
                    'source': 'bilibili-opus-1083165871339208713',
                    'conditionSource': item['condition'],
                    'characterId': char['id'],
                    'bossIds': r['bossIds'],
                }
                matched_source += 1

    rules_by_aid = {str(r['achievementId']): r for r in data['unlockRules']}
    for aid, (priority, display_name) in PRIORITY_OVERRIDES_BY_ACHIEVEMENT.items():
        rule = rules_by_aid.get(aid)
        if not rule:
            raise RuntimeError(f'priority override achievement not found: {aid}')
        if aid not in entries:
            entries[aid] = {
                'priority': priority,
                'name': display_name or data['achievementCatalog'].get(aid, {}).get('name') or f'成就 #{aid}',
                'source': 'bilibili-opus-1083165871339208713',
                'conditionSource': 'manual-source-revision',
                'characterId': rule['characterId'],
                'bossIds': rule['bossIds'],
            }
        else:
            entries[aid]['priority'] = priority
            entries[aid]['name'] = display_name or entries[aid].get('name')
            entries[aid]['source'] = 'bilibili-opus-1083165871339208713'

    payload = {
        'version': 1,
        'source': source['source'],
        'retrieved': source['retrieved'],
        'entries': entries,
        'stats': {
            'matched': len(entries),
            'strong': sum(v['priority']=='strong' for v in entries.values()),
            'recommended': sum(v['priority']=='recommended' for v in entries.values()),
            'unmatched': len(unmatched),
        }
    }
    OUT_JS.write_text('// Generated by tools/build_recommendations.py\nwindow.ISAAC_RECOMMENDATIONS = ' + json.dumps(payload, ensure_ascii=False, indent=2) + ';\n', 'utf-8')
    OUT_REPORT.write_text(json.dumps({'stats':payload['stats'],'unmatched':unmatched}, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps(payload['stats'], ensure_ascii=False))
    for x in unmatched:
        print('UNMATCHED', x)

if __name__ == '__main__':
    main()
