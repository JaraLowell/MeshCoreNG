#!/usr/bin/env python3
"""
MeshCore USB Bridge Client

Connects a repeater running RS232 bridge firmware to the central TCP bridge
server over the internet. The repeater plugs into the PC or Raspberry Pi
via USB; this script relays packets between the serial port and the server.

Because RS232Bridge and TCPBridge use identical packet framing, this script
simply forwards complete frames in both directions without parsing them.

Frame format (same as RS232Bridge and TCPBridge):
    [2 bytes] Magic header 0xC03E
    [2 bytes] Payload length (big-endian)
    [n bytes] Mesh packet payload
    [2 bytes] Fletcher-16 checksum over payload

Architecture:
    [LoRa mesh]  <->  [Repeater + RS232Bridge]  <-USB->  [this script]  <-TCP->  [tcp_bridge_server.py]

Requirements:
    pip install pyserial

Usage:
    python3 usb_bridge_client.py --serial /dev/ttyUSB0 --baud 115200 \\
                                  --server mijnserver.example.com --port 4200

    Windows example:
    python3 usb_bridge_client.py --serial COM3 --server 192.168.1.10 --port 4200

Repeater setup (flash _bridge_rs232 firmware, then via CLI):
    set bridge.enabled on

"""

import argparse
import logging
import socket
import struct
import threading
import time

import serial

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("usb_bridge")

BRIDGE_MAGIC = 0xC03E
MAGIC_HIGH = (BRIDGE_MAGIC >> 8) & 0xFF
MAGIC_LOW = BRIDGE_MAGIC & 0xFF
MAX_PAYLOAD = 256       # MAX_TRANS_UNIT + 1
FRAME_OVERHEAD = 6      # magic(2) + length(2) + checksum(2)
MAX_FRAME = MAX_PAYLOAD + FRAME_OVERHEAD
RECONNECT_DELAY = 5     # seconds between TCP reconnect attempts


def read_frame_from_serial(ser: serial.Serial) -> bytes | None:
    """
    Read one complete RS232Bridge frame from the serial port.
    Returns the raw frame bytes (magic + length + payload + checksum),
    or None on error.
    """
    # Scan for magic header
    buf = bytearray()
    while True:
        b = ser.read(1)
        if not b:
            return None
        buf.append(b[0])
        if len(buf) >= 2:
            if buf[-2] == MAGIC_HIGH and buf[-1] == MAGIC_LOW:
                break
            buf = bytearray([buf[-1]])

    magic_bytes = bytes(buf[-2:])

    # Read 2-byte length
    raw_len = ser.read(2)
    if len(raw_len) < 2:
        return None
    length = struct.unpack(">H", raw_len)[0]

    if length == 0 or length > MAX_PAYLOAD:
        log.warning("Serial RX: invalid frame length %d, discarding", length)
        return None

    # Read payload + checksum
    rest = ser.read(length + 2)
    if len(rest) < length + 2:
        return None

    return magic_bytes + raw_len + rest


def read_frame_from_tcp(sock: socket.socket) -> bytes | None:
    """
    Read one complete bridge frame from the TCP socket.
    Returns the raw frame bytes, or None on connection loss.
    """
    def recv_exactly(n: int) -> bytes | None:
        data = b""
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    # Scan for magic header
    prev = b""
    while True:
        b = sock.recv(1)
        if not b:
            return None
        candidate = prev + b
        if len(candidate) >= 2 and candidate[-2] == MAGIC_HIGH and candidate[-1] == MAGIC_LOW:
            magic_bytes = candidate[-2:]
            break
        prev = b

    raw_len = recv_exactly(2)
    if raw_len is None:
        return None
    length = struct.unpack(">H", raw_len)[0]

    if length == 0 or length > MAX_PAYLOAD:
        log.warning("TCP RX: invalid frame length %d, discarding", length)
        return None

    rest = recv_exactly(length + 2)
    if rest is None:
        return None

    return magic_bytes + raw_len + rest


def serial_to_tcp(ser: serial.Serial, get_sock, stop: threading.Event):
    """Thread: read frames from serial, write to TCP socket."""
    while not stop.is_set():
        try:
            frame = read_frame_from_serial(ser)
            if frame is None:
                continue
            sock = get_sock()
            if sock is None:
                log.debug("Serial->TCP: no TCP connection, dropping frame")
                continue
            sock.sendall(frame)
            log.debug("Serial->TCP: forwarded %d bytes", len(frame))
        except serial.SerialException as e:
            log.error("Serial read error: %s", e)
            stop.set()
        except OSError:
            pass  # TCP send failed, reconnect loop will handle it


def tcp_to_serial(ser: serial.Serial, get_sock, stop: threading.Event):
    """Thread: read frames from TCP socket, write to serial port."""
    while not stop.is_set():
        sock = get_sock()
        if sock is None:
            time.sleep(0.5)
            continue
        try:
            frame = read_frame_from_tcp(sock)
            if frame is None:
                log.info("TCP connection lost")
                continue
            ser.write(frame)
            log.debug("TCP->Serial: forwarded %d bytes", len(frame))
        except OSError:
            time.sleep(0.2)


def run(serial_port: str, baud: int, server: str, tcp_port: int):
    log.info("Opening serial port %s at %d baud", serial_port, baud)
    try:
        ser = serial.Serial(serial_port, baud, timeout=1)
    except serial.SerialException as e:
        log.error("Cannot open serial port: %s", e)
        return

    current_sock: socket.socket | None = None
    sock_lock = threading.Lock()
    stop = threading.Event()

    def get_sock():
        with sock_lock:
            return current_sock

    def set_sock(s):
        nonlocal current_sock
        with sock_lock:
            current_sock = s

    # Start relay threads
    t1 = threading.Thread(target=serial_to_tcp, args=(ser, get_sock, stop), daemon=True)
    t2 = threading.Thread(target=tcp_to_serial, args=(ser, get_sock, stop), daemon=True)
    t1.start()
    t2.start()

    log.info("Relay threads started. Connecting to %s:%d ...", server, tcp_port)

    # Main loop: maintain TCP connection
    while not stop.is_set():
        try:
            sock = socket.create_connection((server, tcp_port), timeout=10)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            set_sock(sock)
            log.info("Connected to TCP server %s:%d", server, tcp_port)

            # Wait until connection drops
            while not stop.is_set():
                try:
                    sock.settimeout(2)
                    data = sock.recv(1, socket.MSG_PEEK)
                    if not data:
                        break
                except socket.timeout:
                    pass  # Still alive
                except OSError:
                    break

        except OSError as e:
            log.warning("TCP connect failed: %s — retrying in %ds", e, RECONNECT_DELAY)
        finally:
            set_sock(None)
            try:
                sock.close()
            except Exception:
                pass

        if not stop.is_set():
            log.info("Reconnecting in %d seconds...", RECONNECT_DELAY)
            time.sleep(RECONNECT_DELAY)

    ser.close()
    log.info("Stopped")


def main():
    parser = argparse.ArgumentParser(
        description="MeshCore USB bridge client — relay RS232Bridge packets to TCP server"
    )
    parser.add_argument(
        "--serial", required=True,
        help="Serial port (e.g. /dev/ttyUSB0, /dev/ttyACM0, COM3)"
    )
    parser.add_argument(
        "--baud", type=int, default=115200,
        help="Baud rate (default: 115200, must match bridge.baud on repeater)"
    )
    parser.add_argument(
        "--server", required=True,
        help="TCP bridge server hostname or IP address"
    )
    parser.add_argument(
        "--port", type=int, default=4200,
        help="TCP bridge server port (default: 4200)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        run(args.serial, args.baud, args.server, args.port)
    except KeyboardInterrupt:
        log.info("Stopped by user")


if __name__ == "__main__":
    main()
