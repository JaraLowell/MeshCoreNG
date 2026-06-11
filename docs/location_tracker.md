# MeshCoreNG Location Tracker

MeshCoreNG has an experimental native location-report payload for APRS-like tracker deployments.

## Flow

```text
GPS tracker node -> LoRa mesh flood -> bridge repeater -> TCP bridge server -> /map and /locations.json
```

The TCP bridge server decodes `PAYLOAD_TYPE_LOCATION` packets and keeps the latest position per tracker node in memory.

## Tracker firmware

The first implementation lives in `examples/simple_sensor/main.cpp` behind a build flag:

```text
-D LOCATION_TRACKER_INTERVAL_SECS=60
```

The board must also compile with GPS support:

```text
-D ENV_INCLUDE_GPS=1
```

The tracker uses the existing `LocationProvider`, so board variants that already expose GPS through `target.cpp` do not need a second GPS driver.

Initial build targets:

```text
Heltec_v3_gps_tracker
Generic_E22_sx1262_gps_tracker
Generic_E22_sx1268_gps_tracker
Tbeam_SX1262_gps_tracker
Tbeam_SX1276_gps_tracker
LilyGo_TBeam_1W_gps_tracker
T_Beam_S3_Supreme_SX1262_gps_tracker
```

GPS must be enabled on the node:

```text
gps on
```

## Display behavior

GPS tracker builds with a display keep the display on instead of using the normal sensor auto-off behavior.

The tracker home screen shows the node name, GPS state, satellite count, battery voltage, and either:

- latitude, longitude, and altitude when a GPS fix is available
- waiting-for-fix status, LoRa frequency/SF, and tracker TX interval while no GPS fix is available

The tracker still only sends `PAYLOAD_TYPE_LOCATION` packets after the GPS provider has a valid fix. Without a GPS fix, the node may still send normal MeshCore packets such as adverts or replies, but it does not send a map position.

## Gateway

Run the TCP bridge server as usual. Tracker output is available at:

```text
http://server:8080/map
http://server:8080/locations.json
```

The public JSON does not expose bridge-client IP addresses or ports.

## Payload

`PAYLOAD_TYPE_LOCATION` is `0x0D`.

The payload starts after the normal MeshCore packet header/path fields:

| Field | Size | Notes |
|-------|------|-------|
| magic | 4 | `MCL1` |
| version | 1 | currently `1` |
| flags | 1 | reserved |
| node_id | 4 | first 4 bytes of the sender identity |
| lat | 4 | signed microdegrees |
| lon | 4 | signed microdegrees |
| altitude | 2 | signed metres |
| speed | 2 | centimetres per second, currently `0` for the simple tracker |
| heading | 2 | centidegrees, currently `0` for the simple tracker |
| satellites | 1 | GPS satellite count |
| battery | 2 | millivolts |
| timestamp | 4 | Unix time from node RTC |
| name_len | 1 | 0-24 |
| name | variable | UTF-8 node name |

Location packets are flood-routed, so normal repeater forwarding rules still apply. They also have a tracker-specific hop cap: a `PAYLOAD_TYPE_LOCATION` packet is only retransmitted while its path contains fewer than two repeater hops. After two repeaters have forwarded it, the next repeater will receive and release it without forwarding it again.
