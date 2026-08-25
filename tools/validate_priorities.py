#!/usr/bin/env python3
"""Validate runtime priority JSON against generated unlock/challenge data.

This script writes no runtime data. Priority JSON files are the editable source
of truth; build_recommendation_profiles.py compiles them for the browser.
"""
from __future__ import annotations
from pathlib import Path
import json,re

ROOT=Path(__file__).resolve().parents[1]
UNLOCKS=ROOT/'data'/'unlocks.js'
CHALLENGES=ROOT/'data'/'challenges.js'
RECOMMEND=ROOT/'tools'/'recommendation_seed.json'
CHALLENGE_PRIORITY=ROOT/'tools'/'challenge_priority.json'
ALLOWED={'normal','recommended','strong','discouraged'}


def load_js(path:Path,var:str):
    text=path.read_text('utf-8')
    m=re.search(rf'window\.{re.escape(var)}\s*=\s*(\{{.*\}});\s*$',text,re.S)
    if not m: raise RuntimeError(f'cannot parse {path}')
    return json.loads(m.group(1))


def main():
    unlocks=load_js(UNLOCKS,'ISAAC_UNLOCK_DATA')
    challenges=load_js(CHALLENGES,'ISAAC_CHALLENGE_DATA')
    rec=json.loads(RECOMMEND.read_text('utf-8'))
    cp=json.loads(CHALLENGE_PRIORITY.read_text('utf-8'))

    char_ids={x['id'] for x in unlocks['characters']}
    boss_ids={x['id'] for x in unlocks['bosses']}
    valid_pairs={(r['characterId'],b) for r in unlocks['unlockRules'] for b in r['bossIds']}
    pair_priority={}
    for i,x in enumerate(rec.get('entries',[])):
        if set(x)!={'characterId','bossId','priority'}:
            raise RuntimeError(f'recommendation entry #{i} must contain only characterId/bossId/priority: {x}')
        c,b,p=x['characterId'],x['bossId'],x['priority']
        if c not in char_ids: raise RuntimeError(f'unknown characterId: {c}')
        if b not in boss_ids: raise RuntimeError(f'unknown bossId: {b}')
        if p not in ALLOWED: raise RuntimeError(f'invalid priority: {p}')
        if (c,b) not in valid_pairs: raise RuntimeError(f'priority pair has no unlock rule: {c}/{b}')
        if (c,b) in pair_priority: raise RuntimeError(f'duplicate priority pair: {c}/{b}')
        pair_priority[(c,b)]=p

    # Bundled tainted-character rewards must render with one consistent priority
    # no matter which constituent Boss page is open.
    for r in unlocks['unlockRules']:
        if len(r['bossIds']) <= 1: continue
        vals=[pair_priority.get((r['characterId'],b),'normal') for b in r['bossIds']]
        if len(set(vals)) != 1:
            raise RuntimeError(f'inconsistent bundled priority for {r["id"]}: {dict(zip(r["bossIds"],vals))}')

    challenge_ids={x['challengeId'] for x in challenges['entries']}
    seen=set()
    for i,x in enumerate(cp.get('entries',[])):
        if set(x)!={'challengeId','priority'}:
            raise RuntimeError(f'challenge priority entry #{i} must contain only challengeId/priority: {x}')
        cid,p=x['challengeId'],x['priority']
        if cid not in challenge_ids: raise RuntimeError(f'unknown challengeId: {cid}')
        if cid in seen: raise RuntimeError(f'duplicate challengeId: {cid}')
        if p not in ALLOWED: raise RuntimeError(f'invalid challenge priority: {p}')
        seen.add(cid)
    if seen != challenge_ids:
        raise RuntimeError(f'challenge priority JSON must cover all challenges; missing={sorted(challenge_ids-seen)}')

    def rule_priority(rule):
        vals=[pair_priority.get((rule['characterId'],b),'normal') for b in rule['bossIds']]
        return max(vals, key=lambda x:{'discouraged':0,'normal':1,'recommended':2,'strong':3}[x])

    rule_priorities=[rule_priority(r) for r in unlocks['unlockRules']]
    stats={
        'recommendationPairs':len(pair_priority),
        'pairStrong':sum(v=='strong' for v in pair_priority.values()),
        'pairRecommended':sum(v=='recommended' for v in pair_priority.values()),
        'pairDiscouraged':sum(v=='discouraged' for v in pair_priority.values()),
        'ruleStrong':sum(v=='strong' for v in rule_priorities),
        'ruleRecommended':sum(v=='recommended' for v in rule_priorities),
        'ruleNormal':sum(v=='normal' for v in rule_priorities),
        'ruleDiscouraged':sum(v=='discouraged' for v in rule_priorities),
        'challenges':len(seen),
        'challengeStrong':sum(x['priority']=='strong' for x in cp['entries']),
        'challengeRecommended':sum(x['priority']=='recommended' for x in cp['entries']),
        'challengeDiscouraged':sum(x['priority']=='discouraged' for x in cp['entries']),
    }
    print(json.dumps(stats,ensure_ascii=False))

if __name__=='__main__': main()
