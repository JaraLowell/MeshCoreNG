#!/usr/bin/env python3
"""Smoke tests for TCP bridge server dedupe, loopguard, groups, and budgets."""

import asyncio
import hmac
import time

import tcp_bridge_server as server


class DummyWriter:
    def __init__(self, name: str):
        self.name = name
        self.sent: list[bytes] = []

    def get_extra_info(self, key: str):
        return (self.name, 1) if key == "peername" else None

    def is_closing(self) -> bool:
        return False

    def write(self, data: bytes) -> None:
        self.sent.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None


def make_client(name: str) -> server.BridgeClient:
    client = server.BridgeClient(None, DummyWriter(name))
    client.node_name = name
    client.start_writer()
    return client


async def settle() -> None:
    await asyncio.sleep(0.05)


async def with_clients(*clients):
    old_clients = server.connected_clients
    old_cache = server.packet_fingerprint_cache
    server.connected_clients = set(clients)
    server.packet_fingerprint_cache = server.OrderedDict()
    try:
        yield
    finally:
        for client in clients:
            client.close()
        server.connected_clients = old_clients
        server.packet_fingerprint_cache = old_cache


async def test_basic_dedupe() -> None:
    a, b, c = make_client("A"), make_client("B"), make_client("C")
    async for _ in with_clients(a, b, c):
        payload = b"mesh-one"
        await server.broadcast(payload, sender=a)
        await settle()
        assert len(a.writer.sent) == 0
        assert len(b.writer.sent) == 1
        assert len(c.writer.sent) == 1

        await server.broadcast(payload, sender=b)
        await settle()
        assert len(a.writer.sent) == 0
        assert len(c.writer.sent) == 1
        assert a.skip_reasons.get("skipped_dup_seen_by_target", 0) == 1
        assert c.skip_reasons.get("skipped_dup_seen_by_target", 0) == 1


async def test_ttl_allows_resend() -> None:
    old_ttl = server.BRIDGE_DEDUPE_TTL_SECS
    server.BRIDGE_DEDUPE_TTL_SECS = 1
    a, b = make_client("A"), make_client("B")
    async for _ in with_clients(a, b):
        payload = b"mesh-two"
        await server.broadcast(payload, sender=a)
        await settle()
        assert len(b.writer.sent) == 1
        await asyncio.sleep(1.1)
        await server.broadcast(payload, sender=a)
        await settle()
        assert len(b.writer.sent) == 2
    server.BRIDGE_DEDUPE_TTL_SECS = old_ttl


async def test_group_mismatch() -> None:
    old_require = server.BRIDGE_REQUIRE_GROUP_MATCH
    server.BRIDGE_REQUIRE_GROUP_MATCH = True
    a, b = make_client("A"), make_client("B")
    a.bridge_group = "alpha"
    b.bridge_group = "beta"
    async for _ in with_clients(a, b):
        await server.broadcast(b"mesh-three", sender=a)
        await settle()
        assert len(b.writer.sent) == 0
        assert b.skip_reasons.get("skipped_group_mismatch", 0) == 1
    server.BRIDGE_REQUIRE_GROUP_MATCH = old_require


async def test_quarantine() -> None:
    a, b = make_client("A"), make_client("B")
    async for _ in with_clients(a, b):
        b.quarantined_until = time.time() + 60
        await server.broadcast(b"mesh-four", sender=a)
        await settle()
        assert len(b.writer.sent) == 0
        assert b.skip_reasons.get("skipped_quarantine", 0) == 1

        b.quarantined_until = time.time() - 1
        assert not b.quarantine_active()
        assert b.skip_reasons.get("bridge_quarantine_end", 0) == 1


async def test_rf_budget_drop() -> None:
    old_enabled = server.BRIDGE_RF_INJECT_ENABLED
    old_max = server.BRIDGE_RF_INJECT_MAX_PER_MIN
    server.BRIDGE_RF_INJECT_ENABLED = True
    server.BRIDGE_RF_INJECT_MAX_PER_MIN = 1
    a, b = make_client("A"), make_client("B")
    async for _ in with_clients(a, b):
        await server.broadcast(b"mesh-five-a", sender=a)
        await settle()
        await server.broadcast(b"mesh-five-b", sender=a)
        await settle()
        assert len(b.writer.sent) == 1
        assert b.skip_reasons.get("skipped_rf_budget", 0) == 1
    server.BRIDGE_RF_INJECT_ENABLED = old_enabled
    server.BRIDGE_RF_INJECT_MAX_PER_MIN = old_max


async def test_caps_v2_group_budget() -> None:
    group = b"GWNL"
    payload = (
        b"MCNG"
        + bytes([server.CONTROL_TYPE_CAPS, 2, 0x07, 2, len(group)])
        + group
        + bytes([1])
        + (120).to_bytes(2, "big")
        + (360000).to_bytes(4, "big")
        + (7500).to_bytes(2, "big")
    )
    caps = server.parse_caps(payload)
    assert caps is not None
    assert caps["bridge_v2"] is True
    assert caps["bridge_proto_ver"] == 2
    assert caps["group"] == "GWNL"
    assert caps["rf_inject_budget_enabled"] is True
    assert caps["rf_inject_max_per_min"] == 120
    assert caps["rf_inject_max_airtime_ms_per_hour"] == 360000
    assert caps["rf_inject_block_duty_above_pct"] == 75.0


async def test_status_hides_unnamed_offline_placeholders() -> None:
    old_clients = server.connected_clients
    old_stats = server.node_traffic_stats
    now = time.time()
    server.connected_clients = set()
    server.node_traffic_stats = {
        "host:placeholder": {
            "key": "host:placeholder",
            "rx_times": server.deque([now]),
            "tx_times": server.deque(),
            "packets_rx": 1,
            "packets_tx": 0,
            "heartbeats_rx": 0,
            "first_seen": now,
            "last_seen": now,
            "last_connected": now,
            "last_disconnect": now,
            "last_heartbeat": 0.0,
            "last_heartbeat_uptime_ms": 0,
            "rf_duty": {},
            "rf_tx_total_baseline_ms": None,
            "rf_tx_total_baseline_at": 0.0,
            "node_name": "",
            "node_id": "",
            "firmware_version": "",
            "supports_bridge_v2": False,
            "bridge_proto_ver": 1,
            "bridge_group": "default",
            "node_rf_inject_budget": {},
            "connected": False,
            "client_id": "",
            "addr": "",
        },
        "name:real": {
            **server.new_node_stats("name:real"),
            "node_name": "real",
            "last_seen": now,
        },
    }
    try:
        snapshot = server.status_snapshot()
        names = [client["display_name"] for client in snapshot["clients"]]
        assert "unnamed bridge node" not in names
        assert "real" in names
    finally:
        server.connected_clients = old_clients
        server.node_traffic_stats = old_stats


async def test_rf_duty_hour_counter_resets() -> None:
    old_stats = server.node_traffic_stats
    server.node_traffic_stats = {}
    client = make_client("Duty")
    heartbeat = {
        "uptime_ms": 1,
        "rf_duty": {
            "tx_used_ms": 1200,
            "tx_max_ms": 360000,
            "window_ms": 3600000,
            "duty_limit_pct": 10.0,
            "tx_used_pct": 0.33,
            "tx_total_ms": 100000,
        },
    }
    try:
        server.record_node_heartbeat(client, heartbeat, now=3610)
        rf = server.get_node_stats(client)["rf_duty"]
        assert rf["tx_used_ms"] == 1200
        assert rf["tx_hour_used_ms"] == 0

        heartbeat["rf_duty"]["tx_used_ms"] = 2400
        heartbeat["rf_duty"]["tx_total_ms"] = 105000
        server.record_node_heartbeat(client, heartbeat, now=3620)
        rf = server.get_node_stats(client)["rf_duty"]
        assert rf["tx_used_ms"] == 2400
        assert rf["tx_hour_used_ms"] == 5000

        heartbeat["rf_duty"]["tx_used_ms"] = 3000
        heartbeat["rf_duty"]["tx_total_ms"] = 110000
        server.record_node_heartbeat(client, heartbeat, now=7205)
        rf = server.get_node_stats(client)["rf_duty"]
        assert rf["tx_used_ms"] == 3000
        assert rf["tx_hour_used_ms"] == 0
        assert rf["tx_hour_resets_in_seconds"] == 3595
    finally:
        client.close()
        server.node_traffic_stats = old_stats


def encrypt_group_plain(secret: bytes, plain: bytes) -> bytes:
    assert server.Cipher is not None
    padded_len = ((len(plain) + server.CIPHER_BLOCK_SIZE - 1) // server.CIPHER_BLOCK_SIZE) * server.CIPHER_BLOCK_SIZE
    padded = plain + (b"\x00" * (padded_len - len(plain)))
    cipher = server.Cipher(server.algorithms.AES(secret[:16]), server.modes.ECB())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    mac = hmac.new(secret, encrypted, server.hashlib.sha256).digest()[:server.CIPHER_MAC_SIZE]
    return mac + encrypted


async def test_group_tracker_location_decode() -> None:
    if server.Cipher is None:
        return
    old_channels = server.public_channels
    server.public_channels = []
    server.load_public_channels("")
    try:
        tracker = (
            b"MCL1"
            + bytes([1, 0])
            + bytes.fromhex("01020304")
            + int(52123456).to_bytes(4, "big", signed=True)
            + int(5123456).to_bytes(4, "big", signed=True)
            + int(12).to_bytes(2, "big", signed=True)
            + int(345).to_bytes(2, "big")
            + int(9000).to_bytes(2, "big")
            + bytes([7])
            + int(4100).to_bytes(2, "big")
            + int(1780000000).to_bytes(4, "big")
            + bytes([4])
            + b"bike"
        )
        plain = (
            int(server.DATA_TYPE_MESHCORENG_TRACKER).to_bytes(2, "little")
            + bytes([len(tracker)])
            + tracker
        )
        encrypted = encrypt_group_plain(server.DEFAULT_TRACKER_CHANNEL_SECRET, plain)
        payload = bytes([(server.PAYLOAD_TYPE_GRP_DATA << server.PH_TYPE_SHIFT) | server.ROUTE_TYPE_FLOOD])
        payload += bytes([0])
        payload += server.channel_hash(server.DEFAULT_TRACKER_CHANNEL_SECRET)
        payload += encrypted

        report = server.parse_mesh_location_payload(payload)
        assert report is not None
        assert report["node_id"] == "01020304"
        assert report["lat"] == 52.123456
        assert report["lon"] == 5.123456
        assert report["altitude_m"] == 12
        assert report["speed_cms"] == 345
        assert report["heading_cdeg"] == 9000
        assert report["satellites"] == 7
        assert report["battery_mv"] == 4100
        assert report["name"] == "bike"
        assert report["payload_type"] == server.PAYLOAD_TYPE_GRP_DATA
    finally:
        server.public_channels = old_channels


async def main() -> None:
    await test_basic_dedupe()
    await test_ttl_allows_resend()
    await test_group_mismatch()
    await test_quarantine()
    await test_rf_budget_drop()
    await test_caps_v2_group_budget()
    await test_status_hides_unnamed_offline_placeholders()
    await test_rf_duty_hour_counter_resets()
    await test_group_tracker_location_decode()
    print("tcp bridge guard smoke tests passed")


if __name__ == "__main__":
    asyncio.run(main())
