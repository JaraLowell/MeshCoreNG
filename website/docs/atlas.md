# Atlas telemetry

## Overview

Atlas is a disabled-by-default telemetry foundation for future topology, map, observer and network-health tools.

It does not add internet services, does not change routing behavior, and should not be used as a high-rate beacon system. Phase 1 focuses on compact structures and local export of information the firmware already has.

## Commands

```text
atlas enable on
atlas position on
atlas neighbors on
atlas pathsample 1
atlas export on
get atlas.stats
observer export json
```

`atlas pathsample` accepts `on`, `off`, or a percentage from `0` to `10`.

`observer export json` returns an event-style export only when Atlas and Atlas export are both enabled. Otherwise it returns an empty array.

## Payload allocation

Atlas uses `PAYLOAD_TYPE_ATLAS` (`0x0C`) with these subtypes:

| Subtype | Name | Purpose |
|---|---|---|
| `0x01` | POSITION | Compact node position. |
| `0x02` | NEIGHBORS | Low-rate neighbor summary. |
| `0x03` | PATH_SAMPLE | Sampled route telemetry. |
| `0x04` | DENSE_STATS | Network-health counters. |

## Future integrations

Atlas is intended to feed external tooling such as dashboards, MQTT gateways, Home Assistant bridges or map views. The firmware should export clean local data and let a gateway handle heavier jobs like TLS, MQTT discovery, databases and visualization.
