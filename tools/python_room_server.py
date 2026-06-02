#!/usr/bin/env python3
"""
MeshCoreNG Python Room Server

Connects to tools/tcp_bridge_server.py as a bridge client and behaves like a
minimal MeshCore room server. It speaks MeshCore packet crypto and bridge
framing, so a TCP bridge repeater with `set bridge.rf on` can carry room
traffic between this script and the RF mesh.

Usage:
    python3 tools/python_room_server.py --server 127.0.0.1 --port 4200 \
        --name "Python Room" --password secret

Optional scoped flood traffic:
    python3 tools/python_room_server.py --scope nl-nh-hhw ...

Requires:
    pip install cryptography
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import logging
import os
import random
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


log = logging.getLogger("python_room_server")

BRIDGE_MAGIC = 0xC03E
MAX_PAYLOAD = 256

MAX_HASH_SIZE = 8
PUB_KEY_SIZE = 32
CIPHER_MAC_SIZE = 2
CIPHER_BLOCK_SIZE = 16
PATH_HASH_SIZE = 1
MAX_PACKET_PAYLOAD = 184
MAX_PATH_SIZE = 64
MAX_ADVERT_DATA_SIZE = 32

ROUTE_TYPE_TRANSPORT_FLOOD = 0x00
ROUTE_TYPE_FLOOD = 0x01
ROUTE_TYPE_DIRECT = 0x02
ROUTE_TYPE_TRANSPORT_DIRECT = 0x03

PAYLOAD_TYPE_REQ = 0x00
PAYLOAD_TYPE_RESPONSE = 0x01
PAYLOAD_TYPE_TXT_MSG = 0x02
PAYLOAD_TYPE_ACK = 0x03
PAYLOAD_TYPE_ADVERT = 0x04
PAYLOAD_TYPE_ANON_REQ = 0x07
PAYLOAD_TYPE_PATH = 0x08

TXT_TYPE_PLAIN = 0
TXT_TYPE_CLI_DATA = 1
TXT_TYPE_SIGNED_PLAIN = 2

ADV_TYPE_ROOM = 3
ADV_NAME_MASK = 0x80

REQ_TYPE_GET_STATUS = 0x01
REQ_TYPE_KEEP_ALIVE = 0x02
RESP_SERVER_LOGIN_OK = 0
FIRMWARE_VER_LEVEL = 1
CONTROL_TYPE_HEARTBEAT = 0x01
CONTROL_TYPE_NODE_INFO = 0x02

OUT_PATH_UNKNOWN = -1

PERM_ACL_ADMIN = 0x03
PERM_ACL_READ_WRITE = 0x02
PERM_ACL_GUEST = 0x01

POST_SYNC_DELAY_SECS = 6
PUSH_NOTIFY_DELAY_SECS = 2
SYNC_PUSH_INTERVAL_SECS = 1.2
PUSH_ACK_TIMEOUT_SECS = 18
CLIENT_TIMEOUT_SECS = 900
HEARTBEAT_INTERVAL_SECS = 30


def fletcher16(data: bytes) -> int:
    s1 = 0
    s2 = 0
    for b in data:
        s1 = (s1 + b) % 255
        s2 = (s2 + s1) % 255
    return (s2 << 8) | s1


def now_unique(last: list[int]) -> int:
    t = int(time.time())
    if t <= last[0]:
        t = last[0] + 1
    last[0] = t
    return t


def trunc_c_string(data: bytes) -> bytes:
    idx = data.find(b"\x00")
    return data if idx < 0 else data[:idx]


def hash_prefix(pub: bytes, size: int = PATH_HASH_SIZE) -> bytes:
    return pub[:size]


def packet_hash(payload_type: int, payload: bytes, path_len: int = 0) -> bytes:
    h = hashlib.sha256()
    h.update(bytes([payload_type]))
    if payload_type == 0x09:
        h.update(struct.pack("<H", path_len))
    h.update(payload)
    return h.digest()[:MAX_HASH_SIZE]


def aes_ecb_encrypt(secret: bytes, data: bytes) -> bytes:
    key = secret[:16]
    if len(data) % CIPHER_BLOCK_SIZE:
        data += b"\x00" * (CIPHER_BLOCK_SIZE - (len(data) % CIPHER_BLOCK_SIZE))
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    enc = cipher.encryptor()
    return enc.update(data) + enc.finalize()


def aes_ecb_decrypt(secret: bytes, data: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(secret[:16]), modes.ECB())
    dec = cipher.decryptor()
    return dec.update(data) + dec.finalize()


def encrypt_then_mac(secret: bytes, data: bytes) -> bytes:
    enc = aes_ecb_encrypt(secret, data)
    mac = hmac.new(secret, enc, hashlib.sha256).digest()[:CIPHER_MAC_SIZE]
    return mac + enc


def mac_then_decrypt(secret: bytes, data: bytes) -> bytes | None:
    if len(data) <= CIPHER_MAC_SIZE:
        return None
    mac = hmac.new(secret, data[CIPHER_MAC_SIZE:], hashlib.sha256).digest()[:CIPHER_MAC_SIZE]
    if mac != data[:CIPHER_MAC_SIZE]:
        return None
    return aes_ecb_decrypt(secret, data[CIPHER_MAC_SIZE:])


P = 2**255 - 19


def ed_pub_to_x25519_u(pub: bytes) -> bytes:
    y_bytes = bytearray(pub)
    y_bytes[31] &= 0x7F
    y = int.from_bytes(y_bytes, "little")
    u = ((1 + y) * pow(1 - y, P - 2, P)) % P
    return u.to_bytes(32, "little")


def transport_key_for_name(name: str) -> bytes:
    if not name.startswith("#"):
        name = "#" + name
    return hashlib.sha256(name.encode("utf-8")).digest()


@dataclass
class Packet:
    header: int
    path_len: int = 0
    path: bytes = b""
    payload: bytes = b""
    transport_codes: tuple[int, int] = (0, 0)

    @property
    def route_type(self) -> int:
        return self.header & 0x03

    @property
    def payload_type(self) -> int:
        return (self.header >> 2) & 0x0F

    @property
    def is_flood(self) -> bool:
        return self.route_type in (ROUTE_TYPE_FLOOD, ROUTE_TYPE_TRANSPORT_FLOOD)

    @property
    def is_direct(self) -> bool:
        return self.route_type in (ROUTE_TYPE_DIRECT, ROUTE_TYPE_TRANSPORT_DIRECT)

    @property
    def has_transport_codes(self) -> bool:
        return self.route_type in (ROUTE_TYPE_TRANSPORT_FLOOD, ROUTE_TYPE_TRANSPORT_DIRECT)

    @property
    def path_hash_size(self) -> int:
        return (self.path_len >> 6) + 1

    @property
    def path_hash_count(self) -> int:
        return self.path_len & 63

    @property
    def path_byte_len(self) -> int:
        return self.path_hash_count * self.path_hash_size

    def key(self) -> bytes:
        return packet_hash(self.payload_type, self.payload, self.path_len)

    @classmethod
    def parse(cls, raw: bytes) -> "Packet | None":
        if len(raw) < 3:
            return None
        i = 0
        header = raw[i]
        i += 1
        route_type = header & 0x03
        transport_codes = (0, 0)
        if route_type in (ROUTE_TYPE_TRANSPORT_FLOOD, ROUTE_TYPE_TRANSPORT_DIRECT):
            if len(raw) < i + 4:
                return None
            transport_codes = struct.unpack_from("<HH", raw, i)
            i += 4
        path_len = raw[i]
        i += 1
        path_hash_size = (path_len >> 6) + 1
        if path_hash_size > 3:
            return None
        path_byte_len = (path_len & 63) * path_hash_size
        if path_byte_len > MAX_PATH_SIZE or len(raw) < i + path_byte_len:
            return None
        path = raw[i:i + path_byte_len]
        i += path_byte_len
        payload = raw[i:]
        if len(payload) > MAX_PACKET_PAYLOAD:
            return None
        return cls(header, path_len, path, payload, transport_codes)

    def encode(self) -> bytes:
        raw = bytearray([self.header])
        if self.has_transport_codes:
            raw.extend(struct.pack("<HH", *self.transport_codes))
        raw.append(self.path_len)
        raw.extend(self.path)
        raw.extend(self.payload)
        return bytes(raw)


@dataclass
class Client:
    pub: bytes
    secret: bytes
    permissions: int
    last_timestamp: int
    sync_since: int
    out_path_len: int = OUT_PATH_UNKNOWN
    out_path: bytes = b""
    last_activity: float = field(default_factory=time.time)
    pending_ack: bytes = b""
    pending_ack_post_ts: int = 0
    ack_deadline: float = 0.0
    push_failures: int = 0


@dataclass
class Post:
    author: bytes
    timestamp: int
    text: str


class PythonRoomServer:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.state_path = Path(args.state)
        self.seed, self.pub = self.load_or_create_identity()
        self.ed_private = ed25519.Ed25519PrivateKey.from_private_bytes(self.seed)
        self.private_scalar = self.derive_private_scalar(self.seed)
        self.scope_key = transport_key_for_name(args.scope) if args.scope else None
        self.clients: dict[bytes, Client] = {}
        self.posts: list[Post] = []
        self.seen: list[bytes] = []
        self.last_unique = [0]
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.started_at = time.monotonic()
        self.load_state()

    def derive_private_scalar(self, seed: bytes) -> bytes:
        h = bytearray(hashlib.sha512(seed).digest()[:32])
        h[0] &= 248
        h[31] &= 63
        h[31] |= 64
        return bytes(h)

    def load_or_create_identity(self) -> tuple[bytes, bytes]:
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text())
            seed = bytes.fromhex(data["identity_seed"])
            private = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
            pub = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            return seed, pub
        seed = os.urandom(32)
        private = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        pub = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        return seed, pub

    def load_state(self) -> None:
        if not self.state_path.exists():
            return
        data = json.loads(self.state_path.read_text())
        self.posts = [
            Post(bytes.fromhex(p["author"]), int(p["timestamp"]), p["text"])
            for p in data.get("posts", [])
        ]

    def save_state(self) -> None:
        data = {
            "identity_seed": self.seed.hex(),
            "public_key": self.pub.hex(),
            "name": self.args.name,
            "posts": [
                {"author": p.author.hex(), "timestamp": p.timestamp, "text": p.text}
                for p in self.posts[-self.args.max_posts:]
            ],
        }
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.state_path)

    def shared_secret(self, other_pub: bytes) -> bytes:
        private = x25519.X25519PrivateKey.from_private_bytes(self.private_scalar)
        public = x25519.X25519PublicKey.from_public_bytes(ed_pub_to_x25519_u(other_pub))
        return private.exchange(public)

    async def connect_loop(self) -> None:
        while True:
            try:
                log.info("Connecting to bridge server %s:%d", self.args.server, self.args.port)
                self.reader, self.writer = await asyncio.open_connection(self.args.server, self.args.port)
                log.info("Connected. Room pubkey: %s", self.pub.hex().upper())
                await self.send_node_info()
                await asyncio.gather(self.read_loop(), self.advert_loop(), self.push_loop(), self.heartbeat_loop())
            except (OSError, asyncio.IncompleteReadError) as exc:
                log.warning("Bridge connection lost: %s", exc)
            finally:
                if self.writer:
                    self.writer.close()
                    try:
                        await self.writer.wait_closed()
                    except Exception:
                        pass
                self.reader = None
                self.writer = None
            await asyncio.sleep(self.args.reconnect_delay)

    async def read_frame(self) -> bytes:
        assert self.reader is not None
        buf = bytearray()
        while True:
            b = await self.reader.readexactly(1)
            buf.append(b[0])
            if len(buf) >= 2:
                if buf[-2] == (BRIDGE_MAGIC >> 8) & 0xFF and buf[-1] == BRIDGE_MAGIC & 0xFF:
                    break
                buf = bytearray([buf[-1]])
        raw_len = await self.reader.readexactly(2)
        length = struct.unpack(">H", raw_len)[0]
        if length == 0 or length > MAX_PAYLOAD:
            raise ValueError(f"invalid bridge payload length {length}")
        payload = await self.reader.readexactly(length)
        raw_csum = await self.reader.readexactly(2)
        received_csum = struct.unpack(">H", raw_csum)[0]
        calc = fletcher16(payload)
        if received_csum != calc:
            raise ValueError("bridge checksum mismatch")
        return payload

    async def send_payload(self, payload: bytes) -> None:
        if not self.writer:
            return
        csum = fletcher16(payload)
        frame = struct.pack(">HH", BRIDGE_MAGIC, len(payload)) + payload + struct.pack(">H", csum)
        self.writer.write(frame)
        await self.writer.drain()

    async def send_packet(self, pkt: Packet) -> None:
        await self.send_payload(pkt.encode())

    async def send_node_info(self) -> None:
        name = self.args.name.encode("utf-8")[:32]
        await self.send_payload(b"MCNG" + bytes([CONTROL_TYPE_NODE_INFO, len(name)]) + name)

    async def send_heartbeat(self) -> None:
        uptime_ms = int((time.monotonic() - self.started_at) * 1000) & 0xFFFFFFFF
        await self.send_payload(b"MCNG" + bytes([CONTROL_TYPE_HEARTBEAT]) + struct.pack(">I", uptime_ms))

    async def heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECS)
            await self.send_heartbeat()

    async def read_loop(self) -> None:
        while True:
            raw = await self.read_frame()
            if raw.startswith(b"MCNG"):
                continue
            pkt = Packet.parse(raw)
            if not pkt:
                continue
            key = pkt.key()
            if key in self.seen:
                continue
            self.seen.append(key)
            self.seen = self.seen[-128:]
            await self.handle_packet(pkt)

    async def advert_loop(self) -> None:
        while True:
            await self.send_advert()
            await asyncio.sleep(self.args.advert_interval)

    async def push_loop(self) -> None:
        while True:
            await asyncio.sleep(SYNC_PUSH_INTERVAL_SECS)
            now = time.time()
            for pub, client in list(self.clients.items()):
                if now - client.last_activity > CLIENT_TIMEOUT_SECS:
                    del self.clients[pub]
                    continue
                if client.pending_ack and now > client.ack_deadline:
                    client.pending_ack = b""
                    client.push_failures += 1
                if client.pending_ack or client.push_failures >= 3:
                    continue
                for post in self.posts:
                    if post.timestamp <= client.sync_since:
                        continue
                    if post.author == client.pub:
                        continue
                    if int(time.time()) < post.timestamp + POST_SYNC_DELAY_SECS:
                        continue
                    await self.push_post(client, post)
                    break

    def calc_transport_codes(self, pkt: Packet) -> tuple[int, int]:
        if not self.scope_key:
            return (0, 0)
        data = bytes([pkt.payload_type]) + pkt.payload
        code = hmac.new(self.scope_key, data, hashlib.sha256).digest()[:2]
        value = struct.unpack("<H", code)[0]
        if value == 0:
            value = 1
        elif value == 0xFFFF:
            value = 0xFFFE
        return (value, 0)

    def flood_packet(self, payload_type: int, payload: bytes, path_hash_size: int = 1) -> Packet:
        route = ROUTE_TYPE_TRANSPORT_FLOOD if self.scope_key else ROUTE_TYPE_FLOOD
        pkt = Packet((payload_type << 2) | route, ((path_hash_size - 1) << 6), b"", payload)
        if self.scope_key:
            pkt.transport_codes = self.calc_transport_codes(pkt)
        return pkt

    def direct_packet(self, payload_type: int, payload: bytes, path_len: int, path: bytes) -> Packet:
        return Packet((payload_type << 2) | ROUTE_TYPE_DIRECT, path_len, path, payload)

    async def send_advert(self) -> None:
        name = self.args.name.encode("utf-8")[: MAX_ADVERT_DATA_SIZE - 1]
        app_data = bytes([ADV_TYPE_ROOM | ADV_NAME_MASK]) + name
        ts = struct.pack("<I", int(time.time()))
        message = self.pub + ts + app_data
        sig = self.ed_private.sign(message)
        payload = self.pub + ts + sig + app_data
        pkt = self.flood_packet(PAYLOAD_TYPE_ADVERT, payload, self.args.path_hash_size)
        await self.send_packet(pkt)
        log.debug("Advert sent")

    async def handle_packet(self, pkt: Packet) -> None:
        if pkt.payload_type == PAYLOAD_TYPE_ANON_REQ:
            await self.handle_anon_req(pkt)
        elif pkt.payload_type in (PAYLOAD_TYPE_TXT_MSG, PAYLOAD_TYPE_REQ, PAYLOAD_TYPE_PATH):
            await self.handle_peer_packet(pkt)
        elif pkt.payload_type == PAYLOAD_TYPE_ACK and len(pkt.payload) >= 4:
            await self.handle_ack(pkt.payload[:4])

    async def handle_anon_req(self, pkt: Packet) -> None:
        if len(pkt.payload) < 1 + PUB_KEY_SIZE + CIPHER_MAC_SIZE:
            return
        if pkt.payload[0:1] != hash_prefix(self.pub):
            return
        sender_pub = pkt.payload[1:33]
        secret = self.shared_secret(sender_pub)
        data = mac_then_decrypt(secret, pkt.payload[33:])
        if data is None or len(data) < 8:
            return
        sender_ts = struct.unpack_from("<I", data, 0)[0]
        sync_since = struct.unpack_from("<I", data, 4)[0]
        password = trunc_c_string(data[8:]).decode("utf-8", errors="replace")
        if password == self.args.admin_password:
            permissions = PERM_ACL_ADMIN
        elif password == self.args.password:
            permissions = PERM_ACL_READ_WRITE
        elif self.args.allow_read_only:
            permissions = PERM_ACL_GUEST
        else:
            log.info("Login rejected from %s: bad password", sender_pub.hex()[:12])
            return

        client = self.clients.get(sender_pub)
        if client and sender_ts <= client.last_timestamp:
            return
        client = Client(sender_pub, secret, permissions, sender_ts, sync_since)
        if pkt.is_flood:
            client.out_path_len = OUT_PATH_UNKNOWN
        self.clients[sender_pub] = client
        log.info("Login ok from %s perm=0x%02x sync_since=%d", sender_pub.hex()[:12], permissions, sync_since)

        now = now_unique(self.last_unique)
        reply = (
            struct.pack("<I", now)
            + bytes([RESP_SERVER_LOGIN_OK, 0, 1 if permissions == PERM_ACL_ADMIN else 0, permissions])
            + os.urandom(4)
            + bytes([FIRMWARE_VER_LEVEL])
        )
        if pkt.is_flood:
            response = self.create_path_return(sender_pub, secret, pkt.path_len, pkt.path, PAYLOAD_TYPE_RESPONSE, reply)
            await self.send_flood_reply(pkt, response)
        else:
            response = self.create_datagram(PAYLOAD_TYPE_RESPONSE, sender_pub, secret, reply)
            await self.send_to_client(client, response)

    async def handle_peer_packet(self, pkt: Packet) -> None:
        if len(pkt.payload) < 2 + CIPHER_MAC_SIZE:
            return
        if pkt.payload[0:1] != hash_prefix(self.pub):
            return
        src_hash = pkt.payload[1:2]
        for client in list(self.clients.values()):
            if hash_prefix(client.pub) != src_hash:
                continue
            data = mac_then_decrypt(client.secret, pkt.payload[2:])
            if data is None:
                continue
            client.last_activity = time.time()
            if pkt.payload_type == PAYLOAD_TYPE_TXT_MSG:
                await self.handle_text(pkt, client, data)
            elif pkt.payload_type == PAYLOAD_TYPE_REQ:
                await self.handle_request(pkt, client, data)
            elif pkt.payload_type == PAYLOAD_TYPE_PATH:
                await self.handle_path(client, data)
            return

    async def handle_text(self, pkt: Packet, client: Client, data: bytes) -> None:
        if len(data) <= 5:
            return
        sender_ts = struct.unpack_from("<I", data, 0)[0]
        flags = data[4] >> 2
        if sender_ts < client.last_timestamp:
            return
        is_retry = sender_ts == client.last_timestamp
        client.last_timestamp = sender_ts
        if flags == TXT_TYPE_PLAIN:
            text = trunc_c_string(data[5:]).decode("utf-8", errors="replace").strip()
            ack_hash = hashlib.sha256(data[:5 + len(text.encode("utf-8"))] + client.pub).digest()[:4]
            if client.permissions != PERM_ACL_GUEST and text and not is_retry:
                post = Post(client.pub, now_unique(self.last_unique), text[: self.args.max_text_len])
                self.posts.append(post)
                self.posts = self.posts[-self.args.max_posts:]
                self.save_state()
                log.info("Post from %s: %s", client.pub.hex()[:12], post.text)
            await self.send_ack(client, ack_hash, pkt)
        elif flags == TXT_TYPE_CLI_DATA and client.permissions == PERM_ACL_ADMIN:
            cmd = trunc_c_string(data[5:]).decode("utf-8", errors="replace").strip()
            reply = self.handle_cli(cmd)
            if reply:
                body = struct.pack("<I", now_unique(self.last_unique)) + bytes([TXT_TYPE_CLI_DATA << 2]) + reply.encode("utf-8")
                payload = self.create_datagram(PAYLOAD_TYPE_TXT_MSG, client.pub, client.secret, body)
                await self.send_to_client(client, payload, fallback_request=pkt)

    async def handle_request(self, pkt: Packet, client: Client, data: bytes) -> None:
        if len(data) < 5:
            return
        sender_ts = struct.unpack_from("<I", data, 0)[0]
        if sender_ts < client.last_timestamp:
            return
        client.last_timestamp = sender_ts
        req_type = data[4]
        if req_type == REQ_TYPE_KEEP_ALIVE:
            if len(data) >= 9:
                force_since = struct.unpack_from("<I", data, 5)[0]
                if force_since:
                    client.sync_since = force_since
            client.pending_ack = b""
            ack_hash = hashlib.sha256(data[:9].ljust(9, b"\x00") + client.pub).digest()[:4]
            ack_payload = ack_hash + bytes([self.unsynced_count(client)])
            await self.send_to_client(client, Packet((PAYLOAD_TYPE_ACK << 2) | ROUTE_TYPE_DIRECT, 0, b"", ack_payload), fallback_request=pkt)
        elif req_type == REQ_TYPE_GET_STATUS:
            reply = struct.pack("<I", sender_ts) + b"Python room server"
            payload = self.create_datagram(PAYLOAD_TYPE_RESPONSE, client.pub, client.secret, reply)
            await self.send_to_client(client, payload, fallback_request=pkt)

    async def handle_path(self, client: Client, data: bytes) -> None:
        if not data:
            return
        path_len = data[0]
        path_hash_size = (path_len >> 6) + 1
        path_bytes = (path_len & 63) * path_hash_size
        if len(data) < 1 + path_bytes:
            return
        client.out_path_len = path_len
        client.out_path = data[1:1 + path_bytes]
        log.info("Path to %s learned: len=0x%02x", client.pub.hex()[:12], path_len)
        extra = data[1 + path_bytes:]
        if len(extra) >= 5 and extra[0] == PAYLOAD_TYPE_ACK:
            await self.handle_ack(extra[1:5])

    async def handle_ack(self, ack: bytes) -> None:
        for client in self.clients.values():
            if client.pending_ack == ack:
                client.pending_ack = b""
                client.push_failures = 0
                client.sync_since = client.pending_ack_post_ts
                log.debug("Push ACK from %s", client.pub.hex()[:12])
                return

    def create_datagram(self, payload_type: int, dest_pub: bytes, secret: bytes, data: bytes) -> Packet:
        payload = hash_prefix(dest_pub) + hash_prefix(self.pub) + encrypt_then_mac(secret, data)
        return Packet(payload_type << 2, 0, b"", payload)

    def create_path_return(self, dest_pub: bytes, secret: bytes, path_len: int, path: bytes, extra_type: int, extra: bytes) -> Packet:
        path_bytes = (path_len & 63) * ((path_len >> 6) + 1)
        body = bytes([path_len]) + path[:path_bytes] + bytes([extra_type]) + extra
        payload = hash_prefix(dest_pub) + hash_prefix(self.pub) + encrypt_then_mac(secret, body)
        return Packet(PAYLOAD_TYPE_PATH << 2, 0, b"", payload)

    async def send_flood_reply(self, request: Packet, reply: Packet) -> None:
        path_hash_size = request.path_hash_size if request.path_hash_size in (1, 2, 3) else self.args.path_hash_size
        pkt = self.flood_packet(reply.payload_type, reply.payload, path_hash_size)
        await self.send_packet(pkt)

    async def send_to_client(self, client: Client, pkt: Packet, fallback_request: Packet | None = None) -> None:
        if client.out_path_len != OUT_PATH_UNKNOWN:
            direct = self.direct_packet(pkt.payload_type, pkt.payload, client.out_path_len, client.out_path)
            await self.send_packet(direct)
        elif fallback_request is not None:
            await self.send_flood_reply(fallback_request, pkt)
        else:
            flood = self.flood_packet(pkt.payload_type, pkt.payload, self.args.path_hash_size)
            await self.send_packet(flood)

    async def send_ack(self, client: Client, ack_hash: bytes, request: Packet) -> None:
        pkt = Packet((PAYLOAD_TYPE_ACK << 2), 0, b"", ack_hash)
        await self.send_to_client(client, pkt, fallback_request=request)

    async def push_post(self, client: Client, post: Post) -> None:
        attempt = random.randint(0, 3)
        body = (
            struct.pack("<I", post.timestamp)
            + bytes([(TXT_TYPE_SIGNED_PLAIN << 2) | attempt])
            + post.author[:4]
            + post.text.encode("utf-8")[: self.args.max_text_len]
        )
        client.pending_ack = hashlib.sha256(body + client.pub).digest()[:4]
        client.pending_ack_post_ts = post.timestamp
        client.ack_deadline = time.time() + PUSH_ACK_TIMEOUT_SECS
        payload = self.create_datagram(PAYLOAD_TYPE_TXT_MSG, client.pub, client.secret, body)
        await self.send_to_client(client, payload)
        log.debug("Pushed post %d to %s", post.timestamp, client.pub.hex()[:12])

    def unsynced_count(self, client: Client) -> int:
        count = 0
        for post in self.posts:
            if post.timestamp > client.sync_since and post.author != client.pub:
                count += 1
        return min(255, count)

    def handle_cli(self, cmd: str) -> str:
        if cmd == "status":
            return f"clients={len(self.clients)} posts={len(self.posts)} room={self.args.name}"
        if cmd == "id":
            return self.pub.hex().upper()
        return "unsupported"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MeshCoreNG Python room server over TCP bridge")
    parser.add_argument("--server", default="127.0.0.1", help="TCP bridge server host")
    parser.add_argument("--port", type=int, default=4200, help="TCP bridge server port")
    parser.add_argument("--name", default="Python Room", help="room name advertised to clients")
    parser.add_argument("--password", default="password", help="room write password")
    parser.add_argument("--admin-password", default="password", help="admin password")
    parser.add_argument("--allow-read-only", action="store_true", help="allow blank/bad-password read-only logins")
    parser.add_argument("--scope", default="", help="optional public region/scope name for transport-flood packets")
    parser.add_argument("--state", default="python_room_server_state.json", help="state file for identity and posts")
    parser.add_argument("--advert-interval", type=int, default=180, help="advert interval in seconds")
    parser.add_argument("--path-hash-size", type=int, choices=(1, 2, 3), default=1, help="flood path hash size")
    parser.add_argument("--max-posts", type=int, default=32, help="number of posts retained")
    parser.add_argument("--max-text-len", type=int, default=151, help="maximum post text bytes")
    parser.add_argument("--reconnect-delay", type=int, default=5, help="reconnect delay in seconds")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    server = PythonRoomServer(args)
    server.save_state()
    asyncio.run(server.connect_loop())


if __name__ == "__main__":
    main()
