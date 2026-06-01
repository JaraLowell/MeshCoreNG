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

## Daily reboot timer

Repeater-only and TCP bridge repeater builds also support an optional uptime-based reboot timer. This is separate from power saving and is disabled by default.

```
set reboot.daily on
set reboot.interval 24
get reboot
```

The interval is configured in hours from `1` to `168`. When the timer expires, the repeater waits until the outbound TX queue is idle and then reboots. RS232 and ESP-NOW bridge builds do not include this timer.
