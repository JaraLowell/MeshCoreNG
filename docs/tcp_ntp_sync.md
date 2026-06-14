# TCP Bridge NTP Time Synchronization

## Overview

The TCP Bridge now includes automatic NTP (Network Time Protocol) time synchronization when WiFi is connected. This ensures accurate timestamping on bridge nodes that have internet access.

## Features

- **Automatic sync on WiFi connection**: When the bridge successfully connects to WiFi, it automatically synchronizes the clock via NTP
- **Periodic hourly refresh**: The time is refreshed every hour (3600 seconds) to maintain accuracy
- **Dual sync methods**: 
  - Primary: NTPClient library with retry logic (up to 3 attempts)
  - Fallback: ESP32 built-in SNTP (Simple NTP) implementation
- **RTC clock update**: The synchronized time is written to the device's RTC clock for consistent timestamping across the firmware

## NTP Server

- **Server**: `pool.ntp.org`
- **UTC offset**: 0 (time is stored as UTC)
- **Update interval**: 3600000 ms (1 hour)

## How It Works

### Initial Sync (on WiFi connection)

When WiFi connects successfully:

1. The bridge attempts to sync time using the NTPClient library
2. Up to 3 retry attempts are made if the first attempt fails
3. If NTPClient fails, the ESP32's built-in SNTP is used as a fallback
4. The synchronized time is validated (must be >= 2026-01-01 UTC)
5. If successful, the RTC clock is updated with the synchronized time

### Periodic Refresh

Every hour while WiFi is connected:

1. A lightweight async SNTP refresh is triggered
2. This runs in the background without blocking the main loop
3. The refresh timestamp is updated for the next hourly cycle

## Checking NTP Sync Status

Use the `get wifi.status` CLI command to check if NTP is synchronized:

```
> get wifi.status
> WiFi: connected | IP: 192.168.1.100 | RSSI: -45 dBm | Server: connected | NTP: synced
```

The status will show:
- `NTP: synced` - Time has been successfully synchronized
- `NTP: not synced` - Waiting for initial sync or sync failed

## Implementation Details

### Minimum Valid Epoch

The implementation validates that the received time is >= 1767225600 (2026-01-01 00:00:00 UTC). This prevents accepting obviously incorrect time values from:
- Uninitialized RTC clocks
- Network errors
- Server misconfigurations

### Retry Logic

Initial sync (via `syncTimeWithNTP()`):
- 3 attempts with NTPClient
- 1 second delay between retries
- Falls back to SNTP if all NTPClient attempts fail
- SNTP fallback retries for up to 10 seconds (20 x 500ms)

### Memory Efficiency

- Uses lightweight async SNTP for periodic refreshes (no blocking, no extra UDP sockets)
- Initial sync blocks briefly but only occurs once per WiFi connection
- No ongoing memory allocation for NTP operations

## Related Features

This NTP synchronization complements:
- **Packet timestamping**: Ensures accurate `ts` fields in bridged packets
- **TCP flood protection**: Uses accurate time for rate limiting windows
- **Heartbeat intervals**: Maintains proper timing for TCP keepalive

## Troubleshooting

### NTP shows "not synced"

1. Verify WiFi is connected: `get wifi.status`
2. Check internet connectivity (ping external server)
3. Verify firewall allows outbound UDP port 123 (NTP)
4. Check logs for NTP sync failure messages

### Time seems incorrect

1. Verify the device's timezone settings (if applicable)
2. Remember that NTP time is stored as UTC, not local time
3. Check if the RTC battery is dead (for boards with battery-backed RTC)

## Code References

- Implementation: `src/helpers/bridges/TCPBridge.cpp`
  - `syncTimeWithNTP()` - Full sync with retry
  - `refreshNTP()` - Lightweight hourly refresh
- Configuration: WiFi connection triggers initial sync
- Status display: `getStatusStr()` shows NTP sync state
