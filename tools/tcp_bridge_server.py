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
import base64
import binascii
from collections import deque
import html
import json
import logging
import struct
import time
from urllib.parse import parse_qs

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
CONTROL_TYPE_COMMAND = 0x10
CONTROL_TYPE_COMMAND_REPLY = 0x11
PAYLOAD_TYPE_ADVERT = 0x04
PAYLOAD_TYPE_LOCATION = 0x0D
PH_ROUTE_MASK = 0x03
PH_TYPE_SHIFT = 2
ROUTE_TYPE_TRANSPORT_FLOOD = 0x00
ROUTE_TYPE_TRANSPORT_DIRECT = 0x03
ADV_TYPE_SENSOR = 0x04
ADV_LATLON_MASK = 0x10
ADV_FEAT1_MASK = 0x20
ADV_FEAT2_MASK = 0x40
ADV_NAME_MASK = 0x80
PUB_KEY_SIZE = 32
SIGNATURE_SIZE = 64
MAX_ADVERT_DATA_SIZE = 32
LOG_PACKETS = False
LOG_HEX_BYTES = 32
CLIENT_TIMEOUT_SECS = 180
STATUS_INTERVAL_SECS = 60
PACKET_COUNTER_WINDOW_SECS = 24 * 60 * 60
REPLACE_SAME_IP = False
BRIDGE_PASSWORD = ""
ADMIN_PASSWORD = ""
COMMAND_TIMEOUT_SECS = 8
next_command_id = 1

connected_clients: set["BridgeClient"] = set()
latest_locations: dict[str, dict] = {}
latest_sensors: dict[str, dict] = {}
pending_commands: dict[int, asyncio.Future] = {}


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


def parse_command_reply(payload: bytes) -> tuple[int, str] | None:
    if len(payload) < 10:
        return None
    if not payload.startswith(CONTROL_PREFIX):
        return None
    if payload[4] != CONTROL_TYPE_COMMAND_REPLY:
        return None

    request_id = struct.unpack(">I", payload[5:9])[0]
    reply_len = payload[9]
    raw_reply = payload[10:10 + reply_len]
    if len(raw_reply) != reply_len:
        return None

    return request_id, raw_reply.decode("utf-8", errors="replace")


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


def parse_mesh_payload(frame_payload: bytes) -> dict | None:
    if len(frame_payload) < 2:
        return None

    header = frame_payload[0]
    payload_type = (header >> PH_TYPE_SHIFT) & 0x0F
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

    return {
        "payload_type": payload_type,
        "route_type": route_type,
        "path_hash_count": path_hash_count,
        "app_payload": frame_payload[pos:],
    }


def parse_mesh_location_payload(frame_payload: bytes) -> dict | None:
    parsed = parse_mesh_payload(frame_payload)
    if not parsed or parsed["payload_type"] != PAYLOAD_TYPE_LOCATION:
        return None

    report = parse_location_report(parsed["app_payload"])
    if report is None:
        return None
    report["hops"] = parsed["path_hash_count"]
    return report


def parse_advert_app_data(app_data: bytes) -> dict | None:
    if not app_data:
        return None

    flags = app_data[0]
    pos = 1
    advert = {
        "advert_type": flags & 0x0F,
        "name": "",
        "lat": None,
        "lon": None,
        "feat1": None,
        "feat2": None,
    }

    if flags & ADV_LATLON_MASK:
        if len(app_data) < pos + 8:
            return None
        advert["lat"] = struct.unpack("<i", app_data[pos:pos + 4])[0] / 1000000.0
        pos += 4
        advert["lon"] = struct.unpack("<i", app_data[pos:pos + 4])[0] / 1000000.0
        pos += 4
    if flags & ADV_FEAT1_MASK:
        if len(app_data) < pos + 2:
            return None
        advert["feat1"] = struct.unpack("<H", app_data[pos:pos + 2])[0]
        pos += 2
    if flags & ADV_FEAT2_MASK:
        if len(app_data) < pos + 2:
            return None
        advert["feat2"] = struct.unpack("<H", app_data[pos:pos + 2])[0]
        pos += 2
    if flags & ADV_NAME_MASK:
        name_len = min(len(app_data) - pos, MAX_ADVERT_DATA_SIZE - pos)
        advert["name"] = app_data[pos:pos + name_len].decode("utf-8", errors="replace").strip()

    return advert


def parse_sensor_advert_payload(frame_payload: bytes) -> dict | None:
    parsed = parse_mesh_payload(frame_payload)
    if not parsed or parsed["payload_type"] != PAYLOAD_TYPE_ADVERT:
        return None

    payload = parsed["app_payload"]
    advert_header_len = PUB_KEY_SIZE + 4 + SIGNATURE_SIZE
    if len(payload) < advert_header_len:
        return None

    pub_key = payload[:PUB_KEY_SIZE]
    timestamp = struct.unpack("<I", payload[PUB_KEY_SIZE:PUB_KEY_SIZE + 4])[0]
    app_data = payload[advert_header_len:advert_header_len + MAX_ADVERT_DATA_SIZE]
    advert = parse_advert_app_data(app_data)
    if not advert or advert["advert_type"] != ADV_TYPE_SENSOR:
        return None

    return {
        "node_id": binascii.hexlify(pub_key[:4]).decode("ascii"),
        "pubkey_prefix": binascii.hexlify(pub_key[:8]).decode("ascii"),
        "timestamp": timestamp,
        "name": advert["name"],
        "lat": advert["lat"],
        "lon": advert["lon"],
        "feat1": advert["feat1"],
        "feat2": advert["feat2"],
        "hops": parsed["path_hash_count"],
        "route_type": parsed["route_type"],
    }


def record_location(report: dict, client: "BridgeClient") -> None:
    now = time.time()
    report = dict(report)
    report["received_at"] = int(now)
    report["age_seconds"] = 0
    report["source"] = client.display_name
    latest_locations[report["node_id"]] = report


def record_sensor_advert(report: dict, client: "BridgeClient") -> None:
    now = time.time()
    report = dict(report)
    existing = latest_sensors.get(report["node_id"], {})
    report["received_at"] = int(now)
    report["age_seconds"] = 0
    report["source"] = client.display_name
    report["seen_count"] = int(existing.get("seen_count", 0)) + 1
    latest_sensors[report["node_id"]] = report


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
        return self.node_name or "unnamed bridge node"

    @property
    def client_id(self) -> str:
        return self.addr

    def status_dict(self, now: float) -> dict:
        prune_packet_times(self.packet_rx_times, now)
        prune_packet_times(self.packet_tx_times, now)
        return {
            "name": self.node_name,
            "id": self.client_id,
            "addr": self.addr,
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

    async def send_command(self, command: str, password: str) -> str:
        global next_command_id

        command = command.strip()
        raw_command = command.encode("utf-8")[:96]
        raw_password = password.encode("utf-8")[:32]
        if not raw_command:
            raise ValueError("empty command")

        request_id = next_command_id
        next_command_id = (next_command_id + 1) & 0xFFFFFFFF
        if next_command_id == 0:
            next_command_id = 1

        payload = (
            CONTROL_PREFIX
            + bytes([CONTROL_TYPE_COMMAND])
            + struct.pack(">I", request_id)
            + bytes([len(raw_password)])
            + bytes([len(raw_command)])
            + raw_password
            + raw_command
        )

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        pending_commands[request_id] = future
        try:
            if not await self.send_payload(payload):
                raise RuntimeError("send failed")
            return await asyncio.wait_for(future, timeout=COMMAND_TIMEOUT_SECS)
        finally:
            pending_commands.pop(request_id, None)

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
            command_reply = parse_command_reply(payload)
            if command_reply is not None:
                request_id, reply = command_reply
                future = pending_commands.get(request_id)
                if future and not future.done():
                    future.set_result(reply)
                else:
                    log.debug("%s: stale command reply id=%d", client.addr, request_id)
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
            sensor_report = parse_sensor_advert_payload(payload)
            if sensor_report is not None:
                record_sensor_advert(sensor_report, client)
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


def sensors_snapshot() -> dict:
    now = int(time.time())
    sensors = []
    for report in latest_sensors.values():
        item = dict(report)
        item["age_seconds"] = max(0, now - item["received_at"])
        sensors.append(item)
    sensors.sort(key=lambda item: (item.get("name") or item["node_id"]).lower())
    return {
        "generated_at": now,
        "sensor_count": len(sensors),
        "sensors": sensors,
    }


def build_status_html(command_result: str = "") -> str:
    snapshot = status_snapshot()
    sensor_snapshot = sensors_snapshot()
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

    options = []
    for client in snapshot["clients"]:
        label = f"{client['display_name']} ({client['addr']})"
        options.append(
            f"<option value=\"{html.escape(client['id'])}\">{html.escape(label)}</option>"
        )
    options_html = "\n".join(options)
    admin_note = (
        "Remote management protected by server admin password; node password still required"
        if ADMIN_PASSWORD
        else "Remote management enabled; enter the selected node's admin password"
    )
    result_html = ""
    if command_result:
        result_html = f"<pre class=\"command-result\">{html.escape(command_result)}</pre>"

    sensor_rows = []
    for sensor in sensor_snapshot["sensors"]:
        name = sensor["name"] or "unknown"
        location = ""
        if sensor["lat"] is not None and sensor["lon"] is not None:
            location = f"{sensor['lat']:.6f}, {sensor['lon']:.6f}"
        else:
            location = "not shared"
        sensor_rows.append(
            "<tr>"
            f"<td>{html.escape(name)}</td>"
            f"<td><code>{html.escape(sensor['node_id'])}</code></td>"
            f"<td>{sensor['age_seconds']}s ago</td>"
            f"<td>{sensor['seen_count']}</td>"
            f"<td>{sensor['hops']}</td>"
            f"<td>{html.escape(sensor['source'])}</td>"
            f"<td>{html.escape(location)}</td>"
            "</tr>"
        )

    sensor_rows_html = "\n".join(sensor_rows) if sensor_rows else (
        '<tr><td colspan="7" class="empty">No sensor node adverts seen yet</td></tr>'
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
    section {{ margin-top: 28px; }}
    h2 {{ margin: 0 0 12px; font-size: 1.15rem; }}
    form {{ display: grid; grid-template-columns: minmax(180px, 1fr) minmax(160px, 1fr) minmax(220px, 2fr) auto; gap: 10px; align-items: end; }}
    label {{ display: grid; gap: 6px; color: #47515d; font-size: .85rem; }}
    select, input, button {{ font: inherit; padding: 9px 10px; border: 1px solid #d8dee4; border-radius: 6px; background: #fff; color: #1b1f24; }}
    button {{ cursor: pointer; background: #0969da; color: #fff; border-color: #0969da; }}
    button:disabled {{ cursor: not-allowed; background: #8c959f; border-color: #8c959f; }}
    .command-result {{ padding: 12px; background: #f6f8fa; border: 1px solid #d8dee4; border-radius: 6px; white-space: pre-wrap; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid #d8dee4; white-space: nowrap; }}
    th {{ background: #eef2f6; font-size: 0.8rem; text-transform: uppercase; color: #47515d; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace; }}
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
      select, input {{ background: #171b20; color: #f0f3f6; border-color: #30363d; }}
      label {{ color: #c8d0d8; }}
      .command-result {{ background: #171b20; border-color: #30363d; }}
      .empty {{ color: #9aa4af; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>MeshCoreNG TCP Bridge Status</h1>
    <p class="summary">{snapshot['connected_count']} connected node(s). Auto-refreshes every 10 seconds. <a href="/map">Tracker map</a></p>
    <section>
      <h2>Remote management</h2>
      <p class="summary">{html.escape(admin_note)}</p>
      <form method="post" action="/command">
        <label>Node
          <select name="target" {"disabled" if not options_html else ""}>
            {options_html}
          </select>
        </label>
        <label>Node password
          <input name="node_password" type="password" autocomplete="current-password" maxlength="32" {"disabled" if not options_html else ""}>
        </label>
        <label>Command
          <input name="command" placeholder="get bridge.status" maxlength="96" {"disabled" if not options_html else ""}>
        </label>
        <button type="submit" {"disabled" if not options_html else ""}>Send</button>
      </form>
      {result_html}
    </section>
    <section>
      <h2>Bridge nodes</h2>
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
    </section>
    <section>
      <h2>Sensor nodes nearby</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Node ID</th>
              <th>Last seen</th>
              <th>Seen</th>
              <th>Hops</th>
              <th>Via bridge</th>
              <th>Location</th>
            </tr>
          </thead>
          <tbody>
            {sensor_rows_html}
          </tbody>
        </table>
      </div>
    </section>
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


def is_admin_authorized(headers: dict[str, str]) -> bool:
    if not ADMIN_PASSWORD:
        return True
    auth = headers.get("authorization", "")
    if not auth.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(auth[6:].strip()).decode("utf-8", errors="replace")
    except Exception:
        return False
    _user, sep, password = decoded.partition(":")
    return bool(sep) and password == ADMIN_PASSWORD


def admin_auth_response() -> tuple[str, str, bytes, list[tuple[str, str]]]:
    return (
        "401 Unauthorized",
        "text/plain",
        b"Admin authentication required\n",
        [("WWW-Authenticate", 'Basic realm="MeshCoreNG Bridge Admin"')],
    )


def find_client(client_id: str) -> BridgeClient | None:
    for client in connected_clients:
        if client.client_id == client_id:
            return client
    return None


async def handle_http_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        request_line = await reader.readline()
        parts = request_line.decode("ascii", errors="ignore").strip().split()
        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if not line or line in (b"\r\n", b"\n"):
                break
            name, sep, value = line.decode("iso-8859-1", errors="ignore").partition(":")
            if sep:
                headers[name.strip().lower()] = value.strip()

        method = parts[0] if len(parts) >= 1 else ""
        path = parts[1] if len(parts) >= 2 else ""
        extra_headers: list[tuple[str, str]] = []

        if len(parts) < 2:
            status, content_type, body = "405 Method Not Allowed", "text/plain", b"Method not allowed\n"
        elif method == "POST" and path == "/command":
            if not is_admin_authorized(headers):
                status, content_type, body, extra_headers = admin_auth_response()
            else:
                content_length = int(headers.get("content-length", "0") or "0")
                raw_body = await reader.readexactly(content_length) if content_length > 0 else b""
                form = parse_qs(raw_body.decode("utf-8", errors="replace"), keep_blank_values=True)
                target = (form.get("target") or [""])[0]
                node_password = (form.get("node_password") or [""])[0]
                command = (form.get("command") or [""])[0].strip()
                client = find_client(target)
                if client is None:
                    result = "Error: selected bridge node is no longer connected"
                elif not command:
                    result = "Error: empty command"
                elif not node_password:
                    result = "Error: node admin password required"
                else:
                    try:
                        reply = await client.send_command(command, node_password)
                        result = f"{client.display_name}> {command}\n{reply}"
                    except Exception as exc:
                        result = f"Error: {exc}"
                status, content_type = "200 OK", "text/html; charset=utf-8"
                body = build_status_html(result).encode("utf-8")
        elif method != "GET":
            status, content_type, body = "405 Method Not Allowed", "text/plain", b"Method not allowed\n"
        elif path == "/status.json":
            status, content_type = "200 OK", "application/json"
            body = json.dumps(status_snapshot(), indent=2).encode("utf-8")
        elif path == "/locations.json":
            status, content_type = "200 OK", "application/json"
            body = json.dumps(locations_snapshot(), indent=2).encode("utf-8")
        elif path == "/sensors.json":
            status, content_type = "200 OK", "application/json"
            body = json.dumps(sensors_snapshot(), indent=2).encode("utf-8")
        elif path == "/map":
            status, content_type = "200 OK", "text/html; charset=utf-8"
            body = build_location_map_html().encode("utf-8")
        elif path in ("/", "/status"):
            status, content_type = "200 OK", "text/html; charset=utf-8"
            body = build_status_html().encode("utf-8")
        else:
            status, content_type, body = "404 Not Found", "text/plain", b"Not found\n"

        headers = (
            f"HTTP/1.1 {status}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "Cache-Control: no-store\r\n"
        ).encode("ascii")
        for name, value in extra_headers:
            headers += f"{name}: {value}\r\n".encode("ascii")
        writer.write(headers + b"\r\n" + body)
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
    parser.add_argument("--admin-password", default="",
                        help="Optional Basic auth password protecting the HTTP status/management page")
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
    ADMIN_PASSWORD = args.admin_password

    try:
        asyncio.run(main(args.host, args.port, args.status_host, max(0, args.status_port)))
    except KeyboardInterrupt:
        log.info("Server stopped")
