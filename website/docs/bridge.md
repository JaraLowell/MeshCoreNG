# Internet bridge

## Purpose of the bridge system

MeshCoreNG is RF-first. The bridge system is optional transport/backhaul for specific deployments, not a replacement for RF-local operation.

Bridges are intended for:

- Linking isolated geographic MeshCore RF regions that should intentionally exchange selected traffic.
- Remote RF gateways that need a controlled backhaul path.
- Temporary backhaul during events, tests, or outages.
- Observer, measurement, and research setups.
- Private infrastructure operated by a known group.

Bridges are not intended for:

- A worldwide flooding backbone.
- An always-on global relay.
- Unrestricted packet replication.
- Bypassing normal RF planning and segmentation.

Selected traffic can optionally be transported between isolated MeshCore deployments. Bridge operators decide which bridge server, repeaters, regions, and traffic sources are appropriate for their network.

## Intended usage

```mermaid
flowchart LR
    subgraph A["Island A: local RF deployment"]
        A1["LoRa clients"] <--> A2["RF repeaters"]
        A2 <--> A3["Bridge repeater"]
    end

    A3 <--> S["Private or controlled bridge server"]

    subgraph B["Island B: local RF deployment"]
        B3["Bridge repeater"] <--> B2["RF repeaters"]
        B2 <--> B1["LoRa clients"]
    end

    S <--> B3
```

The bridge is a controlled link between selected RF islands. Each island should still be designed as a sensible local RF network.

## Not intended

```mermaid
flowchart TB
    G["Single worldwide bridge group"]:::bad
    N1["Region A"] --> G
    N2["Region B"] --> G
    N3["Region C"] --> G
    N4["Region D"] --> G
    G --> F["Unrestricted packet replication"]:::bad
    F --> N1
    F --> N2
    F --> N3
    F --> N4

    classDef bad fill:#ffe7e7,stroke:#b00020,color:#111
```

Large-scale uncontrolled forwarding is discouraged. It wastes RF airtime, makes loops harder to reason about, and works against MeshCoreNG's goal of keeping busy radio networks calm.

## RF locality remains important

RF airtime efficiency remains a primary MeshCoreNG design goal. Internet transport should not be used to bypass sensible RF segmentation.

Operators should bridge only what is needed for the deployment. Keep local traffic local where possible, use regional segmentation, and avoid forwarding traffic into RF areas that do not need it.

## Best practices

- Bridge only required channels, topics, or traffic sources.
- Avoid unnecessary rebroadcast into RF networks.
- Use regional segmentation for large deployments.
- Use private bridge groups or private bridge servers when possible.
- Avoid full-network flooding across bridge links.
- Monitor airtime, duplicate counters, and congestion after enabling a bridge.
- Treat every bridge as an operated network service with an owner and a purpose.

## Planned loop and duplicate protections

Multi-bridge environments need additional safeguards because the same packet may be able to return through a different bridge path.

Planned or under consideration protections include:

- Path fingerprints.
- Lightweight path hashes.
- Bridge loop detection.
- Duplicate suppression.
- TTL and hop controls.
- Bridge scoping.

These mechanisms are intended to make controlled bridge deployments safer. They do not change the basic guidance: avoid uncontrolled forwarding, keep bridge groups scoped, and preserve RF locality.

## Bridge firmware types

MeshCoreNG currently has three bridge-oriented paths:

| Build type | Transport | Typical use |
|---|---|---|
| `_bridge_tcp` | ESP32 WiFi TCP client | A WiFi-capable repeater connects directly to a controlled bridge server. |
| `_bridge_rs232` | Serial/USB to a host script | Boards without WiFi use a PC, Raspberry Pi or other host as the network side. |
| `_bridge_espnow` | ESP-NOW | Local ESP32 bridge experiments where WiFi infrastructure is not the main transport. |

Use `get bridge.type` on the device to confirm which bridge mode is compiled in.

## Path 1: ESP32 repeater with WiFi

Flash a `_bridge_tcp` firmware variant on an ESP32 repeater that has WiFi, then configure it for the selected bridge server:

```text
set wifi.ssid     YourWiFi
set wifi.password secret123
set bridge.server yourserver.example.com
set bridge.port   4200
set bridge.password bridgeSecret
set bridge.enabled on
```

Check the bridge type:

```text
get bridge.type
```

## Path 2: Repeater via USB

Boards without WiFi, including nRF52 (RAK4631), RP2040, STM32, or ESP32 boards without WiFi access, can use a USB-connected PC or Raspberry Pi as the bridge transport host.

Flash the `_bridge_rs232` firmware variant and enable the bridge:

```text
set bridge.enabled on
```

Then run the relay script on the connected computer:

```bash
pip install pyserial
python3 tools/usb_bridge_client.py --serial /dev/ttyUSB0 --baud 115200 \
                                    --server yourserver.example.com --port 4200 \
                                    --bridge-password bridgeSecret
```

On Windows use `--serial COM3`.

## Status and health

Bridge builds expose status through CLI commands where the firmware supports them:

```text
get bridge.type
get bridge.status
get node.info
```

TCP bridge builds may also expose a small HTTP status page on the device once WiFi is connected. Use it as an operator view, not as a public service.

## Running the server

Start the TCP bridge server on a machine the intended bridge repeaters can reach:

```bash
python3 tools/tcp_bridge_server.py --port 4200
```

To require a bridge password from TCP clients:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --password bridgeSecret
```

No external dependencies. WiFi repeaters and USB repeaters can connect to the same controlled bridge server simultaneously.

## Security note

The TCP bridge password is an access check, not transport encryption. Run the server on a trusted network or VPS with firewall rules limiting access. TLS support is planned for a future release.

## FAQ

**Does MeshCoreNG require internet?**  
No. MeshCoreNG remains usable as an RF-only LoRa mesh.

**Is the bridge enabled by default?**  
No. Bridge support requires a bridge-capable firmware build and `set bridge.enabled on`.

**Is this intended to create a global internet mesh?**  
No. The bridge is for controlled transport between selected deployments, not worldwide packet propagation.

**Can bridges be private?**  
Yes. Private bridge servers and private bridge groups are recommended for many deployments.

**Are anti-loop protections planned?**  
Yes. Path fingerprints, lightweight path hashes, loop detection, duplicate suppression, TTL/hop controls, and bridge scoping are planned or being evaluated, especially for multi-bridge environments.
