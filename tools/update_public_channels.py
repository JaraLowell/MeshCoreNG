#!/usr/bin/env python3
"""
Fetch public MeshCore channel links from MeshWiki and write a JSON key file for
tools/tcp_bridge_server.py --public-channels-file.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen


DEFAULT_URL = "https://meshwiki.nl/wiki/Publieke_kanalen"
DEFAULT_OUTPUT = "tools/public_channels.json"


def extract_channels(page: str) -> list[dict]:
    page = html.unescape(page)
    channels: dict[tuple[str, str], dict] = {}
    for raw_url in re.findall(r"meshcore://channel/add\?[^\"'<>\s]+", page):
        parsed = urlsplit(raw_url)
        query = parse_qs(parsed.query)
        name = (query.get("name") or [""])[0].strip()
        secret = (query.get("secret") or [""])[0].strip().lower()
        if not name or not secret:
            continue
        if not re.fullmatch(r"[0-9a-f]{32}|[0-9a-f]{64}", secret):
            continue
        channels[(name.lower(), secret)] = {
            "name": name,
            "secret": secret,
            "source": raw_url,
        }
    return sorted(channels.values(), key=lambda item: item["name"].lower())


def main() -> int:
    parser = argparse.ArgumentParser(description="Build public MeshCore channel key JSON from MeshWiki")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Source wiki URL (default: {DEFAULT_URL})")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Output JSON path (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    with urlopen(args.url, timeout=20) as response:
        page = response.read().decode("utf-8", errors="replace")

    channels = extract_channels(page)
    output = {
        "source": args.url,
        "channels": channels,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(channels)} channel(s) to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
