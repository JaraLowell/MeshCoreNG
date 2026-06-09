#!/usr/bin/env python3
"""
MeshCore TCP Bridge Server

Forwards mesh packets between connected repeaters so geographically separated
LoRa networks can act as one mesh. Each packet received from one repeater is
broadcast to all other connected repeaters.

Usage:
    python3 tcp_bridge_server.py [--host 0.0.0.0] [--port 4200] [--password bridgeSecret]
    open http://localhost:8080/ for connected node status

Repeater firmware configuration (via CLI):
    set wifi.ssid    <your-wifi>
    set wifi.password <your-password>
    set bridge.server <this-server-ip-or-hostname>
    set bridge.port   4200
    set bridge.password <bridgeSecret>  # only when server --password is set
    set bridge.enabled on

Requires Python 3.7+, no external dependencies.
"""

import asyncio
import argparse
import binascii
from collections import deque
import html
import json
import logging
import struct
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("tcp_bridge")

BRIDGE_MAGIC = 0xC03E
MAX_PAYLOAD = 256   # MAX_TRANS_UNIT + 1
CONTROL_PREFIX = b"MCNG"
CONTROL_TYPE_HEARTBEAT = 0x01
CONTROL_TYPE_NODE_INFO = 0x02
CONTROL_TYPE_AUTH = 0x03
PAYLOAD_TYPE_LOCATION = 0x0D
PH_ROUTE_MASK = 0x03
PH_TYPE_SHIFT = 2
ROUTE_TYPE_TRANSPORT_FLOOD = 0x00
ROUTE_TYPE_TRANSPORT_DIRECT = 0x03
LOG_PACKETS = False
LOG_HEX_BYTES = 32
CLIENT_TIMEOUT_SECS = 180
STATUS_INTERVAL_SECS = 60
PACKET_COUNTER_WINDOW_SECS = 24 * 60 * 60
REPLACE_SAME_IP = False
BRIDGE_PASSWORD = ""

connected_clients: set["BridgeClient"] = set()
latest_locations: dict[str, dict] = {}


def fletcher16(data: bytes) -> int:
    s1, s2 = 0, 0
    for b in data:
        s1 = (s1 + b) % 255
        s2 = (s2 + s1) % 255
    return (s2 << 8) | s1


def payload_preview(payload: bytes) -> str:
    shown = payload[:LOG_HEX_BYTES]
    text = binascii.hexlify(shown, sep=" ").decode("ascii")
    if len(payload) > len(shown):
        text += " ..."
    return text


def parse_heartbeat(payload: bytes) -> int | None:
    if len(payload) < 5:
        return None
    if not payload.startswith(CONTROL_PREFIX):
        return None
    if payload[4] != CONTROL_TYPE_HEARTBEAT:
        return None
    if len(payload) >= 9:
        return struct.unpack(">I", payload[5:9])[0]
    return 0


def parse_node_info(payload: bytes) -> tuple[str, str] | None:
    if len(payload) < 6:
        return None
    if not payload.startswith(CONTROL_PREFIX):
        return None
    if payload[4] != CONTROL_TYPE_NODE_INFO:
        return None

    name_len = payload[5]
    raw_name = payload[6:6 + name_len]
    if len(raw_name) != name_len:
        return None

    name = raw_name.decode("utf-8", errors="replace").strip()[:32]

    firmware = ""
    version_pos = 6 + name_len
    if len(payload) > version_pos:
        version_len = payload[version_pos]
        raw_version = payload[version_pos + 1:version_pos + 1 + version_len]
        if len(raw_version) == version_len:
            firmware = raw_version.decode("utf-8", errors="replace").strip()[:32]

    return name, firmware


def parse_auth(payload: bytes) -> str | None:
    if len(payload) < 6:
        return None
    if not payload.startswith(CONTROL_PREFIX):
        return None
    if payload[4] != CONTROL_TYPE_AUTH:
        return None

    password_len = payload[5]
    raw_password = payload[6:6 + password_len]
    if len(raw_password) != password_len:
        return None

    return raw_password.decode("utf-8", errors="replace")


def parse_location_report(payload: bytes) -> dict | None:
    if len(payload) < 32:
        return None
    if payload[:4] != b"MCL1" or payload[4] != 1:
        return None

    name_len = payload[31]
    if name_len > 24 or len(payload) < 32 + name_len:
        return None

    lat_microdeg = struct.unpack(">i", payload[10:14])[0]
    lon_microdeg = struct.unpack(">i", payload[14:18])[0]
    altitude_m = struct.unpack(">h", payload[18:20])[0]
    speed_cms = struct.unpack(">H", payload[20:22])[0]
    heading_cdeg = struct.unpack(">H", payload[22:24])[0]
    battery_mv = struct.unpack(">H", payload[25:27])[0]
    timestamp = struct.unpack(">I", payload[27:31])[0]
    name = payload[32:32 + name_len].decode("utf-8", errors="replace").strip()

    return {
        "version": payload[4],
        "flags": payload[5],
        "node_id": binascii.hexlify(payload[6:10]).decode("ascii"),
        "lat": lat_microdeg / 1000000.0,
        "lon": lon_microdeg / 1000000.0,
        "altitude_m": altitude_m,
        "speed_kmh": round(speed_cms * 0.036, 2),
        "heading_deg": round(heading_cdeg / 100.0, 2),
        "satellites": payload[24],
        "battery_mv": battery_mv,
        "timestamp": timestamp,
        "name": name,
    }


def parse_mesh_location_payload(frame_payload: bytes) -> dict | None:
    if len(frame_payload) < 2:
        return None

    header = frame_payload[0]
    payload_type = (header >> PH_TYPE_SHIFT) & 0x0F
    if payload_type != PAYLOAD_TYPE_LOCATION:
        return None

    route_type = header & PH_ROUTE_MASK
    pos = 1
    if route_type in (ROUTE_TYPE_TRANSPORT_FLOOD, ROUTE_TYPE_TRANSPORT_DIRECT):
        if len(frame_payload) < pos + 4:
            return None
        pos += 4

    if len(frame_payload) <= pos:
        return None
    path_len = frame_payload[pos]
    pos += 1
    path_hash_size = (path_len >> 6) + 1
    path_hash_count = path_len & 63
    path_bytes = path_hash_size * path_hash_count
    if len(frame_payload) < pos + path_bytes:
        return None
    pos += path_bytes

    return parse_location_report(frame_payload[pos:])


def record_location(report: dict, client: "BridgeClient") -> None:
    now = time.time()
    report = dict(report)
    report["received_at"] = int(now)
    report["age_seconds"] = 0
    report["source"] = client.display_name
    latest_locations[report["node_id"]] = report


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def format_sockaddrs(sockets) -> str:
    return ", ".join(
        f"{sock.getsockname()[0]}:{sock.getsockname()[1]}"
        for sock in sockets or []
    )


def prune_packet_times(packet_times: deque[float], now: float) -> None:
    cutoff = now - PACKET_COUNTER_WINDOW_SECS
    while packet_times and packet_times[0] < cutoff:
        packet_times.popleft()


class BridgeClient:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        addr = writer.get_extra_info("peername")
        self.host = addr[0] if addr else "unknown"
        self.port = addr[1] if addr else 0
        self.addr = f"{self.host}:{self.port}" if addr else "unknown"
        self.packets_rx = 0
        self.packets_tx = 0
        self.packet_rx_times: deque[float] = deque()
        self.packet_tx_times: deque[float] = deque()
        self.heartbeats_rx = 0
        self._connect_time = time.time()
        self.last_seen = self._connect_time
        self.last_heartbeat = 0.0
        self.node_name = ""
        self.firmware_version = ""
        self.authenticated = not BRIDGE_PASSWORD

    @property
    def display_name(self) -> str:
        return self.node_name or self.addr

    def status_dict(self, now: float) -> dict:
        prune_packet_times(self.packet_rx_times, now)
        prune_packet_times(self.packet_tx_times, now)
        return {
            "name": self.node_name,
            "firmware_version": self.firmware_version,
            "display_name": self.display_name,
            "connected_seconds": int(now - self._connect_time),
            "connected_for": format_duration(now - self._connect_time),
            "idle_seconds": int(now - self.last_seen),
            "heartbeat_age_seconds": int(now - self.last_heartbeat) if self.last_heartbeat else None,
            "packets_rx": self.packets_rx,
            "packets_tx": self.packets_tx,
            "packets_rx_24h": len(self.packet_rx_times),
            "packets_tx_24h": len(self.packet_tx_times),
            "heartbeats_rx": self.heartbeats_rx,
            "authenticated": self.authenticated,
        }

    async def read_packet(self) -> bytes | None:
        """Read one framed packet from the stream. Returns raw payload bytes or None on error."""
        # Find magic header
        buf = bytearray()
        while True:
            b = await self.reader.readexactly(1)
            buf.append(b[0])
            if len(buf) >= 2:
                if buf[-2] == (BRIDGE_MAGIC >> 8) & 0xFF and buf[-1] == BRIDGE_MAGIC & 0xFF:
                    break
                # Keep only last byte as potential first magic byte
                buf = bytearray([buf[-1]])

        # Read 2-byte length
        raw_len = await self.reader.readexactly(2)
        length = struct.unpack(">H", raw_len)[0]

        if length == 0 or length > MAX_PAYLOAD:
            log.warning("%s: invalid payload length %d, discarding", self.addr, length)
            return None

        # Read payload + 2-byte checksum
        payload = await self.reader.readexactly(length)
        raw_csum = await self.reader.readexactly(2)
        received_csum = struct.unpack(">H", raw_csum)[0]

        calculated_csum = fletcher16(payload)
        if received_csum != calculated_csum:
            log.warning(
                "%s: checksum mismatch (got 0x%04x, expected 0x%04x)",
                self.addr, received_csum, calculated_csum,
            )
            return None

        self.last_seen = time.time()
        return bytes(payload)

    def build_frame(self, payload: bytes) -> bytes:
        """Wrap a payload in the bridge framing."""
        length = len(payload)
        csum = fletcher16(payload)
        return (
            struct.pack(">H", BRIDGE_MAGIC)
            + struct.pack(">H", length)
            + payload
            + struct.pack(">H", csum)
        )

    async def send_payload(self, payload: bytes) -> bool:
        try:
            self.writer.write(self.build_frame(payload))
            await self.writer.drain()
            self.packets_tx += 1
            now = time.time()
            self.packet_tx_times.append(now)
            prune_packet_times(self.packet_tx_times, now)
            if LOG_PACKETS:
                log.info("%s: TX %d bytes: %s", self.addr, len(payload), payload_preview(payload))
            return True
        except Exception:
            return False

    def close(self):
        try:
            self.writer.close()
        except Exception:
            pass


async def broadcast(payload: bytes, sender: "BridgeClient"):
    """Forward payload to every connected client except the sender."""
    dead = set()
    for client in connected_clients:
        if client is sender:
            continue
        ok = await client.send_payload(payload)
        if not ok:
            dead.add(client)

    for client in dead:
        await disconnect(client, reason="send error")


async def disconnect(client: "BridgeClient", reason: str = "EOF"):
    if client in connected_clients:
        connected_clients.discard(client)
        client.close()
        uptime = int(time.time() - client._connect_time)
        log.info(
            "Disconnected %s [%s] (%s) — rx=%d tx=%d hb=%d uptime=%ds",
            client.addr, client.display_name, reason, client.packets_rx, client.packets_tx, client.heartbeats_rx, uptime,
        )


async def status_task():
    while True:
        if STATUS_INTERVAL_SECS <= 0:
            return
        await asyncio.sleep(STATUS_INTERVAL_SECS)
        now = time.time()
        for client in list(connected_clients):
            idle = int(now - client.last_seen)
            if CLIENT_TIMEOUT_SECS > 0 and idle > CLIENT_TIMEOUT_SECS:
                await disconnect(client, reason=f"idle timeout {idle}s")

        if connected_clients:
            summaries = []
            for client in sorted(connected_clients, key=lambda c: c.addr):
                prune_packet_times(client.packet_rx_times, now)
                prune_packet_times(client.packet_tx_times, now)
                summaries.append(
                    f"{client.display_name}@{client.addr} connected={format_duration(now - client._connect_time)} "
                    f"idle={int(now - client.last_seen)}s "
                    f"hb_age={str(int(now - client.last_heartbeat)) + 's' if client.last_heartbeat else 'never'} "
                    f"rx24h={len(client.packet_rx_times)} tx24h={len(client.packet_tx_times)} "
                    f"rx={client.packets_rx} tx={client.packets_tx} hb={client.heartbeats_rx}"
                )
            summary = ", ".join(summaries)
            log.info("Connected clients (%d): %s", len(connected_clients), summary)
        else:
            log.info("Connected clients: none")


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    client = BridgeClient(reader, writer)
    if REPLACE_SAME_IP:
        for existing in list(connected_clients):
            if existing.host == client.host:
                await disconnect(existing, reason=f"replaced by new connection from {client.addr}")

    connected_clients.add(client)
    log.info("Connected %s (total=%d)", client.addr, len(connected_clients))

    try:
        while True:
            payload = await client.read_packet()
            if payload is None:
                continue
            auth_password = parse_auth(payload)
            if auth_password is not None:
                if not BRIDGE_PASSWORD or auth_password == BRIDGE_PASSWORD:
                    client.authenticated = True
                    log.info("%s: bridge auth ok", client.addr)
                else:
                    log.warning("%s: bridge auth failed", client.addr)
                    await disconnect(client, reason="auth failed")
                    return
                continue
            if not client.authenticated:
                log.warning("%s: missing bridge auth", client.addr)
                await disconnect(client, reason="missing auth")
                return
            heartbeat_uptime = parse_heartbeat(payload)
            if heartbeat_uptime is not None:
                client.heartbeats_rx += 1
                client.last_heartbeat = time.time()
                log.debug("%s: heartbeat uptime=%dms", client.addr, heartbeat_uptime)
                continue
            node_name = parse_node_info(payload)
            if node_name is not None:
                client.node_name, client.firmware_version = node_name
                if client.firmware_version:
                    log.info("%s: node name is %s firmware=%s",
                             client.addr, client.node_name, client.firmware_version)
                else:
                    log.info("%s: node name is %s", client.addr, client.node_name)
                continue
            client.packets_rx += 1
            now = time.time()
            client.packet_rx_times.append(now)
            prune_packet_times(client.packet_rx_times, now)
            location_report = parse_mesh_location_payload(payload)
            if location_report is not None:
                record_location(location_report, client)
            if LOG_PACKETS:
                log.info("%s: RX %d bytes: %s", client.addr, len(payload), payload_preview(payload))
            log.debug("%s: RX %d bytes → broadcasting to %d peers",
                      client.addr, len(payload), len(connected_clients) - 1)
            await broadcast(payload, sender=client)
    except asyncio.IncompleteReadError:
        await disconnect(client, reason="EOF")
    except Exception as exc:
        await disconnect(client, reason=str(exc))


def status_snapshot() -> dict:
    now = time.time()
    clients = [
        client.status_dict(now)
        for client in sorted(connected_clients, key=lambda c: (c.display_name.lower(), c.addr))
    ]
    return {
        "generated_at": int(now),
        "connected_count": len(clients),
        "clients": clients,
    }


def locations_snapshot() -> dict:
    now = int(time.time())
    locations = []
    for report in latest_locations.values():
        item = dict(report)
        item["age_seconds"] = max(0, now - item["received_at"])
        locations.append(item)
    locations.sort(key=lambda item: (item.get("name") or item["node_id"]).lower())
    return {
        "generated_at": now,
        "location_count": len(locations),
        "locations": locations,
    }


def build_status_html() -> str:
    snapshot = status_snapshot()
    rows = []
    for client in snapshot["clients"]:
        hb_age = client["heartbeat_age_seconds"]
        heartbeat = f"{hb_age}s ago" if hb_age is not None else "never"
        rows.append(
            "<tr>"
            f"<td>{html.escape(client['display_name'])}</td>"
            f"<td>{html.escape(client['firmware_version'] or 'unknown')}</td>"
            f"<td>{html.escape(client['connected_for'])}</td>"
            f"<td>{client['idle_seconds']}s</td>"
            f"<td>{heartbeat}</td>"
            f"<td>{client['packets_rx_24h']}</td>"
            f"<td>{client['packets_tx_24h']}</td>"
            f"<td>{client['packets_rx']}</td>"
            f"<td>{client['packets_tx']}</td>"
            f"<td>{client['heartbeats_rx']}</td>"
            "</tr>"
        )

    rows_html = "\n".join(rows) if rows else (
        '<tr><td colspan="10" class="empty">No bridge nodes connected</td></tr>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="10">
  <title>MeshCoreNG TCP Bridge Status</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #f4f6f8; color: #1b1f24; }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 32px 20px; }}
    h1 {{ margin: 0 0 6px; font-size: clamp(1.6rem, 4vw, 2.4rem); }}
    .summary {{ margin: 0 0 24px; color: #58606a; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid #d8dee4; white-space: nowrap; }}
    th {{ background: #eef2f6; font-size: 0.8rem; text-transform: uppercase; color: #47515d; }}
    tr:last-child td {{ border-bottom: 0; }}
    .empty {{ text-align: center; color: #69737f; padding: 32px; }}
    @media (max-width: 760px) {{
      main {{ padding: 20px 12px; }}
      .table-wrap {{ overflow-x: auto; }}
      th, td {{ padding: 10px 12px; }}
    }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #111418; color: #f0f3f6; }}
      .summary {{ color: #9aa4af; }}
      table {{ background: #171b20; border-color: #30363d; }}
      th, td {{ border-color: #30363d; }}
      th {{ background: #20262d; color: #c8d0d8; }}
      .empty {{ color: #9aa4af; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>MeshCoreNG TCP Bridge Status</h1>
    <p class="summary">{snapshot['connected_count']} connected node(s). Auto-refreshes every 10 seconds. <a href="/map">Tracker map</a></p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Node</th>
            <th>Firmware</th>
            <th>Connected</th>
            <th>Idle</th>
            <th>Heartbeat</th>
            <th>RX 24h</th>
            <th>TX 24h</th>
            <th>RX</th>
            <th>TX</th>
            <th>HB</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </main>
</body>
</html>
"""


def build_location_map_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MeshCoreNG Tracker Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    html, body, #map { height: 100%; margin: 0; }
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .topbar {
      position: absolute; z-index: 1000; top: 12px; left: 12px; right: 12px;
      display: flex; gap: 12px; align-items: center; justify-content: space-between;
      background: rgba(255, 255, 255, 0.92); border: 1px solid #d8dee4;
      border-radius: 8px; padding: 10px 12px; box-shadow: 0 2px 10px rgba(0,0,0,.08);
    }
    .topbar h1 { margin: 0; font-size: 1rem; }
    .topbar a { color: #0969da; text-decoration: none; }
    .muted { color: #57606a; font-size: .9rem; }
  </style>
</head>
<body>
  <div class="topbar">
    <h1>MeshCoreNG Tracker Map</h1>
    <span class="muted" id="summary">Loading...</span>
    <a href="/">Bridge status</a>
  </div>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const map = L.map('map').setView([52.2, 5.3], 8);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);
    const markers = new Map();

    function fmtAge(seconds) {
      if (seconds < 60) return `${seconds}s`;
      if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
      return `${Math.floor(seconds / 3600)}h`;
    }

    async function refresh() {
      const res = await fetch('/locations.json', { cache: 'no-store' });
      const data = await res.json();
      document.getElementById('summary').textContent = `${data.location_count} tracker node(s)`;
      const seen = new Set();
      for (const loc of data.locations) {
        seen.add(loc.node_id);
        const label = loc.name || loc.node_id;
        const popup = `<strong>${label}</strong><br>` +
          `Node: ${loc.node_id}<br>` +
          `Age: ${fmtAge(loc.age_seconds)}<br>` +
          `Sats: ${loc.satellites}<br>` +
          `Battery: ${loc.battery_mv} mV<br>` +
          `Alt: ${loc.altitude_m} m`;
        let marker = markers.get(loc.node_id);
        if (!marker) {
          marker = L.marker([loc.lat, loc.lon]).addTo(map);
          markers.set(loc.node_id, marker);
        } else {
          marker.setLatLng([loc.lat, loc.lon]);
        }
        marker.bindPopup(popup);
      }
      for (const [nodeId, marker] of markers) {
        if (!seen.has(nodeId)) {
          marker.remove();
          markers.delete(nodeId);
        }
      }
      if (data.locations.length && !refresh.didFit) {
        const bounds = data.locations.map(loc => [loc.lat, loc.lon]);
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
        refresh.didFit = true;
      }
    }

    refresh();
    setInterval(refresh, 10000);
  </script>
</body>
</html>
"""


async def handle_http_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        request_line = await reader.readline()
        parts = request_line.decode("ascii", errors="ignore").strip().split()
        if len(parts) < 2 or parts[0] != "GET":
            status, content_type, body = "405 Method Not Allowed", "text/plain", b"Method not allowed\n"
        elif parts[1] == "/status.json":
            status, content_type = "200 OK", "application/json"
            body = json.dumps(status_snapshot(), indent=2).encode("utf-8")
        elif parts[1] == "/locations.json":
            status, content_type = "200 OK", "application/json"
            body = json.dumps(locations_snapshot(), indent=2).encode("utf-8")
        elif parts[1] == "/map":
            status, content_type = "200 OK", "text/html; charset=utf-8"
            body = build_location_map_html().encode("utf-8")
        elif parts[1] in ("/", "/status"):
            status, content_type = "200 OK", "text/html; charset=utf-8"
            body = build_status_html().encode("utf-8")
        else:
            status, content_type, body = "404 Not Found", "text/plain", b"Not found\n"

        while True:
            line = await reader.readline()
            if not line or line in (b"\r\n", b"\n"):
                break

        headers = (
            f"HTTP/1.1 {status}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "Cache-Control: no-store\r\n"
            "\r\n"
        ).encode("ascii")
        writer.write(headers + body)
        await writer.drain()
    except Exception as exc:
        log.debug("HTTP status request failed: %s", exc)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def main(host: str, port: int, status_host: str, status_port: int):
    server = await asyncio.start_server(handle_client, host, port)
    addrs = format_sockaddrs(server.sockets)
    log.info("MeshCore TCP bridge server listening on %s", addrs)
    http_server = None
    if status_port > 0:
        try:
            http_server = await asyncio.start_server(handle_http_client, status_host, status_port)
            http_addrs = format_sockaddrs(http_server.sockets)
            log.info("Status page listening on http://%s", http_addrs)
        except OSError as exc:
            log.warning("Status page disabled: could not bind %s:%d (%s)",
                        status_host, status_port, exc)
    log.info("Press Ctrl+C to stop")
    status = asyncio.create_task(status_task()) if STATUS_INTERVAL_SECS > 0 else None

    try:
        if http_server:
            async with server, http_server:
                await server.serve_forever()
        else:
            async with server:
                await server.serve_forever()
    finally:
        if http_server:
            http_server.close()
            await http_server.wait_closed()
        if status:
            status.cancel()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MeshCore TCP bridge server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=4200, help="TCP port (default: 4200)")
    parser.add_argument("--log-packets", action="store_true",
                        help="Log every received and forwarded mesh payload")
    parser.add_argument("--log-hex-bytes", type=int, default=32,
                        help="Number of payload bytes to show in packet logs (default: 32)")
    parser.add_argument("--client-timeout", type=int, default=180,
                        help="Disconnect clients after this many seconds without packets or heartbeat (default: 180, 0 disables)")
    parser.add_argument("--status-interval", type=int, default=60,
                        help="Log connected clients every N seconds (default: 60, 0 disables)")
    parser.add_argument("--status-host", default="0.0.0.0",
                        help="Bind address for the HTTP status page (default: 0.0.0.0)")
    parser.add_argument("--status-port", type=int, default=8080,
                        help="HTTP status page port (default: 8080, 0 disables)")
    parser.add_argument("--replace-same-ip", action="store_true",
                        help="When a new client connects, disconnect older clients from the same IP")
    parser.add_argument("--password", default="",
                        help="Optional TCP bridge password required from clients")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)
    LOG_PACKETS = args.log_packets
    LOG_HEX_BYTES = max(0, args.log_hex_bytes)
    CLIENT_TIMEOUT_SECS = max(0, args.client_timeout)
    STATUS_INTERVAL_SECS = max(0, args.status_interval)
    REPLACE_SAME_IP = args.replace_same_ip
    BRIDGE_PASSWORD = args.password

    try:
        asyncio.run(main(args.host, args.port, args.status_host, max(0, args.status_port)))
    except KeyboardInterrupt:
        log.info("Server stopped")
