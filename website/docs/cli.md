# CLI reference

The CLI reference covers all commands available on MeshCoreNG repeaters, room servers and sensors.

The full command reference is maintained in the repository:

- [CLI Commands — full reference](https://github.com/MichTronics/MeshCoreNG/blob/main/docs/cli_commands.md)

## MeshCoreNG-specific commands

These commands are added by MeshCoreNG on top of the standard MeshCore CLI.

### Dense mesh

```
get dense.stats            — show dense-mesh statistics
clear dense.stats          — reset statistics

get flood.advert.base      — get flood advert forwarding base probability
set flood.advert.base <v>  — set (0=off, 0.308=default, 1=always forward)

get flood.relay.prob       — get relay probability (0-255)
set flood.relay.prob <v>   — set (0=never, 128=half, 255=always)

get flood.dynamic.enable   — get dynamic mode state
set flood.dynamic.enable on|off
```

### Internet bridge (TCP)

```
set wifi.ssid <name>
set wifi.password <pass>
set bridge.server <host>
set bridge.port <port>
set bridge.enabled on|off
set bridge.rf on|off       — allow bridge flood packets onto LoRa RF
get bridge.type            — shows "tcp", "rs232" or "espnow"
```

Python room server over the TCP bridge:

```bash
python3 tools/python_room_server.py --server <bridge-host> --port 4200 \
  --name "Python Room" --password secret
```

### Bridge health

```
get bridge.status          — show current bridge connection state when supported
get node.info              — show node info used by bridge/status pages when supported
```

### Power saving

```
powersaving                — show state
powersaving on|off
get power.stats
clear power.stats
```

### Daily reboot

Repeater-only and TCP bridge repeater builds can optionally reboot on an uptime timer. The feature is disabled by default and is not included in RS232 or ESP-NOW bridge builds.

```
set reboot.daily on|off
set reboot.interval <1-168>
get reboot
```

When the timer expires, the firmware waits for the outbound TX queue to become idle, then reboots the board. `set reboot.daily on` uses a 24-hour interval unless changed with `set reboot.interval`.

### Atlas observer

Atlas is disabled by default. It is a local telemetry/export foundation and does not change routing behavior.

```
atlas enable on|off
atlas position on|off
atlas neighbors on|off
atlas pathsample on|off|0-10
atlas export on|off
get atlas.stats
observer export json
```

### Dutch region database

The Dutch region database is a generated, read-only lookup table stored in firmware flash. It can be used by the CLI or a companion app to find Dutch location region codes without loading a database into RAM. It is controlled by the `WITH_DUTCH_REGION_DB` build flag.

```
regiondb                  — show database metadata
regiondb info             — show entries, provinces, code count and source revision
regiondb provinces        — list province abbreviations and counts
regiondb find <prefix>    — find a location by name prefix
regiondb get <index>      — show all codes for a location
regiondb code <code_id>   — resolve an internal region-code ID
```

The full generated-format documentation is maintained in the repository:

- [Dutch Region Database](https://github.com/MichTronics/MeshCoreNG/blob/main/docs/dutch_region_db.md)

### Runtime regions

Runtime regions are editable forwarding scopes used by repeaters, room servers and tooling.

```
region put <name> [parent]
region allowf <name>
region denyf <name>
region home <name>
region tree
region save
```
