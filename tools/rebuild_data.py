#!/usr/bin/env python3
"""Cleanly rebuild generated game data and browser-loadable recommendation profiles."""
from __future__ import annotations
from pathlib import Path
import argparse, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'tools'


def run(*args):
    print('+', ' '.join(map(str,args)))
    subprocess.run([sys.executable, *map(str,args)], cwd=ROOT, check=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('html', type=Path, help='saved Huiji Project:存档/成就 HTML')
    ap.add_argument(
        '--achievements-html',
        type=Path,
        help='saved Huiji 成就 page HTML; when provided, rebuilds data/achievements.js',
    )
    ap.add_argument('--refresh-eid', action='store_true', help='redownload EID language packs')
    args=ap.parse_args()

    # Generated products only. Runtime priority JSON and source seeds are never deleted.
    generated = ['data/unlocks.js','data/challenges.js','data/effects.js','data/effects-report.json','data/recommendation_profiles.js']
    if args.achievements_html:
        generated.append('data/achievements.js')
    for rel in generated:
        p=ROOT/rel
        if p.exists():
            p.unlink()
            print(f'deleted {rel}')

    run(TOOLS/'build_unlocks.py', args.html)
    run(TOOLS/'build_challenges.py', args.html)
    effect_args=[TOOLS/'crawl_effects.py']
    if args.refresh_eid: effect_args.append('--refresh')
    run(*effect_args)
    if args.achievements_html:
        run(TOOLS/'build_achievements.py', args.achievements_html)
    run(TOOLS/'validate_priorities.py')
    run(TOOLS/'build_recommendation_profiles.py')
    if not args.achievements_html:
        print('skipped data/achievements.js; pass --achievements-html with the saved Huiji 成就 page to rebuild it')
    print('clean rebuild complete; tools/*.json remain the editable recommendation sources')

if __name__=='__main__': main()
