# Power saving

## Overview

Power saving lets a repeater sleep when it has nothing to transmit. This is useful for battery-powered or solar-powered nodes.

The default is **off**. Many repeaters are fixed relay or backbone nodes and should not sleep unexpectedly.

## Commands

```
powersaving          — show current state
powersaving on       — enable power saving
powersaving off      — disable power saving

get power.stats      — show sleep/wake statistics
clear power.stats    — reset statistics
```

## Behavior

When power saving is enabled:

- The repeater sleeps only when there is **no outbound work pending**.
- Bridge or WiFi mode **blocks sleep** — a bridged repeater stays awake.
- **ESP32 boards** wake via LoRa DIO1 or timer where supported.
- **nRF52 boards** use event/interrupt sleep.

## Stats

`get power.stats` shows how often and how long the repeater has slept. Stats are RAM-only and reset on reboot or when cleared with `clear power.stats`.

## Low-battery guards

MeshCoreNG also has low-battery guards for boards that report battery voltage.

The boot guard runs directly after `board.begin()`. If the battery reading is valid but below the boot threshold, the node sleeps and retries instead of starting radio, display, GPS, sensors or bridge code.

The runtime guard runs after normal startup on repeater, GPS tracker / sensor, and room server builds. It checks battery voltage periodically. If the node is not externally powered and voltage falls below the runtime threshold, it sleeps before WiFi, bridge, GPS, display or radio work can drain the battery further.

```
get boot.lowbat.guard
set boot.lowbat.guard on|off
get boot.lowbat.mv
set boot.lowbat.mv 3300

get runtime.lowbat.guard
set runtime.lowbat.guard on|off
get runtime.lowbat.mv
set runtime.lowbat.mv 3300
get runtime.lowbat.retry
set runtime.lowbat.retry 1800
```

Default runtime behavior checks every 30 seconds, treats readings below `2500mV` as invalid, and sleeps for `1800s` when a battery-powered node falls below `3300mV`.

## Daily reboot timer

Repeater-only and TCP bridge repeater builds also support an optional uptime-based reboot timer. This is separate from power saving and is disabled by default.

```
set reboot.daily on
set reboot.interval 24
get reboot
```

The interval is configured in hours from `1` to `168`. When the timer expires, the repeater waits until the outbound TX queue is idle and then reboots. RS232 and ESP-NOW bridge builds do not include this timer.
