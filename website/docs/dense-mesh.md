# Dense mesh

## The problem

In a flood mesh, every repeater re-broadcasts every packet it hears. In a sparse rural area this is exactly what you want — maximum propagation. In a dense urban area it causes too many redundant retransmissions, filling the LoRa channel and slowing the network.

The Netherlands has many repeaters close together, so this problem shows up quickly. EU868 duty-cycle limits make every unnecessary retransmission expensive.

## Dense stats

Before changing anything, check what is actually happening:

```
get dense.stats
```

This shows:

| Field | Description |
|---|---|
| flood_advert_rx | Flood adverts received |
| flood_advert_fwd | Flood adverts forwarded |
| flood_advert_drop | Flood adverts dropped |
| flood_dup_packets | Duplicate flood packets seen |
| airtime_rx_ms | Estimated RX airtime (ms) |
| airtime_tx_ms | Estimated TX airtime (ms) |
| cad_busy | CAD / channel-busy events |
| density | Local node density estimate |
| congestion | Channel congestion estimate |

Reset counters with:

```
clear dense.stats
```

Stats are RAM-only and reset on reboot.

## Flood advert forwarding

Control how aggressively flood adverts are forwarded:

```
get flood.advert.base
set flood.advert.base <0.0 .. 1.0>
```

| Value | Effect |
|---|---|
| `0` | Never forward received flood adverts |
| `0.308` | Dense-mesh default — reduces forwarding as hop count grows |
| `1` | Forward everything (original MeshCore behavior) |

The default is `0.308`. Existing networks keep working because the default is already applied.

## Relay probability

Manually reduce how many flood packets are relayed:

```
get flood.relay.prob
set flood.relay.prob <0 .. 255>
```

| Value | Effect |
|---|---|
| `0` | Relay nothing |
| `128` | Relay approximately half |
| `255` | Relay everything allowed (default) |

## Dynamic mode

Dynamic mode is available but does not yet change behavior automatically. Enable it to collect data:

```
set flood.dynamic.enable on
```

Automatic tuning will be added once enough real-world data has been collected. Default is off.
