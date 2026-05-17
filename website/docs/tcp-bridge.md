# Setting up the WiFi TCP bridge

This guide is for a repeater flashed with the `_bridge_tcp` firmware. The bridge links two or more LoRa networks through a central TCP server.

## What you need

- An ESP32 repeater with WiFi and `_bridge_tcp` firmware.
- The repeater USB port, for example `/dev/ttyACM0`.
- `meshcli` installed on your computer.
- A TCP bridge server reachable by the repeater.

## 1. Start the TCP bridge server

Start the server on a machine that the bridge repeaters can reach. This can be a VPS, Raspberry Pi, or local computer.

```bash
python3 tools/tcp_bridge_server.py --port 4200
```

For local testing, use this machine's LAN IP address as `bridge.server`. For internet use, use a public IP address or domain name.

## 2. Connect to the repeater

A TCP bridge build is a repeater, not a serial companion. Use `-r`:

```bash
meshcli -s /dev/ttyACM0 -r
```

If you see this error:

```text
No response from meshcore node, disconnecting
Are you sure your node is a serial companion ?
To connect to a repeater, use -r option.
```

then `-r` was missing. Start again with:

```bash
meshcli -s /dev/ttyACM0 -r
```

## 3. Configure WiFi and the TCP bridge

Run these commands through `meshcli`:

```text
set bridge.enabled off
set wifi.ssid MyWiFiName
set wifi.password MyWiFiPassword
set bridge.server 192.168.1.123
set bridge.port 4200
```

Replace `192.168.1.123` with the IP address or hostname of your TCP bridge server.

For a server on the internet:

```text
set bridge.server myserver.example.com
```

## 4. Reboot after WiFi changes

After `set wifi.ssid` and `set wifi.password`, reboot the repeater before the WiFi settings take effect.

```text
reboot
```

Then connect again:

```bash
meshcli -s /dev/ttyACM0 -r
```

Enable the bridge after reconnecting:

```text
set bridge.enabled on
```

## 5. Check the settings

```text
get bridge.type
get wifi.ssid
get bridge.server
get bridge.port
get bridge.enabled
```

Expected bridge type:

```text
> tcp
```

`get wifi.password` does not show the real password. It returns `***`.

## 6. Link multiple repeaters

Flash a repeater at each location with `_bridge_tcp` firmware and configure all of them to use the same TCP server and port:

```text
set bridge.server myserver.example.com
set bridge.port 4200
set bridge.enabled on
```

Packets received over LoRa by one repeater are sent over TCP to the server and injected back into the local LoRa network by the other repeater.

## Troubleshooting

### Permission denied on `/dev/ttyACM0`

Add your user to the `dialout` group:

```bash
sudo usermod -aG dialout $USER
```

Log out and back in afterwards.

### Wrong serial port

Check which port appears after plugging in the repeater:

```bash
ls /dev/ttyACM*
ls /dev/ttyUSB*
```

Then use the right port with `meshcli -s <port> -r`.

### Bridge does not come online

Check:

- If the CLI becomes slow or noisy while configuring, run `set bridge.enabled off`, reboot, then configure WiFi and server settings before enabling it again.
- The repeater was rebooted after setting WiFi.
- `get bridge.enabled` returns `on`.
- `get bridge.server` and `get bridge.port` are correct.
- The TCP bridge server is running.
- The server is reachable from the same WiFi network or over the internet.
- A firewall allows TCP port `4200`.

### The TCP bridge is not encrypted

The current TCP bridge does not use TLS. Use it on a trusted network or restrict access to the server with firewall rules.
