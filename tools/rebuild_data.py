#!/usr/bin/env python3
"""Cleanly rebuild generated data while keeping priority as runtime JSON config."""
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
    ap.add_argument('--refresh-eid', action='store_true', help='redownload EID language packs')
    args=ap.parse_args()

    # Generated products only. Runtime priority JSON and source seeds are never deleted.
    for rel in ('data/unlocks.js','data/challenges.js','data/effects.js','data/effects-report.json'):
        p=ROOT/rel
        if p.exists():
            p.unlink()
            print(f'deleted {rel}')

    run(TOOLS/'build_unlocks.py', args.html)
    run(TOOLS/'build_challenges.py', args.html)
    effect_args=[TOOLS/'crawl_effects.py']
    if args.refresh_eid: effect_args.append('--refresh')
    run(*effect_args)
    run(TOOLS/'validate_priorities.py')
    print('clean rebuild complete; runtime priority stays in tools/*.json')

if __name__=='__main__': main()
