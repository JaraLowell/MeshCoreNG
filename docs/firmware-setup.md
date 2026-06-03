# Firmware Observer Setup

Observer JSONL export is disabled by default.

Connect to the node over USB serial and run:

```text
atlas export status
atlas export on
observer export json
atlas export test
atlas export off
```

`atlas export test` prints one fake v1 JSONL event of each supported type. It is serial-only, so test fixtures are not sent over LoRa.

When export is on, the repeater firmware also prints a local `dense_stats` JSONL event every 5 seconds. Received station adverts are exported as `node_seen`; adverts with lat/lon also produce `position`; direct zero-hop adverts also produce `neighbor`. `observer export json` emits one dense-stats event immediately on request.

Normal firmware behavior is unchanged while export is off. Observer export writes to local serial/USB only and does not add LoRa airtime.

## Linux Serial Permissions

Typical device names are `/dev/ttyUSB0`, `/dev/ttyACM0`, or `/dev/serial/by-id/...`.

If the port cannot be opened:

```bash
sudo usermod -aG dialout "$USER"
```

Log out and back in after changing group membership.

## Windows

Use the COM port shown in Device Manager, for example:

```text
COM3
```
