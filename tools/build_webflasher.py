#!/usr/bin/env python3
"""
Build the MeshCoreNG web flasher firmware index.

Searches ALL GitHub releases for firmware assets and matches them to the
boards listed in website/public/flasher/boards.json. Boards without a matching
release asset are silently skipped (firmware not yet released).

Writes a lightweight boards.json to website/.vitepress/dist/flasher/. Firmware
files stay on GitHub Releases and are fetched by the browser only when selected.
Run this script AFTER 'vitepress build'.
"""
import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBFLASHER_SRC  = ROOT / "website" / "public" / "flasher"
BOARDS_FILE     = WEBFLASHER_SRC / "boards.json"
SITE_FLASHER    = ROOT / "website" / ".vitepress" / "dist" / "flasher"
LEGACY_FIRMWARE_DIR = SITE_FLASHER / "firmware"


def load_boards():
    with BOARDS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def github_request(url, token=None, accept="application/vnd.github+json"):
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MeshCoreNG-WebFlasher",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def load_all_release_assets(repo, token):
    """Return a list of release asset metadata across ALL releases."""
    assets = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}"
        try:
            releases = json.loads(github_request(url, token).decode("utf-8"))
        except Exception as e:
            print(f"Warning: could not fetch releases page {page}: {e}", file=sys.stderr)
            break
        if not releases:
            break
        for release in releases:
            if release.get("draft"):
                continue
            for asset in release.get("assets", []):
                name = asset.get("name", "")
                item = dict(asset)
                item["release_tag"] = release.get("tag_name", "")
                item["release_name"] = release.get("name", "")
                item["release_prerelease"] = bool(release.get("prerelease"))
                item["release_published_at"] = release.get("published_at") or asset.get("updated_at", "")
                assets.append(item)
        page += 1
    print(f"Collected {len(assets)} release assets total.", file=sys.stderr)
    return assets


def get_device_type(board):
    family = board.get("chipFamily", "").lower()
    if family.startswith("esp32"):
        return "esp32"
    if family == "nrf52" or "nrf528" in family:
        return "nrf52"
    return "download"


def find_assets_for_board(all_assets, board):
    """Find release assets matching the board, newest first."""
    env_name = board["env"]
    device_type = get_device_type(board)
    if device_type == "esp32":
        pattern = re.compile(rf"^{re.escape(env_name)}-.+-merged\.bin$")
    elif device_type == "nrf52":
        pattern = re.compile(rf"^{re.escape(env_name)}-.+\.zip$")
    else:
        pattern = re.compile(rf"^{re.escape(env_name)}-.+\.(uf2|hex|zip|bin)$")
    matches = [a for a in all_assets if pattern.match(a.get("name", ""))]
    matches.sort(key=lambda a: a.get("release_published_at") or a.get("updated_at", ""), reverse=True)
    return matches


def release_files_for_asset(board, asset):
    firmware_name = asset["name"]
    download_url = asset.get("browser_download_url") or asset.get("url", "")
    device_type = get_device_type(board)
    if device_type == "esp32":
        return [{
            "type": "flash-wipe",
            "name": download_url,
            "title": firmware_name,
        }]
    if device_type == "nrf52":
        return [{
            "type": "flash",
            "name": download_url,
            "title": firmware_name,
        }]
    return [{
        "type": "download",
        "name": download_url,
        "title": firmware_name,
    }]


def get_category(env_name):
    n = env_name.rstrip("_").lower()
    if n.endswith("_repeater_bridge_tcp"):    return "bridge_tcp"
    if n.endswith("_repeater_bridge_rs232"):  return "bridge_rs232"
    if n.endswith("_repeater_bridge_espnow"): return "bridge_espnow"
    if "_logging_repeater" in n:              return "repeater"
    if n.endswith("_repeater"):               return "repeater"
    if n.endswith("_repeatr"):                return "repeater"
    if "_companion_radio_ble" in n or n.endswith("_companion_ble"): return "companion_ble"
    if "_companion_radio_usb" in n or n.endswith("_companion_usb") or n.endswith("_comp_radio_usb"): return "companion_usb"
    if "_companion_radio_wifi" in n:          return "companion_wifi"
    if n.endswith("_room_server") or n.endswith("_room_svr"): return "room_server"
    if n.endswith("_sensor"):                 return "sensor"
    if n.endswith("_kiss_modem"):             return "kiss_modem"
    if n.endswith("_terminal_chat"):          return "terminal_chat"
    return "other"


def build_flasher(boards, all_assets):
    if LEGACY_FIRMWARE_DIR.exists():
        shutil.rmtree(LEGACY_FIRMWARE_DIR)

    published = []
    skipped = []

    for board in boards:
        env_name = board["env"]
        device_type = get_device_type(board)
        assets = find_assets_for_board(all_assets, board)
        if not assets:
            skipped.append(env_name)
            continue

        releases = []
        for asset in assets:
            firmware_name = asset["name"]
            version = asset.get("release_tag") or asset.get("updated_at", "release")[:10]
            print(f"  Indexing {firmware_name} ...", file=sys.stderr)

            releases.append({
                "version": version,
                "name": asset.get("release_name") or version,
                "published_at": asset.get("release_published_at") or asset.get("updated_at", ""),
                "prerelease": bool(asset.get("release_prerelease")),
                "firmware": firmware_name,
                "download_url": asset.get("browser_download_url", ""),
                "files": release_files_for_asset(board, asset),
            })

        latest = releases[0]

        published.append({
            **board,
            "category": get_category(env_name),
            "type": device_type,
            "version": latest["version"],
            "download_url": latest.get("download_url", ""),
            "releases": releases,
        })

    with (SITE_FLASHER / "boards.json").open("w", encoding="utf-8") as f:
        json.dump(published, f, indent=2)
        f.write("\n")

    print(f"\nFlasher built: {len(published)} boards published, {len(skipped)} skipped (no release asset).", file=sys.stderr)
    return published


args_token = None  # set in main()


def parse_args():
    parser = argparse.ArgumentParser(description="Build MeshCoreNG web flasher firmware manifests.")
    parser.add_argument("--repo",  default=os.environ.get("GITHUB_REPOSITORY"),
                        help="GitHub repository in owner/name form.")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"),
                        help="GitHub token for reading release assets.")
    return parser.parse_args()


def main():
    global args_token
    args = parse_args()
    args_token = args.token

    if not args.repo:
        print("Repository is required. Set GITHUB_REPOSITORY or pass --repo owner/name.", file=sys.stderr)
        return 1

    if not SITE_FLASHER.exists():
        print(f"VitePress dist not found at {SITE_FLASHER}. Run 'vitepress build' first.", file=sys.stderr)
        return 1

    boards = load_boards()
    if not boards:
        print(f"{BOARDS_FILE} is empty.", file=sys.stderr)
        return 1

    print(f"Loading release assets from {args.repo} ...", file=sys.stderr)
    all_assets = load_all_release_assets(args.repo, args_token)

    build_flasher(boards, all_assets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
