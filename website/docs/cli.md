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
