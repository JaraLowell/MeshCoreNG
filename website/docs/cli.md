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
get bridge.type            — shows "tcp", "rs232" or "espnow"
```

### Power saving

```
powersaving                — show state
powersaving on|off
get power.stats
clear power.stats
```

### Dutch region database

The Dutch region database is a generated, read-only lookup table stored in firmware flash. It can be used by the CLI or a companion app to find Dutch location region codes without loading a database into RAM.

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
