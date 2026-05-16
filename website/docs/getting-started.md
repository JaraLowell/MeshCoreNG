# Getting started

## Flash firmware

The easiest way is the [MeshCoreNG web flasher](/flasher/) for ESP32 boards.

For nRF52, RP2040 and STM32 boards, download the firmware from [GitHub Releases](https://github.com/MichTronics/MeshCoreNG/releases) and use the platform's normal flashing method (UF2, ZIP, HEX).

## Connect a client

MeshCoreNG uses the same protocol as MeshCore. Use any existing MeshCore client:

- **Web**: [app.meshcore.nz](https://app.meshcore.nz)
- **Android**: [Google Play](https://play.google.com/store/apps/details?id=com.liamcottle.meshcore.android)
- **iOS**: [App Store](https://apps.apple.com/us/app/meshcore/id6742354151)
- **Config tool**: [config.meshcore.io](https://config.meshcore.io)

## Start with defaults

The default settings are safe for any network. You do not need to change anything to get a working repeater.

When you want to tune behavior, start with [Dense mesh](/docs/dense-mesh) and check `get dense.stats` to understand what is happening on your network before changing anything.

## Developer setup

1. Install [PlatformIO](https://docs.platformio.org) in [Visual Studio Code](https://code.visualstudio.com).
2. Clone the [MeshCoreNG repository](https://github.com/MichTronics/MeshCoreNG).
3. Open the repository in Visual Studio Code.
4. Select a build environment for your board (e.g. `Heltec_v3_repeater`).
5. Build and upload.
