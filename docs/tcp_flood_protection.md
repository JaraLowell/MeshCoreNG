# TCP Flood Protection

## Overview

TCP flood protection is a **selective rate limiting** feature that monitors incoming packets from the TCP bridge and prevents mass flooding of the mesh network. The system distinguishes between different packet types and applies appropriate rate limits:

- **Transport/Message packets** (DMs, group messages): Strict rate limits to prevent spam
- **Control/Admin packets** (discovery, adverts, ACKs): Higher limits or bypass to ensure network operation
- **Other packets**: No limits by default

When enabled, each category tracks packets within its own time window. When a category exceeds its threshold, only packets of that type are dropped - other categories continue to flow normally.

The Python TCP bridge server also has a server-side transport limiter. It drops excessive DM/group/transport packets before broadcasting them to other bridge clients. This limiter is based on the TCP bridge client and packet category, not on MeshCore node name or advertised identity, so changing names or node IDs does not bypass it.

## Packet Categories

### Transport/Message Packets
Direct messages, group messages, requests, responses, and multipart messages. These are typically user-generated content that should be rate-limited to prevent spam.

**Packet types:**
- `TXT_MSG` - Direct text messages
- `GRP_TXT` / `GRP_DATA` - Group messages and data
- `REQ` / `RESPONSE` / `ANON_REQ` - Request/response pairs
- `MULTIPART` - Large messages split across packets
- Any packet with `TRANSPORT_FLOOD` or `TRANSPORT_DIRECT` routing

### Control/Admin Packets
Network control messages essential for mesh operation. These can bypass flood protection or use much higher limits.

**Packet types:**
- `CONTROL` - Discovery and network control
- `ADVERT` - Node advertisements
- `ACK` - Acknowledgments
- `TRACE` / `PATH` - Path tracing and routing
- `ATLAS` - Telemetry data

## Configuration

### Python TCP Bridge Server Protection

The server-side limiter is enabled by default:

```bash
python3 tools/tcp_bridge_server.py \
  --transport-rate-limit on \
  --transport-rate-max 20 \
  --transport-rate-window 120 \
  --transport-global-rate-max 80 \
  --transport-global-rate-window 120
```

With `tools/tcp_bridge_server_ctl.sh`, use environment variables:

```bash
TCP_BRIDGE_TRANSPORT_RATE_LIMIT=on
TCP_BRIDGE_TRANSPORT_RATE_MAX=20
TCP_BRIDGE_TRANSPORT_RATE_WINDOW=120
TCP_BRIDGE_TRANSPORT_GLOBAL_RATE_MAX=80
TCP_BRIDGE_TRANSPORT_GLOBAL_RATE_WINDOW=120
tools/tcp_bridge_server_ctl.sh restart
```

For an active DM flood, a stricter temporary setup is:

```bash
TCP_BRIDGE_TRANSPORT_RATE_MAX=10
TCP_BRIDGE_TRANSPORT_RATE_WINDOW=120
TCP_BRIDGE_TRANSPORT_GLOBAL_RATE_MAX=40
TCP_BRIDGE_TRANSPORT_GLOBAL_RATE_WINDOW=120
tools/tcp_bridge_server_ctl.sh restart
```

`0` disables only the corresponding max cap. For example, `--transport-global-rate-max 0` keeps per-client limiting but disables the global cap.

### Basic Flood Protection (Legacy)

Global settings that apply when selective protection is not configured:

```bash
get tcp.flood.limit       # Check if enabled
set tcp.flood.limit on    # Enable flood protection
set tcp.flood.max 100     # Max packets (1-10000)
set tcp.flood.window 600  # Time window in seconds (1-3600)
```

### Selective Transport Flood Protection (Recommended)

Configure rate limits specifically for transport/message packets:

```bash
# Enable flood protection first
set tcp.flood.limit on

# Configure transport limits (recommended: 22 packets per 2 minutes)
get tcp.flood.transport.max
set tcp.flood.transport.max 22

get tcp.flood.transport.window
set tcp.flood.transport.window 120
```

**Parameters:**
- `max`: Integer from `1` to `10000`, maximum transport packets in time window
- `window`: Integer from `1` to `3600` seconds (time window duration)

**Default:** `20` packets per `120` seconds (2 minutes)

### Control Packet Flood Protection

Configure rate limits for control/admin packets (or bypass):

```bash
# Configure control limits (500 packets per 2 minutes)
get tcp.flood.control.max
set tcp.flood.control.max 500

# Or bypass control packets entirely (recommended)
set tcp.flood.control.max 0

get tcp.flood.control.window
set tcp.flood.control.window 120
```

**Parameters:**
- `max`: Integer from `0` to `10000` (`0` = bypass, no limit on control packets)
- `window`: Integer from `1` to `3600` seconds

**Default:** `20` packets per `120` seconds

## How It Works

1. When a packet arrives from the TCP bridge, the system first checks if it's a bridge control packet (MCNG heartbeat) - these always bypass
2. If flood protection is enabled, the packet header is examined to determine its category
3. The appropriate rate limiter is checked:
   - **Transport packets**: Checked against `tcp.flood.transport.max` / `tcp.flood.transport.window`
   - **Control packets**: Checked against `tcp.flood.control.max` / `tcp.flood.control.window` (or bypass if max=0)
   - **Other packets**: No rate limit applied
4. If the limit is exceeded, only that specific packet category is dropped - others continue normally
5. Dropped packets are counted separately per category and displayed in status

## Example Configurations

### Recommended: Block transport floods while allowing control
```bash
set tcp.flood.limit on
set tcp.flood.transport.max 20        # Only 20 DMs/group messages per 2 min
set tcp.flood.transport.window 120
set tcp.flood.control.max 0           # Control packets bypass (no limit)
```

### Moderate: Limit both categories with same thresholds
```bash
set tcp.flood.limit on
set tcp.flood.transport.max 20        # 20 messages per 2 min
set tcp.flood.transport.window 120
set tcp.flood.control.max 20          # 20 control packets per 2 min
set tcp.flood.control.window 120
```

### Strict: Very tight limits for high-security networks
```bash
set tcp.flood.limit on
set tcp.flood.transport.max 10
set tcp.flood.transport.window 60
set tcp.flood.control.max 100
set tcp.flood.control.window 60
```

### Check current status:

```bash
get tcp.flood.limit
get tcp.flood.transport.max
get tcp.flood.transport.window
get tcp.flood.control.max
get tcp.flood.control.window
get wifi.status    # Shows drop counts per category
```

The `wifi.status` command will show the number of dropped packets if flood protection is active:

```
> WiFi: connected | IP: 192.168.1.100 | RSSI: -45 dBm | Server: connected | Flood dropped: 23
```

## Use Cases

- **Prevent DoS attacks**: Protect your mesh network from malicious flood attacks via the TCP bridge
- **Rate limiting**: Control the maximum traffic flow from the TCP bridge to prevent overwhelming the mesh network
- **Quality of Service**: Ensure fair resource allocation by limiting burst traffic from individual bridge connections
- **Network stability**: Maintain stable mesh operation even when the TCP bridge receives excessive traffic

## Technical Details

The flood protection uses a sliding time window algorithm:
- Packets are counted within the current time window
- When the window expires (current time > window start + window duration), the counter resets
- The check is performed before packet parsing and relay, minimizing resource usage
- Dropped packets are logged for debugging (when BRIDGE_DEBUG is enabled)

## Notes

- Flood protection only applies to data packets from TCP, not control packets (heartbeats, auth, node info)
- Settings take effect immediately and require a bridge restart (automatic when using `set` commands)
- The dropped packet counter persists until the bridge is restarted
- Scoped transport packets are also subject to flood protection to prevent abuse
