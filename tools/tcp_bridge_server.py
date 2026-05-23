#!/usr/bin/env python3
"""
MeshCore TCP Bridge Server

Forwards mesh packets between connected repeaters so geographically separated
LoRa networks can act as one mesh. Each packet received from one repeater is
broadcast to all other connected repeaters.

Usage:
    python3 tcp_bridge_server.py [--host 0.0.0.0] [--port 4200]
    open http://localhost:8080/ for connected node status

Repeater firmware configuration (via CLI):
    set wifi.ssid    <your-wifi>
    set wifi.password <your-password>
    set bridge.server <this-server-ip-or-hostname>
    set bridge.port   4200
    set bridge.enabled on

Requires Python 3.7+, no external dependencies.
"""

import asyncio
import argparse
import binascii
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
LOG_PACKETS = False
LOG_HEX_BYTES = 32
CLIENT_TIMEOUT_SECS = 180
STATUS_INTERVAL_SECS = 60
REPLACE_SAME_IP = False

connected_clients: set["BridgeClient"] = set()


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


def parse_node_info(payload: bytes) -> str | None:
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

    return raw_name.decode("utf-8", errors="replace").strip()[:32]


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
        self.heartbeats_rx = 0
        self._connect_time = time.time()
        self.last_seen = self._connect_time
        self.last_heartbeat = 0.0
        self.node_name = ""

    @property
    def display_name(self) -> str:
        return self.node_name or self.addr

    def status_dict(self, now: float) -> dict:
        return {
            "name": self.node_name,
            "display_name": self.display_name,
            "address": self.addr,
            "host": self.host,
            "port": self.port,
            "connected_seconds": int(now - self._connect_time),
            "connected_for": format_duration(now - self._connect_time),
            "idle_seconds": int(now - self.last_seen),
            "heartbeat_age_seconds": int(now - self.last_heartbeat) if self.last_heartbeat else None,
            "packets_rx": self.packets_rx,
            "packets_tx": self.packets_tx,
            "heartbeats_rx": self.heartbeats_rx,
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
            summary = ", ".join(
                f"{client.display_name}@{client.addr} connected={format_duration(now - client._connect_time)} "
                f"idle={int(now - client.last_seen)}s "
                f"hb_age={str(int(now - client.last_heartbeat)) + 's' if client.last_heartbeat else 'never'} "
                f"rx={client.packets_rx} tx={client.packets_tx} hb={client.heartbeats_rx}"
                for client in sorted(connected_clients, key=lambda c: c.addr)
            )
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
            heartbeat_uptime = parse_heartbeat(payload)
            if heartbeat_uptime is not None:
                client.heartbeats_rx += 1
                client.last_heartbeat = time.time()
                log.debug("%s: heartbeat uptime=%dms", client.addr, heartbeat_uptime)
                continue
            node_name = parse_node_info(payload)
            if node_name is not None:
                client.node_name = node_name
                log.info("%s: node name is %s", client.addr, client.node_name)
                continue
            client.packets_rx += 1
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


def build_status_html() -> str:
    snapshot = status_snapshot()
    rows = []
    for client in snapshot["clients"]:
        hb_age = client["heartbeat_age_seconds"]
        heartbeat = f"{hb_age}s ago" if hb_age is not None else "never"
        rows.append(
            "<tr>"
            f"<td>{html.escape(client['display_name'])}</td>"
            f"<td>{html.escape(client['address'])}</td>"
            f"<td>{html.escape(client['connected_for'])}</td>"
            f"<td>{client['idle_seconds']}s</td>"
            f"<td>{heartbeat}</td>"
            f"<td>{client['packets_rx']}</td>"
            f"<td>{client['packets_tx']}</td>"
            f"<td>{client['heartbeats_rx']}</td>"
            "</tr>"
        )

    rows_html = "\n".join(rows) if rows else (
        '<tr><td colspan="8" class="empty">No bridge nodes connected</td></tr>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="10">
  <title>MeshCore TCP Bridge Status</title>
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
    <h1>MeshCore TCP Bridge Status</h1>
    <p class="summary">{snapshot['connected_count']} connected node(s). Auto-refreshes every 10 seconds.</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Node</th>
            <th>Address</th>
            <th>Connected</th>
            <th>Idle</th>
            <th>Heartbeat</th>
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


async def handle_http_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        request_line = await reader.readline()
        parts = request_line.decode("ascii", errors="ignore").strip().split()
        if len(parts) < 2 or parts[0] != "GET":
            status, content_type, body = "405 Method Not Allowed", "text/plain", b"Method not allowed\n"
        elif parts[1] == "/status.json":
            status, content_type = "200 OK", "application/json"
            body = json.dumps(status_snapshot(), indent=2).encode("utf-8")
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

    try:
        asyncio.run(main(args.host, args.port, args.status_host, max(0, args.status_port)))
    except KeyboardInterrupt:
        log.info("Server stopped")
