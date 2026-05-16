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

connected_clients: set["BridgeClient"] = set()


def fletcher16(data: bytes) -> int:
    s1, s2 = 0, 0
    for b in data:
        s1 = (s1 + b) % 255
        s2 = (s2 + s1) % 255
    return (s1 << 8) | s2


class BridgeClient:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        addr = writer.get_extra_info("peername")
        self.addr = f"{addr[0]}:{addr[1]}" if addr else "unknown"
        self.packets_rx = 0
        self.packets_tx = 0
        self._connect_time = time.time()

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
            "Disconnected %s (%s) — rx=%d tx=%d uptime=%ds",
            client.addr, reason, client.packets_rx, client.packets_tx, uptime,
        )


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    client = BridgeClient(reader, writer)
    connected_clients.add(client)
    log.info("Connected %s (total=%d)", client.addr, len(connected_clients))

    try:
        while True:
            payload = await client.read_packet()
            if payload is None:
                continue
            client.packets_rx += 1
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

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MeshCore TCP bridge server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=4200, help="TCP port (default: 4200)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        log.info("Server stopped")
