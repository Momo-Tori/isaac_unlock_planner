#!/usr/bin/env python3
"""Build the four curated achievement lists from a saved Huiji Wiki page."""
from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from crawl_effects import CACHE, SOURCES, fetch, parse_pack


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "achievements.js"
DEFAULT_CATALOG = ROOT / "tools" / "achievement_index.json"


class AchievementTableParser(HTMLParser):
    """Collect table rows while retaining cell line breaks and links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: dict[int, list[dict[str, object]]] = {}
        self.in_row = False
        self.in_cell = False
        self.cells: list[dict[str, object]] = []
        self.cell: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "tr" and not self.in_row:
            self.in_row = True
            self.cells = []
        elif self.in_row and tag in {"td", "th"} and not self.in_cell:
            self.in_cell = True
            self.cell = {"text": [], "links": []}
        elif self.in_cell:
            if tag == "br" and self.cell is not None:
                self.cell["text"].append("\n")
            if tag == "a" and self.cell is not None and attrs_dict.get("href"):
                self.cell["links"].append(attrs_dict["href"])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.in_cell and tag == "br" and self.cell is not None:
            self.cell["text"].append("\n")

    def handle_data(self, data: str) -> None:
        if self.in_cell and self.cell is not None:
            self.cell["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_cell and tag in {"td", "th"} and self.cell is not None:
            self.cell["text"] = clean_lines("".join(self.cell["text"]))
            self.cells.append(self.cell)
            self.cell = None
            self.in_cell = False
            return
        if tag == "tr" and self.in_row:
            self.in_row = False
            if len(self.cells) >= 6 and str(self.cells[0]["text"]).isdigit():
                self.rows[int(str(self.cells[0]["text"]))] = self.cells


def clean_lines(value: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    result: list[str] = []
    for line in lines:
        if line and (not result or result[-1] != line):
            result.append(line)
    return "\n".join(result)


def first_line(value: object) -> str:
    return str(value).split("\n", 1)[0].strip()


def parse_catalog(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text("utf-8"))
    cumulative: list[tuple[int, int | None]] = []
    for sequence_group, ids in enumerate(raw["cumulativeGroups"], start=1):
        cumulative.extend((int(achievement_id), sequence_group) for achievement_id in ids)
    cumulative.extend((int(achievement_id), None) for achievement_id in raw["cumulativeSingles"])

    return {
        "main": [int(achievement_id) for achievement_id in raw["main"]],
        "mainEdges": [[int(from_id), int(to_id)] for from_id, to_id in raw["mainEdges"]],
        "normalCharacters": [int(achievement_id) for achievement_id in raw["characters"]["normal"]],
        "taintedCharacters": [int(achievement_id) for achievement_id in raw["characters"]["tainted"]],
        "cumulative": cumulative,
        "completion": [int(achievement_id) for achievement_id in raw["completion"]],
    }


def load_eid_entities(refresh: bool) -> dict[tuple[str, int], dict[str, object]]:
    merged: dict[tuple[str, int], dict[str, object]] = {}
    for kind, url in SOURCES:
        cache_path = CACHE / f'{kind.replace("+", "plus")}_zh_cn.lua'
        for row in parse_pack(kind, fetch(url, cache_path, refresh), "zh"):
            merged[(str(row["category"]), int(row["id"]))] = row
    return merged


def parse_rows(path: Path) -> dict[int, list[dict[str, object]]]:
    parser = AchievementTableParser()
    parser.feed(path.read_text("utf-8", errors="ignore"))
    return parser.rows


def make_entry(
    achievement_id: int,
    rows: dict[int, list[dict[str, object]]],
    eid_entities: dict[tuple[str, int], dict[str, object]],
    sequence_group: int | None = None,
) -> dict[str, object]:
    if achievement_id not in rows:
        raise RuntimeError(f"Wiki HTML is missing achievement #{achievement_id}")
    cells = rows[achievement_id]
    reward_cell = cells[5]
    prefix_types = {"C": "collectible", "T": "trinket", "K": "card", "P": "pill"}
    reward_entities: list[dict[str, object]] = []
    seen_entities: set[tuple[str, int]] = set()
    for href in reward_cell["links"]:
        match = re.search(r"/([CTKP])(\d+)(?:$|[?#])", str(href))
        if not match:
            continue
        prefix, raw_id = match.groups()
        entity_id = int(raw_id)
        key = (prefix_types[prefix], entity_id)
        if key in seen_entities:
            continue
        seen_entities.add(key)
        reward_entities.append({"prefix": prefix, "entityType": key[0], "entityId": entity_id})

    missing = [
        f'{entity["prefix"]}{entity["entityId"]}'
        for entity in reward_entities
        if (str(entity["entityType"]), int(entity["entityId"])) not in eid_entities
    ]
    if missing:
        raise RuntimeError(f'Achievement #{achievement_id} has EID entities that could not be resolved: {missing}')

    eid_rows = [
        eid_entities[(str(entity["entityType"]), int(entity["entityId"]))]
        for entity in reward_entities
    ]
    reward_name = " / ".join(str(row["zhName"]) for row in eid_rows) or first_line(reward_cell["text"])
    reward_effect = "\n".join(
        f'{row["zhName"]}：{row["effect"]}' if len(eid_rows) > 1 else str(row["effect"])
        for row in eid_rows
    )
    return {
        "achievementId": achievement_id,
        "name": first_line(cells[1]["text"]),
        "condition": str(cells[4]["text"]).replace("\n", " "),
        "rewardName": reward_name,
        "rewardEffect": reward_effect,
        "rewardEntities": reward_entities,
        "collectibleIds": [
            int(entity["entityId"])
            for entity in reward_entities
            if entity["entityType"] == "collectible"
        ],
        "sequenceGroup": sequence_group,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path, help="saved Huiji Wiki achievement page")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help="achievement category index JSON, defaults to tools/achievement_index.json",
    )
    parser.add_argument("--refresh-eid", action="store_true")
    args = parser.parse_args()

    catalog = parse_catalog(args.catalog)
    rows = parse_rows(args.html)
    eid_entities = load_eid_entities(args.refresh_eid)

    def entries(ids: list[int]) -> list[dict[str, object]]:
        return [make_entry(achievement_id, rows, eid_entities) for achievement_id in ids]

    payload = {
        "version": 1,
        "source": "https://isaac.huijiwiki.com/wiki/成就",
        "main": entries(catalog["main"]),
        "mainEdges": catalog["mainEdges"],
        "characters": {
            "normal": entries(catalog["normalCharacters"]),
            "tainted": entries(catalog["taintedCharacters"]),
        },
        "cumulative": [
            make_entry(achievement_id, rows, eid_entities, sequence_group)
            for achievement_id, sequence_group in catalog["cumulative"]
        ],
        "completion": entries(catalog["completion"]),
    }
    OUT.write_text(
        "// Generated by tools/build_achievements.py\nwindow.ISAAC_ACHIEVEMENT_DATA = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n",
        "utf-8",
    )

    all_entries = payload["main"] + payload["characters"]["normal"] + payload["characters"]["tainted"] + payload["cumulative"] + payload["completion"]
    entity_counts = {
        prefix: sum(any(entity["prefix"] == prefix for entity in entry["rewardEntities"]) for entry in all_entries)
        for prefix in ("C", "T", "K", "P")
    }
    item_rewards = sum(bool(entry["rewardEntities"]) for entry in all_entries)
    item_effects = sum(bool(entry["rewardEffect"]) for entry in all_entries)
    print(json.dumps({"achievements": len(all_entries), "entityRewards": item_rewards, "itemEffects": item_effects, "entityTypes": entity_counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
