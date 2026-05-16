#!/usr/bin/env python3
"""
Build the MeshCoreNG web flasher firmware manifests.

Searches ALL GitHub releases for '*-merged.bin' assets and matches them
to the boards listed in webflasher/boards.json. Boards without a matching
release asset are silently skipped (firmware not yet released).

Writes output to website/.vitepress/dist/flasher/ which is the VitePress
build output directory. Run this script AFTER 'vitepress build'.
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
SITE_FLASHER    = ROOT / "website" / ".vitepress" / "dist" / "flasher"
FIRMWARE_DIR    = SITE_FLASHER / "firmware"


def load_boards():
    with (ROOT / "webflasher" / "boards.json").open("r", encoding="utf-8") as f:
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
    """Return dict of asset_name → asset metadata, across ALL releases."""
    assets = {}
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
            for asset in release.get("assets", []):
                name = asset.get("name", "")
                if name not in assets:  # keep first (newest) occurrence
                    assets[name] = asset
        page += 1
    print(f"Collected {len(assets)} release assets total.", file=sys.stderr)
    return assets


def find_asset_for_env(all_assets, env_name):
    """Find a '*-merged.bin' asset matching env_name, or None."""
    pattern = re.compile(rf"^{re.escape(env_name)}-.+-merged\.bin$")
    matches = [a for name, a in all_assets.items() if pattern.match(name)]
    if not matches:
        return None
    matches.sort(key=lambda a: a.get("updated_at", ""))
    return matches[-1]


def download_asset(asset, destination, token):
    data = github_request(asset["url"], token, accept="application/octet-stream")
    with destination.open("wb") as f:
        f.write(data)


def write_manifest(board, firmware_name, version):
    manifest = {
        "name": board["name"],
        "version": version,
        "new_install_prompt_erase": True,
        "builds": [
            {
                "chipFamily": board["chipFamily"],
                "parts": [{"path": firmware_name, "offset": 0}],
            }
        ],
    }
    manifest_path = FIRMWARE_DIR / board["env"] / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


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
    FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)

    published = []
    skipped = []

    for board in boards:
        env_name = board["env"]
        asset = find_asset_for_env(all_assets, env_name)
        if asset is None:
            skipped.append(env_name)
            continue

        # Determine version from asset's release tag
        version = asset.get("updated_at", "release")[:10]

        board_dir = FIRMWARE_DIR / env_name
        board_dir.mkdir(parents=True, exist_ok=True)
        firmware_name = asset["name"]

        print(f"  Downloading {firmware_name} ...", file=sys.stderr)
        download_asset(asset, board_dir / firmware_name, args_token)
        write_manifest(board, firmware_name, version)

        published.append({
            **board,
            "category": get_category(env_name),
            "manifest": f"./firmware/{env_name}/manifest.json",
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
        print("webflasher/boards.json is empty.", file=sys.stderr)
        return 1

    print(f"Loading release assets from {args.repo} ...", file=sys.stderr)
    all_assets = load_all_release_assets(args.repo, args_token)

    build_flasher(boards, all_assets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
