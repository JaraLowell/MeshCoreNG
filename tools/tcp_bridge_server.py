#!/usr/bin/env python3
"""
MeshCore TCP Bridge Server

Forwards mesh packets between connected repeaters so geographically separated
LoRa networks can act as one mesh. Each packet received from one repeater is
broadcast to all other connected repeaters.

Usage:
    python3 tcp_bridge_server.py [--host 0.0.0.0] [--port 4200]

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
            "Disconnected %s (%s) — rx=%d tx=%d hb=%d uptime=%ds",
            client.addr, reason, client.packets_rx, client.packets_tx, client.heartbeats_rx, uptime,
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
                f"{client.addr} idle={int(now - client.last_seen)}s "
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


async def main(host: str, port: int):
    server = await asyncio.start_server(handle_client, host, port)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    log.info("MeshCore TCP bridge server listening on %s", addrs)
    log.info("Press Ctrl+C to stop")
    status = asyncio.create_task(status_task()) if STATUS_INTERVAL_SECS > 0 else None

    try:
        async with server:
            await server.serve_forever()
    finally:
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
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        log.info("Server stopped")
