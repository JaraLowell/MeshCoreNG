# Getting started

## Flash firmware

The easiest way is the [MeshCoreNG web flasher](/flasher/).

The web flasher lets you choose the firmware type, board variant, and firmware release version. The newest release is selected by default, but older published versions remain available when release assets exist for that board.

ESP32-family boards flash from merged `.bin` files using Web Serial. nRF52 boards can use serial DFU `.zip` assets when the release provides them. RP2040, STM32 and other download-only targets still use their normal firmware files and tools.

See [Web flasher](/docs/flasher) for asset naming, supported families and download-only behavior.

## Connect a client

MeshCoreNG uses the same protocol as MeshCore. Use any existing MeshCore client:

- **Web**: [app.meshcore.nz](https://app.meshcore.nz)
- **Android**: [Google Play](https://play.google.com/store/apps/details?id=com.liamcottle.meshcore.android)
- **iOS**: [App Store](https://apps.apple.com/us/app/meshcore/id6742354151)
- **Config tool**: [config.meshcore.io](https://config.meshcore.io)

## Start with defaults

The default settings are safe for any network. You do not need to change anything to get a working repeater.

When you want to tune behavior, start with [Dense mesh](/docs/dense-mesh) and check `get dense.stats` to understand what is happening on your network before changing anything.

For dense deployments, also review [Regions](/docs/regions) before connecting multiple towns, provinces or bridge groups.

## Developer setup

1. Install [PlatformIO](https://docs.platformio.org) in [Visual Studio Code](https://code.visualstudio.com).
2. Clone the [MeshCoreNG repository](https://github.com/MichTronics/MeshCoreNG).
3. Open the repository in Visual Studio Code.
4. Select a build environment for your board (e.g. `Heltec_v3_repeater`).
5. Build and upload.
