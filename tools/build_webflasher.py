#!/usr/bin/env python3
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
WEBFLASHER_DIR = ROOT / "webflasher"
SITE_DIR = ROOT / "site" / "flasher"
FIRMWARE_DIR = SITE_DIR / "firmware"


def load_boards():
    with (WEBFLASHER_DIR / "boards.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def clean_site():
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)


def copy_static():
    for name in ("index.html", "app.js", "style.css"):
        shutil.copy2(WEBFLASHER_DIR / name, SITE_DIR / name)


def github_request(url, token=None, accept="application/vnd.github+json"):
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MeshCoreNG-WebFlasher",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        return response.read()


def load_release(repo, tag, token):
    if tag == "latest":
        url = f"https://api.github.com/repos/{repo}/releases/latest"
    else:
        url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    return json.loads(github_request(url, token).decode("utf-8"))


def find_release_asset(release, env_name):
    pattern = re.compile(rf"^{re.escape(env_name)}-.+-merged\.bin$")
    matches = [asset for asset in release.get("assets", []) if pattern.match(asset.get("name", ""))]
    if not matches:
        raise FileNotFoundError(f"No release asset found for {env_name}-*-merged.bin")
    matches.sort(key=lambda asset: asset.get("updated_at", ""))
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
                "parts": [
                    {
                        "path": firmware_name,
                        "offset": 0
                    }
                ]
            }
        ]
    }
    manifest_path = FIRMWARE_DIR / board["env"] / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def publish_release_firmwares(boards, release, token):
    published = []
    version = release.get("tag_name", "release")
    for board in boards:
        env_name = board["env"]
        asset = find_release_asset(release, env_name)
        board_dir = FIRMWARE_DIR / env_name
        board_dir.mkdir(parents=True, exist_ok=True)
        firmware_name = asset["name"]
        download_asset(asset, board_dir / firmware_name, token)
        write_manifest(board, firmware_name, version)
        published.append({
            **board,
            "manifest": f"./firmware/{env_name}/manifest.json"
        })

    with (SITE_DIR / "boards.json").open("w", encoding="utf-8") as f:
        json.dump(published, f, indent=2)
        f.write("\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Build MeshCoreNG web flasher from GitHub release assets.")
    parser.add_argument("--release-tag", default=os.environ.get("WEBFLASHER_RELEASE_TAG", "latest"),
                        help="GitHub release tag to use, or 'latest'.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"),
                        help="GitHub repository in owner/name form.")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"),
                        help="GitHub token used to read release assets.")
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.repo:
        print("Repository is required. Set GITHUB_REPOSITORY or pass --repo owner/name.", file=sys.stderr)
        return 1

    boards = load_boards()
    if not boards:
        print("webflasher/boards.json does not contain any boards", file=sys.stderr)
        return 1

    clean_site()
    copy_static()
    release = load_release(args.repo, args.release_tag, args.token)
    publish_release_firmwares(boards, release, args.token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
