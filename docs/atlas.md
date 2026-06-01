# MeshCore Atlas Foundation

MeshCore Atlas is a disabled-by-default telemetry foundation for future map, topology and network-health tools. The Phase 1 implementation focuses on compact structures and local export of information the firmware already knows.

## Principles

- No internet services or dependencies are implemented.
- Existing routing behavior is unchanged.
- Atlas packets and observer export are optional and off by default.
- Position and neighbor reporting are designed for low rates, not beacon spam.

## CLI

```
atlas enable on
atlas position on
atlas neighbors on
atlas pathsample 1
atlas export on
get atlas.stats
observer export json
```

`atlas pathsample` accepts `on`, `off`, or a percentage from `0` to `10`. A future transport can consume observer events over serial, TCP, WebSocket or MQTT; Phase 1 only defines the reusable event layer and CLI output.

## Payloads

`PAYLOAD_TYPE_ATLAS` is `0x0C`. Atlas subtypes are:

- `POSITION` (`0x01`)
- `NEIGHBORS` (`0x02`)
- `PATH_SAMPLE` (`0x03`)
- `DENSE_STATS` (`0x04`)

The helper encoder lives in `src/helpers/Atlas.h` and `src/helpers/Atlas.cpp`.

## Smart Position Reporting

Position reporting is controlled by thresholds:

- minimum interval
- distance change
- heading change
- speed change
- maximum interval

The default config keeps Atlas disabled and uses conservative thresholds for future opt-in reporting.
