#!/usr/bin/env python3
"""Refresh challenge prerequisite/reward achievement IDs from a saved Huiji Wiki page.

The human-curated challenge priority and reward metadata already in data/challenges.js
are preserved; this script only refreshes the challenge -> prerequisite/reward achievement
mapping from Project:存档/成就.
"""
from __future__ import annotations
from pathlib import Path
import argparse, json, re
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'challenges.js'


def load_current():
    text = OUT.read_text('utf-8')
    m = re.search(r'window\.ISAAC_CHALLENGE_DATA\s*=\s*(\{.*\});\s*$', text, re.S)
    if not m:
        raise RuntimeError(f'cannot parse {OUT}')
    return json.loads(m.group(1))


def extract_mapping(html_path: Path):
    soup = BeautifulSoup(html_path.read_text('utf-8', errors='ignore'), 'html.parser')
    table = soup.find('table', id='mw-customcollapsible-navchallengeachi')
    if table is None:
        raise RuntimeError('challenge achievement table not found')
    rows = table.find_all('tr')
    blocks = [(1, range(1,11)), (3, range(11,21)), (5, range(21,31)), (7, range(31,36)), (9, range(36,46))]
    mapping = {}
    for body_index, ids in blocks:
        cells = rows[body_index].find_all('td')
        for cid, cell in zip(ids, cells):
            aids=[]
            for a in cell.find_all('a', href=True):
                m = re.search(r'(?:%E6%88%90%E5%B0%B1|成就)/(\d+)', a['href'])
                if m:
                    aids.append(int(m.group(1)))
            if not aids:
                raise RuntimeError(f'challenge #{cid} has no achievement link')
            mapping[cid] = (None, aids[0]) if len(aids) == 1 else (aids[0], aids[-1])
    return mapping


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html', type=Path, help='saved Project:存档/成就 HTML file')
    args = ap.parse_args()
    data = load_current()
    mapping = extract_mapping(args.html)
    for entry in data['entries']:
        pre, reward = mapping[entry['challengeId']]
        entry['prerequisiteAchievementId'] = pre
        entry['rewardAchievementId'] = reward
    OUT.write_text('// Challenge unlock data for the planner.\nwindow.ISAAC_CHALLENGE_DATA = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';\n', 'utf-8')
    print(f'updated {len(data["entries"])} challenges -> {OUT}')

if __name__ == '__main__':
    main()
