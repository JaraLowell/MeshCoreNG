#!/usr/bin/env python3
"""
MeshCore TCP Bridge Server

Forwards mesh packets between connected repeaters so geographically separated
LoRa networks can act as one mesh. Each packet received from one repeater is
broadcast to all other connected repeaters.

Usage:
    python3 tcp_bridge_server.py [--host 0.0.0.0] [--port 4200] [--password bridgeSecret]
    open http://localhost:8080/ for connected node status
    open http://localhost:8080/manage for remote management
    use --status-base-path /meshbridgestatus when reverse-proxying below a URL prefix

Repeater firmware configuration (via CLI):
    set wifi.ssid    <your-wifi>
    set wifi.password <your-password>
    set bridge.server <this-server-ip-or-hostname>
    set bridge.port   4200
    set bridge.password <bridgeSecret>  # only when server --password is set
    set bridge.enabled on

Requires Python 3.7+. Public channel decoding additionally needs:
    pip install cryptography
"""

import asyncio
import argparse
import base64
import binascii
from collections import deque
import hashlib
import hmac
import html
import json
import logging
import re
import struct
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ImportError:
    Cipher = None
    algorithms = None
    modes = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("tcp_bridge")

BRIDGE_MAGIC = 0xC03E
MAX_PAYLOAD = 512   # Allows legacy raw packets and TCP bridge v2 envelopes.
CONTROL_PREFIX = b"MCNG"
CONTROL_TYPE_HEARTBEAT = 0x01
CONTROL_TYPE_NODE_INFO = 0x02
CONTROL_TYPE_AUTH = 0x03
CONTROL_TYPE_CAPS = 0x04
CONTROL_TYPE_COMMAND = 0x10
CONTROL_TYPE_COMMAND_REPLY = 0x11
CONTROL_TYPE_BRIDGE_PACKET = 0x20
BRIDGE_PACKET_VERSION = 1
BRIDGE_V2_OVERHEAD = 14
IP_ADDRESS_RE = re.compile(
    r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?(?![\w.])"
    r"|(?<![\w:])(?:[0-9a-fA-F]{1,4}:){2,}[0-9a-fA-F]{0,4}(?::\d{1,5})?(?![\w:])"
)
PAYLOAD_TYPE_ADVERT = 0x04
PAYLOAD_TYPE_GRP_TXT = 0x05
PAYLOAD_TYPE_GRP_DATA = 0x06
PAYLOAD_TYPE_LOCATION = 0x0D
PH_ROUTE_MASK = 0x03
PH_TYPE_SHIFT = 2
ROUTE_TYPE_TRANSPORT_FLOOD = 0x00
ROUTE_TYPE_TRANSPORT_DIRECT = 0x03
ADV_TYPE_SENSOR = 0x04
ADV_TYPE_REPEATER = 0x02
ADV_LATLON_MASK = 0x10
ADV_FEAT1_MASK = 0x20
ADV_FEAT2_MASK = 0x40
ADV_NAME_MASK = 0x80
PUB_KEY_SIZE = 32
SIGNATURE_SIZE = 64
MAX_ADVERT_DATA_SIZE = 32
PATH_HASH_SIZE = 1
CIPHER_MAC_SIZE = 2
CIPHER_BLOCK_SIZE = 16
LOG_PACKETS = False
LOG_HEX_BYTES = 32
PUBLIC_CHANNELS_FILE = ""
CLIENT_TIMEOUT_SECS = 180
STATUS_INTERVAL_SECS = 60
PACKET_COUNTER_WINDOW_SECS = 24 * 60 * 60
LOCATION_TRACK_MAX_POINTS = 500
REPLACE_SAME_IP = False
BRIDGE_PASSWORD = ""
ADMIN_PASSWORD = ""
STATUS_BASE_PATH = "/meshbridgestatus"
COMMAND_TIMEOUT_SECS = 8
next_command_id = 1
next_client_id = 1

connected_clients: set["BridgeClient"] = set()
latest_locations: dict[str, dict] = {}
latest_location_tracks: dict[str, deque[dict]] = {}
latest_sensors: dict[str, dict] = {}
recent_packets: deque[dict] = deque(maxlen=200)
pending_commands: dict[int, asyncio.Future] = {}
public_channels: list[dict] = []

PAYLOAD_TYPE_NAMES = {
    0x00: "request",
    0x01: "response",
    0x02: "text-message",
    0x03: "ack",
    0x04: "advert",
    0x05: "group-text",
    0x06: "group-data",
    0x07: "anon-request",
    0x08: "path",
    0x09: "trace",
    0x0A: "multipart",
    0x0B: "control",
    0x0C: "atlas",
    0x0D: "location",
    0x0F: "raw-custom",
}

ROUTE_TYPE_NAMES = {
    0x00: "transport-flood",
    0x01: "flood",
    0x02: "direct",
    0x03: "transport-direct",
}

CONTROL_TYPE_NAMES = {
    CONTROL_TYPE_HEARTBEAT: "heartbeat",
    CONTROL_TYPE_NODE_INFO: "node-info",
    CONTROL_TYPE_AUTH: "auth",
    CONTROL_TYPE_CAPS: "capabilities",
    CONTROL_TYPE_COMMAND: "command",
    CONTROL_TYPE_COMMAND_REPLY: "command-reply",
    CONTROL_TYPE_BRIDGE_PACKET: "bridge-v2-packet",
}


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


def packet_type_name(payload_type: int) -> str:
    return PAYLOAD_TYPE_NAMES.get(payload_type, f"unknown-0x{payload_type:02x}")


def route_type_name(route_type: int) -> str:
    return ROUTE_TYPE_NAMES.get(route_type, f"unknown-0x{route_type:02x}")


def redact_public_text(value: str) -> str:
    return IP_ADDRESS_RE.sub("[hidden]", value)


def redact_public_value(value):
    if isinstance(value, str):
        return redact_public_text(value)
    if isinstance(value, list):
        return [redact_public_value(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_public_value(item) for key, item in value.items() if key != "addr"}
    return value


def derive_channel_secret(secret_hex: str) -> bytes | None:
    try:
        raw = bytes.fromhex(secret_hex.strip())
    except ValueError:
        return None
    if len(raw) == 16:
        return raw + (b"\x00" * 16)
    if len(raw) == 32:
        return raw
    return None


def channel_hash(secret: bytes) -> bytes:
    key_len = 16 if secret[16:] == b"\x00" * 16 else 32
    return hashlib.sha256(secret[:key_len]).digest()[:PATH_HASH_SIZE]


def load_public_channels(path: str) -> None:
    public_channels.clear()
    if not path:
        return
    if Cipher is None:
        log.warning("Public channel decoding disabled: install python package 'cryptography'")
        return

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Public channel decoding disabled: cannot read %s (%s)", path, exc)
        return

    if isinstance(data, dict):
        data = data.get("channels", [])
    if not isinstance(data, list):
        log.warning("Public channel decoding disabled: %s must contain a list or {'channels': [...]} object", path)
        return

    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        secret = derive_channel_secret(str(item.get("secret", "")))
        if not name or secret is None:
            log.warning("Skipping invalid public channel entry: %s", item)
            continue
        public_channels.append({
            "name": name,
            "secret": secret,
            "hash": channel_hash(secret),
        })

    log.info("Loaded %d public channel key(s) from %s", len(public_channels), path)


def aes_ecb_decrypt(secret: bytes, data: bytes) -> bytes | None:
    if Cipher is None or len(data) == 0 or len(data) % CIPHER_BLOCK_SIZE:
        return None
    cipher = Cipher(algorithms.AES(secret[:16]), modes.ECB())
    decryptor = cipher.decryptor()
    return decryptor.update(data) + decryptor.finalize()


def mac_then_decrypt(secret: bytes, data: bytes) -> bytes | None:
    if len(data) <= CIPHER_MAC_SIZE:
        return None
    expected = hmac.new(secret, data[CIPHER_MAC_SIZE:], hashlib.sha256).digest()[:CIPHER_MAC_SIZE]
    if not hmac.compare_digest(expected, data[:CIPHER_MAC_SIZE]):
        return None
    return aes_ecb_decrypt(secret, data[CIPHER_MAC_SIZE:])


def trim_c_string(data: bytes) -> str:
    data = data.split(b"\x00", 1)[0]
    return data.decode("utf-8", errors="replace").strip()


def decode_public_channel_payload(parsed: dict) -> dict:
    result = {
        "decoded_channel": "",
        "decoded_status": "",
        "decoded_text": "",
        "decoded_data_type": None,
        "decoded_data_len": None,
    }
    payload_type = parsed.get("payload_type")
    app_payload = parsed.get("app_payload") or b""
    if payload_type not in (PAYLOAD_TYPE_GRP_TXT, PAYLOAD_TYPE_GRP_DATA):
        return result
    if not public_channels:
        result["decoded_status"] = "channel-keys-not-loaded"
        return result
    if len(app_payload) <= PATH_HASH_SIZE + CIPHER_MAC_SIZE:
        result["decoded_status"] = "short-group-payload"
        return result

    packet_hash = app_payload[:PATH_HASH_SIZE]
    encrypted = app_payload[PATH_HASH_SIZE:]
    candidates = [ch for ch in public_channels if ch["hash"] == packet_hash]
    if not candidates:
        result["decoded_status"] = "unknown-channel"
        return result

    for channel in candidates:
        plain = mac_then_decrypt(channel["secret"], encrypted)
        if not plain:
            continue
        result["decoded_channel"] = channel["name"]
        if payload_type == PAYLOAD_TYPE_GRP_TXT:
            if len(plain) < 5:
                result["decoded_status"] = "short-group-text"
                return result
            txt_type = plain[4]
            if (txt_type >> 2) != 0:
                result["decoded_status"] = f"unsupported-text-type-{txt_type}"
                return result
            result["decoded_status"] = "decoded"
            result["decoded_text"] = trim_c_string(plain[5:])
            return result

        if len(plain) < 3:
            result["decoded_status"] = "short-group-data"
            return result
        data_type = plain[0] | (plain[1] << 8)
        data_len = plain[2]
        data = plain[3:3 + data_len]
        result["decoded_status"] = "decoded"
        result["decoded_data_type"] = data_type
        result["decoded_data_len"] = min(data_len, len(data))
        result["decoded_text"] = f"data_type=0x{data_type:04x} len={min(data_len, len(data))} preview={payload_preview(data)}"
        return result

    result["decoded_status"] = "mac-failed"
    return result


def describe_packet(payload: bytes) -> dict:
    envelope = parse_bridge_packet_envelope(payload)
    mesh_payload = envelope["mesh_payload"] if envelope is not None else payload
    description = {
        "kind": "mesh",
        "type": "unknown",
        "type_id": None,
        "route": "unknown",
        "route_id": None,
        "hops": None,
        "app_len": None,
        "bridge_v2": envelope is not None,
        "ttl": envelope["ttl"] if envelope is not None else None,
        "origin_id": f"0x{envelope['origin_id']:08x}" if envelope is not None else "",
        "flags": f"0x{envelope['flags']:02x}" if envelope is not None else "",
        "mesh_len": len(mesh_payload),
        "decoded_channel": "",
        "decoded_status": "",
        "decoded_text": "",
        "decoded_data_type": None,
        "decoded_data_len": None,
    }

    if envelope is None and payload.startswith(CONTROL_PREFIX):
        control_type = payload[4] if len(payload) > 4 else None
        description.update({
            "kind": "control",
            "type": CONTROL_TYPE_NAMES.get(control_type, f"control-0x{control_type:02x}" if control_type is not None else "control"),
            "type_id": control_type,
            "route": "",
            "route_id": None,
            "hops": None,
            "app_len": max(0, len(payload) - 5),
            "mesh_len": 0,
        })
        return description

    parsed = parse_mesh_payload(mesh_payload)
    if parsed is None:
        return description

    payload_type = parsed["payload_type"]
    route_type = parsed["route_type"]
    description.update({
        "type": packet_type_name(payload_type),
        "type_id": payload_type,
        "route": route_type_name(route_type),
        "route_id": route_type,
        "hops": parsed["path_hash_count"],
        "app_len": len(parsed["app_payload"]),
        **decode_public_channel_payload(parsed),
    })
    return description


def format_packet_description(description: dict) -> str:
    parts = [f"type={description['type']}"]
    if description.get("route"):
        parts.append(f"route={description['route']}")
    if description.get("decoded_channel"):
        parts.append(f"channel={description['decoded_channel']}")
    if description.get("hops") is not None:
        parts.append(f"hops={description['hops']}")
    if description.get("app_len") is not None:
        parts.append(f"app={description['app_len']}B")
    if description.get("bridge_v2"):
        parts.append(f"bridge-v2 ttl={description['ttl']} origin={description['origin_id']}")
    return " ".join(parts)


def record_packet_log(
    direction: str,
    client: "BridgeClient",
    payload: bytes,
    source: str = "",
    target: str = "",
) -> dict:
    description = describe_packet(payload)
    mesh_payload = mesh_payload_for_parsing(payload)
    source = source or ("server" if direction == "TX" else client.display_name)
    target = target or (client.display_name if direction == "TX" else "server")
    entry = {
        "time": int(time.time()),
        "direction": direction,
        "client": client.display_name,
        "client_id": client.client_id,
        "node_id": client.node_id,
        "source": source,
        "target": target,
        "flow": f"{source} -> {target}",
        "size": len(payload),
        "preview": payload_preview(mesh_payload if description.get("bridge_v2") else payload),
        **description,
    }
    recent_packets.appendleft(entry)
    return entry


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


def parse_node_info(payload: bytes) -> tuple[str, str, str] | None:
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
    version_len = 0
    version_pos = 6 + name_len
    if len(payload) > version_pos:
        version_len = payload[version_pos]
        raw_version = payload[version_pos + 1:version_pos + 1 + version_len]
        if len(raw_version) == version_len:
            firmware = raw_version.decode("utf-8", errors="replace").strip()[:32]
    node_id = ""
    node_id_pos = version_pos + 1 + version_len
    if len(payload) > node_id_pos:
        node_id_len = payload[node_id_pos]
        raw_node_id = payload[node_id_pos + 1:node_id_pos + 1 + node_id_len]
        if node_id_len in (4, 8, 32) and len(raw_node_id) == node_id_len:
            node_id = binascii.hexlify(raw_node_id).decode("ascii")

    return name, firmware, node_id


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


def parse_caps(payload: bytes) -> dict | None:
    if len(payload) < 7:
        return None
    if not payload.startswith(CONTROL_PREFIX):
        return None
    if payload[4] != CONTROL_TYPE_CAPS:
        return None
    return {
        "version": payload[5],
        "flags": payload[6],
        "bridge_v2": bool(payload[6] & 0x01),
    }


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


def parse_bridge_packet_envelope(payload: bytes) -> dict | None:
    if len(payload) < BRIDGE_V2_OVERHEAD:
        return None
    if not payload.startswith(CONTROL_PREFIX):
        return None
    if payload[4] != CONTROL_TYPE_BRIDGE_PACKET:
        return None
    if payload[5] != BRIDGE_PACKET_VERSION:
        return None

    packet_len = struct.unpack(">H", payload[12:14])[0]
    if packet_len == 0 or len(payload) < BRIDGE_V2_OVERHEAD + packet_len:
        return None

    return {
        "version": payload[5],
        "ttl": payload[6],
        "origin_id": struct.unpack(">I", payload[7:11])[0],
        "flags": payload[11],
        "packet_len": packet_len,
        "mesh_payload": payload[BRIDGE_V2_OVERHEAD:BRIDGE_V2_OVERHEAD + packet_len],
    }


def mesh_payload_for_parsing(payload: bytes) -> bytes:
    envelope = parse_bridge_packet_envelope(payload)
    if envelope is not None:
        return envelope["mesh_payload"]
    return payload


def decrement_bridge_ttl(payload: bytes) -> bytes | None:
    envelope = parse_bridge_packet_envelope(payload)
    if envelope is None:
        return payload
    ttl = envelope["ttl"]
    if ttl <= 1:
        return None
    forwarded = bytearray(payload)
    forwarded[6] = ttl - 1
    return bytes(forwarded)


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
        "node_id": binascii.hexlify(pub_key).decode("ascii"),
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


def parse_node_advert_payload(frame_payload: bytes) -> dict | None:
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
    if not advert:
        return None

    return {
        "node_id": binascii.hexlify(pub_key).decode("ascii"),
        "pubkey_prefix": binascii.hexlify(pub_key[:8]).decode("ascii"),
        "timestamp": timestamp,
        "name": advert["name"],
        "advert_type": advert["advert_type"],
        "hops": parsed["path_hash_count"],
    }


def record_location(report: dict, client: "BridgeClient") -> None:
    now = time.time()
    report = dict(report)
    report["received_at"] = int(now)
    report["age_seconds"] = 0
    report["source"] = client.display_name
    client.learn_node_id(report.get("node_id", ""), report.get("name", ""))
    latest_locations[report["node_id"]] = report
    track = latest_location_tracks.setdefault(report["node_id"], deque(maxlen=LOCATION_TRACK_MAX_POINTS))
    point = {
        "lat": report["lat"],
        "lon": report["lon"],
        "speed_kmh": report.get("speed_kmh"),
        "heading_deg": report.get("heading_deg"),
        "timestamp": report.get("timestamp"),
        "received_at": report["received_at"],
    }
    if not track or any(track[-1].get(key) != point.get(key) for key in ("lat", "lon", "timestamp")):
        track.append(point)


def record_sensor_advert(report: dict, client: "BridgeClient") -> None:
    now = time.time()
    report = dict(report)
    existing = latest_sensors.get(report["node_id"], {})
    report["received_at"] = int(now)
    report["age_seconds"] = 0
    report["source"] = client.display_name
    report["seen_count"] = int(existing.get("seen_count", 0)) + 1
    client.learn_node_id(report.get("node_id", ""), report.get("name", ""))
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
        global next_client_id

        self.reader = reader
        self.writer = writer
        addr = writer.get_extra_info("peername")
        self.host = addr[0] if addr else "unknown"
        self.port = addr[1] if addr else 0
        self.addr = f"{self.host}:{self.port}" if addr else "unknown"
        self._client_id = f"client-{next_client_id}"
        next_client_id += 1
        self.packets_rx = 0
        self.packets_tx = 0
        self.packet_rx_times: deque[float] = deque()
        self.packet_tx_times: deque[float] = deque()
        self.heartbeats_rx = 0
        self._connect_time = time.time()
        self.last_seen = self._connect_time
        self.last_heartbeat = 0.0
        self.node_name = ""
        self.node_id = ""
        self.firmware_version = ""
        self.supports_bridge_v2 = False
        self.authenticated = not BRIDGE_PASSWORD

    @property
    def display_name(self) -> str:
        return self.node_name or "unnamed bridge node"

    @property
    def client_id(self) -> str:
        return self._client_id

    def learn_node_id(self, node_id: str, name: str = "") -> None:
        node_id = (node_id or "").strip().lower()
        if not node_id:
            return
        name = (name or "").strip()
        if self.node_name and name and name != self.node_name:
            return
        if not self.node_id or len(node_id) > len(self.node_id) or name == self.node_name:
            self.node_id = node_id

    def status_dict(self, now: float) -> dict:
        prune_packet_times(self.packet_rx_times, now)
        prune_packet_times(self.packet_tx_times, now)
        return {
            "name": self.node_name,
            "id": self.client_id,
            "node_id": self.node_id,
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
            "supports_bridge_v2": self.supports_bridge_v2,
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

    async def send_payload(self, payload: bytes, source: str = "") -> bool:
        try:
            self.writer.write(self.build_frame(payload))
            await self.writer.drain()
            self.packets_tx += 1
            now = time.time()
            self.packet_tx_times.append(now)
            prune_packet_times(self.packet_tx_times, now)
            packet_log = record_packet_log("TX", self, payload, source=source, target=self.display_name)
            if LOG_PACKETS:
                log.info(
                    "%s -> %s: TX %d bytes %s: %s",
                    packet_log["source"],
                    packet_log["target"],
                    len(payload),
                    format_packet_description(packet_log),
                    packet_log["preview"],
                )
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
    forwarded_payload = decrement_bridge_ttl(payload)
    if forwarded_payload is None:
        log.debug("%s: dropping bridge packet with expired TTL", sender.addr)
        return

    dead = set()
    envelope = parse_bridge_packet_envelope(forwarded_payload)
    for client in connected_clients:
        if client is sender:
            continue
        client_payload = forwarded_payload
        if envelope is not None and not client.supports_bridge_v2:
            client_payload = envelope["mesh_payload"]
        ok = await client.send_payload(client_payload, source=sender.display_name)
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
            caps = parse_caps(payload)
            if caps is not None:
                client.supports_bridge_v2 = caps["bridge_v2"]
                log.info("%s: bridge capabilities v%d flags=0x%02x bridge_v2=%s",
                         client.addr, caps["version"], caps["flags"], client.supports_bridge_v2)
                continue
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
            node_info = parse_node_info(payload)
            if node_info is not None:
                client.node_name, client.firmware_version, node_id = node_info
                if node_id:
                    client.node_id = node_id
                if client.firmware_version:
                    log.info("%s: node name is %s firmware=%s node_id=%s",
                             client.addr, client.node_name, client.firmware_version, client.node_id or "unknown")
                else:
                    log.info("%s: node name is %s node_id=%s", client.addr, client.node_name, client.node_id or "unknown")
                continue
            client.packets_rx += 1
            now = time.time()
            client.packet_rx_times.append(now)
            prune_packet_times(client.packet_rx_times, now)
            mesh_payload = mesh_payload_for_parsing(payload)
            location_report = parse_mesh_location_payload(mesh_payload)
            if location_report is not None:
                record_location(location_report, client)
            node_advert = parse_node_advert_payload(mesh_payload)
            if node_advert is not None and node_advert.get("advert_type") == ADV_TYPE_REPEATER:
                client.learn_node_id(node_advert.get("node_id", ""), node_advert.get("name", ""))
            sensor_report = parse_sensor_advert_payload(mesh_payload)
            if sensor_report is not None:
                record_sensor_advert(sensor_report, client)
            packet_log = record_packet_log("RX", client, payload)
            if LOG_PACKETS:
                envelope = parse_bridge_packet_envelope(payload)
                if envelope is not None:
                    log.info(
                        "%s -> server: RX bridge-v2 mesh=%d bytes %s: %s",
                        packet_log["source"],
                        envelope["packet_len"],
                        format_packet_description(packet_log),
                        packet_log["preview"],
                    )
                else:
                    log.info(
                        "%s -> server: RX %d bytes %s: %s",
                        packet_log["source"],
                        len(payload),
                        format_packet_description(packet_log),
                        packet_log["preview"],
                    )
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
        "clients": redact_public_value(clients),
    }


def locations_snapshot() -> dict:
    now = int(time.time())
    locations = []
    for report in latest_locations.values():
        item = dict(report)
        item["age_seconds"] = max(0, now - item["received_at"])
        item["track"] = list(latest_location_tracks.get(item["node_id"], ()))
        locations.append(item)
    locations.sort(key=lambda item: (item.get("name") or item["node_id"]).lower())
    return {
        "generated_at": now,
        "location_count": len(locations),
        "locations": redact_public_value(locations),
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
        "sensors": redact_public_value(sensors),
    }


def packets_snapshot() -> dict:
    now = int(time.time())
    packets = []
    for entry in recent_packets:
        item = dict(entry)
        item["age_seconds"] = max(0, now - item["time"])
        packets.append(redact_public_value(item))
    return {
        "generated_at": now,
        "packet_count": len(packets),
        "packets": packets,
    }


def normalize_base_path(path: str) -> str:
    path = (path or "").strip()
    if not path or path == "/":
        return ""
    return "/" + path.strip("/")


def request_base_path(headers: dict[str, str]) -> str:
    forwarded_prefix = headers.get("x-forwarded-prefix", "") or headers.get("x-script-name", "")
    if forwarded_prefix:
        return normalize_base_path(forwarded_prefix)
    return STATUS_BASE_PATH


def prefixed_url(base_path: str, route: str) -> str:
    base_path = normalize_base_path(base_path)
    if route == "/":
        return base_path or "/"
    if not route.startswith("/"):
        route = "/" + route
    return f"{base_path}{route}"


def strip_base_path(path: str, base_path: str) -> str:
    route = urlsplit(path or "/").path or "/"
    base_path = normalize_base_path(base_path)
    if base_path:
        if route == base_path:
            return "/"
        if route.startswith(base_path + "/"):
            return route[len(base_path):] or "/"
    return route


def build_status_html(base_path: str = "") -> str:
    manage_url = prefixed_url(base_path, "/manage")
    map_url = prefixed_url(base_path, "/map")
    status_json_url = prefixed_url(base_path, "/status.json")
    packets_json_url = prefixed_url(base_path, "/packets.json")
    sensors_json_url = prefixed_url(base_path, "/sensors.json")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MeshCoreNG TCP Bridge Status</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #050806;
      --panel: rgba(8, 18, 12, .88);
      --panel-2: rgba(13, 28, 19, .82);
      --line: rgba(97, 255, 154, .28);
      --line-strong: rgba(97, 255, 154, .55);
      --green: #68ff9d;
      --green-soft: #a1ffc4;
      --amber: #ffd166;
      --red: #ff5f6d;
      --muted: #8fb99e;
      --text: #dfffe9;
      --shadow: 0 18px 60px rgba(0, 0, 0, .45);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
    }}
    * {{ box-sizing: border-box; }}
    html {{ min-height: 100%; background: var(--bg); }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background:
        radial-gradient(circle at 18% 12%, rgba(104, 255, 157, .12), transparent 28%),
        linear-gradient(180deg, rgba(2, 10, 6, .7), rgba(2, 5, 3, .98)),
        var(--bg);
      overflow-x: hidden;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(rgba(104, 255, 157, .04) 50%, rgba(0, 0, 0, .13) 50%),
        linear-gradient(90deg, rgba(255, 0, 0, .025), rgba(0, 255, 95, .018), rgba(0, 120, 255, .025));
      background-size: 100% 4px, 7px 100%;
      mix-blend-mode: screen;
      opacity: .42;
      z-index: 3;
    }}
    main {{
      width: min(1480px, 100%);
      margin: 0 auto;
      padding: 24px;
      position: relative;
      z-index: 1;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
      padding: 18px 0 22px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0;
      color: var(--green);
      font-size: clamp(1.5rem, 3vw, 2.8rem);
      letter-spacing: 0;
      text-transform: uppercase;
      text-shadow: 0 0 16px rgba(104, 255, 157, .45);
    }}
    .subtitle {{ margin: 8px 0 0; color: var(--muted); max-width: 820px; line-height: 1.45; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }}
    a {{
      color: var(--green-soft);
      text-decoration: none;
      border: 1px solid var(--line);
      background: rgba(104, 255, 157, .07);
      padding: 9px 12px;
      border-radius: 4px;
    }}
    a:hover {{ border-color: var(--green); box-shadow: 0 0 18px rgba(104, 255, 157, .22); }}
    .status-strip {{
      display: grid;
      grid-template-columns: repeat(5, minmax(150px, 1fr));
      gap: 12px;
      margin: 20px 0;
    }}
    .metric, .panel {{
      background: linear-gradient(180deg, var(--panel), rgba(3, 10, 6, .92));
      border: 1px solid var(--line);
      box-shadow: var(--shadow), inset 0 0 24px rgba(104, 255, 157, .035);
      border-radius: 6px;
    }}
    .metric {{ padding: 14px; min-height: 96px; }}
    .label {{ color: var(--muted); font-size: .76rem; text-transform: uppercase; }}
    .value {{ margin-top: 8px; color: var(--green); font-size: clamp(1.4rem, 2.4vw, 2.2rem); font-weight: 800; }}
    .value.small {{ font-size: 1rem; overflow-wrap: anywhere; }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(360px, .85fr);
      gap: 16px;
      align-items: start;
    }}
    .panel {{ overflow: hidden; }}
    .panel-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 13px 14px;
      border-bottom: 1px solid var(--line);
      background: rgba(104, 255, 157, .06);
    }}
    h2 {{ margin: 0; font-size: .95rem; color: var(--green-soft); text-transform: uppercase; }}
    .pulse {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: .78rem;
      white-space: nowrap;
    }}
    .pulse::before {{
      content: "";
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 14px var(--green);
    }}
    .pulse.warn::before {{ background: var(--amber); box-shadow: 0 0 14px var(--amber); }}
    .pulse.error::before {{ background: var(--red); box-shadow: 0 0 14px var(--red); }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 840px; }}
    th, td {{
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid rgba(97, 255, 154, .14);
      white-space: nowrap;
      vertical-align: top;
      font-size: .84rem;
    }}
    th {{ color: var(--muted); background: rgba(0, 0, 0, .24); text-transform: uppercase; font-size: .68rem; }}
    td {{ color: #dfffe9; }}
    tr.hot td {{ color: var(--green-soft); background: rgba(104, 255, 157, .055); }}
    .badge {{
      display: inline-block;
      min-width: 42px;
      text-align: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 8px;
      color: var(--green-soft);
      background: rgba(104, 255, 157, .08);
    }}
    .badge.rx {{ color: #86c5ff; border-color: rgba(134, 197, 255, .45); }}
    .badge.tx {{ color: var(--amber); border-color: rgba(255, 209, 102, .45); }}
    .preview {{ max-width: 520px; white-space: normal; overflow-wrap: anywhere; color: var(--muted); }}
    .empty {{ text-align: center; color: var(--muted); padding: 28px; }}
    .feed {{
      padding: 12px 14px;
      height: 430px;
      overflow: auto;
      background: rgba(0, 0, 0, .24);
    }}
    .feed-line {{
      display: grid;
      grid-template-columns: 72px 44px minmax(88px, 1fr);
      gap: 10px;
      padding: 6px 0;
      border-bottom: 1px dashed rgba(97, 255, 154, .14);
      font-size: .82rem;
    }}
    .feed-line .meta {{ color: var(--muted); }}
    .feed-line .dir-rx {{ color: #86c5ff; }}
    .feed-line .dir-tx {{ color: var(--amber); }}
    .feed-line .packet {{ overflow-wrap: anywhere; }}
    .stack {{ display: grid; gap: 16px; }}
    .node-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
      padding: 14px;
    }}
    .node-card {{
      border: 1px solid rgba(97, 255, 154, .22);
      background: var(--panel-2);
      border-radius: 6px;
      padding: 12px;
      min-height: 148px;
    }}
    .node-title {{ display: flex; justify-content: space-between; gap: 10px; color: var(--green-soft); font-weight: 800; }}
    .node-meta {{ margin-top: 8px; color: var(--muted); font-size: .78rem; overflow-wrap: anywhere; }}
    .node-stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px; }}
    .mini {{ border: 1px solid rgba(97, 255, 154, .14); padding: 8px; border-radius: 4px; }}
    .mini b {{ display: block; color: var(--green); font-size: 1rem; margin-top: 4px; }}
    @media (max-width: 980px) {{
      main {{ padding: 16px 12px; }}
      .topbar {{ display: block; }}
      nav {{ justify-content: flex-start; margin-top: 14px; }}
      .status-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .grid {{ grid-template-columns: 1fr; }}
      .feed {{ height: 340px; }}
    }}
    @media (max-width: 560px) {{
      .status-strip {{ grid-template-columns: 1fr; }}
      .node-stats {{ grid-template-columns: 1fr; }}
      table {{ min-width: 760px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="topbar">
      <div>
        <h1>TCP Bridge Tactical Console</h1>
        <p class="subtitle">MeshCoreNG live bridge telemetry, packet flow and nearby sensor adverts. Polling the bridge server every 2 seconds.</p>
      </div>
      <nav>
        <a href="{manage_url}">Remote management</a>
        <a href="{map_url}">Tracker map</a>
      </nav>
    </header>

    <section class="status-strip" aria-label="Live counters">
      <div class="metric"><div class="label">Bridge nodes online</div><div id="metricConnected" class="value">--</div></div>
      <div class="metric"><div class="label">Packets in buffer</div><div id="metricPackets" class="value">--</div></div>
      <div class="metric"><div class="label">Nearby sensors</div><div id="metricSensors" class="value">--</div></div>
      <div class="metric"><div class="label">RX / TX 24h</div><div id="metricTraffic" class="value small">-- / --</div></div>
      <div class="metric"><div class="label">Last sync</div><div id="metricSync" class="value small">booting</div></div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>Bridge nodes</h2>
        <span id="nodeStatus" class="pulse warn">connecting</span>
      </div>
      <div id="nodeCards" class="node-grid"></div>
    </section>

    <div class="grid" style="margin-top:16px">
      <section class="panel">
        <div class="panel-head">
          <h2>Packet log</h2>
          <span id="packetStatus" class="pulse warn">waiting</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Age</th>
                <th>Dir</th>
                <th>From</th>
                <th>To</th>
                <th>Type</th>
                <th>Route</th>
                <th>Hops</th>
                <th>Bytes</th>
                <th>V2</th>
                <th>TTL</th>
                <th>Channel</th>
                <th>Decoded</th>
                <th>Preview</th>
              </tr>
            </thead>
            <tbody id="packetRows">
              <tr><td colspan="13" class="empty">Loading packet telemetry</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="stack">
        <section class="panel">
          <div class="panel-head">
            <h2>Live terminal feed</h2>
            <span id="feedStatus" class="pulse warn">arming</span>
          </div>
          <div id="packetFeed" class="feed"></div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <h2>Sensor nodes nearby</h2>
            <span id="sensorStatus" class="pulse warn">scanning</span>
          </div>
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
              <tbody id="sensorRows">
                <tr><td colspan="7" class="empty">Scanning for sensor adverts</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  </main>
  <script>
    const urls = {{
      status: "{status_json_url}",
      packets: "{packets_json_url}",
      sensors: "{sensors_json_url}"
    }};
    const state = {{
      seenPacketKeys: new Set(),
      firstPacketLoad: true
    }};

    const text = (value, fallback = "") => value === null || value === undefined || value === "" ? fallback : String(value);
    const age = (seconds) => seconds === null || seconds === undefined ? "never" : `${{seconds}}s`;
    const yesNo = (value) => value ? "yes" : "no";

    function escapeHtml(value) {{
      return text(value).replace(/[&<>"']/g, (char) => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }}[char]));
    }}

    function setStatus(id, label, mode = "ok") {{
      const el = document.getElementById(id);
      el.textContent = label;
      el.className = mode === "error" ? "pulse error" : mode === "warn" ? "pulse warn" : "pulse";
    }}

    async function getJson(url) {{
      const response = await fetch(url, {{ cache: "no-store" }});
      if (!response.ok) throw new Error(`${{response.status}} ${{response.statusText}}`);
      return response.json();
    }}

    function renderMetrics(status, packets, sensors) {{
      const rx24 = status.clients.reduce((sum, client) => sum + (client.packets_rx_24h || 0), 0);
      const tx24 = status.clients.reduce((sum, client) => sum + (client.packets_tx_24h || 0), 0);
      document.getElementById("metricConnected").textContent = status.connected_count;
      document.getElementById("metricPackets").textContent = packets.packet_count;
      document.getElementById("metricSensors").textContent = sensors.sensor_count;
      document.getElementById("metricTraffic").textContent = `${{rx24}} / ${{tx24}}`;
      document.getElementById("metricSync").textContent = new Date().toLocaleTimeString();
    }}

    function renderNodes(status) {{
      const target = document.getElementById("nodeCards");
      if (!status.clients.length) {{
        target.innerHTML = '<div class="empty">No bridge nodes connected</div>';
        setStatus("nodeStatus", "offline", "warn");
        return;
      }}
      setStatus("nodeStatus", `${{status.clients.length}} active`, "ok");
      target.innerHTML = status.clients.map((client) => {{
        const heartbeat = client.heartbeat_age_seconds === null ? "never" : `${{client.heartbeat_age_seconds}}s ago`;
        return `
          <article class="node-card">
            <div class="node-title">
              <span>${{escapeHtml(client.display_name)}}</span>
              <span class="badge">${{client.supports_bridge_v2 ? "v2" : "v1"}}</span>
            </div>
            <div class="node-meta">node id ${{escapeHtml(client.node_id || "unknown")}}<br>${{escapeHtml(client.firmware_version || "firmware unknown")}}</div>
            <div class="node-stats">
              <div class="mini"><span class="label">RX 24h</span><b>${{client.packets_rx_24h}}</b></div>
              <div class="mini"><span class="label">TX 24h</span><b>${{client.packets_tx_24h}}</b></div>
              <div class="mini"><span class="label">HB</span><b>${{client.heartbeats_rx}}</b></div>
            </div>
            <div class="node-meta">connected ${{escapeHtml(client.connected_for)}} · idle ${{client.idle_seconds}}s · heartbeat ${{heartbeat}}</div>
          </article>
        `;
      }}).join("");
    }}

    function packetKey(packet) {{
      return [packet.time, packet.direction, packet.client, packet.size, packet.preview].join("|");
    }}

    function renderPackets(packetData) {{
      const rows = document.getElementById("packetRows");
      const packets = packetData.packets.slice(0, 50);
      if (!packets.length) {{
        rows.innerHTML = '<tr><td colspan="13" class="empty">No packets seen yet</td></tr>';
        document.getElementById("packetFeed").innerHTML = '<div class="empty">Awaiting mesh traffic</div>';
        setStatus("packetStatus", "no traffic", "warn");
        setStatus("feedStatus", "quiet", "warn");
        return;
      }}
      setStatus("packetStatus", `${{packets.length}} buffered`, "ok");
      setStatus("feedStatus", "live", "ok");
      rows.innerHTML = packets.map((packet, index) => {{
        const dirClass = packet.direction === "RX" ? "rx" : "tx";
        return `
          <tr class="${{index < 3 ? "hot" : ""}}">
            <td>${{age(packet.age_seconds)}} ago</td>
            <td><span class="badge ${{dirClass}}">${{escapeHtml(packet.direction)}}</span></td>
            <td>${{escapeHtml(packet.source || packet.client || "")}}</td>
            <td>${{escapeHtml(packet.target || "")}}</td>
            <td>${{escapeHtml(packet.type || "unknown")}}</td>
            <td>${{escapeHtml(packet.route || "")}}</td>
            <td>${{text(packet.hops, "")}}</td>
            <td>${{packet.size}}</td>
            <td>${{yesNo(packet.bridge_v2)}}</td>
            <td>${{text(packet.ttl, "")}}</td>
            <td>${{escapeHtml(packet.decoded_channel || "")}}</td>
            <td class="preview">${{escapeHtml(packet.decoded_text || packet.decoded_status || "")}}</td>
            <td class="preview">${{escapeHtml(packet.preview)}}</td>
          </tr>
        `;
      }}).join("");

      const feed = document.getElementById("packetFeed");
      if (state.firstPacketLoad) {{
        state.seenPacketKeys = new Set(packets.map(packetKey));
        state.firstPacketLoad = false;
      }} else {{
        for (const packet of packets.slice().reverse()) {{
          const key = packetKey(packet);
          if (state.seenPacketKeys.has(key)) continue;
          state.seenPacketKeys.add(key);
          const line = document.createElement("div");
          const dirClass = packet.direction === "RX" ? "dir-rx" : "dir-tx";
          line.className = "feed-line";
          line.innerHTML = `
            <span class="meta">${{age(packet.age_seconds)}} ago</span>
            <span class="${{dirClass}}">${{escapeHtml(packet.direction)}}</span>
            <span class="packet">${{escapeHtml(packet.flow || packet.client)}} :: ${{escapeHtml(packet.type || "unknown")}}/${{escapeHtml(packet.route || "-")}} ${{packet.size}}B${{packet.decoded_channel ? " :: " + escapeHtml(packet.decoded_channel) + " :: " + escapeHtml(packet.decoded_text || packet.decoded_status || "") : ""}} :: ${{escapeHtml(packet.preview)}}</span>
          `;
          feed.prepend(line);
        }}
      }}
      if (!feed.children.length) {{
        feed.innerHTML = packets.slice(0, 24).map((packet) => `
          <div class="feed-line">
            <span class="meta">${{age(packet.age_seconds)}} ago</span>
            <span class="${{packet.direction === "RX" ? "dir-rx" : "dir-tx"}}">${{escapeHtml(packet.direction)}}</span>
            <span class="packet">${{escapeHtml(packet.flow || packet.client)}} :: ${{escapeHtml(packet.type || "unknown")}}/${{escapeHtml(packet.route || "-")}} ${{packet.size}}B${{packet.decoded_channel ? " :: " + escapeHtml(packet.decoded_channel) + " :: " + escapeHtml(packet.decoded_text || packet.decoded_status || "") : ""}} :: ${{escapeHtml(packet.preview)}}</span>
          </div>
        `).join("");
      }}
      while (feed.children.length > 80) feed.removeChild(feed.lastChild);
    }}

    function renderSensors(sensorData) {{
      const rows = document.getElementById("sensorRows");
      if (!sensorData.sensors.length) {{
        rows.innerHTML = '<tr><td colspan="7" class="empty">No sensor node adverts seen yet</td></tr>';
        setStatus("sensorStatus", "no adverts", "warn");
        return;
      }}
      setStatus("sensorStatus", `${{sensorData.sensors.length}} detected`, "ok");
      rows.innerHTML = sensorData.sensors.map((sensor) => {{
        const location = sensor.lat !== null && sensor.lon !== null ? `${{Number(sensor.lat).toFixed(6)}}, ${{Number(sensor.lon).toFixed(6)}}` : "not shared";
        return `
          <tr>
            <td>${{escapeHtml(sensor.name || "unknown")}}</td>
            <td>${{escapeHtml(sensor.node_id)}}</td>
            <td>${{age(sensor.age_seconds)}} ago</td>
            <td>${{sensor.seen_count}}</td>
            <td>${{text(sensor.hops, "")}}</td>
            <td>${{escapeHtml(sensor.source)}}</td>
            <td>${{escapeHtml(location)}}</td>
          </tr>
        `;
      }}).join("");
    }}

    async function refresh() {{
      try {{
        const [status, packets, sensors] = await Promise.all([
          getJson(urls.status),
          getJson(urls.packets),
          getJson(urls.sensors)
        ]);
        renderMetrics(status, packets, sensors);
        renderNodes(status);
        renderPackets(packets);
        renderSensors(sensors);
      }} catch (error) {{
        document.getElementById("metricSync").textContent = "link error";
        setStatus("nodeStatus", "link error", "error");
        setStatus("packetStatus", "link error", "error");
        setStatus("feedStatus", "link error", "error");
        setStatus("sensorStatus", "link error", "error");
        console.error(error);
      }}
    }}

    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>
"""


def build_manage_html(command_result: str = "", base_path: str = "") -> str:
    snapshot = status_snapshot()
    options = []
    for client in snapshot["clients"]:
        label = client["display_name"]
        if client.get("node_id"):
            label += f" [{client['node_id']}]"
        if client["firmware_version"]:
            label += f" ({client['firmware_version']})"
        options.append(
            f'<option value="{html.escape(client["id"], quote=True)}">{html.escape(label)}</option>'
        )

    options_html = "\n".join(options) if options else (
        '<option value="">No bridge nodes connected</option>'
    )
    disabled = " disabled" if not options else ""
    admin_note = (
        "Remote management protected by server admin password; node password still required"
        if ADMIN_PASSWORD else
        "Remote management enabled; enter the selected node's admin password"
    )
    result_html = (
        f'<pre class="command-result">{html.escape(redact_public_text(command_result))}</pre>'
        if command_result else
        '<pre class="command-result empty">No command sent yet</pre>'
    )

    status_url = prefixed_url(base_path, "/")
    command_url = prefixed_url(base_path, "/command")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MeshCoreNG Remote Management</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #f4f6f8; color: #1b1f24; }}
    main {{ max-width: 760px; margin: 0 auto; padding: 32px 20px; }}
    h1 {{ margin: 0 0 6px; font-size: clamp(1.6rem, 4vw, 2.4rem); }}
    .summary {{ margin: 0 0 24px; color: #58606a; }}
    .panel {{ background: #fff; border: 1px solid #d8dee4; border-radius: 8px; padding: 18px; }}
    label {{ display: block; font-weight: 650; margin: 14px 0 6px; }}
    select, input {{ width: 100%; box-sizing: border-box; padding: 10px 12px; border: 1px solid #c7ced6; border-radius: 6px; font: inherit; background: #fff; color: inherit; }}
    button {{ margin-top: 16px; padding: 10px 14px; border: 0; border-radius: 6px; background: #0969da; color: #fff; font: inherit; font-weight: 650; cursor: pointer; }}
    button:disabled {{ background: #8c959f; cursor: not-allowed; }}
    .command-result {{ margin: 18px 0 0; padding: 14px; min-height: 72px; overflow-x: auto; border-radius: 6px; background: #20262d; color: #f0f3f6; white-space: pre-wrap; }}
    .empty {{ color: #9aa4af; }}
    a {{ color: #0969da; }}
    @media (max-width: 760px) {{
      main {{ padding: 20px 12px; }}
    }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #111418; color: #f0f3f6; }}
      .summary {{ color: #9aa4af; }}
      .panel {{ background: #171b20; border-color: #30363d; }}
      select, input {{ background: #111418; border-color: #3b434d; }}
      a {{ color: #7cb7ff; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>MeshCoreNG Remote Management</h1>
    <p class="summary">{html.escape(admin_note)}. <a href="{status_url}">Bridge status</a></p>
    <div class="panel">
      <form method="post" action="{command_url}">
        <label for="target">Bridge node</label>
        <select id="target" name="target"{disabled}>
          {options_html}
        </select>
        <label for="node_password">Node admin password</label>
        <input id="node_password" name="node_password" type="password" autocomplete="current-password" maxlength="32"{disabled}>
        <label for="command">Command</label>
        <input id="command" name="command" placeholder="get bridge.status" maxlength="96"{disabled}>
        <button type="submit"{disabled}>Send command</button>
      </form>
      {result_html}
    </div>
  </main>
</body>
</html>
"""


def build_location_map_html(base_path: str = "") -> str:
    status_url = prefixed_url(base_path, "/")
    locations_url = prefixed_url(base_path, "/locations.json")
    page = """<!doctype html>
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
    .tracker-icon {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: #0969da;
      border: 2px solid #fff;
      box-shadow: 0 2px 8px rgba(0,0,0,.35);
      position: relative;
    }
    .tracker-icon::before {
      content: "";
      position: absolute;
      left: 50%;
      top: -11px;
      transform: translateX(-50%);
      border-left: 7px solid transparent;
      border-right: 7px solid transparent;
      border-bottom: 14px solid #0969da;
      filter: drop-shadow(0 -1px 1px rgba(0,0,0,.25));
    }
    .tracker-icon.stationary::before { display: none; }
    .tracker-label {
      margin-left: 32px;
      margin-top: -28px;
      padding: 2px 5px;
      border-radius: 4px;
      background: rgba(255,255,255,.9);
      border: 1px solid #d8dee4;
      color: #24292f;
      font-size: 11px;
      font-weight: 700;
      white-space: nowrap;
      box-shadow: 0 1px 4px rgba(0,0,0,.16);
    }
  </style>
</head>
<body>
  <div class="topbar">
    <h1>MeshCoreNG Tracker Map</h1>
    <span class="muted" id="summary">Loading...</span>
    <a href="__STATUS_URL__">Bridge status</a>
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
    const tracks = new Map();

    function fmtAge(seconds) {
      if (seconds < 60) return `${seconds}s`;
      if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
      return `${Math.floor(seconds / 3600)}h`;
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[char]));
    }

    function fmtNumber(value, decimals = 1) {
      const num = Number(value);
      return Number.isFinite(num) ? num.toFixed(decimals) : '';
    }

    function fmtSpeed(value) {
      const speed = fmtNumber(value, 1);
      return speed ? `${speed} km/h` : 'unknown';
    }

    function fmtHeading(value) {
      const heading = fmtNumber(value, 0);
      return heading ? `${heading}&deg;` : 'unknown';
    }

    function trackerIcon(loc) {
      const heading = Number(loc.heading_deg);
      const speed = Number(loc.speed_kmh);
      const moving = Number.isFinite(speed) && speed >= 1;
      const rotation = Number.isFinite(heading) ? heading : 0;
      const labelSpeed = Number.isFinite(speed) ? `${speed.toFixed(0)} km/h` : '';
      return L.divIcon({
        className: '',
        iconSize: [110, 34],
        iconAnchor: [14, 14],
        popupAnchor: [0, -16],
        html: `<div class="tracker-icon ${moving ? '' : 'stationary'}" style="transform: rotate(${rotation}deg)"></div>` +
          `<div class="tracker-label">${escapeHtml(labelSpeed || '0 km/h')} ${Number.isFinite(heading) ? Math.round(heading) + '&deg;' : ''}</div>`
      });
    }

    function trackLatLngs(loc) {
      const points = Array.isArray(loc.track) ? loc.track : [];
      return points
        .map(point => [Number(point.lat), Number(point.lon)])
        .filter(([lat, lon]) => Number.isFinite(lat) && Number.isFinite(lon));
    }

    function routeDistanceKm(latlngs) {
      let km = 0;
      for (let i = 1; i < latlngs.length; i++) {
        km += map.distance(latlngs[i - 1], latlngs[i]) / 1000;
      }
      return km;
    }

    async function refresh() {
      const res = await fetch('__LOCATIONS_URL__', { cache: 'no-store' });
      const data = await res.json();
      document.getElementById('summary').textContent = `${data.location_count} tracker node(s)`;
      const seen = new Set();
      for (const loc of data.locations) {
        seen.add(loc.node_id);
        const label = loc.name || loc.node_id;
        const latlngs = trackLatLngs(loc);
        const routeKm = routeDistanceKm(latlngs);
        const popup = `<strong>${escapeHtml(label)}</strong><br>` +
          `Node: ${escapeHtml(loc.node_id)}<br>` +
          `Age: ${fmtAge(loc.age_seconds)}<br>` +
          `Speed: ${fmtSpeed(loc.speed_kmh)}<br>` +
          `Heading: ${fmtHeading(loc.heading_deg)}<br>` +
          `Track: ${latlngs.length} point(s), ${routeKm.toFixed(2)} km<br>` +
          `Sats: ${loc.satellites}<br>` +
          `Battery: ${loc.battery_mv} mV<br>` +
          `Alt: ${loc.altitude_m} m`;
        let track = tracks.get(loc.node_id);
        if (latlngs.length >= 2) {
          if (!track) {
            track = L.polyline(latlngs, {
              color: '#0969da',
              weight: 4,
              opacity: 0.7,
              lineJoin: 'round'
            }).addTo(map);
            tracks.set(loc.node_id, track);
          } else {
            track.setLatLngs(latlngs);
          }
        } else if (track) {
          track.remove();
          tracks.delete(loc.node_id);
        }
        let marker = markers.get(loc.node_id);
        if (!marker) {
          marker = L.marker([loc.lat, loc.lon], { icon: trackerIcon(loc) }).addTo(map);
          markers.set(loc.node_id, marker);
        } else {
          marker.setLatLng([loc.lat, loc.lon]);
          marker.setIcon(trackerIcon(loc));
        }
        marker.bindPopup(popup);
      }
      for (const [nodeId, marker] of markers) {
        if (!seen.has(nodeId)) {
          marker.remove();
          markers.delete(nodeId);
        }
      }
      for (const [nodeId, track] of tracks) {
        if (!seen.has(nodeId)) {
          track.remove();
          tracks.delete(nodeId);
        }
      }
      if (data.locations.length && !refresh.didFit) {
        const bounds = data.locations.flatMap(loc => {
          const latlngs = trackLatLngs(loc);
          return latlngs.length ? latlngs : [[loc.lat, loc.lon]];
        });
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
    return page.replace("__STATUS_URL__", status_url).replace("__LOCATIONS_URL__", locations_url)


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
        base_path = request_base_path(headers)
        route = strip_base_path(path, base_path)
        extra_headers: list[tuple[str, str]] = []

        if len(parts) < 2:
            status, content_type, body = "405 Method Not Allowed", "text/plain", b"Method not allowed\n"
        elif method == "POST" and route == "/command":
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
                    except asyncio.TimeoutError:
                        log.warning("%s: remote command timed out: %s", client.addr, command)
                        result = "Error: command timed out waiting for bridge reply"
                    except Exception as exc:
                        result = f"Error: {exc}"
                status, content_type = "200 OK", "text/html; charset=utf-8"
                body = build_manage_html(result, base_path).encode("utf-8")
        elif method != "GET":
            status, content_type, body = "405 Method Not Allowed", "text/plain", b"Method not allowed\n"
        elif route == "/status.json":
            status, content_type = "200 OK", "application/json"
            body = json.dumps(status_snapshot(), indent=2).encode("utf-8")
        elif route == "/locations.json":
            status, content_type = "200 OK", "application/json"
            body = json.dumps(locations_snapshot(), indent=2).encode("utf-8")
        elif route == "/sensors.json":
            status, content_type = "200 OK", "application/json"
            body = json.dumps(sensors_snapshot(), indent=2).encode("utf-8")
        elif route == "/packets.json":
            status, content_type = "200 OK", "application/json"
            body = json.dumps(packets_snapshot(), indent=2).encode("utf-8")
        elif route == "/map":
            status, content_type = "200 OK", "text/html; charset=utf-8"
            body = build_location_map_html(base_path).encode("utf-8")
        elif route == "/manage":
            if not is_admin_authorized(headers):
                status, content_type, body, extra_headers = admin_auth_response()
            else:
                status, content_type = "200 OK", "text/html; charset=utf-8"
                body = build_manage_html(base_path=base_path).encode("utf-8")
        elif route in ("/", "/status"):
            status, content_type = "200 OK", "text/html; charset=utf-8"
            body = build_status_html(base_path).encode("utf-8")
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
    parser.add_argument("--status-base-path", default=STATUS_BASE_PATH,
                        help="Public URL prefix for status pages behind a reverse proxy, e.g. /meshbridgestatus")
    parser.add_argument("--public-channels-file", default="",
                        help="JSON file with public channel names/secrets for optional group packet decoding")
    parser.add_argument("--replace-same-ip", action="store_true",
                        help="When a new client connects, disconnect older clients from the same IP")
    parser.add_argument("--password", default="",
                        help="Optional TCP bridge password required from clients")
    parser.add_argument("--admin-password", default="",
                        help="Optional Basic auth password protecting the HTTP remote management page")
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
    STATUS_BASE_PATH = normalize_base_path(args.status_base_path)
    PUBLIC_CHANNELS_FILE = args.public_channels_file
    load_public_channels(PUBLIC_CHANNELS_FILE)

    try:
        asyncio.run(main(args.host, args.port, args.status_host, max(0, args.status_port)))
    except KeyboardInterrupt:
        log.info("Server stopped")
