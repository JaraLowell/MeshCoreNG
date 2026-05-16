## MeshCoreNG

MeshCoreNG is a Next Gen variant of MeshCore.

In simple terms: MeshCore lets LoRa devices pass messages to each other without the internet. MeshCoreNG builds on that and focuses on making repeaters smarter, so larger and busier networks can keep working better.

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

## What Have We Deliberately Not Done Yet?

We have not built an automatic "AI mesh" yet.

Not automatic yet:

- changing advert intervals
- changing hop limits
- changing relay delays
- using node roles
- making route choices based on link quality
- adding zones or regions to the packet protocol

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

More CLI details are in [docs/cli_commands.md](./docs/cli_commands.md).

## Compatibility

MeshCoreNG remains compatible with the existing MeshCore ecosystem.

- No packet format change for these dense-mesh steps.
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

MeshCoreNG now includes a GitHub Pages web flasher for ESP32-based repeater builds:

- MeshCoreNG web flasher: https://michtronics.github.io/MeshCoreNG/flasher/

The flasher is built with ESP Web Tools and works from Chrome or Edge using Web Serial. It is meant for ESP32-family boards. nRF52, RP2040 and STM32 boards still use their normal flashing files and tools.

The firmware files used by the web flasher are built by GitHub Actions. The workflow builds the ESP32 repeater variants listed in [webflasher/boards.json](./webflasher/boards.json), creates ESP Web Tools manifests for them, and publishes everything to GitHub Pages under `/flasher/`.

To add another ESP32 board to the web flasher, add its PlatformIO environment name, display name, chip family, and description to `webflasher/boards.json`. GitHub will build it during the Pages workflow.

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
