# MeshCoreNG

MeshCoreNG is a Next Gen variant of MeshCore. It builds on the existing firmware and protocol to make repeaters smarter in dense networks — without breaking compatibility with existing clients.

## What is different from MeshCore?

MeshCoreNG adds:

- **Dense-mesh controls** — tune how aggressively repeaters forward flood adverts.
- **Dense stats** — real-time network telemetry per repeater.
- **Bridge firmware** — TCP, RS232 and ESP-NOW bridge variants for controlled transport between selected RF deployments.
- **USB bridge** — connect RS232 bridge repeaters without WiFi via a USB relay script.
- **Web flasher** — browser flashing and firmware downloads backed by GitHub Release assets.
- **Regional tooling** — Dutch region lookup data and region profile support for deployments that need scoped forwarding.
- **Better channel detection** — hardware CAD scan before transmitting.
- **Power saving** — configurable sleep with transparent controls.
- **Malformed chat filtering** — sanitize companion chat display and drop malformed public chat at repeaters by default without breaking binary payloads.
- **Atlas foundation** — disabled-by-default telemetry structures for future topology, observer and network-health tools.

Everything else stays the same. Existing MeshCore clients, apps and firmware keep working.

## Quick links

- [Getting started](/docs/getting-started)
- [Dense mesh](/docs/dense-mesh)
- [Internet bridge](/docs/bridge)
- [Web flasher](/docs/flasher)
- [Regions](/docs/regions)
- [Atlas telemetry](/docs/atlas)
- [Setting up the WiFi TCP bridge](/docs/tcp-bridge)
- [WiFi TCP bridge instellen](/docs/tcp-bridge-nl)
- [Power saving](/docs/power-saving)
- [CLI reference](/docs/cli)
- [CLI App — downloads & releases](/docs/cli-app)
- [Flash firmware](/flasher/)
- [GitHub repository](https://github.com/MichTronics/MeshCoreNG)
- [MeshCore upstream docs](https://docs.meshcore.io)
