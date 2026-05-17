# MeshCoreNG CLI App

The MeshCoreNG CLI App is a Flutter-based console application for interacting with MeshCoreNG repeaters. It runs on Android, Linux, and Windows.

## What it does

The app connects to a MeshCoreNG repeater and gives you a full command interface — either locally over USB/BLE/TCP, or remotely via the mesh network.

**Companion mode** — connect to your local repeater as a serial companion (BLE, USB serial, or TCP):
- Send CLI commands directly to the repeater
- View real-time output

**Remote repeater CLI** — reach any repeater in your mesh network:
- Query stats, change settings, and reboot repeaters that are physically out of reach
- All traffic is relayed over the existing LoRa mesh

**Direct repeater terminal** (`-r` mode) — connect directly as a repeater peer instead of as a companion:
- Useful for initial setup (no companion needed)
- Required for configuring the TCP bridge (`set bridge.*`, `set wifi.*`)

## Platforms

| Platform | Format       |
|----------|-------------|
| Android  | APK (arm64, arm32, x86_64) |
| Linux    | tar.gz (x64) |
| Windows  | zip (x64)    |

## Downloads

Releases are built automatically from the [MeshCoreNG-cli-app](https://github.com/MichTronics/MeshCoreNG-cli-app) repository. Click a platform below to download.

<CliAppReleases />

## Android installation

Android APKs are distributed outside the Play Store. You need to enable **Install from unknown sources** for your browser or file manager before installing.

1. Download the APK for your device:
   - **arm64** — most modern Android phones (2016 and later)
   - **arm32** — older or 32-bit-only Android devices
   - **x86_64** — Android emulators or x86 tablets
2. Open the APK from your downloads folder and follow the installation prompt.

## Linux installation

```bash
tar -xzf meshcli-ng-*-linux-x64.tar.gz
cd meshcli-ng-*-linux-x64/
./meshcli-ng
```

USB serial access requires your user to be in the `dialout` group:

```bash
sudo usermod -aG dialout $USER
```

Log out and back in for the group change to take effect.

## Windows installation

1. Extract the zip file.
2. Run `meshcli-ng.exe` from the extracted folder.

For USB serial you may need a CP210x or CH340 driver depending on your device.

## Source code

[github.com/MichTronics/MeshCoreNG-cli-app](https://github.com/MichTronics/MeshCoreNG-cli-app)
