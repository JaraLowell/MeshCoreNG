# Atlas Serial Ingest

Atlas ingests MeshCoreNG observer JSONL from a local USB serial observer node.

Start Atlas services:

```bash
docker compose up postgres backend frontend
```

Run serial ingest on the host:

```bash
atlas-ingest-serial --port /dev/ttyUSB0 --baud 115200
```

Windows example:

```powershell
atlas-ingest-serial --port COM3 --baud 115200
```

The backend also supports built-in serial ingest when it has direct access to the device:

```bash
SERIAL_OBSERVER_PORT=/dev/ttyUSB0 SERIAL_OBSERVER_BAUD=115200 go run ./cmd/server
```

Docker serial permissions are platform-specific, so host-side ingest is the recommended first setup.

## Troubleshooting

- No events: run `atlas export status`, then `atlas export on`. Repeater firmware should print a `dense_stats` JSONL line about every 5 seconds, and station adverts should appear as `node_seen`/`position`/`neighbor` when heard. Use `atlas export test` for deterministic test events.
- Permission denied on Linux: add your user to `dialout`, then log out and back in.
- Malformed JSON: Atlas rejects the line, logs rejected counts, and continues reading.
- Unsupported version: Atlas rejects versions other than `v:1`.
- Unknown type: Atlas stores the raw event as rejected/ignored and keeps running.
- Dashboard not live: confirm the backend WebSocket is connected and the frontend points to `ws://localhost:8080/ws`.
