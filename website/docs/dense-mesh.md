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

## Retransmit spreading

`txdelay` spreads flood retransmits before packets enter the TX queue:

```
get txdelay
set txdelay <0.0 .. 2.0>
```

When `txdelay` is above `0`, MeshCoreNG adds a small deterministic per-node offset on top of the existing random delay:

```
final flood delay = random txdelay spread + stable node offset
```

The offset is based on the node identity already stored in firmware, so it is stable across reboot and does not require extra traffic, a protocol change, or a packet format change. It is deliberately small and only applies to flood retransmit scheduling. `set txdelay 0` keeps zero-delay behavior and disables the node offset.

CAD retry is a different layer. CAD retry happens after the radio has detected a busy channel; the current retry window is 120-360 ms. The node offset helps earlier by preventing repeaters that heard the same packet at the same time from lining up perfectly.

Suggested tuning:

| Repeater role | Guidance |
|---|---|
| Local / low-site repeater | Use a lower `txdelay` for local responsiveness. |
| High-site / backbone repeater | Use a higher `txdelay` so nearby repeaters can handle local traffic first. |
| Dense city group | Keep `txdelay` enabled to combine random spread with the stable node offset. |

## Duplicate-hearing suppression

In a dense mesh, a repeater may schedule a flood retransmit and then hear nearby repeaters forwarding the same packet before its own timer expires. MeshCoreNG uses that duplicate-hearing signal to cancel redundant retransmits.

Default behavior:

| Case | Result |
|---|---|
| No duplicates heard | Retransmit still happens. |
| One duplicate heard | Retransmit is kept. |
| Two or more duplicates heard | Pending retransmit is cancelled. |

Only queued retransmits of received flood packets are suppressible. Locally generated packets, ACKs, direct packets, path/control packets and trace/control traffic are kept. This keeps sparse networks working while reducing duplicate floods in dense groups.

The threshold is compile-time configurable with `MESH_DUP_SUPPRESS_THRESHOLD`; the default is `2`.

## Dynamic mode

Dynamic mode is available but does not yet change behavior automatically. Enable it to collect data:

```
set flood.dynamic.enable on
```

Automatic tuning will be added once enough real-world data has been collected. Default is off.
