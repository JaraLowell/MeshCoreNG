#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBFLASHER_DIR = ROOT / "webflasher"
OUT_DIR = ROOT / "out"
SITE_DIR = ROOT / "site" / "flasher"
FIRMWARE_DIR = SITE_DIR / "firmware"


def run(cmd, env=None):
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


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


def build_firmwares(boards):
    env = os.environ.copy()
    env.setdefault("FIRMWARE_VERSION", "web")
    env.setdefault("DISABLE_DEBUG", "1")
    if shutil.which("pio", path=env.get("PATH")) is None:
        local_pio = Path.home() / ".platformio" / "penv" / "bin"
        if (local_pio / "pio").exists():
            env["PATH"] = f"{local_pio}{os.pathsep}{env.get('PATH', '')}"
    targets = [board["env"] for board in boards]
    run(["bash", "build.sh", "build-firmware", *targets], env=env)


def find_merged_bin(env_name):
    matches = sorted(OUT_DIR.glob(f"{env_name}-*-merged.bin"))
    if not matches:
        raise FileNotFoundError(f"No merged ESP32 firmware found for {env_name}")
    return matches[-1]


def write_manifest(board, firmware_name):
    manifest = {
        "name": board["name"],
        "version": os.environ.get("FIRMWARE_VERSION", "web"),
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


def publish_firmwares(boards):
    published = []
    for board in boards:
        env_name = board["env"]
        firmware = find_merged_bin(env_name)
        board_dir = FIRMWARE_DIR / env_name
        board_dir.mkdir(parents=True, exist_ok=True)
        firmware_name = firmware.name
        shutil.copy2(firmware, board_dir / firmware_name)
        write_manifest(board, firmware_name)
        published.append({
            **board,
            "manifest": f"./firmware/{env_name}/manifest.json"
        })

    with (SITE_DIR / "boards.json").open("w", encoding="utf-8") as f:
        json.dump(published, f, indent=2)
        f.write("\n")


def main():
    boards = load_boards()
    if not boards:
        print("webflasher/boards.json does not contain any boards", file=sys.stderr)
        return 1

    clean_site()
    copy_static()
    build_firmwares(boards)
    publish_firmwares(boards)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
