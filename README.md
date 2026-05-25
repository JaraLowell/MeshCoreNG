## MeshCoreNG

MeshCoreNG is a Next Gen variant of MeshCore.

In simple terms: MeshCore lets LoRa devices pass messages to each other without the internet. MeshCoreNG builds on that and focuses on making repeaters smarter, so larger and busier networks can keep working better.

Website and web flasher: https://michtronics.github.io/MeshCoreNG/

The goal is not to rebuild MeshCore from scratch. The goal is to add improvements step by step, without breaking existing clients or the existing protocol.

## Why This Matters In The Netherlands

MeshCoreNG is being developed from the Netherlands. This is exactly the kind of place where dense-mesh firmware problems show up quickly.

The Netherlands is small, densely populated, and busy. In cities and towns, many LoRa nodes and repeaters may be able to hear each other at the same time. That sounds useful, but in a flood mesh it can also mean that too many repeaters retransmit the same message. The channel fills up faster.

On top of that, we use EU868 with airtime and duty-cycle limits. Every unnecessary retransmission therefore costs real capacity. In a quiet rural area you want maximum propagation, but in a Dutch city you mainly want to prevent the network from shouting over itself.

MeshCoreNG is trying to solve exactly that problem: stay reliable in quiet areas, but become calmer and smarter in busy Dutch meshes.

## What Are We Trying To Achieve?

MeshCore works well as a simple flood mesh network: repeaters pass messages further through the network. That is strong and reliable, especially in small or quiet networks.

But in a busy network, flooding can also create too much radio traffic. Many repeaters may retransmit the same message again. That costs airtime, increases the chance of collisions, and can make the network slower.

MeshCoreNG aims to improve this:

- Fewer unnecessary retransmissions.
- Less load on the LoRa channel.
- Repeaters that can better measure what is happening.
- Dense city meshes that stay more stable.
- Sparse rural meshes that still propagate reliably.
- No breakage for existing MeshCore clients.

## What Have We Done So Far?

We have added the first real dense-mesh foundation to the repeater firmware.

### 1. Less flood advert noise

Flood adverts are network advertisements that can be spread through repeaters. In a busy network they can use a lot of airtime.

That is why MeshCoreNG now has:

- `flood.advert.base`
- default value `0.308`

Simple explanation:

- `0` means: do not forward received flood adverts.
- `0.308` means: dense mesh default, less forwarding as hop count grows.
- `1` means: forward everything as normal.

This mainly helps in busy repeater networks where many nodes can already hear each other.

### 2. Dense stats

We can now better see what a repeater is doing.

With:

```text
get dense.stats
```

you can see things like:

- how many flood adverts were received
- how many flood adverts were forwarded
- how many flood adverts were dropped
- how many duplicate flood packets were seen
- how much RX/TX airtime is roughly being used
- how many CAD/channel-busy events occurred
- density level
- congestion level

With:

```text
clear dense.stats
```

you reset these counters. The stats are RAM-only and also disappear after reboot.

### 3. Manual relay probability

We added an extra knob:

```text
get flood.relay.prob
set flood.relay.prob <0..255>
```

Simple explanation:

- `0` means: do not relay flood packets.
- `128` means: relay about half of them.
- `255` means: normally relay everything that is allowed.

The default is `255`, so existing networks keep working the same way.

### 4. Dynamic mode preparation

There is also:

```text
get flood.dynamic.enable
set flood.dynamic.enable on
set flood.dynamic.enable off
```

Important: in this version, dynamic mode does not automatically change behavior yet.

For now, it is mostly preparation and observation. We want to collect real data from real networks before letting the firmware make automatic decisions.

Dynamic mode is off by default.

### 5. Better channel-busy detection

The repeater now uses hardware CAD/channel scan where possible. That lets the firmware better detect whether the channel is busy before it transmits.

This helps reduce collisions and unnecessary transmissions on a busy LoRa channel.

### 6. Internet bridge — connecting distant LoRa islands

LoRa is great for local mesh networks, but it has a physical limit. When two groups of LoRa users are too far apart to hear each other — different cities, different hills, different countries — they become isolated islands.

MeshCoreNG now includes a **TCP internet bridge** that solves this. Repeaters with WiFi can connect to a shared server over the internet. Mesh packets received locally are forwarded to all remote repeaters, and packets from remote repeaters are injected into the local LoRa mesh.

This means:
- Two groups in different Dutch cities can still exchange messages.
- A repeater on a hill with WiFi can link an otherwise isolated valley into the wider mesh.
- LoRa stays LoRa — users keep using their normal apps and devices. The bridge is invisible to them.

**How it works:**

```text
[LoRa mesh A]  ←→  [Repeater A with WiFi]  ←→  internet  ←→  [Repeater B with WiFi]  ←→  [LoRa mesh B]
```

**Path 1: ESP32 repeater with WiFi**

Repeaters with WiFi connect directly to the bridge server over the internet.

```text
set wifi.ssid     YourWiFi
set wifi.password secret123
set bridge.server yourserver.example.com
set bridge.port   4200
set bridge.enabled on
```

All 38 ESP32 repeater variants now have a `_bridge_tcp` firmware build available. See [docs/cli_commands.md](./docs/cli_commands.md) for the full command reference.

**Path 2: Repeater via USB (no WiFi required)**

Some repeaters have no WiFi — nRF52 boards (RAK4631), RP2040 boards, STM32 boards, and ESP32 boards in locations without WiFi coverage. These can still participate in the internet bridge via USB.

The repeater runs standard `_bridge_rs232` firmware and sends packets over the serial port to a connected PC or Raspberry Pi. A small Python script on that PC handles the TCP connection to the server.

```
[LoRa mesh]  ←→  [Repeater + RS232Bridge]  ←USB→  [PC/RPi + usb_bridge_client.py]  ←internet→  [tcp_bridge_server.py]
```

Set up on the repeater (RS232 bridge firmware):

```text
set bridge.enabled on
```

Run the relay script on the PC or Raspberry Pi:

```bash
pip install pyserial
python3 tools/usb_bridge_client.py --serial /dev/ttyUSB0 --baud 115200 \
                                    --server yourserver.example.com --port 4200
```

On Windows, use `--serial COM3` instead of `/dev/ttyUSB0`. The script is included in this repository at [tools/usb_bridge_client.py](./tools/usb_bridge_client.py).

**Start the forwarding server** (VPS, Raspberry Pi, or any internet-connected PC):

```bash
python3 tools/tcp_bridge_server.py --port 4200
```

The server script is included in this repository at [tools/tcp_bridge_server.py](./tools/tcp_bridge_server.py). It requires Python 3.7+ and has no external dependencies. WiFi repeaters and USB repeaters can connect to the same server simultaneously.

### 7. Safer repeater power saving

Power saving for repeaters is now clearer and easier to inspect.

```text
powersaving
powersaving on
powersaving off
get power.stats
clear power.stats
```

The default is `off`. That is intentional, because many repeaters are fixed relay or backbone nodes and should not suddenly start sleeping.

When enabled, a repeater only sleeps when there is no outbound work waiting. Bridge/WiFi mode blocks sleep. ESP32 boards wake by LoRa DIO1/timer where supported. nRF52 boards use event/interrupt sleep.

### 8. Dutch region database

MeshCoreNG now includes a compact Dutch Region Database generated from the MeshWiki list of Dutch regions.

It contains 2484 Dutch locations across 12 provinces, with primary and extra MeshCore region codes. The database is compiled into firmware flash as static data. It is not loaded into RAM, does not use runtime JSON parsing, and does not use dynamic `String` or `std::vector` storage.

It is enabled by the shared PlatformIO build flag `WITH_DUTCH_REGION_DB=1`, so normal MeshCoreNG variants get the same default. Constrained variants can disable it by overriding that flag.

This is useful for:

- looking up the correct Dutch region code from the CLI
- helping companion apps offer location-based region selection
- future OTA updates, because the database is regenerated at compile time and shipped inside the firmware image

Example CLI commands:

```text
regiondb info
regiondb provinces
regiondb find gron
regiondb get 45
```

Full details are in [docs/dutch_region_db.md](./docs/dutch_region_db.md).
The Dutch community also provides a practical region-code setup tool at [mesh-up.nl/tools/regiocodes-instellen](https://www.mesh-up.nl/tools/regiocodes-instellen/).

### 9. Regional mesh filtering

MeshCoreNG also supports a practical hierarchical region system for repeaters. A region is a named radio scope, such as `eu`, `nl`, `nl-nh`, or `nl-nh-bov`. Repeaters can be configured to forward only the scopes that make sense for their location and role.

This is separate from the Dutch lookup database above. The database helps you find valid region codes; the region tree tells your repeater what it should forward.

#### Why regions matter

Without regions, a flood mesh is simple:

```text
every repeater hears traffic
every repeater repeats traffic
the same packet appears again and again
```

That works in a small network. In a dense mesh, it becomes expensive. Airtime is limited, especially on EU868. If repeaters in Noord-Holland, Zuid-Holland, Friesland and Limburg all forward every local message, the channel fills up with traffic that is not useful for most listeners.

With regions, traffic can stay local when possible:

- local messages stay in the local mesh
- regional traffic can still move through a province
- national or European traffic can be forwarded by backbone repeaters
- dense city networks create fewer duplicate retransmissions
- remote areas can still use broader scopes when they need reach

The idea is not to make the network smaller. The idea is to stop every repeater from doing every job.

#### Dense mesh scaling

Dense meshes fail gradually: first messages become slower, then collisions rise, then repeaters waste more airtime forwarding duplicates than useful packets. Regional filtering gives operators a manual tool to reduce that load.

For example:

| Repeater role | Typical allowed regions | Why |
| --- | --- | --- |
| Local city repeater | local region only | Keeps neighbourhood traffic local |
| Province repeater | local + province | Connects nearby local meshes |
| Backbone repeater | local + province + country | Carries wider traffic intentionally |
| Gateway or hilltop | country or Europe when needed | Bridges larger areas with a clear purpose |

This makes a nationwide mesh more realistic: not every repeater has to be a national backbone.

#### Example Dutch region hierarchy

Example hierarchy:

```text
eu
└── nl
    ├── nl-nh
    │   ├── nl-nh-sbc
    │   └── nl-nh-bov
    └── nl-hhw
```

Meaning:

| Region | Meaning |
| --- | --- |
| `eu` | Europe |
| `nl` | Netherlands |
| `nl-nh` | Noord-Holland |
| `nl-hhw` | Heerhugowaard / local area |
| `nl-nh-sbc` | Schagen/Bergen/Castricum style local region |
| `nl-nh-bov` | Specific local region |

Parent-child regions give the tree structure. In practice, you add broad regions first, then provinces, then local areas. A child belongs under a parent, so operators and tools can understand the intended scope.

Think of this as scope inheritance: `nl-nh-bov` is a local region inside `nl-nh`, which is inside `nl`, which is inside `eu`. The tree tells humans and future routing logic that relationship. Forwarding policy is still explicit: allow the parent, the child, or both depending on what this repeater should carry.

#### Region forwarding filters

Forwarding is controlled per region:

| Command | Purpose | Example |
| --- | --- | --- |
| `region put <name> [parent]` | Add a region and optionally place it under a parent | `region put nl-nh nl` |
| `region allowf <name>` | Allow flood forwarding for that region | `region allowf nl-nh` |
| `region denyf <name>` | Block flood forwarding for that region | `region denyf eu` |
| `region home <name>` | Mark this node's own home region | `region home nl-nh-bov` |
| `region tree` | Show the configured hierarchy and flags | `region tree` |
| `region save` | Persist changes after reboot | `region save` |

`allowf` means this repeater may forward flood packets for that region. `denyf` means it should not forward that region's flood traffic. This is the main airtime-saving mechanism.

Important: configure the levels you actually want to carry. If a local repeater should only help `nl-nh-bov`, allow only that local region. If a backbone repeater should also carry `nl` or `eu`, allow those broader regions intentionally.

#### Home region

The home region is the region this node belongs to. It helps operators, tooling and future routing logic understand where the repeater lives.

Example:

```text
region home nl-nh-bov
```

For a normal local repeater, set the most specific correct region as the home region. For a high-site backbone repeater, still choose the local physical region, then separately allow the wider regions it is supposed to forward.

#### Example configuration

The following example creates a small Dutch hierarchy and allows forwarding for each level:

```text
region put eu
region put nl eu
region put nl-nh nl
region put nl-hhw nl
region put nl-nh-sbc nl-nh
region put nl-nh-bov nl-nh

region allowf eu
region allowf nl
region allowf nl-nh
region allowf nl-hhw
region allowf nl-nh-sbc
region allowf nl-nh-bov

region home nl-nh-bov

region tree
region save
```

For a busy local repeater, you may choose a narrower filter:

```text
region allowf nl-nh-bov
region denyf eu
region denyf nl
region save
```

That repeater now spends less airtime forwarding wide-area traffic. A nearby backbone repeater can still carry broader regions.

#### Troubleshooting

| Symptom | Check |
| --- | --- |
| Region disappears after reboot | Run `region save` after changes |
| Repeater forwards too much traffic | Use `region tree` and deny broad regions that are not needed |
| Local traffic does not travel far enough | Make sure nearby repeaters allow the same local region |
| Backbone traffic is missing | Check that at least some intentional backbone repeaters allow `nl` or `eu` |
| Wrong parent in the tree | Re-run `region put <child> <correct-parent>` and save |

#### Future smart routing

The region tree is also a foundation for smarter firmware later:

- smart repeaters that change filters under congestion
- regional routing instead of pure flooding
- automatic filtering based on observed airtime
- GPS-assisted region suggestions
- dense nationwide meshes with local, provincial and national layers
- airtime-aware forwarding where backbone repeaters carry more and local repeaters stay calm

For now, MeshCoreNG keeps this manual and predictable. Operators can build a useful hierarchy today, and future firmware can learn from that structure later.

## What Have We Deliberately Not Done Yet?

We have not built an automatic "AI mesh" yet.

Not automatic yet:

- changing advert intervals
- changing hop limits
- changing relay delays
- using node roles
- making route choices based on link quality
- changing the packet protocol for zones or regions

That is intentional. First we measure, then we automate.

If we make too much automatic too quickly, sparse networks could get worse or behavior could become unpredictable. MeshCoreNG therefore takes small, safe steps.

## Why Is This Useful?

In plain language:

MeshCoreNG tries to shout less when everyone can already hear each other.

In a quiet area, you want messages to travel far. In a busy city, you do not want every repeater to keep retransmitting every message again and again.

The new dense stats show how busy the network is. The new settings give us control to tune that behavior carefully.

## Useful Repeater Commands

```text
get dense.stats
clear dense.stats

get flood.advert.base
set flood.advert.base 0
set flood.advert.base 0.308
set flood.advert.base 1

get flood.relay.prob
set flood.relay.prob 0
set flood.relay.prob 128
set flood.relay.prob 255

get flood.dynamic.enable
set flood.dynamic.enable on
set flood.dynamic.enable off
```

**Internet bridge (TCP):**

```text
set wifi.ssid     <ssid>
set wifi.password <password>
set bridge.server <hostname or IP>
set bridge.port   4200
set bridge.enabled on
get bridge.type
```

**Dutch region database:**

```text
regiondb info
regiondb provinces
regiondb find <prefix>
regiondb get <index>
regiondb code <code_id>
```

**Regional mesh filtering:**

```text
region put <name> [parent]
region allowf <name>
region denyf <name>
region home <name>
region tree
region save
```

**Malformed chat handling:**

Companion radio firmware validates human-readable chat before it is shown to apps or displays. Invalid UTF-8, binary-looking text, excessive control characters, replacement characters, impossible timestamps and very low-confidence text are filtered at the chat rendering boundary. Binary datagrams, raw/custom packets, requests, responses and future packet types remain binary-safe.

By default malformed companion chat is shown as a compact filtered placeholder, so garbage text is not rendered in the Android/app side. Payloads that cannot be inspected, binary channel datagrams and unknown/future packet types are not blindly dropped.

Repeater firmware can be configured to drop malformed default-public-channel group text before retransmission:

```text
get malformed.drop
set malformed.drop on
set malformed.drop off
```

This is enabled by default on repeaters. Repeaters only drop text packets they can inspect and classify as malformed. Encrypted/private group text that the repeater cannot decrypt, binary datagrams and unknown/future packet types are still relayed according to the normal forwarding rules.

More CLI details are in [docs/cli_commands.md](./docs/cli_commands.md).

## Compatibility

MeshCoreNG remains compatible with the existing MeshCore ecosystem.

- No packet format change for these dense-mesh steps.
- Chat sanitation is applied only to human-readable chat display/forwarding policy; binary transport stays supported.
- Existing MeshCore clients keep working.
- Existing MeshCore firmware can still talk to MeshCoreNG.
- The default settings remain safe for normal and sparse networks.

## How To Start

- Flash MeshCoreNG repeater firmware on a supported device.
- Use an existing MeshCore client to connect.
- Use the CLI to view dense stats.
- Start safely with the default values.

For developers:

- Install [PlatformIO](https://docs.platformio.org) in [Visual Studio Code](https://code.visualstudio.com).
- Clone and open this MeshCoreNG repository.
- Look at the examples:
  - [Companion Radio](./examples/companion_radio)
  - [KISS Modem](./examples/kiss_modem)
  - [Simple Repeater](./examples/simple_repeater)
  - [Simple Room Server](./examples/simple_room_server)
  - [Simple Secure Chat](./examples/simple_secure_chat)
  - [Simple Sensor](./examples/simple_sensor)

## MeshCoreNG Web Flasher

MeshCoreNG now includes a GitHub Pages web flasher for supported release builds:

- MeshCoreNG web flasher: https://michtronics.github.io/MeshCoreNG/flasher/
- MeshCoreNG website and docs: https://michtronics.github.io/MeshCoreNG/

The flasher works from Chrome or Edge using Web Serial. ESP32-family boards flash from merged `.bin` files, and nRF52 boards flash from serial DFU `.zip` files when those assets are published. RP2040 and STM32 boards still use their normal firmware files and tools.

ESP32 repeater builds flashed from this site have malformed public chat dropping enabled by default. Check or change it after flashing with `get malformed.drop`, `set malformed.drop on`, or `set malformed.drop off`.

The firmware files used by the web flasher come from GitHub Release assets. The release/CI workflow builds the firmware variants and attaches the firmware files to the release. The GitHub Pages workflow publishes only a lightweight firmware index; the browser downloads the selected firmware from GitHub Releases when you press flash or download.

To add another board to the web flasher, add its PlatformIO environment name, display name, chip family, and description to `website/public/flasher/boards.json`. ESP32 release assets must be named like `<env>-*-merged.bin`; nRF52 DFU release assets must be named like `<env>-*.zip`.

When a new GitHub Release is published, the GitHub Pages workflow uses that release tag, downloads the release firmware assets, and updates the web flasher to use exactly those files. On a normal `main` build or manual Pages run, it uses the latest published release.

## MeshCore Flasher And Clients

MeshCoreNG does not yet have its own clients.

For now, use the upstream MeshCore tools and clients:

- MeshCore flasher: https://meshcore.io/flasher
- Web client: https://app.meshcore.nz
- Config tool: https://config.meshcore.io
- MeshCore docs: https://docs.meshcore.io

## Credits

MeshCoreNG exists because of the work done by the MeshCore community.

- [MeshCore](https://github.com/meshcore-dev/MeshCore) is the original project, protocol, firmware base, and ecosystem.
- [MeshCore-Evo](https://github.com/mattzzw/MeshCore-Evo) inspired dense-mesh repeater improvements and reduced flood advert traffic.

## Direction For The Future

The next logical steps are:

- Further refine rolling-window statistics.
- Measure link quality per neighbor.
- Add node roles, such as client, relay, backbone, and sensor.
- Reduce only low-priority traffic under congestion.
- Enable automatic tuning later.
- Prepare for hybrid routed + flooded mesh later.

The end goal is a more scalable LoRa MANET network: simple where possible, smarter where needed.

## License

MeshCoreNG is based on MeshCore and is distributed under the MIT License.
