# Setting up the WiFi TCP bridge

This guide is for a repeater flashed with the `_bridge_tcp` firmware. The bridge provides optional controlled backhaul between selected MeshCore RF deployments through a TCP server.

MeshCoreNG remains RF-first. Use the bridge for scoped deployments such as isolated RF islands, remote RF gateways, temporary backhaul, testing, research, or private infrastructure. Do not use it as a worldwide flooding backbone or unrestricted packet replication system.

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

To require a bridge password from TCP clients:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --password bridgeSecret
```

The server also starts a small status page by default:

```text
http://localhost:8080/
```

Open that page from the server machine, or replace `localhost` with the server's IP address from another machine on the same network. It shows each connected bridge node by node name, firmware version, remote address, how long it has been connected, idle time, heartbeat age, and packet counters.

The status page keeps a 24-hour in-memory traffic window for each known bridge node. It shows `RX 24h` and `TX 24h` per node, and disconnected nodes stay visible as `offline` while they still have packet history inside that 24-hour window. These counters reset when the Python bridge server process restarts.

The `Duty this hour` tile shows how much of the node's allowed hourly RF transmit duty-cycle budget has been used. `0%` means no RF TX budget has been used in the current accounting window. `100%` means the full configured hourly duty-cycle budget has been used. For example, with `set dutycycle 10`, the hourly RF TX budget is 10% of one hour, or 360 seconds. In that case `50%` means 180 seconds of RF TX have been used, and `100%` means 360 seconds have been used. Older bridge firmware that does not send RF duty telemetry will show the tile as unavailable until the repeater is updated.

Remote management is on a separate page:

```text
http://localhost:8080/manage
```

Select a node, enter that node's own MeshCore admin password, and send a normal CLI command such as `get bridge.status`. Repeaters with different admin passwords can be managed from the same page because the password is entered per command and checked by the selected repeater.

To add a separate password on the HTTP page itself, start the server with:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --admin-password webAdminSecret
```

This protects access to the remote management page. It does not replace the per-node admin password.

For monitoring during testing, start it with status and heartbeat timeouts:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --status-interval 10 --client-timeout 90 --log-packets
```

TCP bridge firmware sends a heartbeat to the server every 30 seconds. The server uses normal packets and heartbeats to update the client's `idle` timer. If a node loses power and no heartbeat arrives before `--client-timeout`, the server disconnects that stale node.

For local testing, use this machine's LAN IP address as `bridge.server`. For a controlled remote deployment, use the server's reachable IP address or domain name.

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
set bridge.password bridgeSecret
```

Replace `192.168.1.123` with the IP address or hostname of your TCP bridge server.
Skip `set bridge.password` if the server was started without `--password`.

For a remote server:

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
get bridge.password
get bridge.enabled
```

Expected bridge type:

```text
> tcp
```

`get wifi.password` and `get bridge.password` do not show the real password. They return `***`.

## 6. Link selected repeaters

Flash the intended bridge repeater at each location with `_bridge_tcp` firmware and configure those repeaters to use the same TCP server and port:

```text
set bridge.server myserver.example.com
set bridge.port 4200
set bridge.password bridgeSecret
set bridge.enabled on
```

Selected bridge traffic from one RF deployment is sent over TCP to the server and made available to the other intended bridge repeaters. Keep bridge groups scoped, preserve RF locality, and avoid unnecessary rebroadcast into RF networks.

Best practices:

- Bridge only required channels, topics, or traffic sources.
- Use regional segmentation for larger deployments.
- Use private bridge servers or private bridge groups when possible.
- Avoid full-network flooding across bridge links.
- Monitor duplicate counters, airtime, and congestion after enabling the bridge.

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
- The server is reachable from the same WiFi network or controlled remote network.
- A firewall allows TCP port `4200`.

### Server still shows a node after power is removed

Use the heartbeat-aware timeout:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --status-interval 10 --client-timeout 90
```

The status line shows `idle`, `hb_age`, and `hb`. If `idle` grows beyond `--client-timeout`, the server disconnects the stale TCP session.

The HTTP status page is enabled on port `8080` by default. Change it with:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --status-port 8081
```

Or disable it with:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --status-port 0
```

For single-node-per-IP LAN testing you can also use:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --replace-same-ip
```

Do not use `--replace-same-ip` when multiple bridge nodes may connect from the same public IP or NAT.

### The TCP bridge is not encrypted

The current TCP bridge does not use TLS. Use it on a trusted network or restrict access to the server with firewall rules.
