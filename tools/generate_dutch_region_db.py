#!/usr/bin/env python3
"""Generate the Dutch region lookup database from the MeshWiki HTML page."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen


SOURCE_URL = "https://meshwiki.nl/wiki/Lijst_van_regio%27s"
PROVINCES = [
    ("gr", "Groningen"),
    ("fr", "Friesland"),
    ("dr", "Drenthe"),
    ("ov", "Overijssel"),
    ("fl", "Flevoland"),
    ("ge", "Gelderland"),
    ("ut", "Utrecht"),
    ("nh", "Noord-Holland"),
    ("zh", "Zuid-Holland"),
    ("ze", "Zeeland"),
    ("nb", "Noord-Brabant"),
    ("li", "Limburg"),
]


@dataclass
class WikiEntry:
    name: str
    province_id: int
    codes: list[str]


class RegionPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current_province = ""
        self.in_h3 = False
        self.heading = []
        self.in_tr = False
        self.in_td = False
        self.cell = []
        self.cells = []
        self.rows: list[tuple[str, list[str]]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "h3":
            self.in_h3 = True
            self.heading = []
        elif tag == "tr":
            self.in_tr = True
            self.cells = []
        elif tag in ("td", "th") and self.in_tr:
            self.in_td = True
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.in_h3:
            self.heading.append(data)
        if self.in_td:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3" and self.in_h3:
            name = " ".join("".join(self.heading).split())
            if name in {p[1] for p in PROVINCES}:
                self.current_province = name
            self.in_h3 = False
        elif tag in ("td", "th") and self.in_td:
            self.cells.append(" ".join("".join(self.cell).split()))
            self.in_td = False
        elif tag == "tr" and self.in_tr:
            if self.current_province and len(self.cells) >= 12 and self.cells[0] != "Plaats":
                self.rows.append((self.current_province, self.cells[:12]))
            self.in_tr = False


def cpp_string(value: str) -> str:
    out = []
    for ch in value:
        code = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\0":
            out.append("\\0")
        elif 32 <= code <= 126:
            out.append(ch)
        else:
            out.extend(f"\\x{b:02X}" for b in ch.encode("utf-8"))
    return "".join(out)


def write_byte_array(f, name: str, value: str) -> None:
    data = value.encode("utf-8")
    f.write(f"const uint8_t {name}[] PROGMEM = {{\n")
    for i in range(0, len(data), 16):
        f.write("  " + ", ".join(f"0x{b:02X}" for b in data[i : i + 16]) + ",\n")
    f.write("};\n\n")


def make_pool(values: list[str]) -> tuple[str, dict[str, int]]:
    chunks = []
    offsets = {}
    offset = 0
    for value in values:
        if value in offsets:
            continue
        offsets[value] = offset
        encoded = value.encode("utf-8") + b"\0"
        chunks.append(value)
        offset += len(encoded)
    return "\0".join(chunks) + "\0", offsets


def parse_entries(page: str) -> tuple[list[WikiEntry], int, str]:
    parser = RegionPageParser()
    parser.feed(page)

    province_ids = {name: i + 1 for i, (_, name) in enumerate(PROVINCES)}
    entries = []
    for province, cells in parser.rows:
        codes = []
        for code in cells[6:12]:
            if code and code not in codes:
                codes.append(code)
        entries.append(WikiEntry(cells[0], province_ids[province], codes))

    rev = 0
    match = re.search(r'"wgRevisionId":(\d+)', page)
    if match:
        rev = int(match.group(1))

    modified = ""
    match = re.search(r'"dateModified":"([^"]+)"', page)
    if match:
        modified = match.group(1).replace("\\/", "/")

    return entries, rev, modified


def write_generated(entries: list[WikiEntry], rev: int, modified: str, out_dir: Path) -> None:
    code_values: list[str] = []
    code_ids: dict[str, int] = {}
    extra_ids: list[int] = []
    rendered_entries = []

    def intern_code(code: str) -> int:
        found = code_ids.get(code)
        if found is not None:
            return found
        code_ids[code] = len(code_values) + 1
        code_values.append(code)
        return code_ids[code]

    for entry in entries:
        code_list = [intern_code(code) for code in entry.codes]
        extra_offset = len(extra_ids)
        extra_count = max(0, len(code_list) - 1)
        extra_ids.extend(code_list[1:])
        rendered_entries.append((entry.name, entry.province_id, code_list[0] if code_list else 0, extra_offset, extra_count))

    name_pool, name_offsets = make_pool([entry.name for entry in entries])
    code_pool, code_offsets = make_pool(code_values)

    header = out_dir / "DutchRegionDb.Generated.h"
    source = out_dir / "DutchRegionDb.Generated.cpp"

    header.write_text(
        """#pragma once

#include <Arduino.h>
#include "DutchRegionDb.h"

namespace DutchRegionDbData {

extern const uint8_t kNamePool[] PROGMEM;
extern const uint8_t kCodePool[] PROGMEM;
extern const DutchRegionDbProvince kProvinces[] PROGMEM;
extern const DutchRegionDbCode kCodes[] PROGMEM;
extern const DutchRegionDbEntry kEntries[] PROGMEM;
extern const uint16_t kExtraRegionCodes[] PROGMEM;

constexpr uint16_t kSourceRevision = %d;
constexpr char kSourceModified[] = "%s";
constexpr uint16_t kProvinceCount = %d;
constexpr uint16_t kCodeCount = %d;
constexpr uint16_t kEntryCount = %d;
constexpr uint16_t kExtraRegionCodeCount = %d;
constexpr uint16_t kNamePoolSize = %d;
constexpr uint16_t kCodePoolSize = %d;

}  // namespace DutchRegionDbData
"""
        % (
            rev,
            cpp_string(modified),
            len(PROVINCES),
            len(code_values),
            len(entries),
            len(extra_ids),
            len(name_pool.encode("utf-8")),
            len(code_pool.encode("utf-8")),
        ),
        encoding="utf-8",
    )

    with source.open("w", encoding="utf-8") as f:
        f.write("""#include "DutchRegionDb.Generated.h"

namespace DutchRegionDbData {

""")
        write_byte_array(f, "kNamePool", name_pool)
        write_byte_array(f, "kCodePool", code_pool)
        f.write("const DutchRegionDbProvince kProvinces[] PROGMEM = {\n")
        for i, (abbr, name) in enumerate(PROVINCES, start=1):
            f.write(f'  {{ {i}, "{cpp_string(abbr)}", "{cpp_string(name)}" }},\n')
        f.write("};\n\nconst DutchRegionDbCode kCodes[] PROGMEM = {\n")
        for i, code in enumerate(code_values, start=1):
            f.write(f"  {{ {i}, {code_offsets[code]} }},\n")
        f.write("};\n\nconst DutchRegionDbEntry kEntries[] PROGMEM = {\n")
        for name, province_id, primary, extra_offset, extra_count in rendered_entries:
            f.write(f"  {{ {name_offsets[name]}, {province_id}, {primary}, {extra_offset}, {extra_count} }},\n")
        f.write("};\n\nconst uint16_t kExtraRegionCodes[] PROGMEM = {\n")
        for i in range(0, len(extra_ids), 16):
            f.write("  " + ", ".join(str(v) for v in extra_ids[i : i + 16]) + ",\n")
        f.write("};\n\n}  // namespace DutchRegionDbData\n")

    manifest = {
        "source_url": SOURCE_URL,
        "source_revision": rev,
        "source_modified": modified,
        "entry_count": len(entries),
        "province_count": len(PROVINCES),
        "code_count": len(code_values),
        "extra_region_code_count": len(extra_ids),
        "name_pool_bytes": len(name_pool.encode("utf-8")),
        "code_pool_bytes": len(code_pool.encode("utf-8")),
    }
    (out_dir / "DutchRegionDb.Generated.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, help="Use an already downloaded MeshWiki HTML page")
    parser.add_argument("--out-dir", type=Path, default=Path("src/helpers"))
    args = parser.parse_args()

    if args.html:
        page = args.html.read_text(encoding="utf-8")
    else:
        with urlopen(SOURCE_URL, timeout=30) as response:
            page = response.read().decode("utf-8")

    entries, rev, modified = parse_entries(page)
    expected = sum([197, 413, 225, 178, 19, 330, 104, 238, 184, 126, 279, 191])
    if len(entries) != expected:
        raise SystemExit(f"expected {expected} location entries, parsed {len(entries)}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_generated(entries, rev, modified, args.out_dir)


if __name__ == "__main__":
    main()
