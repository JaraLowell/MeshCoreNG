# Observer JSONL Protocol v1

MeshCoreNG observer export is a local serial/USB protocol for feeding MeshCore Atlas. It is line-delimited JSON: each event is exactly one JSON object followed by a newline.

Atlas telemetry is local-only by default. Enabling observer export does not send extra LoRa packets and does not increase airtime.

In the current repeater firmware slice, `atlas export on` enables a local `dense_stats` JSONL line about every 5 seconds on USB serial. Received station adverts are also exported locally as `node_seen`, as `position` when the advert contains lat/lon, and as `neighbor` for direct zero-hop adverts.

## Common Fields

```json
{"v":1,"type":"position","time":1770000000,"node":"PD4MV","node_id":"abcd1234"}
```

- `v`: protocol version. Current version is `1`.
- `type`: `position`, `neighbor`, `path`, `dense_stats`, or `node_seen`.
- `time`: Unix timestamp in seconds.
- `node`: optional human-readable node name or callsign.
- `node_id`: stable lowercase hex observer node id.

Unknown event types are ignored by Atlas. Missing optional fields must not crash ingest.

## Position

```json
{"v":1,"type":"position","time":1770000000,"node":"PD4MV","node_id":"abcd1234","lat":52.7034,"lon":5.2912,"alt":12,"speed":36,"heading":90}
```

## Neighbor

```json
{"v":1,"type":"neighbor","time":1770000000,"node":"PD4MV","node_id":"abcd1234","neighbors":[{"node_id":"beef5678","rssi":-97,"snr":7.5,"last_heard":1769999980}]}
```

## Path

```json
{"v":1,"type":"path","time":1770000000,"src":"abcd1234","dst":"beef5678","hops":["abcd1234","11223344","beef5678"],"latency_ms":1850}
```

## Dense Stats

```json
{"v":1,"type":"dense_stats","time":1770000000,"node_id":"abcd1234","heard":1234,"duplicates":321,"forwards":456,"suppressed":789,"airtime_ms":123456}
```

## Node Seen

```json
{"v":1,"type":"node_seen","time":1770000000,"node":"PD4MV","node_id":"abcd1234"}
```
