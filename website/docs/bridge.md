# Internet bridge

## What it does

Two LoRa networks that cannot hear each other can exchange messages over the internet. Repeaters on both sides connect to a shared TCP server. Packets received via LoRa are forwarded to all remote repeaters; packets from remote repeaters are injected back into the local LoRa mesh.

Users and apps do not notice the bridge. They use LoRa as normal.

```
[LoRa mesh A]  ←→  [Repeater A]  ←→  internet  ←→  [Repeater B]  ←→  [LoRa mesh B]
```

## Path 1: ESP32 repeater with WiFi

Flash a `_bridge_tcp` firmware variant on an ESP32 repeater that has WiFi, then configure it:

```
set wifi.ssid     YourWiFi
set wifi.password secret123
set bridge.server yourserver.example.com
set bridge.port   4200
set bridge.enabled on
```

Check the bridge type:

```
get bridge.type
```

## Path 2: Repeater via USB

Boards without WiFi — nRF52 (RAK4631), RP2040, STM32, or ESP32 boards without WiFi access — can also participate via USB.

Flash the `_bridge_rs232` firmware variant and enable the bridge:

```
set bridge.enabled on
```

Then run the relay script on a connected PC or Raspberry Pi:

```bash
pip install pyserial
python3 tools/usb_bridge_client.py --serial /dev/ttyUSB0 --baud 115200 \
                                    --server yourserver.example.com --port 4200
```

On Windows use `--serial COM3`.

## Running the server

Start the TCP bridge server on any internet-connected machine with Python 3.7+:

```bash
python3 tools/tcp_bridge_server.py --port 4200
```

No external dependencies. WiFi repeaters and USB repeaters can connect to the same server simultaneously.

## Security note

The current TCP bridge does not encrypt traffic. Run the server on a trusted network or VPS with firewall rules limiting access. TLS support is planned for a future release.
